"""Chat entry point using myagent events; session business APIs are deferred to P4."""

from collections.abc import AsyncIterator

from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType
from lifeprism.llm.providers import LLMResponse
from lifeprism.llm.runtime import agent_runtime
from lifeprism.llm.runtime.service import RuntimeEvent


class ChatBot:
    def stream(
        self, content: str, session_id: str | None = None, channel: str = ChannelType.LOCAL, **extra
    ) -> AsyncIterator[RuntimeEvent]:
        """Submit directly to Runtime and subscribe to the run's events."""
        return agent_runtime.stream(
            InboundMessage(
                type=MessageType.CHAT,
                content=content,
                session_id=session_id,
                channel=channel,
                extra=extra,
            )
        )

    async def chat(self, content: str, session_id: str | None = None, **extra) -> LLMResponse:
        """Collect the complete response without using the background message bus."""
        result = await agent_runtime.execute(
            InboundMessage(
                type=MessageType.CHAT,
                content=content,
                session_id=session_id,
                extra=extra,
            )
        )
        return result.response
