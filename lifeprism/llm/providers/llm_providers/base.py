"""Base LLM provider interface.
本文件部分代码源自 https://github.com/HKUDS/nanobot.git
Copyright (c) [2026.3.22] [HKUDS]
Licensed under the MIT License.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 单个字符串字段落盘时的上限。超长内容（如 base64 图片）截断但保留原始长度，
# 因为请求被拒的原因通常是结构或长度，而非具体内容。
_MAX_DUMP_STRING = 200_000


def _json_safe(value: Any) -> Any:
    """把任意对象转换为可 JSON 序列化的结构。

    Args:
        value: 待转换的对象，可能是请求 kwargs 里的任意嵌套结构。

    Returns:
        仅由 dict / list / str / int / float / bool / None 组成的等价结构。超长
        字符串截断，并在末尾标注被截断的字符数与原始长度。
    """
    if isinstance(value, str):
        if len(value) <= _MAX_DUMP_STRING:
            return value
        dropped = len(value) - _MAX_DUMP_STRING
        return (
            f"{value[:_MAX_DUMP_STRING]}...[truncated {dropped} chars, original_len={len(value)}]"
        )
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return repr(value)


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any] | str
    provider_specific_fields: dict[str, Any] | None = None
    function_provider_specific_fields: dict[str, Any] | None = None

    def to_openai_tool_call(self) -> dict[str, Any]:  # 用于
        """Serialize to an OpenAI-style tool_call payload."""
        tool_call = {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments
                if isinstance(self.arguments, str)
                else json.dumps(self.arguments, ensure_ascii=False),
            },
        }
        if self.provider_specific_fields:
            tool_call["provider_specific_fields"] = self.provider_specific_fields
        if self.function_provider_specific_fields:
            tool_call["function"]["provider_specific_fields"] = (
                self.function_provider_specific_fields
            )
        return tool_call


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"  # 结束原因
    usage: dict[str, int] = field(default_factory=dict)  # tokens使用情况
    reasoning_content: str | None = None  # Kimi, DeepSeek-R1 etc.
    thinking_blocks: list[dict] | None = None  # Anthropic extended thinking

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass(frozen=True)
class GenerationSettings:
    """Default generation parameters for LLM calls.

    repositoryd on the provider so every call site inherits the same defaults
    without having to pass temperature / max_tokens / reasoning_effort
    through every layer.  Individual call sites can still override by
    passing explicit keyword arguments to chat() / chat_with_retry().
    """

    temperature: float = 0.7
    max_tokens: int = 8192  # 翻倍（原4096），CONFLICT_RESOLVE等大输出场景需要更多空间
    reasoning_effort: str | None = None  # 深度思考


class LLMProvider(ABC):
    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Yield raw provider SDK deltas; unsupported implementations fail explicitly."""
        raise NotImplementedError("This provider does not implement streaming")

    _SENTINEL = object()

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base
        self.generation: GenerationSettings = GenerationSettings()

    @staticmethod
    def _sanitize_empty_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize message content: fix empty blocks, strip internal _meta fields."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")

            if isinstance(content, str) and not content:
                clean = dict(msg)
                clean["content"] = (
                    None
                    if (msg.get("role") == "assistant" and msg.get("tool_calls"))
                    else "(empty)"
                )
                result.append(clean)
                continue

            if isinstance(content, list):
                new_items: list[Any] = []
                changed = False
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") in ("text", "input_text", "output_text")
                        and not item.get("text")
                    ):
                        changed = True
                        continue
                    if isinstance(item, dict) and "_meta" in item:
                        new_items.append({k: v for k, v in item.items() if k != "_meta"})
                        changed = True
                    else:
                        new_items.append(item)
                if changed:
                    clean = dict(msg)
                    if new_items:
                        clean["content"] = new_items
                    elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                        clean["content"] = None
                    else:
                        clean["content"] = "(empty)"
                    result.append(clean)
                    continue

            if isinstance(content, dict):
                clean = dict(msg)
                clean["content"] = [content]
                result.append(clean)
                continue

            result.append(msg)
        return result

    @staticmethod
    def _sanitize_request_messages(
        messages: list[dict[str, Any]],
        allowed_keys: frozenset[str],
    ) -> list[dict[str, Any]]:
        """Keep only provider-safe message keys and normalize assistant content."""
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in allowed_keys}
            if clean.get("role") == "assistant" and "content" not in clean:
                clean["content"] = None
            sanitized.append(clean)
        return sanitized

    @staticmethod
    def _validate_last_user_content_is_multimodal(messages: list[dict[str, Any]]) -> None:
        """Reject string content on the final user message.

        InboundMessage normalizes text to text blocks before provider calls. If a
        final user message reaches providers as a string, a caller bypassed that
        contract and may have stringified multimodal image blocks.
        """
        for msg in reversed(messages):
            if msg.get("role") == "user":
                if isinstance(msg.get("content"), str):
                    raise ValueError("last user message content must be a multimodal list, got str")
                return

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier (provider-specific).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            tool_choice: Tool selection strategy ("auto", "required", or specific tool dict).

        Returns:
            LLMResponse with content and/or tool calls.
        """
        pass

    @staticmethod
    def parse_tool_arguments(arguments):
        """Keep invalid or non-object JSON raw for the tool layer."""
        if not isinstance(arguments, str):
            return arguments
        try:
            parsed = json.loads(arguments)
        except (ValueError, TypeError):
            return arguments
        return parsed if isinstance(parsed, dict) else arguments

    def _normalize_error(self, error, *, model=None, phase="request", partial_output=False):
        from lifeprism.llm.providers.errors import classify_provider_error

        return classify_provider_error(
            error,
            provider=getattr(self, "provider_name", type(self).__name__),
            model=model or self.get_default_model(),
            phase=phase,
            partial_output=partial_output,
        )

    def _dump_request_error(self, error, *, model, phase, payload=None) -> None:
        """在请求失败时记录完整上下文，供定位网关返回的通用错误。

        网关常返回 ``Invalid request parameters`` 这类不含参数名的文案，只凭异常
        消息无法判断是哪个字段被拒绝。本方法同时留下我们发出的请求体与原始
        HTTP 响应，并把二者落一份 JSON 到 ``debug_logs/llm_errors/``。

        诊断失败不得改变异常传播，故整个方法体吞掉自身异常。

        Args:
            error: provider 调用抛出的原始异常（未包装的 SDK 异常优先）。
            model: 本次请求使用的模型名。
            phase: 失败阶段，``request`` / ``streaming`` / ``response``。
            payload: 本次请求的 kwargs，None 表示调用方未提供。
        """
        try:
            provider = getattr(self, "provider_name", type(self).__name__)
            response = getattr(error, "response", None)
            raw_text = None
            headers = None
            if response is not None:
                try:
                    raw_text = response.text
                except Exception as exc:
                    # 流式响应体可能已被消费，读不到原文时留下原因而不是静默丢失
                    raw_text = f"<unreadable: {type(exc).__name__}: {exc}>"
                try:
                    headers = dict(response.headers)
                except Exception:
                    headers = None
            status = getattr(error, "status_code", None)
            request_id = getattr(error, "request_id", None) or (headers or {}).get("x-request-id")
            body = getattr(error, "body", None)

            logger.error(
                "LLM 请求失败: provider=%s, model=%s, phase=%s, error=%s, "
                "status=%s, request_id=%s, body=%r, response_text=%r, payload_keys=%s",
                provider,
                model,
                phase,
                type(error).__name__,
                status,
                request_id,
                body,
                raw_text,
                sorted(payload) if isinstance(payload, dict) else None,
            )

            record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "provider": provider,
                "model": model,
                "phase": phase,
                "error": {
                    "type": type(error).__name__,
                    "repr": repr(error),
                    "str": str(error),
                    "status_code": status,
                    "request_id": request_id,
                    "body": _json_safe(body),
                    "cause": repr(error.__cause__) if error.__cause__ else None,
                },
                "raw_response_text": _json_safe(raw_text),
                "response_headers": _json_safe(headers),
                "request": _json_safe(payload),
            }
            self._write_error_dump(record)
        except Exception as exc:  # noqa: BLE001 — 诊断兜底，失败不得影响主流程
            logger.warning("落盘 LLM 请求失败诊断时出错: %s", exc, exc_info=True)

    def _write_error_dump(self, record: dict[str, Any]) -> None:
        """把一条失败诊断写入 ``debug_logs/llm_errors/llm_error_<时间戳>.json``。

        Args:
            record: 已转换为 JSON 安全结构的诊断记录。
        """
        # 延迟导入 settings：避免 provider 层在模块加载期就依赖 config，也避开导入顺序问题
        from lifeprism.config import settings

        dump_dir = settings.lifeprism_data_path / "debug_logs" / "llm_errors"
        dump_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        dump_file = dump_dir / f"llm_error_{stamp}.json"
        with open(dump_file, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, default=str)
        logger.error("LLM 请求失败诊断已落盘: %s", dump_file)

    async def _call_once(self, operation, *, model=None, payload=None):
        """执行一次 SDK 请求，失败时先落诊断再按统一策略转换异常。

        Args:
            operation: 待 await 的 SDK 请求协程。
            model: 本次请求使用的模型名。
            payload: 本次请求的 kwargs，用于失败时落盘完整请求体。
        """
        try:
            return await operation
        except Exception as error:
            self._dump_request_error(error, model=model, phase="request", payload=payload)
            converted = self._normalize_error(error, model=model)
            if converted is error:
                raise
            raise converted from error

    async def _stream_once(self, stream, *, model=None, payload=None):
        partial = False
        failed = False
        try:
            async for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if isinstance(chunk, dict):
                    choices = chunk.get("choices")
                for choice in choices or []:
                    delta = (
                        choice.get("delta", {})
                        if isinstance(choice, dict)
                        else getattr(choice, "delta", None)
                    )
                    if delta:
                        get = (
                            delta.get
                            if isinstance(delta, dict)
                            else lambda key, delta=delta: getattr(delta, key, None)
                        )
                        partial |= bool(
                            get("content") or get("reasoning_content") or get("tool_calls")
                        )
                yield chunk
        except BaseException as error:
            failed = True
            if isinstance(error, Exception):
                # CancelledError 等 BaseException 不是请求失败，不落诊断
                self._dump_request_error(error, model=model, phase="streaming", payload=payload)
            converted = self._normalize_error(
                error, model=model, phase="streaming", partial_output=partial
            )
            if converted is error:
                raise
            raise converted from error
        finally:
            close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
            if close:
                try:
                    await close()
                except BaseException:
                    if not failed:
                        raise

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: object = _SENTINEL,
        temperature: object = _SENTINEL,
        reasoning_effort: object = _SENTINEL,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Compatibility entry point: one call with generation defaults; loop owns retries.

        Parameters default to ``self.generation`` when not explicitly passed,
        so callers no longer need to thread temperature / max_tokens /
        reasoning_effort through every layer.
        """
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort

        kw: dict[str, Any] = dict(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        )

        return await self.chat(**kw)

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass
