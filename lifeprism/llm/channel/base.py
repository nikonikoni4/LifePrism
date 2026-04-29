from abc import ABC, abstractmethod
from typing import Protocol
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import OutboundMessage
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)


class ChannelConfig(Protocol):
    """Channel 配置协议。

    Attributes:
        allow_from: 允许的发送者列表，支持 "*" 通配符
    """
    allow_from: list[str]


class BaseChannel(ABC):
    """消息平台接入基类。

    提供统一的消息平台接入接口，子类需实现具体平台的消息收发逻辑。

    Attributes:
        name: Channel 名称标识
        config: Channel 配置对象
        bus: 消息总线队列
    """

    name: str = "base"

    def __init__(self, config: ChannelConfig, bus: MessageQueue) -> None:
        """初始化 Channel。

        Args:
            config: Channel 配置对象
            bus: 消息总线队列
        """
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """启动 channel，开始接收消息。"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止 channel。"""
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到平台。

        Args:
            msg: 待发送的出站消息
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """检查发送者是否被允许。

        Args:
            sender_id: 发送者 ID

        Returns:
            True 表示允许，False 表示拒绝
        """
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            logger.warning(f"{self.name}: allow_from is empty - all access denied")
            return False
        if "*" in allow_list:
            return True
        return str(sender_id) in allow_list
