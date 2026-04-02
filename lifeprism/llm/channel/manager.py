"""消息收发接口 负责发送和接收"""
import asyncio
import time
from typing import Any
from collections import deque
from lifeprism.llm.bus import InboundMessage, OutboundMessage, bus, MessageQueue
from lifeprism.utils.logger import get_logger, DEBUG
from lifeprism.utils.lazy_singleton import LazySingleton
logger = get_logger(__name__)
logger.setLevel(DEBUG)
TIMEOUT_MAX = 600.0
RATE_LIMIT = 100       # 每分钟最大请求数
RATE_WINDOW = 60.0     # 滑动窗口（秒）

class Channel:
    def __init__(self, bus: MessageQueue):
        self._bus = bus
        self._pending : dict[str,asyncio.Future] = {}
        self.stop_receive = False
        self._receive_task: asyncio.Task | None = None
        self._rate_timestamps: deque[float] = deque()  # 滑动窗口：记录最近请求时间戳
        # send -> 创建msg->创建futrue->_receive_loop内等待任务完成之后set_result, 在send中等待futrue完成

    def _ensure_receive_task(self):
        """懒启动接收循环，确保在事件循环中调用"""
        if self._receive_task is None or self._receive_task.done():
            self._receive_task = asyncio.create_task(self._receive_loop())

    async def close(self):
        """停止接收循环，释放资源"""
        if self._receive_task is None:
            return
        self._receive_task.cancel()
        try:
            await self._receive_task
        except asyncio.CancelledError:
            pass
        self._receive_task = None
    
    
    async def _wait_for_rate_limit(self):
        """滑动窗口限速：确保每分钟请求数不超过 RATE_LIMIT"""
        while True:
            now = time.monotonic()
            # 清除窗口外的旧记录
            while self._rate_timestamps and now - self._rate_timestamps[0] >= RATE_WINDOW:
                self._rate_timestamps.popleft()
            if len(self._rate_timestamps) < RATE_LIMIT:
                self._rate_timestamps.append(now)
                return
            # 等到最早的请求滑出窗口
            wait = RATE_WINDOW - (now - self._rate_timestamps[0])
            logger.debug(f"[Channel] 限速等待 {wait:.2f}s")
            await asyncio.sleep(wait)

    async def send(self, content: str, session_id: str | None = None,
                   type: str = "chat", extra: dict | None = None) -> Any:
        """发送消息并等待结果"""
        self._ensure_receive_task()
        await self._wait_for_rate_limit()
        # 1. 创建消息
        msg = InboundMessage(type=type, content=content, session_id=session_id, extra=extra)
        logger.debug(f"[Channel] 发送 id={msg.id} content={content!r}")

        # 2. 创建future，并入pending
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[msg.id] = future

        # 3. 发送消息
        await self._bus.publish_inbound(msg)

        # 4. 等待对应future回复（60s 超时，防止 agent 异常时永久挂起）
        result: OutboundMessage = await asyncio.wait_for(self._pending[msg.id], timeout=TIMEOUT_MAX)
        logger.debug(f"[Channel] 收到回复: {result.response!r}")

        # 5. 异步保存统计信息 (不阻塞消息返回)
        if result.response and result.response.usage:
            try:
                from lifeprism.llm.providers.llm_usage_db_provider import llm_usage_db_provider
                asyncio.create_task(asyncio.to_thread(
                    llm_usage_db_provider.save_usage,
                    session_id=msg.session_id,
                    usage=result.response.usage,
                    mode=msg.type
                ))
            except Exception as e:
                logger.error(f"[Channel] 保存 token 使用情况失败: {e}")

        response = result.response
        if hasattr(response, 'content'):
            return response.content
        return response

    async def _receive_loop(self):
        while True:
            msg = await self._bus.consume_outbound()
            future = self._pending.pop(msg.id, None) 
            if future:
                future.set_result(msg)

# if __name__ == "__main__":
#     async def main():
#         bus = MessageQueue()
#         agent = AgentLoop(bus)
#         channel = Channel(bus)
#         asyncio.create_task(agent.run())

#         async def sender_a():
#             print("[SenderA] 开始发送")
#             result = await channel.send("你好，我是A",dely=10.0)
#             print(f"[SenderA] 最终收到: {result!r}")

#         async def sender_b():
#             print("[SenderB] 开始发送")
#             result = await channel.send("你好，我是B")
#             print(f"[SenderB] 最终收到: {result!r}")

#         # 两个 sender 同时发，验证各自收到自己的回复
#         await asyncio.gather(sender_a(), sender_b())

#     asyncio.run(main())

channel_manager = LazySingleton(Channel, bus=bus)  # 懒初始化代理