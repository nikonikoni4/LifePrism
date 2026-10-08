"""ConversationClient / RunClient 契约测试（微信 HITL 人工交互与路由发送）。

测试 seam:

- ``ConversationClient(route, send)``：按 route 串行发送；发送前把
  ``extra["wechat_user_id"]`` 固定为 ``route.recipient_id``，调用方无法覆盖。
- ``RunClient(client, operation_id)``：``bind(run_id, session_id)`` 固定本轮归属；
  ``ask_human(HITLMessage)`` 先登记 ``pending`` 再发送提示，随后等待 ``HumanReturn``。
- ``run.answer(text, request_id=None)``：同步摘除 pending 并完成 Future。
- ``run.cancel_pending()``：同步清理并取消未完成 Future。

被测实现（RED 阶段尚未存在）:

- ``lifeprism/llm/conversation/client.py``
- ``lifeprism/llm/conversation/types.py``

设计参考: ``docs/flows/2026-10-08-wechat-conversation-hitl-flow.md``。

测试不依赖数据库与网络：``send`` 全部由测试注入的内存协程替代。
同步一律用 ``asyncio.Event`` 控制；``asyncio.wait_for`` 只作兜底超时，
不使用固定时长的 sleep。
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

pytestmark = pytest.mark.core

# 被测模块缺失时不让 pytest 收集报错，而是让每个测试显式失败（禁止 skip）。
try:
    from myagent.agent.hitl.types import HITLMessage, HumanChoice, HumanReturn

    # 复用现有出站类型：其 extra 注释即 “channel 特定信息（如 wechat_user_id）”。
    from lifeprism.llm.bus.events import OutboundMessage
    from lifeprism.llm.conversation.client import ConversationClient, RunClient
    from lifeprism.llm.conversation.types import ConversationRoute
except ImportError as exc:  # RED 阶段预期分支
    _IMPORT_ERROR: Exception | None = exc
else:
    _IMPORT_ERROR = None


TIMEOUT = 2.0
SESSION_ID = "3f1c0b2a-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def _require_conversation_api():
    """被测模块缺失时让每个测试显式报错，而不是 skip 或静默通过。"""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR


# ==================== 辅助构件 ====================


class _GateSender:
    """可控发送器：记录出站消息，并阻塞在首次发送，直到 ``release`` 被设置。"""

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, message: OutboundMessage) -> None:
        self.sent.append(message)
        self.started.set()
        await self.release.wait()


def _route(recipient: str = "alice") -> ConversationRoute:
    """构造微信路由；transport_id 固定为单实例标识。"""
    return ConversationRoute(channel="wechat", recipient_id=recipient, transport_id="wechat")


def _new_run(send, recipient: str = "alice", operation_id: str = "op1"):
    """装配 client 与已绑定本轮标识的 RunClient。"""
    client = ConversationClient(_route(recipient), send)
    run = RunClient(client, operation_id=operation_id)
    run.bind(run_id="run1", session_id=SESSION_ID)
    return run


def _choices(*options: tuple[str, str]) -> list:
    """把 (choice_name, choice_id) 元组转成 HumanChoice 列表。"""
    return [HumanChoice(choice_name=name, choice_id=cid) for name, cid in options]


def _single_select(*options: tuple[str, str]) -> HITLMessage:
    return HITLMessage(
        human_return_type="single-select",
        content="请选择一个选项",
        choices=_choices(*options),
    )


def _multiple_select(*options: tuple[str, str]) -> HITLMessage:
    return HITLMessage(
        human_return_type="multiple-select",
        content="请选择一个或多个选项",
        choices=_choices(*options),
    )


async def _start_ask(run, sender: _GateSender, question) -> asyncio.Task:
    """启动一次 ask_human，等到提示已进入发送（此时 pending 已登记）。

    Returns:
        仍被 sender 阻塞的 ask 任务。
    """
    task = asyncio.create_task(run.ask_human(question))
    await asyncio.wait_for(sender.started.wait(), TIMEOUT)
    return task


async def _settle(rounds: int = 10) -> None:
    """让出事件循环若干轮，推动已就绪的协程前进（不依赖固定时长）。"""
    for _ in range(rounds):
        await asyncio.sleep(0)


async def _wait_until(predicate, attempts: int = 100) -> None:
    """在有限次让步内等待条件成立；超限直接失败，不使用计时等待。"""
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("条件未在有限次事件循环让步内成立")


async def _abort(run, sender: _GateSender, task: asyncio.Task) -> None:
    """放行并取消仍挂起的 ask，确保测试结束不残留任务。"""
    sender.release.set()
    run.cancel_pending()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, TIMEOUT)


# ==================== 1. 登记先于发送完成 ====================


def test_ask_human_registers_pending_before_send_completes():
    """提示仍阻塞在发送时 pending 已登记，快速回答可先行完成 Future。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        question = _single_select(("继续", "continue"), ("停止", "stop"))

        ask_task = await _start_ask(run, sender, question)

        assert len(sender.sent) == 1
        assert run.pending is not None
        assert run.pending.request_id
        assert run.pending.question is question
        assert not run.pending.answer_future.done()

        assert run.answer("1") is True
        assert run.pending is None

        sender.release.set()
        result = await asyncio.wait_for(ask_task, TIMEOUT)

        assert isinstance(result, HumanReturn)
        assert result.choice_id == "continue"

    asyncio.run(scenario())


