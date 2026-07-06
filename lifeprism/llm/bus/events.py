"""消息中转类型定义"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from lifeprism.llm.providers.llm_providers.base import LLMResponse


class MessageType:
    CLASSIFY = "classify"  # 从extra 中 提供 分类提示词 + templates\agent\classify\classify_preference.md 分类偏好
    CHAT = "chat"  # 会添加专门的系统提示词
    GENERAL_TASK = "general_task"  # 不会添加任何系统提示词，可以自行通过extra传递
    DREAM_TASK = "dream_task"  # 1. 从聊天数据中提取内容在chat_history.json和user.md 2. 从chat_history提取内容到behavior.md 3. 从behavior.md提取内容到recent_state.md


class TokenType:
    CLASSIFY = "classify"  # 从extra 中 提供 分类提示词 + templates\agent\classify\classify_preference.md 分类偏好
    CHAT = "chat"  # 会添加专门的系统提示词
    GENERAL_TASK = "general_task"  # 不会添加任何系统提示词，可以自行通过extra传递
    DREAM_TASK = "dream_task"  # 1. 从聊天数据中提取内容在chat_history.json和user.md 2. 从chat_history提取内容到behavior.md 3. 从behavior.md提取内容到recent_state.md


class ChannelType:
    WECHAT = "wechat"  # 微信渠道
    LOCAL = "local"  # 本机渠道


MESSAGE_TYPE = [
    MessageType.CLASSIFY,
    MessageType.CHAT,
    MessageType.GENERAL_TASK,
    MessageType.DREAM_TASK,
]
CHANNEL_TYPE = [ChannelType.WECHAT, ChannelType.LOCAL]

MessageContentInput = str | dict[str, Any] | list[dict[str, Any]] | None


class MessageContent(list):
    """Normalized multimodal message content blocks.

    External callers may provide plain text, a single content block, a list of
    content blocks, None, or another MessageContent. Internally the value is
    always a list of provider-compatible content blocks.
    """

    def __init__(self, value: MessageContentInput | MessageContent = None):
        super().__init__()
        self.add_tail(value)

    def add_head(self, value: MessageContentInput | MessageContent) -> None:
        blocks = self._normalize(value)
        self[:0] = blocks

    def add_tail(self, value: MessageContentInput | MessageContent) -> None:
        self.extend(self._normalize(value))

    @property
    def blocks(self) -> list[dict[str, Any]]:
        return list(self)

    @classmethod
    def _normalize(cls, value: MessageContentInput | MessageContent) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, MessageContent):
            return value.blocks
        if isinstance(value, str):
            return [{"type": "text", "text": value}]
        if isinstance(value, dict):
            cls._validate_block(value)
            return [value]
        if isinstance(value, list):
            for block in value:
                cls._validate_block(block)
            return value
        raise TypeError(
            f"content 必须是 str、dict、list、MessageContent 或 None，当前类型为 {type(value)!r}"
        )

    @staticmethod
    def _validate_block(block: dict[str, Any]) -> None:
        if not isinstance(block, dict):
            raise TypeError(f"content block 必须是 dict，当前类型为 {type(block)!r}")

        block_type = block.get("type")
        if block_type == "text":
            if not isinstance(block.get("text"), str):
                raise ValueError("text block 必须包含字符串字段 text")
            return

        if block_type == "image_url":
            image_url = block.get("image_url")
            if not isinstance(image_url, dict) or not isinstance(image_url.get("url"), str):
                raise ValueError("image_url block 必须包含字符串字段 image_url.url")
            return

        raise ValueError(f"不支持的 content block type: {block_type!r}")


@dataclass
class InboundMessage:
    type: str  # 功能类型， 具体的功能类型会影响cotext模块最初的system prompt的构建
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:4])  # 随机id,用于进行任务的
    channel: str = ChannelType.LOCAL
    content: MessageContentInput = ""  # 消息内容，统一归一化为多模态列表
    session_id: str | None = None  # 用户继续会话的id，未传入时会自动创建session
    token_type: str | None = None  # token 统计类型，为空时使用 type
    extra: dict | None = None

    # extra 说明
    # 对于classify 包括 system_prompt:str ，每个节点单独传递
    # 对于chat 包括skill_list : list , 传送需要加载的skill
    # 对于general_task，可以添加system_prompt
    # 对于dream_task,可以添加system_prompt
    def __post_init__(self):
        if self.type not in MESSAGE_TYPE:
            raise ValueError(f"无效的消息类型: {self.type!r}，合法值为 {MESSAGE_TYPE}")
        if self.channel not in CHANNEL_TYPE:
            raise ValueError(f"无效的channel: {self.channel!r}，合法值为 {CHANNEL_TYPE}")
        self.content = MessageContent(self.content)


@dataclass
class OutboundMessage:
    id: str = ""
    response: LLMResponse | None = None  # 返回消息
    session_id: str | None = None  # 用户当创建首次创建session时返回id，tokens_usage保存需要
    extra: dict | None = None  # 额外数据，用于传递 channel 特定信息（如 wechat_user_id）
