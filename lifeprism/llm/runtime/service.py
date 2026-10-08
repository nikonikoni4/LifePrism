"""以会话级隔离的事件订阅运行 myagent，同时服务聊天与后台任务。"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from myagent.agent.agent_context import AgentContext, AgentPolicySpec
from myagent.agent.core.agent.types import AgentConfig
from myagent.agent.core.provider import Message
from myagent.agent.core.session import SessionStore
from myagent.infra.events.eventspec import REQUEST_ERROR, SESSION_EVENT, TOOL_CALL

from lifeprism.config import settings
from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage
from lifeprism.llm.guard import ToolUseGuard
from lifeprism.llm.providers import LLMResponse, create_llm_client
from lifeprism.llm.providers.llm_retry import LLMRetry
from lifeprism.llm.runtime.limiter import ModelCallLimiter
from lifeprism.llm.runtime.prompts import register_prompts
from lifeprism.llm.runtime.provider import ProviderAdapter
from lifeprism.llm.runtime.session_storage import resolve_session_category, resolve_session_folder
from lifeprism.utils import LazySingleton, get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from lifeprism.llm.runtime.chat_sessions import ChatSessionManager


@dataclass
class RuntimeEvent:
    """对外事件信封；业务调用方不依赖 myagent 的载荷类型。

    Attributes:
        type: 事件种类——``session`` 为会话头；分块类事件如 ``content``/
            ``reasoning``、``tool/call``、``tool/result``；``done``/``error``
            为终止事件。
        run_id: 同一次执行的每个事件共享的标识，用于区分同一会话上的并发运行。
        session_id: 本轮所属的 native myagent 会话。
        turn: 会话内的轮次编号，仅当来源记录携带该字段时存在。
        step: 轮次内的步骤编号，仅当来源记录携带该字段时存在。
        seq: 单调递增的记录序号，仅当来源记录携带该字段时存在。
        text: 内容/思维链事件的分块文本，或 ``error`` 事件上的失败原因。
        data: myagent 为工具事件与终止事件序列化出的记录载荷。
        result: 最终 ``OutboundMessage``，仅在 ``done`` 事件上填充。
    """

    type: str
    run_id: str
    session_id: str
    turn: int | None = None
    step: int | None = None
    seq: int | None = None
    text: str = ""
    data: dict = field(default_factory=dict)
    result: OutboundMessage | None = None


class _AgentSlot:
    """跨轮次保活的会话级执行状态。

    每个 native myagent 会话对应一个 slot。它持有该会话的 context 与 provider
    client，通过 ``lock`` 串行化并发轮次，并把内核的会话记录事件桥接到当前流正在
    消费的 ``queue`` 上。
    """

    def __init__(self, context: AgentContext, client, session_folder: Path):
        """绑定执行 context 并订阅其会话记录。

        Args:
            context: 持有会话与 agent loop 的 native myagent context。
            client: 本会话所有模型调用共用的 provider adapter。
            session_folder: 已验证的会话存储归属目录。
        """
        self.context = context
        self.client = client
        self.session_folder = session_folder
        self.lock = asyncio.Lock()
        self.queue: asyncio.Queue | None = None
        self.run_id = ""
        self.usage: dict[str, int] = {}
        self.response = LLMResponse(content="")
        self.terminal = None
        self.header = None
        context.event_service.register(SESSION_EVENT.name, self.on_record)

    def on_record(self, payload) -> None:
        """把一条 native 会话记录转换为 ``RuntimeEvent``。

        在 ``__init__`` 中注册到 ``SESSION_EVENT``。没有流在运行（``queue`` 为
        ``None``）时到达的记录会被丢弃。会话头、assistant 与 turn-end 记录还会
        同时记在 slot 上，使队列排空后仍能取到 system prompt、模型名、token 用量
        与失败原因。
        """
        if self.queue is None:
            return
        record = payload.session_record
        data = record.data
        event = RuntimeEvent(
            type=record.type,
            run_id=self.run_id,
            session_id=self.context.session.meta_data.session_id,
            turn=record.turn,
            step=record.step,
            seq=record.seq,
        )
        if record.type == "request/header":
            self.header = data
        elif record.type == "assistant/chunk":
            event.type = data.type or "chunk"
            event.text = data.texts or ""
        elif record.type == "assistant/message":
            message = data.message
            self.response.content = message.content
            self.response.reasoning_content = message.reasoning_content
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                self.usage[key] = self.usage.get(key, 0) + getattr(data.usage, key)
        elif record.type in ("tool/call", "tool/result"):
            event.data = data.to_record_dict()
        elif record.type == "turn/end":
            self.terminal = data
            event.data = data.to_record_dict()
        self.queue.put_nowait(event)


class AgentRuntime:
    """负责执行 context、会话级串行化与运行生命周期。

    对外入口是 :meth:`stream`（聊天 SSE）与 :meth:`execute`（后台任务）。两者都
    汇入同一条订阅事件路径，因此 token 统计与调用日志行为一致。聊天会话常驻
    ``_slots`` 以保留多轮历史，后台任务则在轮次结束后立即释放 context。
    :meth:`close` 会先取消所有在途轮次，再关闭各 context。
    """

    def __init__(
        self,
        data_path: Path | None = None,
        session_folder: Path | None = None,
        client_factory: Callable | None = None,
        tools_factory: Callable | None = None,
        usage_writer: Callable | None = None,
        log_writer: Callable | None = None,
    ):
        """配置运行期依赖。

        所有协作者均可注入，使测试无需网络即可运行真实内核。

        Args:
            data_path: LifePrism 数据根目录；省略时回退到
                ``settings.lifeprism_data_path``。
            session_folder: 业务会话的存储根目录，其下按工作流或聊天分目录；省略时回退到
                ``<data_path>/session``。
            client_factory: 零参数工厂，为每个新会话返回一个 provider。传
                ``None`` 时创建生产 LLM client 并用 :class:`ProviderAdapter`
                包装。
            tools_factory: 接收消息类型并返回该轮工具列表的可调用对象；默认使用
                ``lifeprism.llm.runtime_tools.build_tools``。
            usage_writer: 形如 ``(session_id, usage, mode)`` 的可 await 写入端，
                用于 token 统计；默认使用 :meth:`_save_usage`。
            log_writer: 形如 ``(message, result, header)`` 的可 await 写入端，
                用于聊天调用日志；默认使用 :meth:`_log_chat`。
        """
        self._data_path = data_path
        self._session_folder = session_folder
        self._client_factory = client_factory
        self._tools_factory = tools_factory
        self._usage_writer = usage_writer or self._save_usage
        self._log_writer = log_writer or self._log_chat
        self._slots: dict[str, _AgentSlot] = {}
        self._tasks: set[asyncio.Task] = set()
        self._consumers: set[asyncio.Task] = set()
        self._limiter = ModelCallLimiter()
        self._closing = False
        self._active_sessions: dict[str, int] = {}
        self._managed_sessions: set[str] = set()

    @property
    def chat_sessions(self) -> "ChatSessionManager":
        """返回仅管理 chat 目录的会话接口。"""
        from lifeprism.llm.runtime.chat_sessions import ChatSessionManager

        return ChatSessionManager(self)

    @property
    def session_root(self) -> Path:
        """返回会话存储根目录，注入的根目录优先于默认数据目录。

        默认根直接位于 :attr:`data_path` 之下，不重复嵌套数据目录名。聊天与
        工作流两条路径共用本属性，避免默认根表达式分散后发生漂移。
        """
        return self._session_folder or self.data_path / "session"

    @property
    def chat_session_folder(self) -> Path:
        """返回经过归属校验的统一聊天目录。"""
        return resolve_session_folder(
            self.session_root,
            InboundMessage(type=MessageType.CHAT, content=""),
        )

    def is_session_running(self, session_id: str) -> bool:
        """执行及等待同会话锁的请求均视为运行中。"""
        return self._active_sessions.get(session_id, 0) > 0

    @contextlib.asynccontextmanager
    async def manage_chat_session(self, session_id: str) -> AsyncIterator[None]:
        """预留空闲会话，阻止管理过程中创建新的执行 context。"""
        if self._closing:
            raise RuntimeError("Agent Runtime 正在关闭")
        if self.is_session_running(session_id):
            raise RuntimeError("Session 正在执行，不能修改或删除")
        if session_id in self._managed_sessions:
            raise RuntimeError("Session 正在管理中")
        slot = self._slots.get(session_id)
        if slot is not None and slot.session_folder != self.chat_session_folder:
            raise ValueError("Session 不属于聊天目录")
        self._managed_sessions.add(session_id)
        try:
            if slot is not None:
                await self._close_slot(slot)
                self._slots.pop(session_id, None)
            yield
        finally:
            self._managed_sessions.discard(session_id)

    @property
    def data_path(self) -> Path:
        """返回当前生效的、已解析的 LifePrism 数据根目录。"""
        return (self._data_path or settings.lifeprism_data_path).resolve()

    def start(self) -> None:
        """在上一轮关闭后重新打开 runtime。

        只有在上一轮关闭已释放全部自有资源时才允许重启，否则会与旧的限流器状态和
        slot 集合发生串扰。

        Raises:
            RuntimeError: runtime 已置为关闭中，但 slot、轮次或消费方仍然存在。
        """
        if self._closing:
            if self._slots or self._tasks or self._consumers:
                raise RuntimeError("Agent Runtime 尚未完成关闭")
            self._limiter = ModelCallLimiter()
            self._closing = False

    def _get_slot(self, message: InboundMessage) -> tuple[_AgentSlot, bool]:
        """返回 ``message`` 对应的会话 slot，不存在时创建。

        只为 native UUID 会话创建 slot；旧式 ``session_*`` 标识会被拒绝，其适配
        工作推迟到 P4。

        Args:
            message: 入站消息，由其 ``session_id`` 决定使用哪个 slot。

        Returns:
            tuple: ``(slot, is_new)``——本次使用的执行 slot，以及是否为它新建了
            native 会话。

        Raises:
            RuntimeError: runtime 已在关闭中。
            ValueError: ``session_id`` 不是 native UUID，或指向磁盘上已不存在的
                会话。
        """
        if self._closing:
            raise RuntimeError("Agent Runtime 正在关闭")
        sid = message.session_id
        if sid in self._managed_sessions:
            raise RuntimeError("Session 正在管理中")
        root = self.session_root
        folder = resolve_session_folder(root, message)
        if sid:
            try:
                UUID(sid)
            except ValueError as exc:
                raise ValueError("仅支持 myagent 新会话，旧会话适配留到 P4") from exc
            if sid in self._slots:
                if self._slots[sid].session_folder != folder:
                    raise ValueError("Session 归属与当前聊天或工作流不一致")
                return self._slots[sid], False
        store = SessionStore(folder, flat=True)
        session = store.load(sid, self.data_path) if sid else None
        if sid and session is None:
            guidance = (
                "请发送 /new 开始新会话"
                if message.channel == ChannelType.WECHAT
                else "请开始新会话"
            )
            raise ValueError(
                f"myagent 会话不存在于当前归属目录；{guidance}；旧目录会话暂不自动迁移"
            )
        is_new = session is None
        if is_new:
            preview = "".join(block.get("text", "") for block in message.content)[:20]
            session = store.create(preview or message.type, self.data_path)
        agent_settings = settings.agent
        guard_settings = agent_settings.policies.tool_guard
        guard_paths = guard_settings.resolve_paths(self.data_path)
        client = (
            self._client_factory()
            if self._client_factory
            else ProviderAdapter(create_llm_client(), self._limiter)
        )
        context = AgentContext(
            agent_name=f"lifeprism-{uuid4().hex[:8]}",
            session=session,
            agent_config=AgentConfig(
                step_limit=agent_settings.step_limit, max_retry_count=agent_settings.max_retry_count
            ),
            llm_client=client,
            prompt_render_parame=None,
        )
        if agent_settings.policies.llm_retry.enabled:
            llm_retry = LLMRetry(agent_settings.policies.llm_retry.backoff_policy())
            context.register_policy(
                AgentPolicySpec(REQUEST_ERROR, [llm_retry.request_error_event], llm_retry)
            )
        tool_guard = ToolUseGuard({"allow_path": guard_paths})
        context.register_policy(
            AgentPolicySpec(TOOL_CALL, [tool_guard.file_sys_path_guard], tool_guard)
        )
        slot = _AgentSlot(context, client, folder)
        self._slots[session.meta_data.session_id] = slot
        return slot, is_new

    async def stream(self, message: InboundMessage) -> AsyncIterator[RuntimeEvent]:
        """流式执行一轮，并把当前消费方注册进关闭流程可取消的集合。

        当前任务会被记入 ``_consumers``，使 :meth:`close` 能直接取消仍在运行的
        调用方，而不必等它自然结束。

        Args:
            message: 待执行的入站消息。

        Yields:
            依次产出会话头事件、每条流式记录事件，以及终止的 ``done`` 或
            ``error`` 事件。
        """
        consumer = asyncio.current_task()
        self._consumers.add(consumer)
        sid = None
        try:
            slot, is_new = self._get_slot(message)
            sid = slot.context.session.meta_data.session_id
            self._active_sessions[sid] = self._active_sessions.get(sid, 0) + 1
            async with contextlib.aclosing(self._stream(message, slot, is_new)) as events:
                async for event in events:
                    yield event
        finally:
            if sid is not None:
                remaining = self._active_sessions[sid] - 1
                if remaining:
                    self._active_sessions[sid] = remaining
                else:
                    self._active_sessions.pop(sid, None)
            self._consumers.discard(consumer)

    async def _stream(
        self, message: InboundMessage, slot: _AgentSlot, is_new: bool
    ) -> AsyncIterator[RuntimeEvent]:
        """执行一轮串行化的运行并产出其事件。

        queue 会在 agent 任务启动前安装好，因此不会漏掉任何会话记录。模型与轮次
        失败以终止 ``error`` 事件上报，而不向外抛出。当消费方放弃生成器时，
        ``finally`` 块会取消本轮，但仍会持久化会话，并结算已经完成的模型调用。

        Args:
            message: 待执行的入站消息。

        Yields:
            依次产出会话头、流式记录，最后是 ``done``；失败则以终止 ``error``
            事件呈现。

        Raises:
            RuntimeError: runtime 正在关闭，或轮次准备阶段失败。
            ValueError: 消息指向不受支持的旧式会话。
        """
        sid = slot.context.session.meta_data.session_id
        run_id = uuid4().hex
        async with slot.lock:
            if self._closing:
                raise RuntimeError("Agent Runtime 正在关闭")
            context = slot.context
            try:
                await self._prepare_slot(slot, message, is_new)
            except BaseException:
                if is_new or message.type != MessageType.CHAT:
                    self._slots.pop(sid, None)
                    await self._close_slot(slot)
                raise
            slot.queue = asyncio.Queue()
            slot.run_id = run_id
            slot.usage = {}
            slot.response = LLMResponse(content="")
            slot.terminal = None
            task = asyncio.create_task(
                context.agent_loop.turn(Message(role="user", content=list(message.content)))
            )
            self._tasks.add(task)
            queue = slot.queue
            task.add_done_callback(lambda _: queue.put_nowait(None))
            result = None
            try:
                yield RuntimeEvent(
                    type="session",
                    run_id=run_id,
                    session_id=sid,
                    data={
                        "name": context.session.meta_data.name,
                        "is_new": is_new,
                        "workflow_id": message.workflow_id,
                        "channel": message.channel,
                        "session_category": resolve_session_category(message),
                    },
                )
                async with asyncio.timeout(1000):
                    while True:
                        event = await queue.get()
                        if event is None:
                            break
                        yield event
                    await task
                if slot.terminal is None:
                    raise RuntimeError("Agent 未产生本轮终态")
                if slot.terminal.reason_type != "success":
                    raise RuntimeError(slot.terminal.reason_text or slot.terminal.reason_type)
                slot.response.usage = slot.usage.copy()
                result = OutboundMessage(
                    id=message.id, response=slot.response, session_id=sid, extra=message.extra
                )
                yield RuntimeEvent(type="done", run_id=run_id, session_id=sid, result=result)
            except Exception as exc:
                reason = slot.terminal.reason_text if slot.terminal is not None else str(exc)
                logger.error("Agent 运行失败: run_id=%s error=%s", run_id, reason)
                yield RuntimeEvent(type="error", run_id=run_id, session_id=sid, text=reason)
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self._tasks.discard(task)
                slot.queue = None
                # Persist and account for completed model calls even on failed/cancelled turns.
                try:
                    if context.session.presistence is not None:
                        context.session.presistence.presist()
                    if slot.usage:
                        await self._usage_writer(
                            sid, slot.usage.copy(), message.token_type or message.type
                        )
                except Exception as exc:
                    logger.warning("Agent 辅助持久化/统计失败: %s", exc)
                if message.type == MessageType.CHAT and result is not None:
                    try:
                        await self._log_writer(
                            replace(message, session_id=sid), result, slot.header
                        )
                    except Exception as exc:
                        logger.warning("聊天调用日志失败: %s", exc)
                if message.type != MessageType.CHAT:
                    self._slots.pop(sid, None)
                    await self._close_slot(slot)

    async def _prepare_slot(self, slot: _AgentSlot, message: InboundMessage, is_new: bool) -> None:
        """就地刷新本轮的提示词与工具配置。

        保留 native context 与会话，使多轮聊天得以延续历史；只按消息类型重建提示词
        参数与已注册工具。

        Args:
            slot: 正在准备的会话 slot。
            message: 决定提示词与工具选择的入站消息。
            is_new: slot 是否为刚刚创建。只有已存在的会话才会重新读取生产
                provider 配置。
        """
        context = slot.context
        if self._client_factory is None and not is_new:
            # Keep the native context/session while refreshing production settings per turn.
            await slot.client.refresh(create_llm_client())
        context.agent_loop.prompt_render_parame = register_prompts(
            context.system_prompt, message, self.data_path
        )
        from lifeprism.llm.runtime_tools import build_tools

        context.agent_loop.tool_register.unregister(context.agent_loop.tool_register.tool_list())
        context.agent_loop.tool_register.register(
            (self._tools_factory or build_tools)(message.type)
        )

    async def execute(self, message: InboundMessage) -> OutboundMessage:
        """从与聊天相同的订阅事件路径中收集最终响应。

        Args:
            message: 待执行的入站消息。

        Returns:
            终止 ``done`` 事件所携带的 ``OutboundMessage``。

        Raises:
            RuntimeError: 本次运行上报了 ``error`` 事件，或结束时未产出结果。
        """
        result = None
        async with contextlib.aclosing(self.stream(message)) as events:
            async for event in events:
                if event.type == "done":
                    result = event.result
                elif event.type == "error":
                    raise RuntimeError(event.text)
        if result is None:
            raise RuntimeError("Agent 没有最终结果")
        return result

    @staticmethod
    async def _log_chat(message: InboundMessage, result: OutboundMessage, header) -> None:
        """把一次聊天调用写入 LLM 调用日志。

        只有聊天消息会走到这里，后台任务不记日志。阻塞式写文件被放到工作线程中
        执行。

        Args:
            message: 入站聊天消息，已被改写为携带 native 会话 id。
            result: 待记录的完整响应。
            header: 运行期间捕获的 ``request/header`` 记录，提供 system prompt
                与模型名；可能为 ``None``。
        """
        from lifeprism.llm.utils.llm_call_logger import llm_call_logger

        await asyncio.to_thread(
            llm_call_logger.log_call,
            inbound_msg=message,
            outbound_msg=result,
            prompt_module="chat",
            prompt_name="chat",
            system_prompt=header.system_prompt if header is not None else "",
            model=header.model_name if header is not None else None,
        )

    @staticmethod
    async def _save_usage(sid: str, usage: dict[str, int], mode: str) -> None:
        """把本轮 token 用量累加到会话的历史总计上。

        Args:
            sid: native myagent 会话标识。
            usage: 以 ``prompt_tokens``、``completion_tokens``、
                ``total_tokens`` 为键的本轮计数。
            mode: 与总计一并持久化的用量分类，取自消息的 token type 或 type。
        """
        from lifeprism.repository import tokens_usage_repository

        def save() -> None:
            """把新计数与已存总计合并后写回。"""
            existing = tokens_usage_repository.get_session_tokens_usage(sid) or {}
            values = {
                key: existing.get(key, 0) + usage.get(source, 0)
                for key, source in (
                    ("input_tokens", "prompt_tokens"),
                    ("output_tokens", "completion_tokens"),
                    ("total_tokens", "total_tokens"),
                )
            }
            tokens_usage_repository.upsert_session_tokens_usage(sid, {**values, "mode": mode})

        await asyncio.to_thread(save)

    async def close(self) -> None:
        """先停止全部在途轮次，再关闭各 context 及其持久化 worker。"""
        self._closing = True
        consumers = [task for task in self._consumers if task is not asyncio.current_task()]
        for consumer in consumers:
            consumer.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for slot in list(self._slots.values()):
            async with slot.lock:
                try:
                    await self._close_slot(slot)
                except Exception:
                    logger.exception("Agent context 关闭失败")
        self._slots.clear()
        self._tasks.clear()

    @staticmethod
    async def _close_slot(slot: _AgentSlot) -> None:
        """先关闭 slot 的 context，再关闭其 client，即使前者失败也照常执行。

        Args:
            slot: 需要释放 context 与 provider client 的 slot。
        """
        try:
            await slot.context.close()
        finally:
            close = getattr(slot.client, "aclose", None)
            if close is not None:
                await close()


agent_runtime: AgentRuntime = LazySingleton(AgentRuntime)
