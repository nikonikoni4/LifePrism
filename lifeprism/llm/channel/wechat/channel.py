"""微信协议收发适配；会话和 Agent 业务由注入的入口处理。"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import httpx

from lifeprism.config.settings_manager import settings
from lifeprism.llm.bus import ChannelType, MessageQueue, OutboundMessage
from lifeprism.llm.channel.base import BaseChannel
from lifeprism.llm.channel.wechat.auth import WechatAuth
from lifeprism.llm.channel.wechat.client import WechatClient
from lifeprism.llm.channel.wechat.config import WechatConfig
from lifeprism.llm.channel.wechat.exceptions import (
    WechatAPIError,
    WechatMediaError,
    WechatMessageError,
)
from lifeprism.llm.channel.wechat.media import WechatMedia
from lifeprism.llm.channel.wechat.message import WechatMessage
from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore
from lifeprism.llm.conversation.types import ConversationInput, ConversationRoute
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class WechatChannel(BaseChannel):
    """只负责认证、协议转换、媒体、回复凭据和收发生命周期。

    on_message 由应用装配注入，提交统一输入后应及时返回。
    bus 参数仅保留构造兼容，不用于聊天或人工交互。
    """

    name = "wechat"

    def __init__(
        self,
        config: WechatConfig,
        bus: MessageQueue,
        *,
        on_message: Callable[[ConversationInput], Awaitable[object]] | None = None,
        allow_input: Callable[[ConversationRoute], bool] | None = None,
        on_start: Callable[[], Awaitable[None]] | None = None,
        on_stop: Callable[[], Awaitable[None]] | None = None,
        reply_store: WechatReplyStore | None = None,
    ):
        super().__init__(config, bus)
        self.config = config
        self.wechat_dir = settings.channel_path / "wechat"
        self.media_dir = self.wechat_dir / "media"
        self.state_file = self.wechat_dir / "account.json"
        self.client: WechatClient | None = None
        self.auth: WechatAuth | None = None
        self.media: WechatMedia | None = None
        self.reply_store = reply_store if reply_store is not None else WechatReplyStore()
        self.on_message = on_message
        self.allow_input = allow_input
        self.on_start = on_start
        self.on_stop = on_stop
        self._poll_task: asyncio.Task | None = None

    async def start(self) -> None:
        """完成认证和注入入口的启动后开始轮询；失败时释放连接。"""
        if self._running:
            return
        self.client = WechatClient(self.config.base_url)
        await self.client.__aenter__()
        prepared = False
        try:
            self.auth = WechatAuth(self.client, self.state_file)
            state = self.auth.load_state()
            self.reply_store.migrate_legacy(self.state_file)
            token = state.get("token", "")
            if not token:
                logger.info("微信未配置登录凭据，跳过启动")
                await self.client.__aexit__(None, None, None)
                self.client = None
                return
            if self.on_message is None:
                raise RuntimeError("微信渠道尚未注入输入接收入口")
            self.client.token = token
            self.media = WechatMedia(self.client, self.media_dir)
            if self.on_start is not None:
                prepared = True
                await self.on_start()
            self._running = True
            self._poll_task = asyncio.create_task(self._poll_loop(), name="wechat-poll")
        except BaseException:
            self._running = False
            try:
                if prepared and self.on_stop is not None:
                    await self.on_stop()
            finally:
                await self.client.__aexit__(None, None, None)
                self.client = None
            raise

    async def stop(self) -> None:
        """先停止输入，再等待注入任务收尾，最后关闭微信连接。"""
        self._running = False
        try:
            if self._poll_task is not None:
                self._poll_task.cancel()
                try:
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._poll_task
                finally:
                    self._poll_task = None
        finally:
            try:
                if self.on_stop is not None:
                    await self.on_stop()
            finally:
                if self.client is not None:
                    try:
                        await self.client.__aexit__(None, None, None)
                    finally:
                        self.client = None
        logger.info("微信渠道已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """使用当前回复凭据发送完整消息；未送达不能静默视为成功。"""
        if self.client is None or not self._running:
            raise WechatAPIError("微信客户端未初始化或未运行")
        user_id = (msg.extra or {}).get("wechat_user_id")
        if not user_id:
            raise WechatAPIError("无法发送微信消息：缺少目标用户 ID")
        content = msg.response.content if msg.response is not None else ""
        if not content:
            return
        token = self.reply_store.get_token(user_id)
        body = WechatMessage.build_text_message(user_id, content, token)
        try:
            await self.client.api_post("ilink/bot/sendmessage", body)
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as exc:
            raise WechatAPIError(f"发送微信消息失败: {exc}") from exc

    async def _poll_loop(self) -> None:
        """不断接收消息；入口不等待 Agent，单个坏输入不终止下一批轮询。"""
        cursor = ""
        while self._running:
            try:
                data = await self.client.api_post(
                    "ilink/bot/getupdates", {"get_updates_buf": cursor}
                )
                cursor = data.get("get_updates_buf", "")
                for msg in data.get("msgs", []):
                    try:
                        await self._handle_wechat_message(msg)
                    except Exception:
                        # 最外层入站任务边界：标记本条失败，不能让它终止整个接收器。
                        # CancelledError 属于 BaseException，仍交给生命周期关闭。
                        logger.exception("微信单条输入处理失败")
            except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError, WechatAPIError):
                logger.exception("微信轮询连接失败")
                await asyncio.sleep(5)
            except (KeyError, ValueError, TypeError):
                logger.exception("微信轮询数据无效")
                await asyncio.sleep(5)

    async def _handle_wechat_message(self, msg: dict[str, Any]) -> None:
        """转换协议输入、更新回复凭据和媒体，交给注入的业务入口。"""
        try:
            parsed = WechatMessage.parse_message(msg)
            user_id = parsed["from_user_id"]
            if not user_id:
                return
            route = ConversationRoute(channel=ChannelType.WECHAT, recipient_id=user_id)
            if self.allow_input is not None and not self.allow_input(route):
                return
            try:
                self.reply_store.remember(user_id, parsed["context_token"])
            except Exception:
                # 内存已保留最新凭据；存储失败不能让正在等待的用户答案丢失。
                logger.warning("微信回复凭据持久化失败", exc_info=True)
            media_paths = []
            for item in parsed["media"]:
                path = await self.media.download_media(item["info"], item["type"])
                if path:
                    media_paths.append(path)
            incoming = ConversationInput(
                route=route,
                content=parsed["content"],
                input_id=str(msg.get("message_id") or msg.get("client_id") or uuid4().hex),
                extra={"media": media_paths, "wechat_user_id": user_id},
            )
            if self.on_message is None:
                raise RuntimeError("微信渠道尚未注入输入接收入口")
            await self.on_message(incoming)
        except (KeyError, ValueError, TypeError) as exc:
            raise WechatMessageError(f"微信输入解析失败: {exc}") from exc
        except (httpx.HTTPStatusError, httpx.RequestError, WechatMediaError) as exc:
            raise WechatMessageError(f"微信媒体下载失败: {exc}") from exc
