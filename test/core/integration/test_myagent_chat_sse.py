"""校验本地 SSE 边界在真实 native Agent 轮次下的行为。"""

import asyncio

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.server.services.chatbot_service import ChatbotService

pytestmark = pytest.mark.core


def test_sse_returns_final_tool_answer_and_total_usage(tmp_path, monkeypatch):
    """守护单轮 SSE 会透出工具事件、最终回答并汇总 usage。"""
    async def scenario():
        """在 `asyncio.run` 下驱动工具轮次的 SSE 场景。"""
        runtime = make_runtime(tmp_path, FakeClient(with_tool=True))
        monkeypatch.setattr("lifeprism.llm.chat.chat_bot.agent_runtime", runtime)
        try:
            events = [event async for event in ChatbotService().send_message("test")]
            assert events[0].type == "session"
            assert any(event.type == "status" and event.node == "tool/result" for event in events)
            assert "".join(event.message for event in events if event.type == "content") == "hello"
            assert events[-1].type == "done"
            assert events[-1].message == "hello"
            assert events[-1].usage["total_tokens"] == 14
            assert len({event.run_id for event in events}) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_sse_disconnect_cancels_model_and_errors_have_no_done(tmp_path, monkeypatch):
    """守护断开连接会取消模型调用，且 provider 报错后不再产生 done 事件。"""
    async def scenario():
        """在 `asyncio.run` 下驱动先断开、后失败的 SSE 场景。"""
        client = FakeClient(block=True)
        runtime = make_runtime(tmp_path, client)
        monkeypatch.setattr("lifeprism.llm.chat.chat_bot.agent_runtime", runtime)
        stream = ChatbotService().send_message("test")
        await anext(stream)
        while not client.calls:
            await asyncio.sleep(0)
        await stream.aclose()
        assert client.cancelled
        assert not runtime._tasks
        await runtime.close()
        runtime = make_runtime(tmp_path, FakeClient(fail=True))
        monkeypatch.setattr("lifeprism.llm.chat.chat_bot.agent_runtime", runtime)
        try:
            events = [event async for event in ChatbotService().send_message("test")]
            assert events[-1].type == "error"
            assert "provider failed" in events[-1].error
            assert not any(event.type == "done" for event in events)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_deferred_token_api_returns_501(tmp_path, monkeypatch):
    """守护延后处理的 token 接口保持未实现，直接返回 HTTP 501。"""
    async def scenario():
        """在 `asyncio.run` 下驱动延后 token 接口场景。"""
        from fastapi import HTTPException

        from lifeprism.server.api import chatbot_api

        monkeypatch.setattr(chatbot_api, "chatbot_service", ChatbotService())
        with pytest.raises(HTTPException) as error:
            await chatbot_api.get_session_tokens("native-session")
        assert error.value.status_code == 501

    asyncio.run(scenario())
