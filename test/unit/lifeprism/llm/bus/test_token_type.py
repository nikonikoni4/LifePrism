"""测试 InboundMessage 的 token_type 字段"""
import pytest
from lifeprism.llm.bus.events import InboundMessage, MessageType


def test_token_type_default_none():
    """测试 token_type 默认为 None"""
    msg = InboundMessage(
        type=MessageType.CHAT,
        content="test"
    )
    assert msg.token_type is None


def test_token_type_custom_value():
    """测试可以设置自定义 token_type"""
    msg = InboundMessage(
        type=MessageType.CHAT,
        token_type="chat_deep_analysis",
        content="test"
    )
    assert msg.token_type == "chat_deep_analysis"


def test_token_type_fallback_logic():
    """测试 token_type 为空时回退到 type 的逻辑"""
    # 模拟 queue.py 中的逻辑
    msg1 = InboundMessage(type=MessageType.CHAT, content="test")
    mode1 = msg1.token_type or msg1.type
    assert mode1 == MessageType.CHAT

    msg2 = InboundMessage(
        type=MessageType.CHAT,
        token_type="custom_type",
        content="test"
    )
    mode2 = msg2.token_type or msg2.type
    assert mode2 == "custom_type"
