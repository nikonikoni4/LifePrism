"""消息中转类型定义"""

from dataclasses import dataclass, field
from lifeprism.llm.providers.llm_providers.base import LLMResponse
import uuid

class MessageType:
    CLASSIFY = "classify"  # 从extra 中 提供 分类提示词 + templates\agent\classify\classify_preference.md 分类偏好
    CHAT = "chat" # 会添加专门的系统提示词
    GENERAL_TASK = "general_task" # 不会添加任何系统提示词，可以自行通过extra传递

class ChannelType:
    WECHAT = "wechat" # 微信渠道
    LOCAL = "local" # 本机渠道

MESSAGE_TYPE = [MessageType.CLASSIFY, MessageType.CHAT,MessageType.GENERAL_TASK]
CHANNEL_TYPE = [ChannelType.WECHAT, ChannelType.LOCAL]

@dataclass
class InboundMessage:
    type : str # 功能类型， 具体的功能类型会影响cotext模块最初的system prompt的构建
    id : str = field(default_factory=lambda : str(uuid.uuid4())[:4]) # 随机id,用于进行任务的
    channel : str = ChannelType.LOCAL
    content : str | list | None = '' # 消息内容，支持文本、多模态列表（图片+文本）或空值
    session_id : str | None = None # 用户继续会话的id，未传入时会自动创建session
    extra : dict | None = None 
    # extra 说明 
    # 对于classify 包括 system_prompt:str ，每个节点单独传递
    # 对于chat 包括skill_list : list , 传送需要加载的skill
    # 对于general_task，可以添加system_prompt
    def __post_init__(self):
        if self.type not in MESSAGE_TYPE:
            raise ValueError(f"无效的消息类型: {self.type!r}，合法值为 {MESSAGE_TYPE}")
        if self.channel not in CHANNEL_TYPE:
            raise ValueError(f"无效的channel: {self.channel!r}，合法值为 {CHANNEL_TYPE}")

@dataclass 
class OutboundMessage:
    id : str = ''
    response : LLMResponse | None = None # 返回消息
    session_id :str | None = None # 用户当创建首次创建session时返回id，tokens_usage保存需要



