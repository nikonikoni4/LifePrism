"""不发起网络调用的流式 provider 契约测试。"""

import asyncio

import pytest
from myagent.agent.core.provider import LLMResponse, Message, StreamChunk

from lifeprism.llm.providers import GenerationSettings
from lifeprism.llm.runtime.provider import ProviderAdapter

pytestmark = pytest.mark.core


class RawProvider:
    """流式 provider 测试替身，回放 OpenAI 风格的原始分块字典。"""
    generation = GenerationSettings()

    def __init__(self, chunks):
        """使用固定的分块序列初始化该 provider。

        Args:
            chunks: ``stream_chat`` 依次产出的原始分块字典。
        """
        self.chunks = chunks
        self.closed = False
        self.kwargs = None

    def get_default_model(self):
        """返回被测 adapter 使用的固定模型名。"""
        return "fake"

    async def stream_chat(self, **kwargs):
        """按顺序产出脚本化分块，并在退出时把 provider 标记为已关闭。"""
        self.kwargs = kwargs
        try:
            for chunk in self.chunks:
                yield chunk
        finally:
            self.closed = True


def raw(delta=None, finish=None, usage=None):
    """构造一个 OpenAI 风格的原始流式分块。

    Args:
        delta: 放入首个 choice 的 delta 载荷。
        finish: 可选；首个 choice 上报的结束原因。
        usage: 可选；附加到该分块的 usage 载荷。

    Returns:
        dict: 形如原始 provider 流事件的字典。
    """
    return {"choices": [{"delta": delta or {}, "finish_reason": finish}], "usage": usage}


def test_stream_preserves_raw_arguments_and_both_text_channels():
    """守护 adapter 保留原始参数、两条文本通道以及合并后的 usage。"""
    async def scenario():
        """在 `asyncio.run` 下驱动原始参数流式场景。"""
        provider = RawProvider(
            [
                raw({"content": "answer", "reasoning_content": "thought"}),
                raw(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "tool-id",
                                "function": {"name": "echo", "arguments": '{"text":'},
                            }
                        ]
                    }
                ),
                raw(
                    {"tool_calls": [{"index": 0, "function": {"arguments": '"hello"}'}}]},
                    "tool_calls",
                ),
                {
                    "choices": [],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                },
            ]
        )
        events = [
            item
            async for item in ProviderAdapter(provider).stream_chat(
                [
                    Message(role="user", content=[{"type": "text", "text": "x"}]),
                ]
            )
        ]
        final = events[-1]
        assert isinstance(final, LLMResponse)
        assert final.content == "answer" and final.reasoning_content == "thought"
        assert final.tool_call_requests[0].arguments == '{"text":"hello"}'
        assert final.tool_call_requests[0].id == "tool-id"
        assert final.usage.total_tokens == 5
        assert [e.content for e in events if isinstance(e, StreamChunk) and e.content] == ["answer"]
        assert [
            e.reasoning_content
            for e in events
            if isinstance(e, StreamChunk) and e.reasoning_content
        ] == ["thought"]
        assert provider.closed
        assert provider.kwargs["max_tokens"] == provider.generation.max_tokens

    asyncio.run(scenario())


def test_unfinished_stream_cannot_be_reported_as_success():
    """守护没有结束原因就中断的流会抛错，而不是被当作成功。"""
    async def scenario():
        """在 `asyncio.run` 下驱动未完成流场景。"""
        provider = RawProvider([raw({"content": "partial"})])
        with pytest.raises(RuntimeError, match="finish reason"):
            _ = [item async for item in ProviderAdapter(provider).stream_chat([])]
        assert provider.closed

    asyncio.run(scenario())


def test_truncated_tool_arguments_are_preserved_for_native_validation():
    """守护被截断的工具参数会带着 truncated 标记进入 native 校验。"""
    async def scenario():
        """在 `asyncio.run` 下驱动工具参数被截断的场景。"""
        provider = RawProvider(
            [
                raw(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "id",
                                "function": {"name": "echo", "arguments": '{"text":'},
                            }
                        ]
                    },
                    "length",
                )
            ]
        )
        final = await ProviderAdapter(provider).chat([])
        assert final.tool_call_requests[0].truncated
        assert final.tool_call_requests[0].arguments == '{"text":'

    asyncio.run(scenario())


def test_refresh_releases_previous_provider_and_changes_model():
    """守护刷新 adapter 会关闭旧 provider 并采用新模型。"""
    async def scenario():
        """在 `asyncio.run` 下驱动 provider 刷新场景。"""
        closed = []

        class Client:
            """替身 provider client，用于记录自己被关闭的时机。"""

            async def close(self):
                """记录旧 provider 的 client 已被关闭。"""
                closed.append(True)

        old = RawProvider([])
        old._client = Client()
        new = RawProvider([])
        new.get_default_model = lambda: "new-model"
        adapter = ProviderAdapter(old)
        await adapter.refresh(new)
        assert closed == [True]
        assert adapter.model == "new-model"

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["custom", "litellm"])
def test_production_stream_closes_sdk_when_consumer_disconnects(monkeypatch, kind):
    """守护消费方断开时，两种 provider 都会关闭底层 SDK 流。

    Args:
        kind: 被测的 provider 类型，取值为 ``custom`` 或 ``litellm``。
    """
    async def scenario():
        """在 `asyncio.run` 下驱动 SDK 断开场景。"""
        from types import SimpleNamespace

        from lifeprism.llm.providers.llm_providers import custom_provider, litellm_provider

        captured = []
        closed = []

        async def chunks():
            """产出两个脚本化分块，并在流结束时记录关闭。"""
            try:
                yield raw({"content": "first"})
                yield raw({"content": "second"}, "stop")
            finally:
                closed.append(True)

        async def create(**kwargs):
            """捕获 SDK 调用参数并返回脚本化分块流。"""
            captured.append(kwargs)
            return chunks()

        if kind == "custom":
            monkeypatch.setattr(
                custom_provider,
                "AsyncOpenAI",
                lambda **kwargs: SimpleNamespace(
                    chat=SimpleNamespace(completions=SimpleNamespace(create=create))
                ),
            )
            provider = custom_provider.CustomProvider(api_key="fake", default_model="test-model")
        else:
            monkeypatch.setattr(litellm_provider, "acompletion", create)
            provider = litellm_provider.LiteLLMProvider(
                api_key="fake",
                api_base="https://example.invalid/v1",
                default_model="test-model",
                provider_name="custom",
            )
        stream = provider.stream_chat(
            messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
        )
        first = await anext(stream)
        assert first["choices"][0]["delta"]["content"] == "first"
        await stream.aclose()
        assert closed == [True]
        assert len(captured) == 1
        assert captured[0]["stream"] is True
        assert captured[0]["stream_options"]["include_usage"] is True

    asyncio.run(scenario())
