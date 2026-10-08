"""HITL 观测日志回归测试（裁决触发与人工等待生命周期）。

背景：微信会话服务接入原生人在回路后，人工等待与错误裁决缺少可追踪的观测点；
同时问题正文、回答正文、自定义选项、接收人与凭据不能进入日志。

目标契约（本次日志增强，只改观测不改业务）：

- ``HITLPolicy.maxstep_continue`` / ``tool_breaker_continue`` 只对真正匹配的
  ``MaxStepsExceededError`` / 工具熔断错记录 INFO（触发原因、timeout/grant_steps、
  返回裁决）；未匹配的错误静默委托给链上下一个订阅方，不得刷屏。
- ``RunClient.ask_human`` 记录 INFO 生命周期：创建待答（session_id/run_id/
  request_id/channel）、提示发送完成、人工返回成功、等待取消、等待结束。
  取消来源多样（外部取消 / 原生等待超时 / 关闭清理），日志不得标成确定超时。
- 提示发送失败记录 ERROR（只含异常类型），异常原样传播，不新增重试或改状态机。
- 任意日志不得出现问题正文、回答正文、自定义 choice 内容、recipient 或凭据。

测试不依赖数据库、网络与真实模型：原生 HITL 用真实实现 + 替身接收人，
发送入口用注入的内存协程替代。
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from myagent.agent.execption import MaxStepsExceededError, ToolConsecutiveFailureError
from myagent.agent.hitl.types import HITLMessage, HumanChoice, HumanReturn
from myagent.infra.events.payload import RequestErrorPayLoad

from lifeprism.llm.bus.events import OutboundMessage
from lifeprism.llm.conversation.client import ConversationClient, RunClient
from lifeprism.llm.conversation.types import ConversationRoute
from lifeprism.llm.runtime.hitl import HITLPolicy

pytestmark = pytest.mark.regression

POLICY_LOGGER = "lifeprism.llm.runtime.hitl"
CLIENT_LOGGER = "lifeprism.llm.conversation.client"

TIMEOUT = 2.0
SESSION_ID = "3f1c0b2a-0000-4000-8000-000000000001"
RUN_ID = "run-logging-1"

# 敏感哨兵：任何一条日志都不允许出现这些字符串。
SECRET_QUESTION = "SECRET-QUESTION-BODY"
SECRET_ANSWER = "SECRET-ANSWER-BODY"
SECRET_CHOICE_NAME = "SECRET-CHOICE-NAME"
SECRET_CHOICE_ID = "SECRET-CHOICE-ID"
SECRET_RECIPIENT = "SECRET-RECIPIENT"
SECRET_ERROR = "SECRET-ERROR-DETAIL"

SENSITIVE = (
    SECRET_QUESTION,
    SECRET_ANSWER,
    SECRET_CHOICE_NAME,
    SECRET_CHOICE_ID,
    SECRET_RECIPIENT,
    SECRET_ERROR,
)


# ==================== 日志读取辅助 ====================


def _records(caplog, name: str) -> list[logging.LogRecord]:
    """取出指定 logger 产生的全部记录。"""
    return [record for record in caplog.records if record.name == name]


def _text(caplog, name: str) -> str:
    """拼接指定 logger 的消息正文。"""
    return "\n".join(record.getMessage() for record in _records(caplog, name))


def _assert_no_sensitive(caplog) -> None:
    """任何 logger 的日志都不得泄露哨兵文本。"""
    text = "\n".join(record.getMessage() for record in caplog.records)
    for secret in SENSITIVE:
        assert secret not in text, f"日志泄露了敏感文本: {secret}"


# ==================== A. HITLPolicy 裁决触发 ====================


class _FakeInteractionClient:
    """替身接收人：记录问题并按预置结果返回、抛错或永久阻塞。"""

    def __init__(
        self,
        result: HumanReturn | None = None,
        *,
        error: Exception | None = None,
        block: bool = False,
    ) -> None:
        self.result = result
        self.error = error
        self.block = block
        self.asked: list[HITLMessage] = []

    def bind(self, *, run_id: str, session_id: str) -> None:
        """满足 InteractionClient 协议；本测试不校验绑定。"""

    async def ask_human(self, message: HITLMessage) -> HumanReturn:
        self.asked.append(message)
        if self.block:
            await asyncio.Event().wait()
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _payload(error) -> RequestErrorPayLoad:
    """构造 REQUEST_ERROR waterfall 的 payload。"""
    return RequestErrorPayLoad(error_type=error)


def _bound_policy(
    client: _FakeInteractionClient, *, timeout: float = 7.0, grant_steps: int = 3
) -> HITLPolicy:
    """装配已绑定本轮接收人与参数的策略。"""
    policy = HITLPolicy()
    policy.bind(client, timeout=timeout, grant_steps=grant_steps)
    return policy


async def _must_not_delegate():
    raise AssertionError("匹配的错误不应委托给链上下一个订阅方")


def test_maxstep_match_logs_trigger_and_continue_verdict(caplog):
    """匹配 MaxStepsExceededError：INFO 记录触发原因、参数与裁决，且不委托。"""
    client = _FakeInteractionClient(HumanReturn(choice_id="continue", content=SECRET_ANSWER))
    policy = _bound_policy(client, timeout=7.0, grant_steps=3)

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(
            policy.maxstep_continue(
                _payload(MaxStepsExceededError(SECRET_ERROR)), _must_not_delegate
            )
        )

    assert verdict == {"decision": "continue", "grant": {"steps": 3}}
    records = _records(caplog, POLICY_LOGGER)
    assert records, "匹配的步数上限必须留下 INFO"
    assert {record.levelno for record in records} == {logging.INFO}
    text = _text(caplog, POLICY_LOGGER)
    assert "MaxStepsExceededError" in text, "缺少触发原因"
    assert "7.0" in text, "缺少原生等待超时"
    assert "3" in text, "缺少授予步数"
    assert "continue" in text, "缺少返回的裁决"
    _assert_no_sensitive(caplog)


def test_maxstep_timeout_logs_break_without_error_body(caplog):
    """人工等待超时：记录 break 裁决与超时值，不打印错误正文。"""
    client = _FakeInteractionClient(block=True)
    policy = _bound_policy(client, timeout=0.05, grant_steps=5)

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(
            policy.maxstep_continue(
                _payload(MaxStepsExceededError(SECRET_ERROR)), _must_not_delegate
            )
        )

    assert verdict == {"decision": "break"}
    text = _text(caplog, POLICY_LOGGER)
    assert "break" in text, "缺少超时后的裁决"
    assert "0.05" in text, "缺少原生等待超时"
    _assert_no_sensitive(caplog)


def test_unmatched_error_delegates_without_logging(caplog):
    """未匹配的错误静默委托：每个错误都会经过回调，记录会刷屏。"""
    client = _FakeInteractionClient(HumanReturn(choice_id="continue", content=""))
    policy = _bound_policy(client)
    delegated: list[bool] = []

    async def next_handler():
        delegated.append(True)
        return {"decision": "break", "as_error": True}

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(
            policy.maxstep_continue(_payload(ValueError(SECRET_ERROR)), next_handler)
        )

    assert verdict == {"decision": "break", "as_error": True}
    assert delegated == [True], "未匹配错误必须委托"
    assert _records(caplog, POLICY_LOGGER) == [], "未匹配错误不得产生日志"
    assert client.asked == [], "未匹配错误不得请求人工"


def test_unbound_policy_delegates_without_logging(caplog):
    """未绑定本轮接收人的后台/本地调用：保持原委托契约，不产生日志。"""
    policy = HITLPolicy()
    delegated: list[bool] = []

    async def next_handler():
        delegated.append(True)
        return None

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(
            policy.maxstep_continue(_payload(MaxStepsExceededError(SECRET_ERROR)), next_handler)
        )

    assert verdict is None
    assert delegated == [True]
    assert _records(caplog, POLICY_LOGGER) == []


def test_tool_breaker_match_logs_trigger_and_verdict(caplog):
    """匹配工具熔断错：INFO 记录触发原因、参数与裁决，且不委托。"""
    client = _FakeInteractionClient(HumanReturn(choice_id="break", content=SECRET_ANSWER))
    policy = _bound_policy(client, timeout=9.0, grant_steps=4)

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(
            policy.tool_breaker_continue(
                _payload(ToolConsecutiveFailureError(SECRET_ERROR)), _must_not_delegate
            )
        )

    assert verdict == {"decision": "break", "as_error": True}
    text = _text(caplog, POLICY_LOGGER)
    assert "ToolConsecutiveFailureError" in text, "缺少触发原因"
    assert "9.0" in text, "缺少原生等待超时"
    assert "break" in text, "缺少返回的裁决"
    _assert_no_sensitive(caplog)


def test_tool_breaker_match_unwraps_exception_group(caplog):
    """TaskGroup 包装的熔断错仍算匹配，日志不打印嵌套错误正文。"""
    client = _FakeInteractionClient(HumanReturn(choice_id="continue", content=""))
    policy = _bound_policy(client, timeout=9.0, grant_steps=4)
    grouped = ExceptionGroup(
        "batch", [ValueError(SECRET_ERROR), ToolConsecutiveFailureError(SECRET_ERROR)]
    )

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(policy.tool_breaker_continue(_payload(grouped), _must_not_delegate))

    assert verdict == {"decision": "continue"}
    assert _records(caplog, POLICY_LOGGER), "包在 ExceptionGroup 里的熔断错必须留痕"
    _assert_no_sensitive(caplog)


def test_tool_breaker_unmatched_group_delegates_without_logging(caplog):
    """只含普通错误的 ExceptionGroup 不算匹配，静默委托。"""
    client = _FakeInteractionClient(HumanReturn(choice_id="continue", content=""))
    policy = _bound_policy(client)
    delegated: list[bool] = []
    grouped = ExceptionGroup("batch", [ValueError(SECRET_ERROR)])

    async def next_handler():
        delegated.append(True)
        return {"decision": "break"}

    with caplog.at_level(logging.INFO):
        verdict = asyncio.run(policy.tool_breaker_continue(_payload(grouped), next_handler))

    assert verdict == {"decision": "break"}
    assert delegated == [True]
    assert _records(caplog, POLICY_LOGGER) == []


# ==================== B. RunClient.ask_human 生命周期 ====================


class _GateSender:
    """可控发送器：记录出站消息，并阻塞在发送，直到 ``release`` 被设置。"""

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, message: OutboundMessage) -> None:
        self.sent.append(message)
        self.started.set()
        await self.release.wait()


def _new_run(send, *, recipient: str = SECRET_RECIPIENT) -> RunClient:
    """装配已绑定本轮标识的 RunClient；接收人使用哨兵值以校验不泄露。"""
    route = ConversationRoute(channel="wechat", recipient_id=recipient)
    run = RunClient(ConversationClient(route, send), operation_id="op-logging")
    run.bind(run_id=RUN_ID, session_id=SESSION_ID)
    return run


def _single_select() -> HITLMessage:
    """自定义 id 的单选问题：选项内容全部是敏感哨兵。"""
    return HITLMessage(
        human_return_type="single-select",
        content=SECRET_QUESTION,
        choices=[HumanChoice(choice_name=SECRET_CHOICE_NAME, choice_id=SECRET_CHOICE_ID)],
    )


async def _settle(rounds: int = 10) -> None:
    """让出事件循环若干轮，推动已就绪的协程前进（不依赖固定时长）。"""
    for _ in range(rounds):
        await asyncio.sleep(0)


def test_ask_human_logs_lifecycle_without_sensitive_text(caplog):
    """正常路径：创建待答 / 发送完成 / 返回成功 / 结束，且不泄露正文与接收人。"""
    captured: dict[str, str] = {}

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)

        with caplog.at_level(logging.INFO):
            task = asyncio.create_task(run.ask_human(_single_select()))
            await asyncio.wait_for(sender.started.wait(), TIMEOUT)
            assert run.pending is not None
            captured["request_id"] = run.pending.request_id
            assert run.answer("1") is True
            sender.release.set()
            result = await asyncio.wait_for(task, TIMEOUT)

        assert result.choice_id == SECRET_CHOICE_ID
        return run

    asyncio.run(scenario())

    records = _records(caplog, CLIENT_LOGGER)
    assert records, "人工等待必须留下 INFO 生命周期"
    assert {record.levelno for record in records} == {logging.INFO}
    text = _text(caplog, CLIENT_LOGGER)
    assert SESSION_ID in text, "缺少 session_id"
    assert RUN_ID in text, "缺少 run_id"
    assert captured["request_id"] in text, "缺少 request_id"
    assert "wechat" in text, "缺少 channel"
    assert "发送完成" in text, "缺少提示发送完成"
    assert "返回成功" in text, "缺少人工返回成功"
    assert "结束" in text, "缺少 finally 结束标记"
    _assert_no_sensitive(caplog)


def test_ask_human_cancel_logs_cancel_not_timeout(caplog):
    """取消路径：记录取消但不标成确定超时（取消来源多样）。"""

    async def scenario():
        sender = _GateSender()
        run = _new_run(sender)

        with caplog.at_level(logging.INFO):
            task = asyncio.create_task(run.ask_human(_single_select()))
            await asyncio.wait_for(sender.started.wait(), TIMEOUT)
            sender.release.set()
            await _settle()
            run.cancel_pending()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, TIMEOUT)

        assert run.pending is None

    asyncio.run(scenario())

    text = _text(caplog, CLIENT_LOGGER)
    assert "取消" in text, "缺少等待取消记录"
    assert "超时" not in text, "取消来源多样，不得标成确定超时"
    assert "结束" in text, "缺少 finally 结束标记"
    _assert_no_sensitive(caplog)


def test_ask_human_send_failure_logs_error_type_and_propagates(caplog):
    """发送失败：ERROR 只含异常类型，异常原样传播，不进入等待也不重试。"""

    async def scenario():
        async def failing_send(message: OutboundMessage) -> None:
            raise RuntimeError(SECRET_ERROR)

        run = _new_run(failing_send)

        with caplog.at_level(logging.INFO):
            with pytest.raises(RuntimeError):
                await asyncio.wait_for(run.ask_human(_single_select()), TIMEOUT)

        assert run.pending is None, "发送失败必须清理 pending"

    asyncio.run(scenario())

    errors = [
        record for record in _records(caplog, CLIENT_LOGGER) if record.levelno == logging.ERROR
    ]
    assert len(errors) == 1, "发送失败必须留下且只留下一条 ERROR"
    assert "RuntimeError" in errors[0].getMessage(), "ERROR 缺少异常类型"
    text = _text(caplog, CLIENT_LOGGER)
    assert "发送完成" not in text, "发送失败不得记发送完成"
    assert "返回成功" not in text, "发送失败不得记人工返回"
    _assert_no_sensitive(caplog)


def test_ask_human_hides_message_only_and_custom_choice_content(caplog):
    """message-only 正文与自定义 choice 内容不入日志，只记录返回类型。"""

    async def one_case(question: HITLMessage, answer_text: str) -> HumanReturn:
        sender = _GateSender()
        run = _new_run(sender)

        with caplog.at_level(logging.INFO):
            task = asyncio.create_task(run.ask_human(question))
            await asyncio.wait_for(sender.started.wait(), TIMEOUT)
            assert run.answer(answer_text) is True
            sender.release.set()
            return await asyncio.wait_for(task, TIMEOUT)

    async def scenario():
        message_only = HITLMessage(
            human_return_type="message-only", content=SECRET_QUESTION, choices=[]
        )
        result = await one_case(message_only, SECRET_ANSWER)
        assert result.content == SECRET_ANSWER

        custom = _single_select()
        assert (await one_case(custom, "1")).choice_id == SECRET_CHOICE_ID

    asyncio.run(scenario())

    text = _text(caplog, CLIENT_LOGGER)
    assert "message-only" in text, "应记录返回类型"
    assert "single-select" in text, "应记录返回类型"
    _assert_no_sensitive(caplog)


def test_ask_human_logs_continue_and_break_choice_ids(caplog):
    """可枚举的 continue / break 选项可记录，便于追踪原生裁决来源。"""

    async def one_case(answer_text: str) -> str:
        sender = _GateSender()
        run = _new_run(sender)
        question = HITLMessage(
            human_return_type="single-select",
            content=SECRET_QUESTION,
            choices=[HumanChoice("继续", "continue"), HumanChoice("停止", "break")],
        )

        with caplog.at_level(logging.INFO):
            task = asyncio.create_task(run.ask_human(question))
            await asyncio.wait_for(sender.started.wait(), TIMEOUT)
            assert run.answer(answer_text) is True
            sender.release.set()
            result = await asyncio.wait_for(task, TIMEOUT)
        return result.choice_id

    async def scenario():
        assert await one_case("1") == "continue"
        assert await one_case("2") == "break"

    asyncio.run(scenario())

    text = _text(caplog, CLIENT_LOGGER)
    assert "continue" in text, "缺少 continue 裁决"
    assert "break" in text, "缺少 break 裁决"
    _assert_no_sensitive(caplog)
