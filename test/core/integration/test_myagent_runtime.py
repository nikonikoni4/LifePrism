"""使用真实 myagent 循环与确定性模型响应的迁移契约测试。"""

import asyncio
import contextlib

import pytest
from myagent.agent.core.provider import ChatParams, LLMResponse, RawToolCall, StreamChunk, Usage
from myagent.agent.core.tool.tool import Tool, ToolResult

from lifeprism.llm.bus import InboundMessage, MessageQueue, MessageType
from lifeprism.llm.runtime import AgentRuntime
from lifeprism.llm.runtime.worker import AgentBusWorker
from lifeprism.llm.runtime_tools.base import normalize_tool_result

pytestmark = pytest.mark.core


class EchoTool(Tool):
    """最简 Tool 测试替身，回显文本，并对哨兵输入返回失败。"""

    name = "echo"
    description = "Echo the supplied text"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    @normalize_tool_result
    async def execute(self, text: str):
        """对哨兵输入 ``fail`` 返回 native 错误结果，其余输入原样回显。"""
        return "Error: rejected" if text == "fail" else text


class FakeClient:
    """确定性的流式 provider 测试替身，提供脚本化轮次与多种失败模式。"""

    model = "fake"
    params = ChatParams()

    def __init__(self, with_tool=False, fail=False, block=False):
        """初始化脚本化的 client。

        Args:
            with_tool: 为 True 时，首轮在最终回答前先发一次工具调用。
            fail: 为 True 时，每次流式调用都抛出 provider 错误。
            block: 为 True 时，流式调用阻塞直到被取消，用于模拟卡住的模型。
        """
        self.with_tool = with_tool
        self.fail = fail
        self.block = block
        self.calls = []
        self.cancelled = False

    async def stream_chat(self, messages, tools=None):
        """按脚本产出分块；当 client 被设为失败时改为抛错。"""
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("provider failed")
        if self.block:
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True
        if self.with_tool and len(self.calls) == 1:
            yield LLMResponse(
                content="checking",
                tool_call_requests=[
                    RawToolCall(
                        id="call-1",
                        name="echo",
                        arguments='{"text":"hello"}',
                    )
                ],
                usage=Usage(2, 3, 5),
            )
        else:
            yield StreamChunk(content="hel")
            await asyncio.sleep(0)
            yield StreamChunk(content="lo")
            yield LLMResponse(content="hello", usage=Usage(4, 5, 9))


def make_runtime(tmp_path, client, usage=None):
    """构建一个绑定到指定 client 与内存写入器的 AgentRuntime。

    Args:
        tmp_path: 作为 runtime 数据路径的临时目录。
        client: client 工厂返回的流式 provider 测试替身。
        usage: 可选列表；提供时会记录每次 usage 写入。

    Returns:
        AgentRuntime: 用于确定性离线运行的 runtime 实例。
    """

    async def write_usage(sid, values, mode):
        """测试需要采集时，把一次 usage 写入记录到共享列表。"""
        if usage is not None:
            usage.append((sid, values, mode))

    async def skip_log(*args):
        """丢弃日志写入，避免测试触碰文件系统。"""
        pass

    return AgentRuntime(
        data_path=tmp_path,
        session_folder=tmp_path / "sessions",
        client_factory=lambda: client,
        tools_factory=lambda kind: [EchoTool()],
        usage_writer=write_usage,
        log_writer=skip_log,
    )


