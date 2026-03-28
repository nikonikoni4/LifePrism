"""消息中转类型定义"""

from dataclasses import dataclass, field

import uuid

@dataclass
class InboundMessage:
    type : str # 功能类型， 具体的功能类型会影响cotext模块最初的system prompt的构建
    id : str = field(default_factory=lambda : str(uuid.uuid4())[:4]) # 随机id
    content : str = '' # 消息内容

@dataclass 
class OutboundMessage:
    id : str = ''
    response : str = '' # 返回消息



