"""把生产 provider 适配到 myagent 的流式契约，不引入重试策略。"""

from collections.abc import AsyncIterator
from typing import Any

from myagent.agent.core.provider import (
    ChatParams,
    LLMResponse,
    Message,
    RawToolCall,
    StreamChunk,
    Usage,
)

from lifeprism.llm.providers import LLMProvider


def _value(obj: Any, key: str, default: Any = None) -> Any:
    """从映射或 provider SDK 对象中读取一个字段。

    provider SDK 返回 OpenAI 风格的对象，而测试中基于 dict 的假 provider 返回
    普通映射，因此字段读取必须同时兼容两种形态。

    Args:
        obj: 待读取的映射或 SDK 对象。
        key: 要查找的字段名。
        default: 字段缺失时返回的取值。

    Returns:
        字段值；字段缺失时返回 ``default``。
    """
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


class ProviderAdapter:
    """把生产 ``LLMProvider`` 暴露为 myagent 的 provider 契约。

    职责仅限于转换：把每次调用路由到下层生产 provider，透传其生成参数，并把原始
    OpenAI 风格数据流转换为 ``StreamChunk`` 增量，最后恰好以一个
    ``LLMResponse`` 收尾。重试策略刻意不放在本层。
    """

    def __init__(self, provider: LLMProvider, limiter: Any = None):
        """包装一个生产 provider，可选地置于共享限流器之后。

        Args:
            provider: 负责模型路由与鉴权的生产 provider。
            limiter: 提供可 await 的 ``acquire()`` 的对象，每次模型请求调用一次。
                传 ``None`` 表示关闭准入控制。
        """
        self.provider = provider
        self.limiter = limiter

    @property
    def model(self) -> str:
        """返回当前路由选定的模型名称。"""
        return self.provider.get_default_model()

    @property
    def params(self) -> ChatParams:
        """把生成参数转换为内核的 ``ChatParams``。"""
        generation = self.provider.generation
        return ChatParams(temperature=generation.temperature, max_tokens=generation.max_tokens)

    async def aclose(self) -> None:
        """释放生产 provider 持有的 HTTP 客户端（如果存在）。

        未暴露 ``_client`` 的 provider 不作处理，由其自行管理生命周期。
        """
        client = getattr(self.provider, "_client", None)
        if client is not None:
            await client.close()

    async def refresh(self, provider: LLMProvider) -> None:
        """在串行化的轮次之间换入刷新后的模型配置。

        会先关闭上一个 provider 的 HTTP 客户端，避免用户会话中途修改配置时反复
        泄漏连接。

        Args:
            provider: 新建的生产 provider，后续请求经它路由。
        """
        await self.aclose()
        self.provider = provider

    async def chat(self, messages: list[Message], tools: list[dict] | None = None) -> LLMResponse:
        """通过排空流式路径完成一次非流式请求。

        Args:
            messages: 待发送的对话，使用内核消息格式。
            tools: 可选，向模型声明的工具 schema。

        Returns:
            流式路径产出的完整响应。

        Raises:
            RuntimeError: 数据流结束前始终未产出最终响应。
        """
        async for item in self.stream_chat(messages, tools):
            if isinstance(item, LLMResponse):
                return item
        raise RuntimeError("Provider stream did not produce a final response")

    async def stream_chat(
        self, messages: list[Message], tools: list[dict] | None = None
    ) -> AsyncIterator[StreamChunk | LLMResponse]:
        """流式获取一次模型响应，并以一个完整响应收尾。

        原始增量以 ``StreamChunk`` 转发。工具调用分片按 ``index`` 累积，使跨分块
        切开的参数在交给 native 校验前重新拼合；对把 ``<tool_call>`` XML 写进正文
        的 provider，走回退路径解析。即使消费方提前断开，也会关闭下层 provider
        数据流。

        Args:
            messages: 待发送的对话，使用内核消息格式。
            tools: 可选，向模型声明的工具 schema。

        Yields:
            每个内容、思维链或工具调用增量各产出一个 ``StreamChunk``，随后恰好
            产出一个 ``LLMResponse``，携带拼装后的内容、思维链、工具调用、结束
            原因与 token 用量。

        Raises:
            RuntimeError: 数据流结束时缺少 finish reason，或 provider 以
                ``finish_reason="error"`` 上报失败。
        """
        if self.limiter is not None:
            await self.limiter.acquire()
        generation = self.provider.generation
        text: list[str] = []
        reasoning: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        usage = Usage()
        finish_reason = None
        stream = self.provider.stream_chat(
            messages=[message.to_dict() for message in messages],
            tools=tools,
            max_tokens=generation.max_tokens,
            temperature=generation.temperature,
            reasoning_effort=generation.reasoning_effort,
        )
        try:
            async for raw in stream:
                raw_usage = _value(raw, "usage")
                if raw_usage:
                    usage = Usage(
                        **{
                            key: _value(raw_usage, key, 0) or 0
                            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                        }
                    )
                choices = _value(raw, "choices", []) or []
                if not choices:
                    continue
                choice = choices[0]
                delta = _value(choice, "delta", {})
                content = _value(delta, "content")
                thought = _value(delta, "reasoning_content")
                if content:
                    text.append(content)
                if thought:
                    reasoning.append(thought)
                if content:
                    yield StreamChunk(content=content)
                if thought:
                    yield StreamChunk(reasoning_content=thought)
                for call in _value(delta, "tool_calls", []) or []:
                    index = _value(call, "index", 0)
                    slot = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    function = _value(call, "function", {})
                    call_id = _value(call, "id")
                    name = _value(function, "name")
                    arguments = _value(function, "arguments")
                    if call_id:
                        slot["id"] = call_id
                    if name:
                        slot["name"] += name
                    if arguments:
                        slot["arguments"] += arguments
                    yield StreamChunk(
                        tool_index=index,
                        tool_id=call_id,
                        tool_name=name,
                        tool_arguments_delta=arguments,
                    )
                reason = _value(choice, "finish_reason")
                if reason:
                    finish_reason = reason
                    yield StreamChunk(finish_reason=reason)
        finally:
            await stream.aclose()
        if finish_reason is None:
            raise RuntimeError("Provider stream ended without a finish reason")
        if finish_reason == "error":
            raise RuntimeError("".join(text) or "Provider request failed")
        tool_calls = [
            RawToolCall(
                id=slot["id"],
                name=slot["name"],
                arguments=slot["arguments"],
                truncated=finish_reason == "length",
            )
            for _, slot in sorted(calls.items())
        ]
        content = "".join(text)
        # Preserve existing production support for XML-based tool calling providers.
        if not tool_calls and "<tool_call>" in content:
            xml_calls = self.provider._parse_xml_tool_calls(content)
            tool_calls = [
                RawToolCall(id=call.id, name=call.name, arguments=call.arguments)
                for call in xml_calls
            ]
            if tool_calls:
                content = ""
        yield LLMResponse(
            content=content or None,
            reasoning_content="".join(reasoning) or None,
            tool_call_requests=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
