"""渠道之外的输入路由、后台执行拥有权与统一输出。"""

import asyncio
import contextlib
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lifeprism.llm.bus import InboundMessage, MessageType, OutboundMessage
from lifeprism.llm.conversation.client import ConversationClient, RunClient, Sender
from lifeprism.llm.conversation.references import SessionReferences
from lifeprism.llm.conversation.types import ConversationInput, ConversationRoute
from lifeprism.llm.providers import LLMResponse
from lifeprism.utils import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from lifeprism.llm.runtime import AgentRuntime


@dataclass
class _Operation:
    operation_id: str
    source_input_id: str
    run: RunClient | None = None
    task: asyncio.Task | None = None


class ConversationService:
    """提交输入及时返回；原消费任务始终拥有最终输出和资源清理。"""

    def __init__(
        self,
        runtime: "AgentRuntime",
        references: SessionReferences,
        sender: Sender,
        *,
        allow_input: Callable[[ConversationRoute], bool] | None = None,
        hitl_timeout: float = 60,
        hitl_grant_steps: int = 5,
    ) -> None:
        from lifeprism.llm.conversation.commands import SessionCommandService

        if hitl_timeout <= 0 or hitl_grant_steps < 1:
            raise ValueError("人工等待超时和额外步数必须为正数")
        self.runtime = runtime
        self.references = references
        self.commands = SessionCommandService(runtime.chat_sessions, references)
        self._sender = sender
        self._allow_input = allow_input or (lambda route: True)
        self.hitl_timeout = hitl_timeout
        self.hitl_grant_steps = hitl_grant_steps
        self._clients: dict[ConversationRoute, ConversationClient] = {}
        self._active: dict[ConversationRoute, _Operation] = {}
        self._tasks: set[asyncio.Task] = set()
        self._seen: OrderedDict[tuple[ConversationRoute, str], None] = OrderedDict()
        self._closing = False

    def start(self) -> None:
        """完成关闭后重开接入，避免复用旧 Future 和发送锁。"""
        if self._tasks or self._active:
            if self._closing:
                raise RuntimeError("会话服务尚未完成关闭")
            return
        self._closing = False

    def can_receive(self, route: ConversationRoute) -> bool:
        """检查准入；拒绝时取消该路由旧任务，禁止旧归属继续执行。

        transport 在媒体下载前检查，submit 在实际准入前再检查，覆盖期间的归属变化。
        """
        allowed = not self._closing and self._allow_input(route)
        if not allowed:
            operation = self._active.get(route)
            if operation is not None and operation.task is not None:
                operation.task.cancel()
        return allowed

    def is_busy(self, route: ConversationRoute) -> bool:
        """准备、执行、人工等待、终态发送及命令管理均视为忙。"""
        return route in self._active

    def _client(self, route: ConversationRoute) -> ConversationClient:
        if route not in self._clients:
            self._clients[route] = ConversationClient(route, self._sender)
        return self._clients[route]

    def _spawn(self, coroutine: Coroutine, *, name: str) -> asyncio.Task:
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("会话后台任务失败: task=%s error=%s", task.get_name(), task.exception())

    def _notice(self, route: ConversationRoute, text: str) -> None:
        self._spawn(
            self._client(route).send(
                OutboundMessage(response=LLMResponse(content=text), extra={"kind": "notice"})
            ),
            name="conversation-notice",
        )

    async def submit(self, incoming: ConversationInput) -> str | None:
        """原子路由/预留后及时返回；不等待网络、命令或 Agent 结果。

        Returns:
            新操作 ID；交互答案、重复或被拒输入返回 None。
        """
        route = incoming.route
        if not self.can_receive(route):
            return None
        key = (route, incoming.input_id)
        operation = self._active.get(route)
        if key in self._seen or (
            operation is not None and operation.source_input_id == incoming.input_id
        ):
            return None
        self._seen[key] = None
        if len(self._seen) > 4096:
            self._seen.popitem(last=False)
        if operation is not None and operation.run is not None:
            run = operation.run
            if run.pending is not None:
                try:
                    run.answer(incoming.text, incoming.request_id)
                except ValueError as exc:
                    self._notice(route, str(exc))
                return None
        if incoming.request_id is not None:
            self._notice(route, "这个选择请求已经结束。")
            return None
        is_command = self.commands.matches(incoming.text)
        if operation is not None:
            if is_command and self.commands.is_readonly(incoming.text):
                # 独立跟踪的只读操作，不能替换或清理原 Agent 操作。
                extra_operation = _Operation(uuid4().hex, incoming.input_id)
                self._spawn(
                    self._command(incoming, extra_operation, is_running=True),
                    name=f"conversation-command-{extra_operation.operation_id}",
                )
            else:
                text = (
                    "[ERROR] 当前任务正在执行，请稍候；不能切换会话。"
                    if is_command
                    else "[ERROR] 当前任务正在执行，请等待完成后再发送消息。"
                )
                self._notice(route, text)
            return None
        # 这里没有 await；两条首次输入不能同时通过空闲检查。
        operation = _Operation(uuid4().hex, incoming.input_id)
        self._active[route] = operation
        if is_command:
            coroutine = self._command(incoming, operation, is_running=False)
        else:
            operation.run = RunClient(self._client(route), operation.operation_id)
            coroutine = self._run(incoming, operation)
        operation.task = self._spawn(coroutine, name=f"conversation-{operation.operation_id}")
        operation.task.add_done_callback(lambda _: self._operation_done(route, operation))
        return operation.operation_id

    def _operation_done(self, route: ConversationRoute, operation: _Operation) -> None:
        """任务首次调度前就被取消时，协程 finally 不运行，由拥有者兜底。"""
        if operation.run is not None:
            operation.run.close()
        self._release(route, operation)

    def _release(self, route: ConversationRoute, operation: _Operation) -> None:
        if self._active.get(route) is operation:
            self._active.pop(route)

    async def _command(
        self, incoming: ConversationInput, operation: _Operation, *, is_running: bool
    ) -> None:
        try:
            reply = await self.commands.handle(incoming.text, incoming.route, is_running=is_running)
            if reply is not None and not self._closing:
                await self._client(incoming.route).send(
                    replace(
                        reply,
                        id=incoming.input_id,
                        extra={
                            **(reply.extra or {}),
                            "kind": "command",
                            "operation_id": operation.operation_id,
                        },
                    )
                )
        finally:
            self._release(incoming.route, operation)

    async def _run(self, incoming: ConversationInput, operation: _Operation) -> None:
        run = operation.run
        terminal = None
        terminal_attempted = False
        try:
            try:
                sid = self.references.get(incoming.route) or None
                if sid:
                    try:
                        UUID(sid)
                    except ValueError:
                        sid = None  # 旧业务 Session 不自动迁移。
                message = InboundMessage(
                    type=MessageType.CHAT,
                    id=incoming.input_id,
                    channel=incoming.route.channel,
                    content=incoming.content,
                    session_id=sid,
                    extra=dict(incoming.extra),
                )
                async with contextlib.aclosing(
                    self.runtime.stream(
                        message,
                        interaction_client=run,
                        hitl_timeout=self.hitl_timeout,
                        hitl_grant_steps=self.hitl_grant_steps,
                    )
                ) as events:
                    async for event in events:
                        if event.type == "session":
                            self.references.set(incoming.route, event.session_id)
                        elif event.type in {"done", "error"} and terminal is None:
                            terminal = event
                # 必须在流关闭之后输出，Runtime 的 finally 此时已结算并释放锁。
                if terminal is None:
                    raise RuntimeError("Agent 没有产生本轮终态")
            except Exception as exc:
                logger.exception("会话执行失败: operation=%s", operation.operation_id)
                if not self._closing:
                    terminal_attempted = True
                    await run.send_text(f"[ERROR] 处理消息时出错: {exc}", kind="terminal")
                return
            if self._closing:
                return
            terminal_attempted = True
            if terminal.type == "done":
                await run.client.send(
                    replace(
                        terminal.result,
                        extra={
                            **(terminal.result.extra or {}),
                            "kind": "terminal",
                            "operation_id": run.operation_id,
                            "run_id": run.run_id,
                        },
                    )
                )
            else:
                if terminal.data.get("reason_type") == "interrupted":
                    text = "[CANCELLED] 当前任务已取消。"
                else:
                    text = f"[ERROR] 处理消息时出错: {terminal.text}"
                await run.send_text(text, kind="terminal")
        except Exception:
            # 发送异常只记日志：不能重跑 Agent 或再发送另一份终态。
            logger.exception(
                "会话输出失败: operation=%s terminal_attempted=%s",
                operation.operation_id,
                terminal_attempted,
            )
        finally:
            run.close()
            self._release(incoming.route, operation)

    async def drain(self) -> None:
        """等待当前自有工作结束；用于优雅等待，不阻止新输入解决交互。"""
        while self._tasks:
            tasks = tuple(self._tasks)
            await asyncio.gather(*tasks, return_exceptions=True)
            # gather 对全已完成任务可能立即返回，不能依赖尚未调度的 done callback。
            self._tasks.difference_update(task for task in tasks if task.done())

    async def close(self) -> None:
        """拒绝新输入，取消并等待自有任务，再清空路由与旧 Future。"""
        self._closing = True
        operations = tuple(self._active.values())
        for operation in operations:
            if operation.run is not None:
                operation.run.close()
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._active.clear()
        self._clients.clear()
        self._seen.clear()
