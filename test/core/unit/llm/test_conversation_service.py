"""ConversationService 会话路由契约测试。

测试 seam（真实实现，不使用替身）:

- ``ConversationService.submit``：同一短原子段内完成准入检查与操作预留；
  交互答案、重复 input_id 与被拒输入返回 ``None``，不启动第二个 user turn。
- ``ConversationService.can_receive`` / ``is_busy``：准入与忙状态查询。
- ``ConversationService.close`` / ``start``：关闭清理与重开接入。
- 真实 ``RunClient``：pending 登记、request_id 校验与答案唤醒。

替身只有两个：``ScriptedRuntime`` 提供可控的 ``stream`` async generator 与
``chat_sessions``；``Recorder`` 作为 ``sender`` 记录出站消息。二者都不触碰
网络、数据库与真实 myagent 内核。

同步一律用 ``asyncio.Event`` 与 ``asyncio.Condition`` 控制；``asyncio.wait_for``
只作兜底超时，不使用固定时长的 sleep 猜测时序。

设计参考: ``docs/flows/2026-10-08-wechat-conversation-hitl-flow.md``（链路 3/4
与「并发边界与不变量」）。

"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from myagent.agent.hitl.types import HITLMessage, HumanChoice, HumanReturn

from lifeprism.llm.bus import OutboundMessage
from lifeprism.llm.conversation.service import ConversationService
from lifeprism.llm.conversation.types import ConversationInput, ConversationRoute
from lifeprism.llm.providers import LLMResponse
from lifeprism.llm.runtime.service import RuntimeEvent

pytestmark = pytest.mark.core

TIMEOUT = 2.0
SESSION_ID = "3f1c0b2a-0000-4000-8000-000000000001"
RUN_ID = "run-1"
ANSWER = "hello"


def _route(recipient: str = "alice") -> ConversationRoute:
    """构造微信路由；transport_id 固定为单实例标识。"""
    return ConversationRoute(channel="wechat", recipient_id=recipient, transport_id="wechat")


def _single_select(*options: tuple[str, str]) -> HITLMessage:
    """把 (choice_name, choice_id) 元组转成单选 HITLMessage。"""
    return HITLMessage(
        human_return_type="single-select",
        content="请选择一个选项",
        choices=[HumanChoice(choice_name=name, choice_id=cid) for name, cid in options],
    )


# ==================== 替身 ====================


class MemoryReferences:
    """会话引用存储替身；不触碰生产账号状态。"""

    def __init__(self) -> None:
        self.values: dict[ConversationRoute, str] = {}

    def get(self, route: ConversationRoute) -> str | None:
        return self.values.get(route)

    def set(self, route: ConversationRoute, session_id: str) -> None:
        self.values[route] = session_id


class FailingReferences(MemoryReferences):
    """写入必定失败的引用存储替身，用于验证错误路径。"""

    def set(self, route: ConversationRoute, session_id: str) -> None:
        raise RuntimeError("引用写入失败")


class FakeChatSessions:
    """``agent_runtime.chat_sessions`` 的最小替身，覆盖命令服务用到的四个方法。"""

    def __init__(self, session_id: str = SESSION_ID) -> None:
        self.session_id = session_id
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.list_calls: list[dict[str, Any]] = []

    async def list_sessions(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return {
            "total": 1,
            "items": [
                {
                    "id": self.session_id,
                    "name": "会话一",
                    "is_running": True,
                    "preview": "你好",
                }
            ],
        }

    async def get_history(self, session_id: str) -> dict[str, Any] | None:
        return None

    async def create(self) -> dict[str, Any]:
        self.created.append(self.session_id)
        return {"session_id": self.session_id}

    async def delete(self, session_id: str) -> bool:
        self.deleted.append(session_id)
        return True


class ScriptedRuntime:
    """可控假 Runtime：只实现 ConversationService 依赖的两个 seam。

    ``stream`` 是显式脚本化的 async generator：先产出 ``session`` 事件，再按需
    触发人工等待，最后停在 ``release`` 上，直到测试放行才产出 ``done``。
    ``closed`` 按流的创建顺序记录其是否已被关闭，供错误路径验证「先关流再输出」。
    """

    def __init__(self, session_id: str = SESSION_ID) -> None:
        self.session_id = session_id
        self.chat_sessions = FakeChatSessions(session_id)
        self.calls: list[Any] = []
        self.closed: list[bool] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.ask: HITLMessage | None = None
        self._calls_condition = asyncio.Condition()

    def stream(
        self,
        message: Any,
        *,
        interaction_client: Any = None,
        hitl_timeout: float = 60,
        hitl_grant_steps: int = 5,
    ):
        """返回本轮的事件流；签名与 ``AgentRuntime.stream`` 对齐。"""
        return self._events(message, interaction_client)

    async def _events(self, message: Any, interaction_client: Any):
        index = len(self.closed)
        self.closed.append(False)
        async with self._calls_condition:
            self.calls.append(message)
            self._calls_condition.notify_all()
        self.started.set()
        try:
            yield RuntimeEvent(
                type="session",
                run_id=RUN_ID,
                session_id=self.session_id,
                data={"is_new": True},
            )
            if interaction_client is not None:
                interaction_client.bind(run_id=RUN_ID, session_id=self.session_id)
                if self.ask is not None:
                    await interaction_client.ask_human(self.ask)
            await self.release.wait()
            yield RuntimeEvent(
                type="done",
                run_id=RUN_ID,
                session_id=self.session_id,
                result=OutboundMessage(
                    id=message.id,
                    response=LLMResponse(content=ANSWER),
                    session_id=self.session_id,
                ),
            )
        finally:
            self.closed[index] = True

    async def wait_calls(self, count: int) -> None:
        """确定性等待至少 ``count`` 个 user turn 已进入 stream。"""
        async with self._calls_condition:
            await self._calls_condition.wait_for(lambda: len(self.calls) >= count)


class Recorder:
    """发送替身：记录出站消息，并快照发送时刻各流的关闭状态。"""

    def __init__(self, runtime: ScriptedRuntime) -> None:
        self.runtime = runtime
        self.messages: list[OutboundMessage] = []
        self.stream_closed_at_send: list[tuple[bool, ...]] = []
        self._condition = asyncio.Condition()

    async def __call__(self, message: OutboundMessage) -> None:
        snapshot = tuple(self.runtime.closed)
        async with self._condition:
            self.messages.append(message)
            self.stream_closed_at_send.append(snapshot)
            self._condition.notify_all()

    def kinds(self) -> list[str | None]:
        return [(message.extra or {}).get("kind") for message in self.messages]

    def of_kind(self, kind: str) -> list[OutboundMessage]:
        return [message for message in self.messages if (message.extra or {}).get("kind") == kind]

    def index_of(self, kind: str, count: int = 1) -> int:
        matches = [
            index
            for index, message in enumerate(self.messages)
            if (message.extra or {}).get("kind") == kind
        ]
        return matches[count - 1]

    async def wait_kind(self, kind: str, count: int = 1) -> None:
        async with self._condition:
            await self._condition.wait_for(lambda: len(self.of_kind(kind)) >= count)


def build(*, allow_input=None, references=None, session_id: str = SESSION_ID):
    """装配真实 ConversationService 与两个替身。"""
    runtime = ScriptedRuntime(session_id)
    recorder = Recorder(runtime)
    refs = references if references is not None else MemoryReferences()
    service = ConversationService(runtime, refs, recorder, allow_input=allow_input)
    return service, runtime, refs, recorder


async def _finish(service: ConversationService, runtime: ScriptedRuntime) -> None:
    """放行终态、等待后台任务并关闭服务，避免遗留未回收任务。"""
    runtime.release.set()
    await service.drain()
    await service.close()


# ==================== 用例 ====================


def test_concurrent_first_submits_on_same_route_start_single_user_turn():
    """同一 route 的两条并发首次提交只允许一条成为 user turn。"""

    async def scenario():
        service, runtime, _, recorder = build()
        route = _route()
        try:
            first, second = await asyncio.gather(
                service.submit(ConversationInput(route, "第一条", input_id="i1")),
                service.submit(ConversationInput(route, "第二条", input_id="i2")),
            )
            assert [first, second].count(None) == 1
            assert service.is_busy(route)
            await asyncio.wait_for(recorder.wait_kind("notice"), TIMEOUT)
            assert "正在执行" in recorder.of_kind("notice")[0].response.content
            runtime.release.set()
            await service.drain()
            assert len(runtime.calls) == 1
            assert runtime.calls[0].id in {"i1", "i2"}
            assert service._active == {}
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_distinct_routes_run_independently():
    """不同 route 各自运行，互不占用对方的 busy 状态。"""

    async def scenario():
        service, runtime, refs, recorder = build()
        alice, bob = _route("alice"), _route("bob")
        try:
            first = await service.submit(ConversationInput(alice, "a", input_id="a1"))
            second = await service.submit(ConversationInput(bob, "b", input_id="b1"))
            assert first and second
            assert service.is_busy(alice) and service.is_busy(bob)
            runtime.release.set()
            await service.drain()
            assert {call.id for call in runtime.calls} == {"a1", "b1"}
            assert recorder.kinds() == ["terminal", "terminal"]
            assert not service.is_busy(alice) and not service.is_busy(bob)
            assert refs.get(alice) == SESSION_ID and refs.get(bob) == SESSION_ID
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_replayed_input_id_never_starts_second_turn_or_output():
    """重复 input_id 在执行中与结束后都不再次裁决、启动或输出。"""

    async def scenario():
        service, runtime, _, recorder = build()
        route = _route()
        try:
            assert (
                await service.submit(ConversationInput(route, "任务", input_id="dup")) is not None
            )
            assert await service.submit(ConversationInput(route, "任务", input_id="dup")) is None
            assert recorder.messages == []
            runtime.release.set()
            await service.drain()
            assert recorder.kinds() == ["terminal"]

            assert await service.submit(ConversationInput(route, "任务", input_id="dup")) is None
            await service.drain()
            assert len(runtime.calls) == 1
            assert recorder.kinds() == ["terminal"]
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_running_route_allows_readonly_session_list_without_stealing_operation():
    """执行中的 /session-list 作为独立只读操作输出，不替换也不清理原任务。"""

    async def scenario():
        service, runtime, _, recorder = build()
        route = _route()
        try:
            operation_id = await service.submit(ConversationInput(route, "任务", input_id="t1"))
            await asyncio.wait_for(runtime.started.wait(), TIMEOUT)
            original = service._active[route]
            assert original.operation_id == operation_id

            assert (
                await service.submit(ConversationInput(route, "/session-list", input_id="c1"))
                is None
            )
            await asyncio.wait_for(recorder.wait_kind("command"), TIMEOUT)

            reply = recorder.of_kind("command")[0]
            assert reply.response.content.startswith("[SUCCESS] 聊天会话")
            assert reply.extra["operation_id"] != original.operation_id
            assert service._active[route] is original
            assert service.is_busy(route)
            assert len(runtime.calls) == 1
            assert runtime.chat_sessions.list_calls == [
                {"page": 1, "page_size": 10, "include_preview": True}
            ]

            runtime.release.set()
            await service.drain()
            assert recorder.kinds() == ["command", "terminal"]
            assert not service.is_busy(route)
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


@pytest.mark.parametrize("command", ["/new", f"/continue {SESSION_ID}"])
def test_running_route_rejects_session_switch(command):
    """执行中拒绝 /new 与 /continue，保留原运行绑定与会话引用。"""

    async def scenario():
        service, runtime, refs, recorder = build()
        route = _route()
        try:
            operation_id = await service.submit(ConversationInput(route, "任务", input_id="t1"))
            await asyncio.wait_for(runtime.started.wait(), TIMEOUT)
            current = refs.get(route)
            assert current == SESSION_ID

            assert await service.submit(ConversationInput(route, command, input_id="c1")) is None
            await asyncio.wait_for(recorder.wait_kind("notice"), TIMEOUT)
            assert "不能切换会话" in recorder.of_kind("notice")[0].response.content

            assert service._active[route].operation_id == operation_id
            assert refs.get(route) == current
            assert runtime.chat_sessions.created == []
            assert len(runtime.calls) == 1
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_invalid_and_expired_request_id_keep_pending_and_start_no_turn():
    """无效与已结束的 request_id 只提示，不唤醒 pending，也不启动新任务。"""

    async def scenario():
        service, runtime, _, recorder = build()
        route = _route()
        runtime.ask = _single_select(("继续", "go"), ("取消", "stop"))
        try:
            await service.submit(ConversationInput(route, "任务", input_id="t1"))
            await asyncio.wait_for(recorder.wait_kind("interaction"), TIMEOUT)
            request_id = recorder.of_kind("interaction")[0].extra["request_id"]
            run = service._active[route].run
            pending = run.pending
            assert pending is not None and pending.request_id == request_id

            # 无效 request_id：保留原 pending，只提示重输
            assert (
                await service.submit(
                    ConversationInput(route, "go", input_id="a1", request_id="stale")
                )
                is None
            )
            await asyncio.wait_for(recorder.wait_kind("notice"), TIMEOUT)
            assert "失效" in recorder.of_kind("notice")[0].response.content
            assert run.pending is pending
            assert not pending.answer_future.done()

            # 有效答案完成旧 Future
            assert (
                await service.submit(
                    ConversationInput(route, "go", input_id="a2", request_id=request_id)
                )
                is None
            )
            assert pending.answer_future.result() == HumanReturn(choice_id="go", content="go")

            # 已结束的 request_id：仍只提示，不启动新任务
            assert (
                await service.submit(
                    ConversationInput(route, "go", input_id="a3", request_id=request_id)
                )
                is None
            )
            await asyncio.wait_for(recorder.wait_kind("notice", 2), TIMEOUT)
            assert "已经结束" in recorder.of_kind("notice")[1].response.content
            assert len(runtime.calls) == 1

            runtime.release.set()
            await service.drain()
            assert recorder.kinds() == ["interaction", "notice", "notice", "terminal"]
            assert not service.is_busy(route)
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_valid_answer_only_resumes_existing_run():
    """有效答案只完成原 run 的 Future，不新建操作、不启动第二个 user turn。"""

    async def scenario():
        service, runtime, _, recorder = build()
        route = _route()
        runtime.ask = _single_select(("继续", "go"))
        try:
            operation_id = await service.submit(ConversationInput(route, "任务", input_id="t1"))
            await asyncio.wait_for(recorder.wait_kind("interaction"), TIMEOUT)
            request_id = recorder.of_kind("interaction")[0].extra["request_id"]
            operation = service._active[route]
            assert operation.operation_id == operation_id

            assert (
                await service.submit(
                    ConversationInput(route, "go", input_id="answer", request_id=request_id)
                )
                is None
            )
            assert service._active[route] is operation
            assert service.is_busy(route)
            assert len(runtime.calls) == 1
            assert runtime.calls[0].id == "t1"

            runtime.release.set()
            await service.drain()
            assert recorder.kinds() == ["interaction", "terminal"]
            assert recorder.of_kind("terminal")[0].response.content == ANSWER
            assert not service.is_busy(route)
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_reference_write_failure_closes_stream_then_emits_single_error():
    """引用写入失败先关闭事件流，再输出且只输出一份错误终态。"""

    async def scenario():
        service, runtime, refs, recorder = build(references=FailingReferences())
        route = _route()
        try:
            assert await service.submit(ConversationInput(route, "任务", input_id="t1")) is not None
            await service.drain()

            terminal = recorder.of_kind("terminal")
            assert len(terminal) == 1
            assert terminal[0].response.content.startswith("[ERROR] 处理消息时出错")
            assert "引用写入失败" in terminal[0].response.content
            assert runtime.closed == [True]
            assert recorder.stream_closed_at_send[recorder.index_of("terminal")] == (True,)
            assert refs.get(route) is None
            assert not service.is_busy(route)
        finally:
            await _finish(service, runtime)

    asyncio.run(scenario())


def test_close_before_first_schedule_clears_state_and_allows_restart():
    """任务首次调度前关闭服务即完成清理，随后可以重开接入。"""

    async def scenario():
        service, runtime, _, recorder = build()
        route = _route()
        try:
            assert await service.submit(ConversationInput(route, "任务", input_id="t1")) is not None
            assert service.is_busy(route)
            assert runtime.calls == []  # 任务尚未第一次调度

            await service.close()
            assert not service.is_busy(route)
            assert service._active == {}
            assert service._tasks == set()
            assert runtime.calls == []
            assert runtime.closed == []

            service.start()  # 清理完成后重开不应抛错
            assert not service.is_busy(route)

            assert await service.submit(ConversationInput(route, "任务", input_id="t2")) is not None
            await asyncio.wait_for(runtime.started.wait(), TIMEOUT)
            runtime.release.set()
            await service.drain()
            assert recorder.kinds() == ["terminal"]
            assert recorder.of_kind("terminal")[0].response.content == ANSWER
        finally:
            await service.close()

    asyncio.run(scenario())


def test_can_receive_cancel_before_first_schedule_releases_route():
    """准入拒绝取消未调度任务后，route 必须回到空闲。

    任务从未被调度时 ``_run`` 的 ``finally`` 不会执行，拥有者的 done 回调
    仍须释放 active operation，防止 ``is_busy`` 永久为真。
    """

    async def scenario():
        allowed = {"value": True}
        service, runtime, _, recorder = build(allow_input=lambda route: allowed["value"])
        route = _route()
        try:
            assert await service.submit(ConversationInput(route, "任务", input_id="t1")) is not None
            assert service.is_busy(route)
            assert runtime.calls == []  # 任务尚未第一次调度

            allowed["value"] = False
            assert service.can_receive(route) is False
            await asyncio.gather(*tuple(service._tasks), return_exceptions=True)

            assert not service.is_busy(route), "取消未调度任务后 route 仍被占用"
        finally:
            await service.close()

    asyncio.run(scenario())
