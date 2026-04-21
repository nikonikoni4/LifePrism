"""消息中转类型定义"""

from dataclasses import dataclass, field
from lifeprism.llm.providers.llm_providers.base import LLMResponse
import uuid

class MessageType:
    CLASSIFY = "classify"  # 从extra 中 提供 分类提示词 + templates\agent\classify\classify_preference.md 分类偏好
    CHAT = "chat"
    GENERAL_TASK = "general_task"

MESSAGE_TPYE = [MessageType.CLASSIFY, MessageType.CHAT,MessageType.GENERAL_TASK]


@dataclass
class InboundMessage:
    type : str # 功能类型， 具体的功能类型会影响cotext模块最初的system prompt的构建
    id : str = field(default_factory=lambda : str(uuid.uuid4())[:4]) # 随机id,用于进行任务的
    content : str = '' # 消息内容
    session_id : str | None = None # 用户继续会话的id，未传入时会自动创建session
    extra : dict | None = None 
    # extra 说明 
    # 对于classify 包括 system_prompt:str ，每个节点单独传递
    # 对于chat 包括skill_list : list , 传送需要加载的skill
    def __post_init__(self):
        if self.type not in MESSAGE_TPYE:
            raise ValueError(f"无效的消息类型: {self.type!r}，合法值为 {MESSAGE_TPYE}")

@dataclass 
class OutboundMessage:
    id : str = ''
    response : LLMResponse | None = None # 返回消息



