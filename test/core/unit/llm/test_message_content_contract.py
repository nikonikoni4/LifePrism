"""Tests for LLM message content shape invariants."""

import pytest

from lifeprism.llm.agent.context import Context
from lifeprism.llm.agent.loop import AgentLoop
from lifeprism.llm.bus import InboundMessage, MessageContent, MessageType
from lifeprism.llm.providers.llm_providers.base import LLMProvider


@pytest.mark.core
def test_inbound_message_converts_text_content_to_text_block():
    msg = InboundMessage(type=MessageType.GENERAL_TASK, content="hello")

    assert isinstance(msg.content, MessageContent)
    assert msg.content.blocks == [{"type": "text", "text": "hello"}]


@pytest.mark.core
def test_message_content_adds_head_and_end_messages():
    content = MessageContent({"type": "text", "text": "middle"})

    content.add_head("head")
    content.add_tail({"type": "text", "text": "tail"})

    assert content.blocks == [
        {"type": "text", "text": "head"},
        {"type": "text", "text": "middle"},
        {"type": "text", "text": "tail"},
    ]


@pytest.mark.core
def test_message_content_rejects_invalid_block_shape():
    with pytest.raises(ValueError, match="不支持的 content block type"):
        MessageContent({"type": "unknown"})


@pytest.mark.core
def test_context_preserves_multimodal_user_content_blocks():
    image_block = {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,abc"},
    }
    msg = InboundMessage(
        type=MessageType.GENERAL_TASK,
        content=[image_block],
    )

    user_message = Context._build_user_message(msg)

    assert isinstance(user_message, list)
    assert user_message[0]["type"] == "text"
    assert "## user's message" in user_message[0]["text"]
    assert user_message[1] is image_block
    assert "data:image/png;base64" not in user_message[0]["text"]


@pytest.mark.core
def test_provider_rejects_string_content_on_last_user_message():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "plain text should have been normalized"},
    ]

    with pytest.raises(ValueError, match="last user message content"):
        LLMProvider._validate_last_user_content_is_multimodal(messages)


@pytest.mark.core
def test_provider_accepts_list_content_on_last_user_message():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
    ]

    LLMProvider._validate_last_user_content_is_multimodal(messages)


@pytest.mark.core
def test_agent_loop_extracts_text_from_normalized_command_message():
    msg = InboundMessage(type=MessageType.CHAT, content="/new")

    assert AgentLoop._message_text(msg) == "/new"
