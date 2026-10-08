"""收发路由与统一输入，不携带 Agent 或微信业务处理。"""

from dataclasses import dataclass, field
from uuid import uuid4

from lifeprism.llm.bus.events import CHANNEL_TYPE, MessageContent, MessageContentInput


@dataclass(frozen=True)
class ConversationRoute:
    """不可变的收发归属；Session ID 不决定接收人。"""

    channel: str
    recipient_id: str
    transport_id: str = "wechat"

    def __post_init__(self) -> None:
        if self.channel not in CHANNEL_TYPE or not self.recipient_id or not self.transport_id:
            raise ValueError("无效的会话收发路由")


@dataclass
class ConversationInput:
    """渠道提交的统一输入，人工回复不必构造成 Agent user turn。"""

    route: ConversationRoute
    content: MessageContentInput
    input_id: str = field(default_factory=lambda: uuid4().hex)
    extra: dict = field(default_factory=dict)
    request_id: str | None = None

    def __post_init__(self) -> None:
        self.content = MessageContent(self.content)

    @property
    def text(self) -> str:
        """返回供命令和选项解析使用的文本。"""
        return "".join(block.get("text", "") for block in self.content)