def test_tool_turn_waits_for_final_message_and_accounts_all_steps(tmp_path):
    """守护一次工具轮次产出分块、工具事件、最终回答以及一次 usage 写入。"""

    async def scenario():
        """在 `asyncio.run` 下驱动工具轮次的 runtime 场景。"""
        usage = []
        client = FakeClient(with_tool=True)
        runtime = make_runtime(tmp_path, client, usage)
        try:
            events = [
                event
                async for event in runtime.stream(
                    InboundMessage(type=MessageType.CHAT, content="test")
                )
            ]
            assert [e.text for e in events if e.type == "content"] == ["hel", "lo"]
            assert any(e.type == "tool/call" for e in events)
            assert any(e.type == "tool/result" for e in events)
            assert events[-1].type == "done"
            assert events[-1].result.response.content == "hello"
            assert events[-1].result.response.usage["total_tokens"] == 14
            assert len({e.run_id for e in events}) == 1
            assert len(usage) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_session_serializes_runs_and_refreshes_prompt_files(tmp_path):
    """守护同一 session 上的并发运行被串行化，且每轮重新加载 prompt 文件。"""

    async def scenario():
        """在 `asyncio.run` 下驱动同 session 并发场景。"""
        prompt_file = tmp_path / "agent/chat/soul.md"
        prompt_file.parent.mkdir(parents=True)
        prompt_file.write_text("first prompt", encoding="utf-8")
        client = FakeClient()
        runtime = make_runtime(tmp_path, client)
        try:
            first = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
            sid = first.session_id
            prompt_file.write_text("second prompt", encoding="utf-8")
            results = await asyncio.gather(
                *[
                    runtime.execute(
                        InboundMessage(type=MessageType.CHAT, content=str(i), session_id=sid)
                    )
                    for i in range(2)
                ]
            )
            assert all(result.session_id == sid for result in results)
            assert "first prompt" in client.calls[0][0].content
            assert all("second prompt" in call[0].content for call in client.calls[1:])
            assert runtime._slots[sid].context.session.turn == 3
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_provider_failure_emits_error_without_success(tmp_path):
    """守护 provider 失败时只透出 error 事件，绝不产生 done 事件。"""

    async def scenario():
        """在 `asyncio.run` 下驱动 provider 失败场景。"""
        runtime = make_runtime(tmp_path, FakeClient(fail=True))
        try:
            events = [
                e async for e in runtime.stream(InboundMessage(type=MessageType.CHAT, content="x"))
            ]
            assert events[-1].type == "error"
            assert "provider failed" in events[-1].text
            assert not any(e.type == "done" for e in events)
            assert next(e for e in events if e.type == "turn/end").data["reason_type"] == "error"
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_abandoned_stream_cancels_turn_and_persists_terminal(tmp_path):
    """守护关闭流会取消当前轮次，并落盘一条 interrupted 终止记录。"""

    async def scenario():
        """在 `asyncio.run` 下驱动流被中途放弃的场景。"""
        client = FakeClient(block=True)
        runtime = make_runtime(tmp_path, client)
        events = runtime.stream(InboundMessage(type=MessageType.CHAT, content="x"))
        first = await anext(events)
        while not client.calls:
            await asyncio.sleep(0)
        await events.aclose()
        assert client.cancelled
        records = runtime._slots[first.session_id].context.session.record_list
        assert records[-1].type == "turn/end"
        assert records[-1].data.reason_type == "interrupted"
        assert not runtime._tasks
        await runtime.close()

    asyncio.run(scenario())


def test_background_bus_returns_result_and_releases_context(tmp_path):
    """守护后台 bus 任务返回结果并释放 session 槽位。"""

    async def scenario():
        """在 `asyncio.run` 下驱动后台任务成功的场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        bus = MessageQueue()
        worker = AgentBusWorker(bus, runtime)
        task = asyncio.create_task(worker.loop())
        try:
            response = await asyncio.wait_for(
                bus.send(InboundMessage(type=MessageType.GENERAL_TASK, content="job")), 3
            )
            assert response.response.content == "hello"
            assert not runtime._slots
            assert not bus._pending
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_background_failure_rejects_waiter_immediately(tmp_path):
    """守护后台任务失败会立即拒绝等待方，而不是一直挂起。"""

    async def scenario():
        """在 `asyncio.run` 下驱动后台任务失败场景。"""
        runtime = make_runtime(tmp_path, FakeClient(fail=True))
        bus = MessageQueue()
        worker = AgentBusWorker(bus, runtime)
        task = asyncio.create_task(worker.loop())
        try:
            with pytest.raises(RuntimeError, match="provider failed"):
                await asyncio.wait_for(
                    bus.send(InboundMessage(type=MessageType.GENERAL_TASK, content="job")), 3
                )
            assert not bus._pending
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_old_session_is_not_loaded(tmp_path):
    """守护早于迁移切点的 session id 会被拒绝，而不是被恢复。"""

    async def scenario():
        """在 `asyncio.run` 下驱动过期 session 场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        with pytest.raises(ValueError, match="P4"):
            await runtime.execute(
                InboundMessage(type=MessageType.CHAT, content="x", session_id="session_20261002")
            )
        await runtime.close()

    asyncio.run(scenario())


