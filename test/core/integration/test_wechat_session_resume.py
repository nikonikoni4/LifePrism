"""微信命令与原生聊天目录的跨渠道恢复契约。"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType
from lifeprism.llm.channel.wechat import channel as channel_module
from lifeprism.llm.channel.wechat.channel import WechatChannel

pytestmark = pytest.mark.core


def test_wechat_commands_resume_local_chat_and_exclude_workflow(tmp_path, monkeypatch):
    """本地会话可从微信继续，工作流不可切换；命令本身不调用模型。"""

    async def scenario():
        client = FakeClient()
        runtime = make_runtime(tmp_path, client)
        monkeypatch.setattr(channel_module, "agent_runtime", runtime)
        channel = WechatChannel.__new__(WechatChannel)
        channel._user_data = {"wx": {"context_token": "ctx"}}
        channel.send = AsyncMock()
        channel._save_user_data_to_db = Mock()
        try:
            local = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="local"))
            workflow = await runtime.execute(
                InboundMessage(
                    type=MessageType.GENERAL_TASK, content="task", workflow_id="daily-memory"
                )
            )
            calls = len(client.calls)
            assert await channel._handle_session_command("/session-list", "wx")
            listing = channel.send.call_args.args[0].response.content
            assert local.session_id in listing
            assert workflow.session_id not in listing
            await channel._handle_session_command(f"/continue {local.session_id}", "wx")
            assert channel._user_data["wx"]["last_session_id"] == local.session_id
            await channel._handle_session_command(f"/continue {workflow.session_id}", "wx")
            assert channel._user_data["wx"]["last_session_id"] == local.session_id
            assert len(client.calls) == calls
            result = await runtime.execute(
                InboundMessage(
                    type=MessageType.CHAT,
                    channel=ChannelType.WECHAT,
                    content="wechat follow-up",
                    session_id=channel._user_data["wx"]["last_session_id"],
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


def test_new_command_saved_session_continues_after_runtime_restart(tmp_path, monkeypatch):
    """/new回复的ID已落盘，重启后首条普通消息继续同一ID。"""

    async def scenario():
        client = FakeClient()
        runtime = make_runtime(tmp_path, client)
        monkeypatch.setattr(channel_module, "agent_runtime", runtime)
        channel = WechatChannel.__new__(WechatChannel)
        channel._user_data = {"wx": {"context_token": "ctx"}}
        channel.send = AsyncMock()
        channel._save_user_data_to_db = Mock()
        await channel._handle_session_command("/new", "wx")
        sid = channel._user_data["wx"]["last_session_id"]
        assert channel.send.call_args.args[0].session_id == sid
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
