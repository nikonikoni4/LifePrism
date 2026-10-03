import asyncio
import contextlib

from lifeprism.llm.bus.events import InboundMessage, MessageContent, OutboundMessage
from lifeprism.utils.lazy_singleton import LazySingleton
from lifeprism.utils.logger import DEBUG, get_logger

logger = get_logger(__name__)
logger.setLevel(DEBUG)

TIMEOUT_MAX = 1000.0


# ─────────────────────────────────────────
# MessageQueue：双向队列，纯数据通道
# ─────────────────────────────────────────
class MessageQueue:
    def __init__(self):
        self._inbound = None
        self._outbound = None
        self._pending: dict[str, asyncio.Future] = {}
        self.stop_receive = False
        self._receive_task: asyncio.Task | None = None

    @property
    def inbound(self) -> asyncio.Queue[InboundMessage]:
        if self._inbound is None:
            self._inbound = asyncio.Queue()
        return self._inbound

    @property
    def outbound(self) -> asyncio.Queue[OutboundMessage]:
        if self._outbound is None:
            self._outbound = asyncio.Queue()
        return self._outbound

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        return await self.outbound.get()

    def bind_execution(self, message_id: str, task: asyncio.Task) -> None:
        """Cancel background work when its requesting Future is cancelled or times out."""
        future = self._pending.get(message_id)
        if future is not None:

            def cancel_execution(done: asyncio.Future) -> None:
                if done.cancelled() and not task.done():
                    task.cancel()

            future.add_done_callback(cancel_execution)

    def _content_preview(self, content: MessageContent) -> str:
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "".join(text_parts)[:20]

    def _ensure_receive_task(self):
        """懒启动接收循环，确保在事件循环中调用"""
        if self._receive_task is None or self._receive_task.done():
            self.stop_receive = False
            self._receive_task = asyncio.create_task(self._receive_loop())

    async def close(self):
        """停止接收循环，释放资源"""
        if self._receive_task is None:
            return
        self.stop_receive = True  # 设置停止标志
        self._receive_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._receive_task
        self._receive_task = None

    async def send(self, msg: InboundMessage) -> OutboundMessage:
        """发送消息并等待结果
        args:
            msg : InboundMessage
        return:
            OutboundMessage 消息回复内容
        """
        self._ensure_receive_task()
        # Model-call admission and usage accounting now belong to Runtime/provider.
        # 1. 创建消息
        logger.info("[MessageQueue] 发送 content=%r", self._content_preview(msg.content))

        # 2. 创建future，并入pending
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        if msg.id in self._pending:
            raise ValueError(f"Duplicate in-flight message id: {msg.id}")
        self._pending[msg.id] = future
        msg._cancelled = False

        # 3. 发送消息
        try:
            await self.publish_inbound(msg)
            # Wait only for this request; Runtime owns execution and terminal events.
            result: OutboundMessage = await asyncio.wait_for(future, timeout=TIMEOUT_MAX)
            logger.debug("[MessageQueue] 收到回复: %r", result.response)
        except TimeoutError:
            logger.error("[MessageQueue] 消息 %s 超时", msg.id)
            raise
        finally:
            if not future.done():
                future.cancel()
            msg._cancelled = future.cancelled()
            self._pending.pop(msg.id, None)  # 确保清理，避免内存泄漏

        return result

    async def _receive_loop(self):
        try:
            while not self.stop_receive:
                msg = await self.consume_outbound()
                future = self._pending.pop(msg.id, None)
                if future and not future.done():
                    if msg.error is not None:
                        future.set_exception(RuntimeError(msg.error))
                    else:
                        future.set_result(msg)
        except asyncio.CancelledError:
            # 清理所有 pending futures
            for future in self._pending.values():
                if not future.done():
                    future.cancel()
            self._pending.clear()
            raise
        except Exception as e:
            logger.error("[MessageQueue] 接收循环异常: %s", e)
            raise


bus: MessageQueue = LazySingleton(MessageQueue)  # 单一实例代理
