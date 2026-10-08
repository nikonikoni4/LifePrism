"""微信命令与原生聊天目录的跨渠道恢复契约。

命令业务已从微信渠道迁到 ``SessionCommandService``：本测试用真实 Runtime
的 ``chat_sessions`` 和内存会话引用直接驱动命令服务，验证跨渠道继续、
工作流排除与重启后沿用 /new 会话。
"""

import asyncio

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType
from lifeprism.llm.conversation.commands import SessionCommandService
from lifeprism.llm.conversation.types import ConversationRoute

pytestmark = pytest.mark.core


class MemoryReferences:
    """内存会话引用；不触碰生产账号状态。"""

    def __init__(self):
        self.values = {}

    def get(self, route):
        return self.values.get(route)

    def set(self, route, session_id):
        self.values[route] = session_id


def _content(message) -> str:
    """取出命令回复文本。"""
    assert message is not None
    assert message.response is not None
    return message.response.content


def test_wechat_commands_resume_local_chat_and_exclude_workflow(tmp_path):
    """本地会话可从微信继续，工作流不可切换；命令本身不调用模型。"""

    async def scenario():
        client = FakeClient()
        runtime = make_runtime(tmp_path, client)
        references = MemoryReferences()
        service = SessionCommandService(runtime.chat_sessions, references)
        route = ConversationRoute(channel=ChannelType.WECHAT, recipient_id="wx")
        try:
            local = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="local"))
            workflow = await runtime.execute(
                InboundMessage(
                    type=MessageType.GENERAL_TASK, content="task", workflow_id="daily-memory"
                )
            )
            calls = len(client.calls)
            listing = await service.handle("/session-list", route)
            assert local.session_id in _content(listing)
            assert workflow.session_id not in _content(listing)
            await service.handle(f"/continue {local.session_id}", route)
            assert references.get(route) == local.session_id
            await service.handle(f"/continue {workflow.session_id}", route)
            assert references.get(route) == local.session_id
            assert len(client.calls) == calls
            result = await runtime.execute(
                InboundMessage(
                    type=MessageType.CHAT,
                    channel=ChannelType.WECHAT,
                    content="wechat follow-up",
                    session_id=references.get(route),
                )
            )
            assert result.session_id == local.session_id
            history = await runtime.chat_sessions.get_history(local.session_id)
            user_text = [m["content"] for m in history["messages"] if m["role"] == "user"]
            assert any("local" in text for text in user_text)
            assert any("wechat follow-up" in text for text in user_text)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_new_command_saved_session_continues_after_runtime_restart(tmp_path):
    """/new 回复的 ID 已落盘，重启后首条普通消息继续同一 ID。"""

    async def scenario():
        client = FakeClient()
        runtime = make_runtime(tmp_path, client)
        references = MemoryReferences()
        service = SessionCommandService(runtime.chat_sessions, references)
        route = ConversationRoute(channel=ChannelType.WECHAT, recipient_id="wx")
        message = await service.handle("/new", route)
        sid = references.get(route)
        assert message.session_id == sid
        assert not client.calls
        await runtime.close()
        restarted = make_runtime(tmp_path, client)
        try:
            result = await restarted.execute(
                InboundMessage(
                    type=MessageType.CHAT,
                    channel=ChannelType.WECHAT,
                    content="first",
                    session_id=sid,
                )
            )
            assert result.session_id == sid
            history = await restarted.chat_sessions.get_history(sid)
            assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
        finally:
            await restarted.close()

    asyncio.run(scenario())
