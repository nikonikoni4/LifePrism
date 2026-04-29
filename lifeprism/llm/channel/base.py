from abc import ABC, abstractmethod
from typing import Any
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import OutboundMessage
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

class BaseChannel(ABC):
    """消息平台接入基类"""

    name: str = "base"

    def __init__(self, config: Any, bus: MessageQueue):
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """启动 channel，开始接收消息"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止 channel"""
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到平台"""
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """检查发送者是否被允许"""
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            logger.warning(f"{self.name}: allow_from is empty - all access denied")
            return False
        if "*" in allow_list:
            return True
        return str(sender_id) in allow_list