"""真实 myagent 人在回路在渠道之外等待、唤醒和输出的契约。"""

import asyncio
from types import SimpleNamespace

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.config.agent_config import AgentSettings
from lifeprism.llm.bus import InboundMessage, MessageType

pytestmark = pytest.mark.core


class MemoryReferences:
    """会话引用存储替身；不触碰生产账号状态。"""

    def __init__(self):
        self.values = {}

    def get(self, route):
        return self.values.get(route)

    def set(self, route, session_id):
        self.values[route] = session_id


def setup_conversation(tmp_path, monkeypatch, *, timeout=2.0, sender=None):
    """按一轮一步预算构建真实 Runtime 与可观测会话服务。"""
    from lifeprism.llm.conversation.service import ConversationService
    from lifeprism.llm.conversation.types import ConversationInput, ConversationRoute
    from lifeprism.llm.runtime import service as runtime_module

    monkeypatch.setattr(
        runtime_module, "settings", SimpleNamespace(agent=AgentSettings(step_limit=1))
    )
    provider = FakeClient(with_tool=True)
    runtime = make_runtime(tmp_path, provider)
    outputs = []
    prompt_sent = asyncio.Event()

    async def send(message):
        outputs.append(message)
        if message.extra["kind"] == "interaction":
            prompt_sent.set()
        if sender:
            await sender(message, runtime)

    references = MemoryReferences()
    service = ConversationService(
        runtime, references, send, hitl_timeout=timeout, hitl_grant_steps=5
    )
    route = ConversationRoute(channel="wechat", recipient_id="alice")
    return service, runtime, provider, references, route, outputs, prompt_sent, ConversationInput


def test_native_hitl_answer_resumes_original_turn_and_outputs_once(tmp_path, monkeypatch):
    """接收不阻塞，人工答案不创建 user turn，清理后才输出最终答复。"""

    async def scenario():
        async def inspect_terminal(message, runtime):
            if message.extra["kind"] == "terminal":
                assert not runtime.is_session_running(message.session_id)

        service, runtime, provider, refs, route, outputs, prompt, Input = setup_conversation(
            tmp_path, monkeypatch, sender=inspect_terminal
        )
        try:
            await asyncio.wait_for(service.submit(Input(route, "do task", input_id="task")), 1)
            await asyncio.wait_for(prompt.wait(), 3)
            sid = refs.get(route)
            assert sid and runtime.is_session_running(sid)
            assert len(provider.calls) == 1
            with pytest.raises(RuntimeError, match="执行"):
                await runtime.chat_sessions.delete(sid)
            await service.submit(Input(route, "继续", input_id="answer"))
            await asyncio.wait_for(service.drain(), 3)
            assert [m.extra["kind"] for m in outputs] == ["interaction", "terminal"]
            assert outputs[-1].response.content == "hello"
            assert len(provider.calls) == 2
            history = await runtime.chat_sessions.get_history(sid)
            assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
            assert history["messages"][0]["content"].split("\n## runtime", 1)[0] == "do task"
            session = runtime._slots[sid].context.session
            assert session.turn == 1
            assert any(r.type == "agent/grant" for r in session.record_list)
        finally:
            await service.close()
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("answer", ["取消", None])
def test_native_hitl_cancel_and_timeout_keep_interrupted_reason(tmp_path, monkeypatch, answer):
    """用户取消和超时都保留 interrupted，不能伪装为成功完成。"""

    async def scenario():
        service, runtime, provider, refs, route, outputs, prompt, Input = setup_conversation(
            tmp_path, monkeypatch, timeout=0.1 if answer is None else 2
        )
        try:
            await service.submit(Input(route, "task"))
            await asyncio.wait_for(prompt.wait(), 3)
            if answer:
                await service.submit(Input(route, answer))
            await asyncio.wait_for(service.drain(), 3)
            assert len(provider.calls) == 1
            assert outputs[-1].extra["kind"] == "terminal"
            assert "取消" in outputs[-1].response.content
            slot = runtime._slots[refs.get(route)]
            assert slot.terminal.reason_type == "interrupted"
            assert not service.is_busy(route)
        finally:
            await service.close()
            await runtime.close()

    asyncio.run(scenario())


