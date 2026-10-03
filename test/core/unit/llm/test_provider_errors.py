"""Provider errors keep SDK identity, transport phase and raw tool arguments."""

import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest
from litellm import exceptions as lite

from lifeprism.llm.providers.llm_providers.base import LLMProvider, ToolCallRequest
from lifeprism.llm.providers.llm_providers.custom_provider import CustomProvider
from lifeprism.llm.providers.llm_providers.litellm_provider import LiteLLMProvider

pytestmark = pytest.mark.core


def api_error(cls, status, code=None):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.invalid"))
    return cls("failure", response=response, body={"error": {"code": code}})


def classify(error, **kwargs):
    from lifeprism.llm.providers.errors import classify_provider_error

    return classify_provider_error(error, provider="test", model="test-model", **kwargs)


@pytest.mark.parametrize(
    "error,kind,reason",
    [
        (
            openai.APITimeoutError(request=httpx.Request("POST", "https://example.invalid")),
            "timeout",
            "timeout",
        ),
        (lite.APIConnectionError("failed", "test", "model"), "connection", "connection"),
        (api_error(openai.RateLimitError, 429), "rate_limit", "rate_limit"),
        (
            api_error(openai.RateLimitError, 429, "insufficient_quota"),
            "quota_exceeded",
            "insufficient_quota",
        ),
        (lite.BudgetExceededError(3, 2), "quota_exceeded", "budget_exceeded"),
        (lite.ContextWindowExceededError("too long", "test", "model"), "request", "context_limit"),
        (lite.UnsupportedParamsError("unsupported", "test", "model"), "request", "unsupported"),
        (lite.ContentPolicyViolationError("blocked", "test", "model"), "request", "content_policy"),
        (api_error(openai.AuthenticationError, 401), "request", "authentication"),
        (api_error(openai.PermissionDeniedError, 403), "request", "permission"),
        (api_error(openai.NotFoundError, 404), "request", "not_found"),
        (api_error(openai.BadRequestError, 400), "request", "invalid"),
        (api_error(openai.InternalServerError, 503), "unavailable", "service_unavailable"),
        (api_error(openai.APIStatusError, 418), "unknown", "unknown"),
    ],
)
def test_classification_precedence(error, kind, reason):
    converted = classify(error)
    assert converted.kind == kind
    assert converted.reason == reason
    assert converted.__cause__ is error
    assert converted.provider == "test" and converted.model == "test-model"


def test_programming_errors_and_cancellation_are_not_disguised():
    error = AttributeError("bug")
    assert classify(error) is error
    cancellation = asyncio.CancelledError()
    assert classify(cancellation) is cancellation


def test_stream_context_keeps_retry_after_and_cause():
    error = api_error(openai.RateLimitError, 429)
    error.response.headers["retry-after"] = "2.5"
    converted = classify(error, phase="streaming", partial_output=True)
    assert converted.phase == "streaming" and converted.partial_output
    assert converted.retry_after == 2.5
    again = classify(converted, phase="streaming", partial_output=True)
    assert again is converted and again.__cause__ is error


@pytest.mark.parametrize(
    "provider_cls,method", [(CustomProvider, "_parse"), (LiteLLMProvider, "_parse_response")]
)
@pytest.mark.parametrize("arguments", ['{"text":', "[1,2]", "null", "42"])
def test_bad_tool_arguments_are_not_repaired(provider_cls, method, arguments):
    call = SimpleNamespace(id="call-1", function=SimpleNamespace(name="echo", arguments=arguments))
    message = SimpleNamespace(content=None, tool_calls=[call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="tool_calls")], usage=None
    )
    parsed = getattr(object.__new__(provider_cls), method)(response)
    assert parsed.tool_calls[0].arguments == arguments
    assert parsed.tool_calls[0].to_openai_tool_call()["function"]["arguments"] == arguments


def test_raw_tool_string_is_not_double_encoded():
    raw = '{"text":'
    assert ToolCallRequest("id", "echo", raw).to_openai_tool_call()["function"]["arguments"] == raw


