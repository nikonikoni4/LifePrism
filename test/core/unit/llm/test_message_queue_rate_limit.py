import time

import pytest

from lifeprism.llm.bus import queue as queue_module
from lifeprism.llm.bus.queue import MessageQueue


@pytest.mark.core
@pytest.mark.asyncio
async def test_rate_limit_waits_between_requests(monkeypatch):
    """连续请求按安全系数计算的最小间隔放行。"""
    monkeypatch.setattr(queue_module, "RATE_LIMIT", 10)
    monkeypatch.setattr(queue_module, "RATE_WINDOW", 1.0)
    monkeypatch.setattr(queue_module, "RATE_SAFETY_FACTOR", 0.5, raising=False)

    queue = MessageQueue()
    expected_interval = queue_module.RATE_WINDOW / (
        queue_module.RATE_LIMIT * queue_module.RATE_SAFETY_FACTOR
    )

    await queue._wait_for_rate_limit()
    started_at = time.monotonic()
    await queue._wait_for_rate_limit()
    elapsed = time.monotonic() - started_at

    assert elapsed >= expected_interval * 0.9
