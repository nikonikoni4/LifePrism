import asyncio
from typing import Optional, Dict
from lifeprism.llm.bus import bus, InboundMessage, OutboundMessage, MessageType
from lifeprism.llm.providers import LLMResponse
from lifeprism.utils import get_logger

logger = get_logger(__name__)

class ChatBot:
    def __init__(self):
        self._bus = bus
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._running = True
        self._distributor_task = asyncio.create_task(self._response_distributor())

    async def _response_distributor(self):
        """Consumes outbound messages and fulfills pending futures."""
        try:
            while self._running:
                out_msg = await self._bus.consume_outbound()
                if out_msg.id in self._pending_requests:
                    fut = self._pending_requests[out_msg.id]
                    if not fut.done():
                        fut.set_result(out_msg.response)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ChatBot] Response distributor error: {e}")

    async def chat(self, content: str, session_id: str = None, **extra) -> LLMResponse:
        """Sends a chat message and waits for the response."""
        msg = InboundMessage(
            type=MessageType.CHAT,
            content=content,
            session_id=session_id,
            extra=extra
        )

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_requests[msg.id] = fut

        try:
            await self._bus.publish_inbound(msg)
            return await fut
        finally:
            self._pending_requests.pop(msg.id, None)

    def stop(self):
        """Stops the response distributor."""
        self._running = False
        self._distributor_task.cancel()