# ==================== 2. 单选：接受三种标识，拒绝无效与多值 ====================


def test_single_select_accepts_id_name_and_index():
    """单选接受 choice_id、choice_name 与数字编号三种写法。"""

    async def one_case(answer_text: str) -> str:
        sender = _GateSender()
        run = _new_run(sender)
        question = _single_select(("继续", "continue"), ("停止", "stop"))
        task = await _start_ask(run, sender, question)

        assert run.answer(answer_text) is True
        assert run.pending is None

        sender.release.set()
        result = await asyncio.wait_for(task, TIMEOUT)
        return result.choice_id

    async def scenario():
        assert await one_case("continue") == "continue"  # choice_id
        assert await one_case("继续") == "continue"  # choice_name
        assert await one_case("1") == "continue"  # 数字编号
        assert await one_case("2") == "stop"

    asyncio.run(scenario())


def test_single_select_rejects_invalid_and_multiple_inputs():
    """单选收到未知选项或多个选项时抛 ValueError，且 pending 保持。"""

    async def one_case(answer_text: str) -> None:
        sender = _GateSender()
        run = _new_run(sender)
        question = _single_select(("继续", "continue"), ("停止", "stop"))
        task = await _start_ask(run, sender, question)

        with pytest.raises(ValueError):
            run.answer(answer_text)

        assert run.pending is not None
        assert not run.pending.answer_future.done()
        assert sender.sent  # 已发出提示，未因无效答案重发

        await _abort(run, sender, task)

    async def scenario():
        await one_case("999")  # 不存在的编号
        await one_case("1,2")  # 单选却给了多个值
        await one_case("继续,停止")  # 单选却给了多个选项名
        await one_case("没有这个选项")  # 未知文本

    asyncio.run(scenario())


# ==================== 3. 多选与 message-only ====================


def test_multiple_select_accepts_all_valid_and_dedupes():
    """多选在全部合法时接受，重复值只保留一次。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        question = _multiple_select(("读文件", "read"), ("写文件", "write"), ("删除", "delete"))
        task = await _start_ask(run, sender, question)

        assert run.answer("1,2,1") is True
        assert run.pending is None

        sender.release.set()
        result = await asyncio.wait_for(task, TIMEOUT)

        assert isinstance(result.choice_id, list)
        assert len(result.choice_id) == 2  # 重复值已去重
        assert set(result.choice_id) == {"read", "write"}

    asyncio.run(scenario())


def test_multiple_select_rejects_when_any_invalid():
    """多选中只要有一个非法值，整体拒绝且 pending 保持。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        question = _multiple_select(("读文件", "read"), ("写文件", "write"))
        task = await _start_ask(run, sender, question)

        with pytest.raises(ValueError):
            run.answer("1,9")

        assert run.pending is not None
        assert not run.pending.answer_future.done()

        await _abort(run, sender, task)

    asyncio.run(scenario())


def test_message_only_returns_raw_text():
    """message-only 把用户原文作为 HumanReturn 的 content 返回。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        question = HITLMessage(
            human_return_type="message-only",
            content="请补充说明",
            choices=[],
        )
        task = await _start_ask(run, sender, question)

        assert run.answer("这是我的补充说明") is True
        assert run.pending is None

        sender.release.set()
        result = await asyncio.wait_for(task, TIMEOUT)

        assert isinstance(result, HumanReturn)
        assert result.content == "这是我的补充说明"

    asyncio.run(scenario())


# ==================== 4. 重复 ask 拒绝 ====================


def test_second_ask_is_rejected_without_overwriting_future():
    """同一 run 上重复 ask 被拒绝，原 pending 与 Future 不被覆盖。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        first = _single_select(("继续", "continue"), ("停止", "stop"))
        task = await _start_ask(run, sender, first)
        original = run.pending.answer_future

        with pytest.raises(RuntimeError):
            await run.ask_human(_single_select(("继续", "continue"), ("停止", "stop")))

        assert run.pending is not None
        assert run.pending.answer_future is original
        assert not original.done()
        assert len(sender.sent) == 1  # 第二个问题没有发出

        assert run.answer("1") is True
        sender.release.set()
        result = await asyncio.wait_for(task, TIMEOUT)
        assert result.choice_id == "continue"

    asyncio.run(scenario())


# ==================== 5. 清理路径 ====================


