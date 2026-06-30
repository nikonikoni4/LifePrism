"""微信 Channel 主类模块
本文件源自 https://github.com/HKUDS/nanobot.git，经 AI 改写适配 lifeprism 项目。
"""

import asyncio
import httpx
from typing import Any
from pathlib import Path
from lifeprism.llm.channel.base import BaseChannel
from lifeprism.llm.channel.wechat.config import WechatConfig
from lifeprism.llm.channel.wechat.client import WechatClient
from lifeprism.llm.channel.wechat.auth import WechatAuth
from lifeprism.llm.channel.wechat.media import WechatMedia
from lifeprism.llm.channel.wechat.exceptions import WechatAPIError, WechatMessageError
from lifeprism.llm.bus import MessageQueue,OutboundMessage,MessageType,ChannelType,InboundMessage
from lifeprism.llm.providers import LLMResponse
from lifeprism.config.settings_manager import settings
from lifeprism.utils.logger import get_logger
from lifeprism.llm.session import session_manager
from lifeprism.llm.utils.llm_call_logger import llm_call_logger
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

        # 加载状态
        state = self.auth.load_state()
        token = state.get("token", "")

        # 加载用户数据（新格式）
        self._user_data = state.get("user_data", {})

        # 兼容旧格式：如果存在 context_tokens，迁移到新格式
        old_context_tokens = state.get("context_tokens", {})
        if old_context_tokens and not self._user_data:
            logger.info("检测到旧格式数据，正在迁移...")
            for user_id, context_token in old_context_tokens.items():
                self._user_data[user_id] = {
                    "context_token": context_token,
                    # 旧数据没有 session_id，使用 None 而不是空字符串
                }
            logger.info(f"已迁移 {len(old_context_tokens)} 个用户的数据")

        logger.info(f"加载的 token: {token[:20] if token else 'None'}...")
        logger.info(f"加载的用户数据: {len(self._user_data)} 个用户")

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
            logger.info(f"Token 测试成功，返回数据: {test_data}")
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
            logger.error(f"Token 测试失败: {e}", exc_info=True)

        # 初始化媒体处理
        self.media = WechatMedia(self.client, self.media_dir)

        # 启动长轮询
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """停止 channel

        取消消息轮询任务并关闭客户端连接。
        """
        self._running = False

        # 保存最新的用户数据（兜底保障）
        if self.auth and self.client and self._user_data:
            try:
                state = {
                    "token": self.client.token,
                    "user_data": self._user_data
                }
                self.auth.save_state(state)
                logger.info(f"停止时保存用户数据: {len(self._user_data)} 个用户")
            except Exception as e:
                logger.error(f"停止时保存用户数据失败: {e}", exc_info=True)

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
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
            logger.debug(f"消息内容为空，跳过发送: {wechat_user_id}")
            return

        # 构造并发送消息
        try:
            from lifeprism.llm.channel.wechat.message import WechatMessage
            message_body = WechatMessage.build_text_message(wechat_user_id, content, context_token)
            await self.client.api_post("ilink/bot/sendmessage", message_body)
            logger.info(f"发送消息到微信: 用户id :{wechat_user_id}")
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
            logger.error(f"发送消息失败，目标用户: {wechat_user_id}, 错误: {e}", exc_info=True)
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
                logger.debug(f"第 {poll_count} 次轮询, get_updates_buf={get_updates_buf[:50]}...")
                body = {"get_updates_buf": get_updates_buf}
                data = await self.client.api_post("ilink/bot/getupdates", body)

                # 打印完整响应（使用 DEBUG 级别避免日志噪音）
                logger.debug(f"完整响应数据: {data}")

                get_updates_buf = data.get("get_updates_buf", "")
                messages = data.get("msgs", [])

                logger.debug(f"轮询返回: get_updates_buf={get_updates_buf[:50]}..., 消息数={len(messages)}")

                if messages:
                    logger.info(f"*** 收到 {len(messages)} 条消息 ***")
                    for idx, msg in enumerate(messages):
                        logger.info(f"消息 {idx+1}: {msg}")
                        await self._handle_wechat_message(msg)

            except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
                logger.error(f"长轮询网络错误: {e}", exc_info=True)
                await asyncio.sleep(5)
            except (KeyError, ValueError) as e:
                logger.error(f"长轮询数据解析错误: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _handle_wechat_message(self, msg: dict[str, Any]) -> None:
        """处理微信消息

        解析微信消息，检查权限，下载媒体文件，构造 InboundMessage 并发送到消息总线。
        单个消息处理失败不会影响其他消息的处理。

        Args:
            msg: 原始微信消息字典
        """
        try:
            logger.info(f"开始处理微信消息: {msg}")
            from lifeprism.llm.channel.wechat.message import WechatMessage

            parsed = WechatMessage.parse_message(msg)
            logger.debug(f"解析后的消息: {parsed}")

            wechat_user_id = parsed["from_user_id"]
            content = parsed["content"]
            context_token = parsed["context_token"]

            # 检查权限
            if not self.is_allowed(wechat_user_id):
                logger.warning(f"拒绝未授权用户: {wechat_user_id}")
                return

            logger.info(f"用户 {wechat_user_id} 已授权")

            # 标记是否需要持久化
            need_save = False

            # 保存 context_token 到用户数据
            if context_token:
                if wechat_user_id not in self._user_data:
                    self._user_data[wechat_user_id] = {}
                self._user_data[wechat_user_id]["context_token"] = context_token
                logger.debug(f"context_token ： {context_token}")
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
                }
            )

            logger.info(f"准备发布到 bus: id={inbound_msg.id}, content={content}")
            # 发送到 bus
            logger.info(f"发送消息")
            try:
                response: OutboundMessage = await self.bus.send(inbound_msg)

                # 记录 LLM 调用（命令消息如 /new /continue 不记录）
                if not content.startswith('/'):
                    try:
                        llm_call_logger.log_call(
                            inbound_msg=inbound_msg,
                            outbound_msg=response,
                            prompt_module="chat",
                            prompt_name="wechat_chat",
                        )
                    except Exception as log_e:
                        logger.warning(f"记录 LLM 调用日志失败: {log_e}")

                if response.session_id:
                    # 使用最新的session_id继续处理
                    logger.debug(f"更新session_id {session_id} -> {response.session_id}")
                    # 更新用户数据中的 session_id
                    if wechat_user_id not in self._user_data:
                        self._user_data[wechat_user_id] = {}
                    self._user_data[wechat_user_id]["last_session_id"] = response.session_id
                    need_save = True

                # 统一持久化（避免多次写文件）
                if need_save:
                    try:
                        state = {
                            "token": self.client.token if self.client else "",
                            "user_data": self._user_data
                        }
                        self.auth.save_state(state)
                        logger.debug(f"已保存用户 {wechat_user_id} 的数据")
                    except Exception as save_error:
                        logger.error(f"保存用户数据失败: {save_error}", exc_info=True)

                # 将用户ID传递到响应中
                if not response.extra:
                    response.extra = {}
                response.extra["wechat_user_id"] = wechat_user_id

                logger.info(f"发送响应消息->wechat")
                await self.send(response)
            except Exception as e:
                logger.error(f"处理消息失败: {e}", exc_info=True)
                # 发送错误消息给用户
                error_response = OutboundMessage(
                    id=inbound_msg.id,
                    response=LLMResponse(content=f"[ERROR] 处理消息时出错: {e}"),
                    extra={"wechat_user_id": wechat_user_id}  # 传递用户ID
                )
                
                try:
                    await self.send(error_response)
                except Exception as send_error:
                    logger.error(f"发送错误消息也失败: {send_error}", exc_info=True)
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"消息解析错误: {e}", exc_info=True)
            raise WechatMessageError(f"消息解析失败: {e}") from e
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(f"媒体下载错误: {e}", exc_info=True)
            raise WechatMessageError(f"媒体下载失败: {e}") from e
