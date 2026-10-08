"""收发适配器与会话业务的应用装配点。"""

from typing import TYPE_CHECKING

from lifeprism.config import settings
from lifeprism.llm.bus import bus
from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig
from lifeprism.llm.conversation.references import SessionReferences, WechatSessionReferences
from lifeprism.llm.conversation.service import ConversationService
from lifeprism.llm.conversation.types import ConversationRoute
from lifeprism.llm.runtime import agent_runtime
from lifeprism.utils import LazySingleton, get_logger

if TYPE_CHECKING:
    from lifeprism.llm.runtime import AgentRuntime

logger = get_logger(__name__)


def wire_wechat_channel(
    channel: WechatChannel, runtime: "AgentRuntime", references: SessionReferences
) -> ConversationService:
    """注入业务接收入口、输出与生命周期；transport 不导入这些业务。"""

    def permitted(route: ConversationRoute) -> bool:
        allowed = channel.config.allow_from
        if not allowed or ("*" not in allowed and route.recipient_id not in allowed):
            return False
        if settings.run_mode == "agent_only":
            from lifeprism.sync.heartbeat_manager import heartbeat_manager

            if heartbeat_manager.is_local_online():
                logger.info("本地在线，跳过云端处理微信消息")
                return False
            logger.info("本地离线，云端接管处理微信消息")
        return True

    service = ConversationService(runtime, references, channel.send, allow_input=permitted)

    async def start_service() -> None:
        runtime.start()
        service.start()

    channel.on_message = service.submit
    channel.allow_input = service.can_receive
    channel.on_start = start_service
    channel.on_stop = service.close
    return service


def _create_wechat_channel(config: WechatConfig) -> WechatChannel:
    channel = WechatChannel(config, bus)
    wire_wechat_channel(channel, agent_runtime, WechatSessionReferences())
    return channel


wechat_channel: WechatChannel = LazySingleton(
    _create_wechat_channel, WechatConfig(enabled=True, allow_from=["*"])
)

__all__ = ["wechat_channel"]