def test_cancelling_ask_clears_pending():
    """取消 ask 任务后 pending 被清理。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        task = await _start_ask(run, sender, _single_select(("继续", "continue"), ("停止", "stop")))
        assert run.pending is not None

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, TIMEOUT)

        assert run.pending is None

    asyncio.run(scenario())


def test_prompt_send_failure_clears_pending():
    """提示发送失败时 ask 抛错并清理 pending，不留下等待中的 Future。"""

    async def scenario():
        async def failing_send(message: OutboundMessage) -> None:
            raise RuntimeError("发送失败")

        run = _new_run(failing_send)
        question = _single_select(("继续", "continue"), ("停止", "stop"))

        with pytest.raises(RuntimeError):
            await asyncio.wait_for(run.ask_human(question), TIMEOUT)

        assert run.pending is None

    asyncio.run(scenario())


def test_cancel_pending_wakes_ask_without_hanging():
    """cancel_pending 清理 pending 并唤醒等待中的 ask，不悬挂。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        task = await _start_ask(run, sender, _single_select(("继续", "continue"), ("停止", "stop")))

        sender.release.set()
        await _settle()  # 让 ask 进入等待 Future
        assert run.pending is not None

        run.cancel_pending()
        assert run.pending is None

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, TIMEOUT)

    asyncio.run(scenario())


# ==================== 6. 过期 request_id ====================


def test_stale_request_id_is_rejected_and_keeps_future():
    """过期 request_id 被拒绝且不唤醒当前 Future；正确 id 才被接受。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        task = await _start_ask(run, sender, _single_select(("继续", "continue"), ("停止", "stop")))
        pending = run.pending
        assert pending is not None

        with pytest.raises(ValueError):
            run.answer("1", request_id="stale-request-id")

        assert run.pending is pending  # 未被摘除
        assert not pending.answer_future.done()  # 当前 Future 未被唤醒

        assert run.answer("1", request_id=pending.request_id) is True

        sender.release.set()
        result = await asyncio.wait_for(task, TIMEOUT)
        assert result.choice_id == "continue"

    asyncio.run(scenario())


# ==================== 7. 发送锁与接收人固定 ====================


def test_concurrent_sends_on_one_client_are_serialized():
    """同一 client 上的并发发送被路由锁串行化。"""

    async def scenario():
        entered: list[str] = []
        release = asyncio.Event()
        concurrent = 0
        peak = 0

        async def send(message: OutboundMessage) -> None:
            nonlocal concurrent, peak
            concurrent += 1
            peak = max(peak, concurrent)
            entered.append(message.id)
            if len(entered) == 1:
                await release.wait()
            concurrent -= 1

        client = ConversationClient(_route("alice"), send)

        first = asyncio.create_task(client.send(OutboundMessage(id="m1")))
        await _wait_until(lambda: len(entered) == 1)

        second = asyncio.create_task(client.send(OutboundMessage(id="m2")))
        await _settle()

        assert entered == ["m1"]  # 第二条被同一路由锁挡住
        assert peak == 1

        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), TIMEOUT)

        assert entered == ["m1", "m2"]
        assert peak == 1

    asyncio.run(scenario())


def test_different_routes_do_not_block_each_other():
    """不同 route 的发送互不阻塞。"""

    async def scenario():
        entered_a: list[str] = []
        release_a = asyncio.Event()

        async def send_a(message: OutboundMessage) -> None:
            entered_a.append(message.id)
            await release_a.wait()

        entered_b: list[str] = []

        async def send_b(message: OutboundMessage) -> None:
            entered_b.append(message.id)

        client_a = ConversationClient(_route("alice"), send_a)
        client_b = ConversationClient(_route("bob"), send_b)

        task_a = asyncio.create_task(client_a.send(OutboundMessage(id="a1")))
        await _wait_until(lambda: entered_a == ["a1"])

        # alice 仍阻塞在发送中，bob 的发送必须立刻完成
        await asyncio.wait_for(client_b.send(OutboundMessage(id="b1")), TIMEOUT)
        assert entered_b == ["b1"]

        release_a.set()
        await asyncio.wait_for(task_a, TIMEOUT)

    asyncio.run(scenario())


def test_send_pins_recipient_over_message_extra():
    """接收人由 route 固定，OutboundMessage.extra 不能覆盖。"""

    async def scenario():
        received: list[OutboundMessage] = []

        async def send(message: OutboundMessage) -> None:
            received.append(message)

        client = ConversationClient(_route("alice"), send)
        await client.send(OutboundMessage(id="m1", extra={"wechat_user_id": "bob"}))

        assert len(received) == 1
        assert received[0].extra["wechat_user_id"] == "alice"

    asyncio.run(scenario())


# ==================== 8. answer 的摘除与幂等 ====================


def test_answer_removes_pending_immediately_and_repeat_returns_false():
    """answer 同步摘除 pending；再次 answer 返回 False。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)
        task = await _start_ask(run, sender, _single_select(("继续", "continue"), ("停止", "stop")))

        assert run.answer("1") is True
        assert run.pending is None  # 同步摘除，不等 Future 被消费

        assert run.answer("1") is False  # 已无 pending

        sender.release.set()
        result = await asyncio.wait_for(task, TIMEOUT)
        assert result.choice_id == "continue"

    asyncio.run(scenario())


def test_answer_without_pending_returns_false():
    """从未发起交互时 answer 返回 False。"""

    async def scenario():
        async def send(message: OutboundMessage) -> None:
            return None

        run = _new_run(send)
        assert run.answer("1") is False

    asyncio.run(scenario())