def test_legacy_entry_is_single_attempt_and_keeps_exception(monkeypatch):
    async def no_sleep(seconds):
        pass

    class BrokenProvider(LLMProvider):
        calls = 0

        async def chat(self, **kwargs):
            self.calls += 1
            raise openai.APIConnectionError(
                request=httpx.Request("POST", "https://example.invalid")
            )

        def get_default_model(self):
            return "fake"

    async def scenario():
        monkeypatch.setattr(asyncio, "sleep", no_sleep)
        provider = BrokenProvider()
        with pytest.raises(openai.APIConnectionError):
            await provider.chat_with_retry(
                [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
            )
        assert provider.calls == 1

    asyncio.run(scenario())


def test_adapter_interruption_preserves_cause_and_partial_output():
    from myagent.agent.core.provider import Message

    from lifeprism.llm.providers import GenerationSettings
    from lifeprism.llm.providers.errors import LLMProviderError
    from lifeprism.llm.runtime.provider import ProviderAdapter

    failure = openai.APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))

    class Provider:
        generation = GenerationSettings()

        def get_default_model(self):
            return "fake"

        async def stream_chat(self, **kwargs):
            yield {"choices": [{"delta": {"content": "partial"}}]}
            raise failure

    async def scenario():
        with pytest.raises(LLMProviderError) as caught:
            async for _ in ProviderAdapter(Provider()).stream_chat(
                [Message(role="user", content="hi")]
            ):
                pass
        assert caught.value.kind == "connection"
        assert caught.value.phase == "streaming" and caught.value.partial_output
        assert caught.value.__cause__ is failure

    asyncio.run(scenario())


def test_adapter_missing_finish_is_protocol_error():
    from lifeprism.llm.providers import GenerationSettings
    from lifeprism.llm.providers.errors import LLMProviderError
    from lifeprism.llm.runtime.provider import ProviderAdapter

    class Provider:
        generation = GenerationSettings()

        def get_default_model(self):
            return "fake"

        async def stream_chat(self, **kwargs):
            if False:
                yield

    async def scenario():
        with pytest.raises(LLMProviderError) as caught:
            async for _ in ProviderAdapter(Provider()).stream_chat([]):
                pass
        assert caught.value.kind == "invalid_response"

    asyncio.run(scenario())


@pytest.mark.parametrize("provider_cls", [CustomProvider, LiteLLMProvider])
def test_sdk_error_is_shared_by_chat_and_stream(provider_cls, monkeypatch):
    from lifeprism.llm.providers.errors import LLMProviderError
    from lifeprism.llm.providers.llm_providers import litellm_provider

    failure = api_error(openai.RateLimitError, 429)
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        raise failure

    async def scenario():
        if provider_cls is CustomProvider:
            provider = CustomProvider(api_key="fake")
            assert provider._client.max_retries == 0
            monkeypatch.setattr(provider._client.chat.completions, "create", create)
        else:
            provider = LiteLLMProvider(
                api_key="fake",
                api_base="https://example.invalid",
                default_model="fake",
                provider_name="custom",
            )
            monkeypatch.setattr(litellm_provider, "acompletion", create)
        messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
        try:
            with pytest.raises(LLMProviderError) as chat:
                await provider.chat(messages)
            with pytest.raises(LLMProviderError) as stream:
                async for _ in provider.stream_chat(messages):
                    pass
            assert chat.value.kind == stream.value.kind == "rate_limit"
            assert chat.value.__cause__ is stream.value.__cause__ is failure
            assert len(calls) == 2
            if provider_cls is LiteLLMProvider:
                assert all(c["num_retries"] == c["max_retries"] == 0 for c in calls)
        finally:
            if provider_cls is CustomProvider:
                await provider._client.close()

    asyncio.run(scenario())


def test_stream_cleanup_does_not_mask_cancellation():
    class BrokenStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise asyncio.CancelledError()

        async def aclose(self):
            raise RuntimeError("cleanup failed")

    async def scenario():
        provider = object.__new__(CustomProvider)
        provider.default_model = "fake"
        with pytest.raises(asyncio.CancelledError):
            async for _ in provider._stream_once(BrokenStream()):
                pass

    asyncio.run(scenario())