def test_tool_failure_uses_native_result_and_default_breaker():
    """守护工具失败保持 native 结果形态与默认熔断设置。"""

    async def scenario():
        """在 `asyncio.run` 下驱动工具熔断默认值场景。"""
        tool = EchoTool()
        result = await tool.execute("fail")
        assert isinstance(result, ToolResult) and result.is_error
        assert tool.max_consecutive_failures is None
        assert tool.breaker_mode == "schema_hide"
        assert tool.raise_on_break is False

    asyncio.run(scenario())


def test_runtime_shutdown_cancels_live_subscriber_without_deadlock(tmp_path):
    """守护 runtime 关闭会取消存活的订阅者且不发生死锁。"""

    async def scenario():
        """在 `asyncio.run` 下驱动 runtime 关闭场景。"""
        client = FakeClient(block=True)
        runtime = make_runtime(tmp_path, client)

        async def consume():
            """为关闭场景收集 runtime 流中的全部事件。"""
            return [
                e async for e in runtime.stream(InboundMessage(type=MessageType.CHAT, content="x"))
            ]

        consumer = asyncio.create_task(consume())
        while not client.calls:
            await asyncio.sleep(0)
        await asyncio.wait_for(runtime.close(), 3)
        assert consumer.cancelled()
        assert client.cancelled
        assert not runtime._slots
        assert not runtime._tasks

    asyncio.run(scenario())


