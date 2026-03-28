import asyncio
from lifeprism.llm.bus.events import InboundMessage, OutboundMessage

# ─────────────────────────────────────────
#MessageQueue：双向队列，纯数据通道
# ─────────────────────────────────────────
class MessageQueue:
    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        return await self.outbound.get()

bus = MessageQueue() # 单一实例