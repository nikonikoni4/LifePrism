"""Shared admission replaces the former bus-only limiter."""

import time

import pytest

from lifeprism.llm.runtime.limiter import ModelCallLimiter


@pytest.mark.core
@pytest.mark.asyncio
async def test_rate_limit_waits_between_model_requests():
    limiter = ModelCallLimiter(rpm=600, safety_factor=0.5)
    await limiter.acquire()
    started_at = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - started_at >= limiter.interval * 0.9