def test_closing_while_waiting_cleans_future_and_all_runtime_tasks(tmp_path, monkeypatch):
    """关闭人工等待不能遗留 turn、消费任务、pending 或旧目标绑定。"""

    async def scenario():
        service, runtime, _, refs, route, outputs, prompt, Input = setup_conversation(
            tmp_path, monkeypatch
        )
        try:
            await service.submit(Input(route, "task"))
            await asyncio.wait_for(prompt.wait(), 3)
            await asyncio.wait_for(service.close(), 3)
            assert not service.is_busy(route)
            assert not runtime._tasks and not runtime._consumers
            assert not runtime.is_session_running(refs.get(route))
            assert len(outputs) == 1
            service.start()
            # 同一缓存 context 的后续普通调用不注入 HITL，不保留微信 client。
            result = await runtime.execute(
                InboundMessage(type=MessageType.CHAT, content="local", session_id=refs.get(route))
            )
            assert result.response.content == "hello"
            assert len(outputs) == 1
        finally:
            await service.close()
            await runtime.close()

    asyncio.run(scenario())


def test_terminal_send_failure_does_not_rerun_or_emit_second_terminal(tmp_path, monkeypatch):
    """最终消息发送失败后释放运行，不能把网络异常转成第二份最终输出。"""

    async def scenario():
        async def failing_terminal(message, runtime):
            if message.extra["kind"] == "terminal":
                raise ConnectionError("delivery unknown")

        service, runtime, provider, refs, route, outputs, prompt, Input = setup_conversation(
            tmp_path, monkeypatch, sender=failing_terminal
        )
        try:
            await service.submit(Input(route, "task"))
            await asyncio.wait_for(prompt.wait(), 3)
            await service.submit(Input(route, "1"))
            await asyncio.wait_for(service.drain(), 3)
            assert len(provider.calls) == 2
            assert len([m for m in outputs if m.extra["kind"] == "terminal"]) == 1
            assert not service.is_busy(route)
            assert not runtime.is_session_running(refs.get(route))
        finally:
            await service.close()
            await runtime.close()

    asyncio.run(scenario())


def test_wechat_poll_receives_answer_while_native_loop_is_waiting(tmp_path, monkeypatch):
    """真实收发/装配/Runtime/原生 HITL 串联；仅协议网络和模型使用替身。"""

    async def scenario():
        from unittest.mock import Mock

        from lifeprism.llm import channel as assembly
        from lifeprism.llm.bus import MessageQueue
        from lifeprism.llm.channel import wechat as wechat_package
        from lifeprism.llm.channel import wire_wechat_channel
        from lifeprism.llm.channel.wechat.channel import WechatChannel
        from lifeprism.llm.channel.wechat.config import WechatConfig
        from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

        unused, runtime, provider, refs, route, _, _, _ = setup_conversation(tmp_path, monkeypatch)
        await unused.close()
        monkeypatch.setattr(assembly, "settings", SimpleNamespace(run_mode="local"))
        prompt = asyncio.Event()
        finished = asyncio.Event()
        sent = []

        def incoming(text, mid, token):
            return {
                "from_user_id": "alice",
                "message_id": mid,
                "context_token": token,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }

        class ProtocolClient:
            def __init__(self):
                self.polls = 0
                self.closed = False

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                self.closed = True

            async def api_post(self, endpoint, body):
                if endpoint.endswith("sendmessage"):
                    sent.append(body["msg"])
                    (prompt if len(sent) == 1 else finished).set()
                    return {}
                self.polls += 1
                if self.polls == 1:
                    return {"msgs": [incoming("do task", "task", "first-token")]}
                if self.polls == 2:
                    await prompt.wait()
                    return {"msgs": [incoming("继续", "answer", "answer-token")]}
                await asyncio.Event().wait()

        http = ProtocolClient()
        monkeypatch.setattr(wechat_package.channel, "WechatClient", lambda base: http)
        monkeypatch.setattr(
            wechat_package.channel,
            "WechatAuth",
            lambda *args: SimpleNamespace(load_state=lambda: {"token": "fake-login"}),
        )
        repo = Mock()
        repo.save_context_token.return_value = True
        reply_store = WechatReplyStore(repo)
        reply_store.migrate_legacy = Mock()
        channel = WechatChannel(
            WechatConfig(allow_from=["*"]), MessageQueue(), reply_store=reply_store
        )
        service = wire_wechat_channel(channel, runtime, refs)
        service.hitl_timeout = 2
        try:
            await channel.start()
            await asyncio.wait_for(finished.wait(), 4)
            await asyncio.wait_for(service.drain(), 2)
            assert len(sent) == 2
            assert [m["context_token"] for m in sent] == ["first-token", "answer-token"]
            assert sent[-1]["item_list"][0]["text_item"]["text"] == "hello"
            assert len(provider.calls) == 2
            sid = refs.get(route)
            assert runtime._slots[sid].context.session.turn == 1
            assert not service.is_busy(route)
            assert not runtime._tasks and not runtime._consumers
        finally:
            await channel.stop()
            await runtime.close()
        assert http.closed

    asyncio.run(scenario())


