"""request/error waterfall policy contracts."""

import asyncio

import pytest
from myagent.infra.events.payload import RequestErrorPayLoad

from lifeprism.llm.providers.errors import LLMProviderError

pytestmark = pytest.mark.core


@pytest.mark.parametrize("kind", ["connection", "timeout", "rate_limit", "unavailable"])
def test_transient_provider_error_is_claimed(kind):
    from lifeprism.llm.providers.llm_retry import LLMRetry

    async def scenario():
        async def next_handler():
            pytest.fail("claimed error reached downstream")

        error = LLMProviderError("failed", kind=kind, reason=kind, provider="fake", model="fake")
        result = await LLMRetry().request_error_event(
            RequestErrorPayLoad(error_type=error), next_handler
        )
        assert result == {
            "decision": "backoff_retry",
            "policy": {"base_delay": 1.0, "multiplier": 2.0, "cap": 30.0},
        }

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "error",
    [
        LLMProviderError("failed", kind=kind, reason=kind, provider="fake", model="fake")
        for kind in ["request", "quota_exceeded", "invalid_response", "unknown"]
    ]
    + [
        RuntimeError("bug"),
        asyncio.CancelledError(),
        LLMProviderError(
            "partial",
            kind="connection",
            reason="connection",
            provider="fake",
            model="fake",
            partial_output=True,
        ),
    ],
)
def test_unclaimed_errors_delegate(error):
    from lifeprism.llm.providers.llm_retry import LLMRetry

    async def scenario():
        calls = []

        async def next_handler():
            calls.append(1)
            return {"decision": "downstream"}

        assert await LLMRetry().request_error_event(
            RequestErrorPayLoad(error_type=error), next_handler
        ) == {"decision": "downstream"}
        assert calls == [1]

    asyncio.run(scenario())
