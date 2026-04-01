import asyncio
from lifeprism.llm.bus.events import InboundMessage, OutboundMessage

# ─────────────────────────────────────────
#MessageQueue：双向队列，纯数据通道
# ─────────────────────────────────────────
class MessageQueue:
    def __init__(self):
        self._inbound = None
        self._outbound = None

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

bus = MessageQueue() # 单一实例