def test_prompt_send_failure_releases_native_wait_without_rerun(tmp_path, monkeypatch):
    """问题发送失败时不等待一个未送达的问题，也不重跑 Agent。"""

    async def scenario():
        async def fail_prompt(message, runtime):
            if message.extra["kind"] == "interaction":
                raise ConnectionError("question delivery failed")

        service, runtime, provider, refs, route, outputs, _, Input = setup_conversation(
            tmp_path, monkeypatch, sender=fail_prompt
        )
        try:
            await service.submit(Input(route, "task"))
            await asyncio.wait_for(service.drain(), 3)
            assert [m.extra["kind"] for m in outputs] == ["interaction", "terminal"]
            assert "ERROR" in outputs[-1].response.content
            assert len(provider.calls) == 1
            assert not service.is_busy(route)
            assert not runtime._tasks and not runtime._consumers
            assert runtime._slots[refs.get(route)].hitl.target is None
        finally:
            await service.close()
            await runtime.close()

    asyncio.run(scenario())


def test_cached_session_rebinds_new_run_without_old_future(tmp_path, monkeypatch):
    """两轮使用同一缓存 Session，人工请求与回调目标不串到上一轮。"""

    async def scenario():
        service, runtime, provider, refs, route, outputs, prompt, Input = setup_conversation(
            tmp_path, monkeypatch
        )
        try:
            await service.submit(Input(route, "first"))
            await asyncio.wait_for(prompt.wait(), 3)
            first_run = service._active[route].run
            first_id = first_run.pending.request_id
            await service.submit(Input(route, "继续"))
            await asyncio.wait_for(service.drain(), 3)
            sid = refs.get(route)
            slot = runtime._slots[sid]
            assert slot.hitl.target is None and first_run.pending is None
            # 测试替身重新从首步工具响应开始，触发下一轮同样的步数上限。
            provider.calls.clear()
            prompt.clear()
            await service.submit(Input(route, "second"))
            await asyncio.wait_for(prompt.wait(), 3)
            second_run = service._active[route].run
            assert second_run is not first_run
            assert second_run.run_id != first_run.run_id
            assert second_run.pending.request_id != first_id
            await service.submit(Input(route, "继续"))
            await asyncio.wait_for(service.drain(), 3)
            assert runtime._slots[sid] is slot
            assert slot.context.session.turn == 2
            assert slot.hitl.target is None and second_run.pending is None
            assert [m.extra["kind"] for m in outputs] == [
                "interaction",
                "terminal",
                "interaction",
                "terminal",
            ]
        finally:
            await service.close()
            await runtime.close()

    asyncio.run(scenario())
