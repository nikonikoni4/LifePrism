import asyncio

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import InboundMessage, MessageType

pytestmark = pytest.mark.core


def test_extraction_progress_survives_restart(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="hello"))
        seen = []

        async def handler(messages, start, end):
            seen.append((messages, start, end))

        assert await runtime.chat_sessions.process_pending(result.session_id, handler)
        assert seen[0][1:] == (1, 1)
        await runtime.close()
        runtime = make_runtime(tmp_path, FakeClient())
        assert not await runtime.chat_sessions.process_pending(result.session_id, handler)
        assert len(seen) == 1
        await runtime.close()

    asyncio.run(scenario())
