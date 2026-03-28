"""消息收发接口 负责发送和接收"""
import asyncio
from lifeprism.llm.bus import InboundMessage, OutboundMessage,bus
from lifeprism.utils.logger import get_logger,DEBUG
logger = get_logger(__name__)
logger.setLevel(DEBUG)
class Channel:
    def __init__(self):
        self._pending : dict[str,asyncio.Future] = {}
        self.stop_receive = False
        asyncio.create_task(self._receive_loop())
        # send -> 创建msg->创建futrue->_receive_loop内等待任务完成之后set_result, 在send中等待futrue完成
    
    
    async def send(self, content: str) -> str:
        """发送消息并等待结果"""
        # 1. 创建消息
        msg = InboundMessage(type="chat", content=content)
        logger.debug(f"[Channel] 发送 id={msg.id} content={content!r}")

        # 2. 创建future，并入pending
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[msg.id] = future

        # 3. 发送消息
        await bus.publish_inbound(msg)

        # 4. 等待对应future回复
        result:OutboundMessage = await asyncio.wait_for(self._pending[msg.id],None)  # 等队列里的下一个结果
        logger.debug(f"[Channel] 收到回复: {result.response!r}")

        return result.response

    async def _receive_loop(self):
        while True:
            msg = await bus.consume_outbound()
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