def test_bus_caller_cancellation_stops_background_model(tmp_path):
    """守护取消 bus 调用方会一并取消后台模型轮次。"""

    async def scenario():
        """在 `asyncio.run` 下驱动调用方取消场景。"""
        client = FakeClient(block=True)
        runtime = make_runtime(tmp_path, client)
        bus = MessageQueue()
        worker = AgentBusWorker(bus, runtime)
        task = asyncio.create_task(worker.loop())
        caller = asyncio.create_task(
            bus.send(InboundMessage(type=MessageType.GENERAL_TASK, content="job"))
        )
        try:
            while not client.calls:
                await asyncio.sleep(0)
            caller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await caller
            for _ in range(100):
                if not worker._active_tasks:
                    break
                await asyncio.sleep(0.01)
            assert client.cancelled
            assert not worker._active_tasks
            assert not bus._pending
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_worker_can_restart_after_shutdown(tmp_path):
    """守护 worker 循环在生命周期被取消后仍能重新启动。"""

    async def scenario():
        """在 `asyncio.run` 下驱动 worker 重启场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        bus = MessageQueue()
        worker = AgentBusWorker(bus, runtime)
        for _ in range(2):
            task = asyncio.create_task(worker.loop())
            try:
                result = await asyncio.wait_for(
                    bus.send(InboundMessage(type=MessageType.GENERAL_TASK, content="restart")), 3
                )
                assert result.response.content == "hello"
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    asyncio.run(scenario())


def test_setup_failure_releases_new_context(tmp_path):
    """守护工具构建失败时会释放刚创建的 session 槽位。"""

    async def scenario():
        """在 `asyncio.run` 下驱动工具构建失败场景。"""
        runtime = make_runtime(tmp_path, FakeClient())

        def broken_tools(kind):
            """抛出异常，模拟在构建阶段失败的工具工厂。"""
            raise RuntimeError("tool setup failed")

        runtime._tools_factory = broken_tools
        try:
            with pytest.raises(RuntimeError, match="tool setup failed"):
                await runtime.execute(InboundMessage(type=MessageType.GENERAL_TASK, content="job"))
            assert not runtime._slots
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_chat_logging_uses_native_prompt_and_does_not_duplicate_background(tmp_path, monkeypatch):
    """守护 chat 轮次用 native prompt 只记录一次日志，而后台任务不记录。"""

    async def scenario():
        """在 `asyncio.run` 下驱动 chat 日志场景。"""
        from lifeprism.llm.utils.llm_call_logger import llm_call_logger

        logged = []
        monkeypatch.setattr(llm_call_logger, "log_call", lambda **kwargs: logged.append(kwargs))
        runtime = make_runtime(tmp_path, FakeClient(with_tool=True))
        runtime._log_writer = runtime._log_chat
        try:
            result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="log me"))
            assert len(logged) == 1
            assert logged[0]["inbound_msg"].session_id == result.session_id
            assert logged[0]["outbound_msg"].response.usage["total_tokens"] == 14
            assert logged[0]["system_prompt"]
            assert logged[0]["model"] == "fake"
            await runtime.execute(InboundMessage(type=MessageType.GENERAL_TASK, content="job"))
            assert len(logged) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("always_fail", [False, True])
def test_request_error_policy_drives_native_loop_retries(tmp_path, always_fail, monkeypatch):
    from lifeprism.llm.providers.errors import LLMProviderError

    class TransientClient(FakeClient):
        attempts = 0

        async def stream_chat(self, messages, tools=None):
            self.attempts += 1
            if always_fail or self.attempts == 1:
                raise LLMProviderError(
                    "network failed",
                    kind="connection",
                    reason="connection",
                    provider="fake",
                    model="fake",
                )
            yield LLMResponse(content="recovered", usage=Usage())

    async def scenario():
        client = TransientClient()
        runtime = make_runtime(tmp_path, client)
        # Remove wall-clock waits while keeping the actual native policy/loop path.
        from lifeprism.config.agent_config import AgentSettings
        from lifeprism.config.settings_manager import SettingsManager

        config = AgentSettings.model_validate({"policies": {"llm_retry": {"base_delay": 0.0}}})
        monkeypatch.setattr(SettingsManager, "agent", property(lambda self: config))
        try:
            events = [
                event
                async for event in runtime.stream(
                    InboundMessage(type=MessageType.CHAT, content="hi")
                )
            ]
            assert client.attempts == (4 if always_fail else 2)
            assert events[-1].type == ("error" if always_fail else "done")
            slot = next(iter(runtime._slots.values()))
            assert slot.context.session.llm_retry_count(slot.context.session.turn) == (
                3 if always_fail else 1
            )
        finally:
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("retry_enabled", [False, True])
def test_context_loads_agent_settings_and_guard(tmp_path, monkeypatch, retry_enabled):
    from lifeprism.config.agent_config import AgentSettings
    from lifeprism.config.settings_manager import SettingsManager
    from lifeprism.llm.providers.errors import LLMProviderError

    config = AgentSettings.model_validate(
        {
            "step_limit": 8,
            "max_retry_count": 1,
            "policies": {
                "llm_retry": {"enabled": retry_enabled, "base_delay": 0.0},
                "tool_guard": {"enabled": False, "allow_paths": ["user"]},
            },
        }
    )
    monkeypatch.setattr(SettingsManager, "agent", property(lambda self: config))

    class Client(FakeClient):
        attempts = 0

        async def stream_chat(self, messages, tools=None):
            self.attempts += 1
            raise LLMProviderError(
                "failure", kind="connection", reason="connection", provider="fake", model="fake"
            )
            yield

    async def scenario():
        client = Client()
        runtime = make_runtime(tmp_path, client)
        try:
            events = [
                event
                async for event in runtime.stream(
                    InboundMessage(type=MessageType.CHAT, content="hi")
                )
            ]
            slot = next(iter(runtime._slots.values()))
            assert slot.context.agent_loop.agent_config.step_limit == 8
            assert slot.context.agent_loop.agent_config.max_retry_count == 1
            from lifeprism.llm.guard import ToolUseGuard
            from lifeprism.llm.providers.llm_retry import LLMRetry

            guards = [obj for obj in slot.context.policy_objects if isinstance(obj, ToolUseGuard)]
            assert len(guards) == 1
            assert guards[0].allow_path == [(tmp_path / "user").resolve()]
            from types import SimpleNamespace

            from myagent.infra.events.eventspec import TOOL_CALL

            vetoes = await slot.context.event_service.waterfall(
                TOOL_CALL.name,
                SimpleNamespace(
                    tool_call_requests=[
                        SimpleNamespace(
                            id="outside",
                            name="read_file",
                            arguments={"file_path": str(tmp_path / "outside.txt")},
                        )
                    ]
                ),
            )
            assert vetoes["outside"]["decision"] == "deny"
            assert (
                any(isinstance(obj, LLMRetry) for obj in slot.context.policy_objects)
                == retry_enabled
            )
            assert client.attempts == (2 if retry_enabled else 1)
            assert events[-1].type == "error"
        finally:
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "created_channel,resumed_channel", [("local", "wechat"), ("wechat", "local")]
)
def test_chat_sessions_use_unified_directory_and_resume_across_channels(
    tmp_path, created_channel, resumed_channel
):
    """聊天统一落盘 chat/<session_id>.jsonl，关闭 Runtime 后可从另一渠道恢复。"""

    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        first = await runtime.execute(
            InboundMessage(type=MessageType.CHAT, channel=created_channel)
        )
        await runtime.close()
        target = tmp_path / "sessions" / "chat" / f"{first.session_id}.jsonl"
        assert target.is_file()
        resumed = make_runtime(tmp_path, FakeClient())
        try:
            result = await resumed.execute(
                InboundMessage(
                    type=MessageType.CHAT,
                    channel=resumed_channel,
                    session_id=first.session_id,
                )
            )
            assert result.session_id == first.session_id
            assert resumed._slots[first.session_id].context.session.turn == 2
        finally:
            await resumed.close()

    asyncio.run(scenario())


def test_workflow_storage_is_independent_of_tools_and_token_type(tmp_path):
    """同一工作流不同消息用途共享目录，其他工作流无法恢复其会话。"""

    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            first = await runtime.execute(
                InboundMessage(
                    type=MessageType.GENERAL_TASK,
                    workflow_id="daily-memory",
                    token_type="dream_task",
                )
            )
            assert (
                tmp_path / "sessions" / "workflows" / "daily-memory" / f"{first.session_id}.jsonl"
            ).is_file()
            await runtime.execute(
                InboundMessage(
                    type=MessageType.DREAM_TASK,
                    workflow_id="daily-memory",
                    session_id=first.session_id,
                )
            )
            with pytest.raises(ValueError, match="不存在"):
                await runtime.execute(
                    InboundMessage(
                        type=MessageType.GENERAL_TASK,
                        workflow_id="other",
                        session_id=first.session_id,
                    )
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_cached_session_allows_channel_switch_but_not_workflow_owner(tmp_path):
    """常驻聊天缓存可在同一 slot 内跨渠道继续，但不能改换工作流归属。"""

    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            first = await runtime.execute(InboundMessage(type=MessageType.CHAT, channel="local"))
            same = await runtime.execute(
                InboundMessage(
                    type=MessageType.CHAT,
                    channel="wechat",
                    session_id=first.session_id,
                )
            )
            assert same.session_id == first.session_id
            with pytest.raises(ValueError, match="归属"):
                await runtime.execute(
                    InboundMessage(
                        type=MessageType.CHAT,
                        session_id=first.session_id,
                        workflow_id="daily-memory",
                    )
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "workflow_id", ["", "../escape", "a/b", "a\\b", "C:escape", "CON", "abc.", "a b", 123]
)
def test_invalid_workflow_id_is_rejected(workflow_id):
    """工作流 ID 必须是跨平台安全的目录标识。"""
    with pytest.raises(ValueError, match="workflow_id"):
        InboundMessage(type=MessageType.GENERAL_TASK, workflow_id=workflow_id)


def test_unassigned_background_session_uses_tasks_directory(tmp_path):
    """兼容无归属的后台调用，不按工具用途或用量类型猜测目录。"""

    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            result = await runtime.execute(
                InboundMessage(
                    type=MessageType.GENERAL_TASK,
                    token_type="dream_task",
                )
            )
            assert (tmp_path / "sessions" / "tasks" / f"{result.session_id}.jsonl").is_file()
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_storage_directory_cannot_escape_root_via_symlink(tmp_path):
    """目录中的符号链接不能把会话写到存储根目录之外。"""
    from lifeprism.llm.runtime.session_storage import resolve_session_folder

    root = tmp_path / "sessions"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    try:
        (root / "workflows").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 用户没有创建符号链接权限")
    with pytest.raises(ValueError, match="逃出"):
        resolve_session_folder(
            root, InboundMessage(type=MessageType.GENERAL_TASK, workflow_id="test")
        )


def test_default_session_root_is_directly_under_data_path(tmp_path):
    """默认根目录不重复嵌套 localData，数据根迁移不参与文件定位。"""

    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        runtime._session_folder = None
        try:
            first = await runtime.execute(InboundMessage(type=MessageType.CHAT))
            assert runtime.chat_session_folder == tmp_path / "session" / "chat"
        finally:
            await runtime.close()
        assert (tmp_path / "session" / "chat" / f"{first.session_id}.jsonl").is_file()
        assert not (tmp_path / "myagent_sessions").exists()
        resumed = make_runtime(tmp_path / "new-data-root", FakeClient())
        resumed._session_folder = tmp_path / "session"
        try:
            result = await resumed.execute(
                InboundMessage(type=MessageType.CHAT, session_id=first.session_id)
            )
            assert result.session_id == first.session_id
        finally:
            await resumed.close()

    asyncio.run(scenario())


def test_workflow_chat_reports_storage_owner_without_changing_usage(tmp_path):
    """有聊天工具的工作流仍按 workflow_id 存储，统计类型保持独立。"""

    async def scenario():
        usage = []
        runtime = make_runtime(tmp_path, FakeClient(), usage)
        try:
            events = [
                event
                async for event in runtime.stream(
                    InboundMessage(
                        type=MessageType.CHAT,
                        workflow_id="assistant-workflow",
                        token_type="custom-usage",
                    )
                )
            ]
            head = events[0]
            assert head.data["workflow_id"] == "assistant-workflow"
            assert head.data["session_category"] == "workflow"
            assert head.data["channel"] == "local"
            assert (
                tmp_path
                / "sessions"
                / "workflows"
                / "assistant-workflow"
                / f"{head.session_id}.jsonl"
            ).is_file()
            assert usage[0][2] == "custom-usage"
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_storage_directory_cannot_alias_another_workflow(tmp_path):
    """根目录内的符号链接也不能让两个工作流共享存储归属。"""
    from lifeprism.llm.runtime.session_storage import resolve_session_folder

    root = tmp_path / "sessions"
    target = root / "workflows" / "owner-a"
    target.mkdir(parents=True)
    try:
        (root / "workflows" / "owner-b").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 用户没有创建符号链接权限")
    with pytest.raises(ValueError, match="归属"):
        resolve_session_folder(
            root, InboundMessage(type=MessageType.GENERAL_TASK, workflow_id="owner-b")
        )


def test_missing_wechat_session_gives_new_command(tmp_path):
    """旧引用无法恢复时，微信得到可执行的新会话指引。"""
    from uuid import uuid4

    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            with pytest.raises(ValueError, match="/new"):
                await runtime.execute(
                    InboundMessage(
                        type=MessageType.CHAT,
                        channel="wechat",
                        session_id=str(uuid4()),
                    )
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())
