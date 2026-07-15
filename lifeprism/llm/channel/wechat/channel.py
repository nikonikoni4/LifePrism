"""微信 Channel 主类模块
本文件源自 https://github.com/HKUDS/nanobot.git，经 AI 改写适配 lifeprism 项目。
"""

import asyncio
import contextlib
import json
from typing import Any

import httpx

from lifeprism.config.settings_manager import settings
from lifeprism.llm.agent.context import Context
from lifeprism.llm.bus import (
    ChannelType,
    InboundMessage,
    MessageQueue,
    MessageType,
    OutboundMessage,
)
from lifeprism.llm.channel.base import BaseChannel
from lifeprism.llm.channel.wechat.auth import WechatAuth
from lifeprism.llm.channel.wechat.client import WechatClient
from lifeprism.llm.channel.wechat.config import WechatConfig
from lifeprism.llm.channel.wechat.exceptions import WechatAPIError, WechatMessageError
from lifeprism.llm.channel.wechat.media import WechatMedia
from lifeprism.llm.providers import LLMResponse
from lifeprism.llm.utils.llm_call_logger import llm_call_logger
from lifeprism.utils.exceptions import LWBaseError
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)


class WechatChannel(BaseChannel):
    """微信 Channel

    提供微信平台的消息接入能力，包括认证、消息收发、媒体处理等功能。

    Attributes:
        name: Channel 名称标识
        config: 微信配置对象
        wechat_dir: 微信数据目录
        media_dir: 媒体文件存储目录
        state_file: 状态文件路径
        client: 微信 API 客户端
        auth: 认证模块
        media: 媒体处理模块
    """

    name = "wechat"

    def __init__(self, config: WechatConfig, bus: MessageQueue):
        """初始化微信 Channel

        Args:
            config: 微信配置对象
            bus: 消息总线队列
        """
        super().__init__(config, bus)
        self.config: WechatConfig = config

        # 路径设置
        self.wechat_dir = settings.channel_path / "wechat"
        self.media_dir = self.wechat_dir / "media"
        self.state_file = self.wechat_dir / "account.json"

        # 模块
        self.client: WechatClient | None = None
        self.auth: WechatAuth | None = None
        self.media: WechatMedia | None = None

        # 状态
        self._poll_task: asyncio.Task | None = None
        # 用户数据：{wechat_user_id: {"context_token": "xxx", "last_session_id": "xxx"}}
        self._user_data: dict[str, dict[str, str]] = {}

        # 数据库访问（wechat_account_state 表，替代 account.json 文件存储）
        # 参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
        from lifeprism.repository import lw_db_manager
        from lifeprism.repository.providers.wechat_account_state_provider import (
            WechatAccountStateProvider,
        )

        self._db_manager = lw_db_manager
        self._account_state_provider = WechatAccountStateProvider(db_manager=self._db_manager)
        # 使用公共方法 get_all_states()，不直接调用 _generic_query

    def _migrate_account_json_to_db(self) -> bool:
        """将 account.json 文件数据迁移到 wechat_account_state 数据库表

        迁移条件：account.json 存在且 DB 表中无任何记录时执行迁移。
        迁移完成后将 account.json 重命名为 account.json.bak（保留备份）。

        支持的文件格式：
        - 新格式：{"user_data": {user_id: {"context_token": "xxx", "last_session_id": "xxx"}}}
        - 旧格式：{"context_tokens": {user_id: "context_token_string"}}

        Returns:
            True 表示已执行迁移；False 表示跳过迁移（文件不存在或 DB 已有记录）

        参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
        """
        # 1. account.json 不存在 → 跳过
        if not self.state_file.exists():
            return False

        # 2. DB 已有记录 → 跳过（避免覆盖新数据）
        with self._db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM wechat_account_state")
            count = cursor.fetchone()[0]
        if count > 0:
            logger.info("DB 中已有 %s 条记录，跳过 account.json 迁移", count)
            return False

        # 3. 读取并解析 account.json
        try:
            file_state = json.loads(self.state_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.error("读取 account.json 失败: error=%s", e, exc_info=True)
            return False

        # 4. 提取用户数据（支持新旧格式）
        user_data = {}
        if "user_data" in file_state:
            # 新格式
            user_data = file_state.get("user_data", {})
        elif "context_tokens" in file_state:
            # 旧格式：context_tokens = {user_id: "context_token_string"}
            logger.info("检测到旧格式 context_tokens，迁移到新格式")
            old_context_tokens = file_state.get("context_tokens", {})
            for user_id, context_token in old_context_tokens.items():
                user_data[user_id] = {
                    "context_token": context_token,
                    # 旧数据没有 session_id
                    "last_session_id": None,
                }

        if not user_data:
            logger.info("account.json 中无用户数据，跳过迁移")
            # 即使无数据也重命名文件，避免反复尝试
            self._rename_account_json_to_bak()
            return True

        # 5. 迁移到 DB
        for wechat_user_id, data in user_data.items():
            context_token = data.get("context_token")
            last_session_id = data.get("last_session_id")
            self._account_state_provider.save_state(
                wechat_user_id=wechat_user_id,
                context_token=context_token,
                last_session_id=last_session_id,
            )
        logger.info("已迁移 %s 个用户的数据到 DB", len(user_data))

        # 6. 重命名 account.json 为 account.json.bak
        self._rename_account_json_to_bak()
        return True

    def _rename_account_json_to_bak(self) -> None:
        """将 account.json 重命名为 account.json.bak"""
        try:
            bak_file = self.state_file.with_suffix(".json.bak")
            self.state_file.rename(bak_file)
            logger.info("已将 account.json 重命名为 %s", bak_file.name)
        except OSError as e:
            logger.error("重命名 account.json 失败: error=%s", e, exc_info=True)

    def _save_user_data_to_db(self) -> None:
        """将 _user_data 中的所有用户数据保存到 DB

        使用 INSERT OR REPLACE 语义：已存在的记录会被覆盖。
        参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
        """
        if not self._user_data:
            return
        for wechat_user_id, data in self._user_data.items():
            context_token = data.get("context_token")
            last_session_id = data.get("last_session_id")
            self._account_state_provider.save_state(
                wechat_user_id=wechat_user_id,
                context_token=context_token,
                last_session_id=last_session_id,
            )
        logger.info("已保存 %s 个用户数据到 DB", len(self._user_data))

    def _load_user_data_from_db(self) -> None:
        """从 DB 加载所有用户数据到 _user_data

        参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
        """
        results = self._account_state_provider.get_all_states()
        self._user_data = {}
        for row in results:
            wechat_user_id = row["wechat_user_id"]
            self._user_data[wechat_user_id] = {
                "context_token": row.get("context_token"),
                "last_session_id": row.get("last_session_id"),
            }
        logger.info("从 DB 加载了 %s 个用户数据", len(self._user_data))

    async def start(self) -> None:
        """启动 channel

        初始化客户端、认证模块和媒体处理模块，完成登录后启动消息轮询。
        """
        if self._running:
            return

        self._running = True
        logger.info("启动微信 channel")

        # 初始化客户端
        self.client = WechatClient(self.config.base_url)
        await self.client.__aenter__()

        # 初始化认证
        self.auth = WechatAuth(self.client, self.state_file)

        # 加载状态（主要用于从 keyring 加载 token；
        # 若 account.json 仍存在，auth.load_state 会先把 token 迁移到 keyring）
        state = self.auth.load_state()
        token = state.get("token", "")

        # 迁移 account.json → DB（一次性迁移，参考 ADR 决策 4）
        # 此时 account.json 中的 token 已被 auth.load_state 迁移到 keyring，
        # 剩余的 user_data/context_tokens 迁移到 wechat_account_state 表
        self._migrate_account_json_to_db()

        # 从 DB 加载用户数据（替代原文件加载方式）
        self._load_user_data_from_db()

        logger.info("加载的 token: %s...", token[:20] if token else "None")
        logger.info("加载的用户数据: %s 个用户", len(self._user_data))

        if token:
            self.client.token = token
            logger.info("使用已保存的 token")
        else:
            # # QR 登录
            # success = await self.auth.qr_login()
            # if not success:
            #     logger.error("登录失败")
            #     self._running = False
            #     return
            # 不存在token放弃启动
            logger.info("微信 channel 不存在 token，放弃启动")
            self._running = False
            return
        # 测试 token 是否有效
        try:
            test_body = {"get_updates_buf": ""}
            test_data = await self.client.api_post("ilink/bot/getupdates", test_body)
            logger.info("Token 测试成功")
            logger.debug("返回数据: %s", test_data)
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
            logger.error("Token 测试失败: error=%s", e, exc_info=True)

        # 初始化媒体处理
        self.media = WechatMedia(self.client, self.media_dir)

        # 启动长轮询
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """停止 channel

        取消消息轮询任务并关闭客户端连接。
        """
        self._running = False

        # 保存最新的用户数据到 DB（兜底保障，替代原 account.json 文件存储）
        # 参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
        if self._user_data:
            try:
                self._save_user_data_to_db()
                logger.info("停止时保存用户数据到 DB: %s 个用户", len(self._user_data))
            except Exception as e:
                logger.error("停止时保存用户数据失败: error=%s", e, exc_info=True)

        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        if self.client:
            await self.client.__aexit__(None, None, None)
        logger.info("微信 channel 已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到微信平台

        Args:
            msg: 待发送的出站消息
        """
        if not self.client or not self._running:
            logger.warning("客户端未初始化或未运行")
            return

        # 从 extra 中获取目标用户ID
        wechat_user_id = msg.extra.get("wechat_user_id") if msg.extra else None
        if not wechat_user_id:
            logger.error("无法发送消息：未找到目标用户 ID")
            return

        # 从用户数据中获取 context_token
        user_data = self._user_data.get(wechat_user_id, {})
        context_token = user_data.get("context_token", "")

        # 提取内容
        content = ""
        if msg.response and hasattr(msg.response, "content"):
            content = msg.response.content

        if not content:
            logger.debug("消息内容为空，跳过发送")
            return

        # 构造并发送消息
        try:
            from lifeprism.llm.channel.wechat.message import WechatMessage

            message_body = WechatMessage.build_text_message(wechat_user_id, content, context_token)
            logger.info("开始发送消息到微信: content_len=%s", len(content))
            await self.client.api_post("ilink/bot/sendmessage", message_body)
            logger.info("发送消息到微信成功")
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
            logger.error("发送消息失败: 错误=%s", e, exc_info=True)
            raise WechatAPIError(f"发送消息失败: {e}") from e

    async def _poll_loop(self) -> None:
        """消息轮询循环

        持续轮询微信服务器获取新消息，处理接收到的消息并发送到消息总线。
        发生网络或 API 错误时会记录日志并等待 5 秒后重试，确保轮询持续运行。
        """
        logger.info("轮询循环已启动")
        get_updates_buf = ""
        poll_count = 0

        while self._running:
            try:
                poll_count += 1
                logger.debug(
                    "第 %s 次轮询, get_updates_buf=%s...", poll_count, get_updates_buf[:50]
                )
                body = {"get_updates_buf": get_updates_buf}
                data = await self.client.api_post("ilink/bot/getupdates", body)

                # 打印完整响应（使用 DEBUG 级别避免日志噪音）
                logger.debug("完整响应数据: %s", data)

                get_updates_buf = data.get("get_updates_buf", "")
                messages = data.get("msgs", [])

                logger.debug(
                    "轮询返回: get_updates_buf=%s..., 消息数=%s",
                    get_updates_buf[:50],
                    len(messages),
                )

                if messages:
                    logger.debug("*** 收到 %s 条消息 ***", len(messages))
                    for idx, msg in enumerate(messages):
                        logger.debug("消息 %s: %s", idx + 1, msg)
                        await self._handle_wechat_message(msg)

            except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
                logger.error("长轮询网络错误: error=%s", e, exc_info=True)
                await asyncio.sleep(5)
            except (KeyError, ValueError) as e:
                logger.error("长轮询数据解析错误: error=%s", e, exc_info=True)
                await asyncio.sleep(5)

    async def _handle_wechat_message(self, msg: dict[str, Any]) -> None:
        """处理微信消息

        解析微信消息，检查权限，下载媒体文件，构造 InboundMessage 并发送到消息总线。
        单个消息处理失败不会影响其他消息的处理。

        消息路由：仅在云端模式（agent_only）下，在解析消息之前先判断本地在线状态，
        本地在线时跳过云端处理，由本地负责回复，避免重复回复；本地离线时云端接管处理。
        本地模式（full）下 heartbeat_manager 从不被更新，直接处理所有消息。

        Args:
            msg: 原始微信消息字典
        """
        # 消息路由：仅在云端模式（agent_only）时检查心跳
        # 本地模式（full）下 heartbeat_manager 从不被更新，is_local_online() 永远返回 False，
        # 路由检查为死代码。此守卫确保只在云端执行路由判断，防止未来误更新 heartbeat_manager
        # 导致本地消息被错误跳过。
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        if settings.run_mode == "agent_only":
            # 云端模式：根据本地心跳状态决定是否跳过消息处理
            if heartbeat_manager.is_local_online():
                logger.info(
                    "本地在线，跳过云端处理: from_user=%s, message=%s",
                    msg.get("from_user_id"),
                    str(msg.get("content", ""))[:50],
                )
                return  # 本地会处理

            # 本地离线，云端接管处理
            logger.info(
                "本地离线，云端接管处理: from_user=%s, message=%s",
                msg.get("from_user_id"),
                str(msg.get("content", ""))[:50],
            )

        try:
            logger.info("开始处理微信消息")
            from lifeprism.llm.channel.wechat.message import WechatMessage

            parsed = WechatMessage.parse_message(msg)
            logger.debug(
                "解析后的消息: content_len=%s, media_count=%s",
                len(parsed["content"]),
                len(parsed["media"]),
            )

            wechat_user_id = parsed["from_user_id"]
            content = parsed["content"]
            context_token = parsed["context_token"]

            # 检查权限
            if not self.is_allowed(wechat_user_id):
                logger.warning("拒绝未授权用户")
                return

            logger.info("用户已授权")

            # 标记是否需要持久化
            need_save = False

            # 保存 context_token 到用户数据
            if context_token:
                if wechat_user_id not in self._user_data:
                    self._user_data[wechat_user_id] = {}
                self._user_data[wechat_user_id]["context_token"] = context_token
                logger.debug("context_token已更新")
                need_save = True

            # 下载媒体
            media_paths = []
            for media_item in parsed["media"]:
                media_type = media_item["type"]
                media_info = media_item["info"]
                path = await self.media.download_media(media_info, media_type)
                if path:
                    media_paths.append(path)

            # 从用户数据中读取 session_id（可能是 None，让 AgentLoop 处理）
            # 使用 or None 确保空字符串被规范化为 None
            session_id = self._user_data.get(wechat_user_id, {}).get("last_session_id") or None

            # 构造 InboundMessage
            inbound_msg = InboundMessage(
                type=MessageType.CHAT,
                channel=ChannelType.WECHAT,
                content=content,
                session_id=session_id,
                extra={
                    "media": media_paths,
                    "wechat_user_id": wechat_user_id,  # 传递用户ID，供 send() 使用
                },
            )

            logger.info("准备发布到 bus: id=%s, content=%s", inbound_msg.id, content)
            # 发送到 bus
            try:
                response: OutboundMessage = await self.bus.send(inbound_msg)

                # 记录 LLM 调用（命令消息如 /new /continue 不记录）
                if not content.startswith("/"):
                    try:
                        system_prompt = Context.build_system_prompt(inbound_msg)
                        llm_call_logger.log_call(
                            inbound_msg=inbound_msg,
                            outbound_msg=response,
                            prompt_module="chat",
                            prompt_name="wechat_chat",
                            system_prompt=system_prompt,
                        )
                    except Exception as log_e:
                        # ✅ 日志记录是辅助操作，允许 except Exception 防止影响主流程
                        logger.warning("记录 LLM 调用日志失败: %s", log_e)

                if response.session_id:
                    # 使用最新的session_id继续处理
                    logger.debug("更新session_id %s -> %s", session_id, response.session_id)
                    # 更新用户数据中的 session_id
                    if wechat_user_id not in self._user_data:
                        self._user_data[wechat_user_id] = {}
                    self._user_data[wechat_user_id]["last_session_id"] = response.session_id
                    need_save = True

                # 统一持久化到 DB（替代原文件存储方式）
                # 参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
                if need_save:
                    try:
                        self._save_user_data_to_db()
                        logger.info("已保存用户数据到 DB")
                    except Exception as save_error:
                        logger.error("保存用户数据失败: error=%s", save_error, exc_info=True)

                # 将用户ID传递到响应中
                if not response.extra:
                    response.extra = {}
                response.extra["wechat_user_id"] = wechat_user_id

                await self.send(response)
            except LWBaseError as e:
                logger.error("处理消息失败: error=%s", e, exc_info=True)
                # 发送错误消息给用户
                error_response = OutboundMessage(
                    id=inbound_msg.id,
                    response=LLMResponse(content=f"[ERROR] 处理消息时出错: {e.message or str(e)}"),
                    extra={"wechat_user_id": wechat_user_id},  # 传递用户ID
                )

                try:
                    await self.send(error_response)
                except Exception as send_error:
                    # ✅ 发送错误消息失败时，允许 except Exception（未知的第三方 API 错误）
                    logger.error("发送错误消息也失败: error=%s", send_error, exc_info=True)

        except (KeyError, ValueError, TypeError) as e:
            logger.error("消息解析错误: error=%s", e, exc_info=True)
            raise WechatMessageError(f"消息解析失败: {e}") from e
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("媒体下载错误: error=%s", e, exc_info=True)
            raise WechatMessageError(f"媒体下载失败: {e}") from e
