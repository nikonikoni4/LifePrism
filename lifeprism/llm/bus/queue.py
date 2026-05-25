import asyncio
import time
from collections import deque
from lifeprism.llm.bus.events import InboundMessage, OutboundMessage
from lifeprism.utils.lazy_singleton import LazySingleton
from lifeprism.utils.logger import get_logger, INFO,DEBUG

logger = get_logger(__name__)
logger.setLevel(DEBUG)

TIMEOUT_MAX = 1000.0
RATE_LIMIT = 60
RATE_WINDOW = 60.0
RATE_SAFETY_FACTOR = 0.7

# ─────────────────────────────────────────
#MessageQueue：双向队列，纯数据通道
# ─────────────────────────────────────────
class MessageQueue:
    def __init__(self):
        self._inbound = None
        self._outbound = None
        self._pending: dict[str, asyncio.Future] = {}
        self.stop_receive = False
        self._receive_task: asyncio.Task | None = None
        self._rate_timestamps: deque[float] = deque()
        self._rate_lock = asyncio.Lock()
        self._last_request_at: float | None = None

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

    def _content_preview(self, content: str | list | None) -> str:
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            return "".join(text_parts)[:20]
        return str(content or "")[:20]

    def _ensure_receive_task(self):
        """懒启动接收循环，确保在事件循环中调用"""
        if self._receive_task is None or self._receive_task.done():
            self._receive_task = asyncio.create_task(self._receive_loop())

    async def close(self):
        """停止接收循环，释放资源"""
        if self._receive_task is None:
            return
        self.stop_receive = True  # 设置停止标志
        self._receive_task.cancel()
        try:
            await self._receive_task
        except asyncio.CancelledError:
            pass
        self._receive_task = None

    async def _wait_for_rate_limit(self):
        """滑动窗口限速，并按安全系数平滑请求间隔。"""
        async with self._rate_lock:
            while True:
                now = time.monotonic()

                if self._last_request_at is not None:
                    request_interval = RATE_WINDOW / (RATE_LIMIT * RATE_SAFETY_FACTOR)
                    interval_wait = request_interval - (now - self._last_request_at)
                    if interval_wait > 0:
                        logger.debug(f"[MessageQueue] 请求间隔等待 {interval_wait:.2f}s")
                        await asyncio.sleep(interval_wait)
                        now = time.monotonic()

                # 清除窗口外的旧记录
                while self._rate_timestamps and now - self._rate_timestamps[0] >= RATE_WINDOW:
                    self._rate_timestamps.popleft()
                if len(self._rate_timestamps) < RATE_LIMIT:
                    self._rate_timestamps.append(now)
                    self._last_request_at = now
                    return
                # 等到最早的请求滑出窗口
                wait = RATE_WINDOW - (now - self._rate_timestamps[0])
                logger.debug(f"[MessageQueue] 限速等待 {wait:.2f}s")
                await asyncio.sleep(wait)

    async def send(self, msg:InboundMessage) -> OutboundMessage:
        """发送消息并等待结果
        args:
            msg : InboundMessage
        return:
            OutboundMessage 消息回复内容
        """
        self._ensure_receive_task()
        await self._wait_for_rate_limit()
        # 1. 创建消息
        logger.info(f"[MessageQueue] 发送 content={self._content_preview(msg.content)!r}")

        # 2. 创建future，并入pending
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[msg.id] = future

        # 3. 发送消息
        await self.publish_inbound(msg)

        # 4. 等待对应future回复（600s 超时，防止 agent 异常时永久挂起）
        try:
            result: OutboundMessage = await asyncio.wait_for(future, timeout=TIMEOUT_MAX)
            logger.debug(f"[MessageQueue] 收到回复: {result.response!r}")
        except asyncio.TimeoutError:
            logger.error(f"[MessageQueue] 消息 {msg.id} 超时")
            raise
        finally:
            self._pending.pop(msg.id, None)  # 确保清理，避免内存泄漏

        # 5. 异步保存统计信息 (不阻塞消息返回)
        if result.response and result.response.usage:
            try:
                from lifeprism.llm.providers.dataset_providers import llm_dataset_provider
                asyncio.create_task(asyncio.to_thread(
                    llm_dataset_provider.save_usage,
                    session_id=result.session_id,
                    usage=result.response.usage,
                    mode=msg.token_type or msg.type
                ))
            except Exception as e:
                logger.error(f"[MessageQueue] 保存 token 使用情况失败: {e}")

        return result

    async def _receive_loop(self):
        try:
            while not self.stop_receive:
                msg = await self.consume_outbound()
                future = self._pending.pop(msg.id, None)
                if future and not future.done():
                    future.set_result(msg)
        except asyncio.CancelledError:
            # 清理所有 pending futures
            for future in self._pending.values():
                if not future.done():
                    future.cancel()
            self._pending.clear()
            raise
        except Exception as e:
            logger.error(f"[MessageQueue] 接收循环异常: {e}")
            raise

bus:MessageQueue = LazySingleton(MessageQueue) # 单一实例代理
