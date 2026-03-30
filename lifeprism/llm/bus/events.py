"""消息中转类型定义"""

from dataclasses import dataclass, field

import uuid

class MessageType:
    CLASSIFY = "classify"
    CHAT = "chat"

MESSAGE_TPYE = [MessageType.CLASSIFY, MessageType.CHAT]


@dataclass
class InboundMessage:
    type : str # 功能类型， 具体的功能类型会影响cotext模块最初的system prompt的构建
    id : str = field(default_factory=lambda : str(uuid.uuid4())[:4]) # 随机id,用于进行任务的
    content : str = '' # 消息内容
    session_id : str | None = None # 用户继续会话的id，未传入时会自动创建session
    extra : dict | None = None
    def __post_init__(self):
        if self.type not in MESSAGE_TPYE:
            raise ValueError(f"无效的消息类型: {self.type!r}，合法值为 {MESSAGE_TPYE}")

@dataclass 
class OutboundMessage:
    id : str = ''
    response : str = '' # 返回消息



