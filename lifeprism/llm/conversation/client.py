"""统一发送入口与原生 HITLChannel 的运行级实现。"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from uuid import uuid4

from myagent.agent.hitl.types import HITLMessage, HumanReturn

from lifeprism.llm.bus import ChannelType, OutboundMessage
from lifeprism.llm.conversation.types import ConversationRoute
from lifeprism.llm.providers import LLMResponse
from lifeprism.utils import get_logger

logger = get_logger(__name__)

Sender = Callable[[OutboundMessage], Awaitable[None]]


class ConversationClient:
    """同一路由的所有业务输出共用一个短期发送锁。"""

    def __init__(self, route: ConversationRoute, send: Sender):
        self.route = route
        self._sender = send
        self._send_lock = asyncio.Lock()

    async def send(self, message: OutboundMessage) -> None:
        """固定接收人，串行发送；人工等待不占用此锁。"""
        extra = dict(message.extra or {})
        extra.update(
            channel=self.route.channel,
            transport_id=self.route.transport_id,
            recipient_id=self.route.recipient_id,
        )
        if self.route.channel == ChannelType.WECHAT:
            extra["wechat_user_id"] = self.route.recipient_id
        async with self._send_lock:
            await self._sender(replace(message, extra=extra))


@dataclass
class PendingInteraction:
    """单次待答请求；Future 属于原执行，输入处理只负责完成它。"""

    request_id: str
    question: HITLMessage
    answer_future: asyncio.Future[HumanReturn]


# 原生 HITL 的枚举裁决；其余选项内容不写入日志。
_SAFE_CHOICE_IDS = frozenset({"continue", "break"})


def _choice_tag(result: HumanReturn) -> str:
    """只暴露可枚举的 continue/break，其余仅暴露类型，避免泄露自定义选项内容。"""
    choice_id = result.choice_id
    if isinstance(choice_id, str) and choice_id in _SAFE_CHOICE_IDS:
        return choice_id
    return f"<{type(choice_id).__name__}>"


class RunClient:
    """本轮不可变归属及人工等待，不复用上一轮的 Future。"""

    def __init__(self, client: ConversationClient, operation_id: str):
        self.client = client
        self.operation_id = operation_id
        self.run_id: str | None = None
        self.session_id: str | None = None
        self.pending: PendingInteraction | None = None
        self._closed = False

    def bind(self, *, run_id: str, session_id: str) -> None:
        """由 Runtime 在启动 turn 之前建立本轮关联。"""
        if self._closed or (self.run_id is not None and self.run_id != run_id):
            raise RuntimeError("交互客户端不能绑定到另一轮运行")
        self.run_id, self.session_id = run_id, session_id

    async def send_text(self, text: str, *, kind: str, request_id: str | None = None) -> None:
        """人工提示、普通提示和终态均经会话 client 发送。"""
        await self.client.send(
            OutboundMessage(
                response=LLMResponse(content=text),
                session_id=self.session_id,
                extra={
                    "kind": kind,
                    "operation_id": self.operation_id,
                    "run_id": self.run_id,
                    "request_id": request_id,
                },
            )
        )

    async def ask_human(self, message: HITLMessage) -> HumanReturn:
        """先登记 Future，再发送问题，随后在原 turn 中等待决定。"""
        if self._closed or self.run_id is None or self.session_id is None:
            raise RuntimeError("交互客户端尚未绑定或已经结束")
        if self.pending is not None:
            raise RuntimeError("当前运行已有待答请求")
        pending = PendingInteraction(
            uuid4().hex, message, asyncio.get_running_loop().create_future()
        )
        self.pending = pending
        logger.info(
            "人工待答创建: session_id=%s, run_id=%s, request_id=%s, channel=%s",
            self.session_id,
            self.run_id,
            pending.request_id,
            self.client.route.channel,
        )
        lines = [f"[需要你的选择] {message.content}"]
        for index, choice in enumerate(message.choices, 1):
            description = f"：{choice.description}" if choice.description else ""
            lines.append(f"{index}. {choice.choice_name}{description}")
        if message.choices:
            lines.append("请回复选项编号或名称。")
        try:
            try:
                await self.send_text(
                    "\n".join(lines), kind="interaction", request_id=pending.request_id
                )
            except Exception as exc:
                # 异常原样传播；只记类型，不落问题正文与回复凭据。
                logger.error(
                    "人工提示发送失败: session_id=%s, run_id=%s, request_id=%s, error_type=%s",
                    self.session_id,
                    self.run_id,
                    pending.request_id,
                    type(exc).__name__,
                )
                raise
            logger.info("人工提示发送完成: request_id=%s", pending.request_id)
            result = await pending.answer_future
            logger.info(
                "人工返回成功: request_id=%s, return_type=%s, choice=%s",
                pending.request_id,
                message.human_return_type,
                _choice_tag(result),
            )
            return result
        finally:
            # 快速回答可能已摘除 pending；旧 finally 不清理后来的问题。
            if self.pending is pending:
                self.pending = None
            if not pending.answer_future.done():
                pending.answer_future.cancel()
            if pending.answer_future.cancelled():
                # 取消来源多样（外部取消、原生等待超时、关闭清理），不能标成确定超时。
                logger.info(
                    "人工等待取消: session_id=%s, run_id=%s, request_id=%s",
                    self.session_id,
                    self.run_id,
                    pending.request_id,
                )
            logger.info("人工等待结束: request_id=%s", pending.request_id)

    def answer(self, text: str, request_id: str | None = None) -> bool:
        """同步完成当前 Future；无效或过期选择保持原等待不变。"""
        pending = self.pending
        if pending is None:
            return False
        if request_id is not None and request_id != pending.request_id:
            raise ValueError("这个选择请求已经失效，请回答当前问题。")
        if pending.answer_future.done():
            if self.pending is pending:
                self.pending = None
            raise ValueError("这个选择请求已经结束。")
        result = self._parse_answer(text, pending.question)
        self.pending = None
        pending.answer_future.set_result(result)
        return True

    @staticmethod
    def _parse_answer(text: str, question: HITLMessage) -> HumanReturn:
        """将显示名称、原生 ID 或编号转换成原生 HumanReturn。"""
        if question.human_return_type == "message-only":
            return HumanReturn(choice_id="", content=text)
        tokens = [part for part in re.split(r"[,，\s]+", text.strip()) if part]
        if not tokens or (question.human_return_type == "single-select" and len(tokens) != 1):
            raise ValueError("请选择有效选项。")
        ids = []
        for token in tokens:
            choice = next(
                (c for c in question.choices if token in (c.choice_id, c.choice_name)), None
            )
            if choice is None and token.isdigit() and 1 <= int(token) <= len(question.choices):
                choice = question.choices[int(token) - 1]
            if choice is None:
                raise ValueError("请选择有效选项。")
            if choice.choice_id not in ids:
                ids.append(choice.choice_id)
        value = ids if question.human_return_type == "multiple-select" else ids[0]
        return HumanReturn(choice_id=value, content=text)

    def cancel_pending(self) -> None:
        """清理本轮未解决请求，不阻塞读取循环。"""
        pending, self.pending = self.pending, None
        if pending is not None and not pending.answer_future.done():
            pending.answer_future.cancel()

    def close(self) -> None:
        """本轮结束后禁止产生新的待答请求。"""
        self._closed = True
        self.cancel_pending()
