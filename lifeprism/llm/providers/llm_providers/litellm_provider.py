"""LiteLLM provider implementation for multi-provider support.
本文件部分代码源自 https://github.com/HKUDS/nanobot.git
Copyright (c) [2026.3.22] [HKUDS]
Licensed under the MIT License.
"""

import hashlib
import os
import secrets
import string
from typing import Any

import json_repair
import litellm
from litellm import acompletion
from lifeprism.utils import get_logger

from lifeprism.llm.providers.llm_providers.base import LLMProvider, LLMResponse, ToolCallRequest
from lifeprism.llm.providers.llm_providers.registry import find_by_model, find_gateway
logger = get_logger(__name__)

# Standard chat-completion message keys.
_ALLOWED_MSG_KEYS = frozenset({"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"})
_ANTHROPIC_EXTRA_KEYS = frozenset({"thinking_blocks"})
_ALNUM = string.ascii_letters + string.digits

def _short_tool_id() -> str:
    """Generate a 9-char alphanumeric ID compatible with all providers (incl. Mistral)."""
    return "".join(secrets.choice(_ALNUM) for _ in range(9))


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """

    def __init__(
        self,
        api_key: str ,
        api_base: str ,
        default_model: str ,
        provider_name: str ,
        extra_headers: dict[str, str] | None = None,
        
    ):
        """
        args:
            为了简化代码逻辑, 将api_key ，api_base，default_model，provider_name都设置为非空

            provider_name : llm 提供商
                在nanobot中：provider_name的作用
                通过 self._gateway 影响了 至少 8 个不同的行为：

                环境变量名 → 写入哪个 XXX_API_KEY
                覆盖策略 → 是否覆盖已有环境变量
                模型前缀 → 给 litellm 发什么模型名
                前缀剥离 → 是否先清理原有前缀
                Prompt Caching → 是否注入 

                cache_control
                额外请求参数 → 网关特有的 litellm_kwargs
                消息字段过滤 → 保留哪些非标准字段（如 thinking_blocks）
                参数覆盖 → 对某些模型强制设定 temperature 等

                在lifeprism中，由于不是从环境中读取，而是从keyring中读取，而且LiteLLMProvider没有设置llm 元信息的权利
                所有在lifeprism中，provider_name的作用：
                1. 继承nanobot的能力：
                    模型前缀 → 给 litellm 发什么模型名
                    前缀剥离 → 是否先清理原有前缀
                    Prompt Caching → 是否注入 

                    cache_control
                    额外请求参数 → 网关特有的 litellm_kwargs
                    消息字段过滤 → 保留哪些非标准字段（如 thinking_blocks）
                    参数覆盖 → 对某些模型强制设定 temperature 等

        """
        super().__init__(api_key, api_base)
        
        self.extra_headers = extra_headers or {}

        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        self.default_model =  default_model
        if api_base:
            litellm.api_base = api_base

        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True

        self._langsmith_enabled = bool(os.getenv("LANGSMITH_API_KEY"))

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix:
                model = f"{prefix}/{model}"
            return model

        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            model = self._canonicalize_explicit_prefix(model, spec.name, spec.litellm_prefix)
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    @staticmethod
    def _canonicalize_explicit_prefix(model: str, spec_name: str, canonical_prefix: str) -> str:
        """Normalize explicit provider prefixes like `github-copilot/...`."""
        if "/" not in model:
            return model
        prefix, remainder = model.split("/", 1)
        if prefix.lower().replace("-", "_") != spec_name:
            return model
        return f"{canonical_prefix}/{remainder}"

    def _supports_cache_control(self, model: str) -> bool:
        """Return True when the provider supports cache_control on content blocks."""
        if self._gateway is not None:
            return self._gateway.supports_prompt_caching
        spec = find_by_model(model)
        return spec is not None and spec.supports_prompt_caching

    def _apply_cache_control(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Return copies of messages and tools with cache_control injected."""
        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    new_content = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
                else:
                    new_content = list(content)
                    new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
                new_messages.append({**msg, "content": new_content})
            else:
                new_messages.append(msg)

        new_tools = tools
        if tools:
            new_tools = list(tools)
            new_tools[-1] = {**new_tools[-1], "cache_control": {"type": "ephemeral"}}

        return new_messages, new_tools

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    @staticmethod
    def _extra_msg_keys(original_model: str, resolved_model: str) -> frozenset[str]:
        """Return provider-specific extra keys to preserve in request messages."""
        spec = find_by_model(original_model) or find_by_model(resolved_model)
        if (spec and spec.name == "anthropic") or "claude" in original_model.lower() or resolved_model.startswith("anthropic/"):
            return _ANTHROPIC_EXTRA_KEYS
        return frozenset()

    @staticmethod
    def _normalize_tool_call_id(tool_call_id: Any) -> Any:
        """Normalize tool_call_id to a provider-safe 9-char alphanumeric form."""
        if not isinstance(tool_call_id, str):
            return tool_call_id
        if len(tool_call_id) == 9 and tool_call_id.isalnum():
            return tool_call_id
        return hashlib.sha1(tool_call_id.encode()).hexdigest()[:9]

    @staticmethod
    def _sanitize_messages(messages: list[dict[str, Any]], extra_keys: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
        """Strip non-standard keys and ensure assistant messages have a content key."""
        allowed = _ALLOWED_MSG_KEYS | extra_keys
        sanitized = LLMProvider._sanitize_request_messages(messages, allowed)
        id_map: dict[str, str] = {}

        def map_id(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            return id_map.setdefault(value, LiteLLMProvider._normalize_tool_call_id(value))

        for clean in sanitized:
            # Keep assistant tool_calls[].id and tool tool_call_id in sync after
            # shortening, otherwise strict providers reject the broken linkage.
            if isinstance(clean.get("tool_calls"), list):
                normalized_tool_calls = []
                for tc in clean["tool_calls"]:
                    if not isinstance(tc, dict):
                        normalized_tool_calls.append(tc)
                        continue
                    tc_clean = dict(tc)
                    tc_clean["id"] = map_id(tc_clean.get("id"))
                    normalized_tool_calls.append(tc_clean)
                clean["tool_calls"] = normalized_tool_calls

            if "tool_call_id" in clean and clean["tool_call_id"]:
                clean["tool_call_id"] = map_id(clean["tool_call_id"])
        return sanitized

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
        Send a chat completion request via LiteLLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5'). 为None时使用spec中指定的默认模型
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        self._validate_last_user_content_is_multimodal(messages)
        original_model = model or self.default_model
        model = self._resolve_model(original_model)
        extra_msg_keys = self._extra_msg_keys(original_model, model)

        if self._supports_cache_control(original_model):
            messages, tools = self._apply_cache_control(messages, tools)

        # Clamp max_tokens to at least 1 — negative or zero values cause
        # LiteLLM to reject the request with "max_tokens must be at least 1".
        max_tokens = max(1, max_tokens)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._sanitize_messages(self._sanitize_empty_content(messages), extra_keys=extra_msg_keys),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if self._gateway:
            kwargs.update(self._gateway.litellm_kwargs)

        # Apply model-specific overrides (e.g. kimi-k2.5 temperature)
        self._apply_model_overrides(model, kwargs)

        if self._langsmith_enabled:
            kwargs.setdefault("callbacks", []).append("langsmith")

        # Pass api_key directly — more reliable than env vars alone
        if self.api_key:
            kwargs["api_key"] = self.api_key

        # Pass api_base for custom endpoints
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # Pass extra headers (e.g. APP-Code for AiHubMix)
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
            kwargs["drop_params"] = True
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            # Return error as content for graceful handling
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    @staticmethod
    def _parse_xml_tool_calls(content: str) -> list[ToolCallRequest]:
        """Parse XML-format tool calls from content (for MIMO and similar models).

        Handles formats like:
        <tool_call>
        <function=read_file>
        <parameter=file_path>path/to/file</parameter>
        <parameter=offset>1</parameter>
        </function>
        </tool_call>
        """
        import re

        tool_calls = []
        # Match <tool_call>...</tool_call> blocks
        tool_call_pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(tool_call_pattern, content, re.DOTALL)

        for match in matches:
            # Extract function name from <function=name>
            func_match = re.search(r'<function=([^>]+)>', match)
            if not func_match:
                continue

            function_name = func_match.group(1)

            # Extract all parameters
            param_pattern = r'<parameter=([^>]+)>([^<]*)</parameter>'
            params = re.findall(param_pattern, match)

            # Build arguments dict
            arguments = {}
            for param_name, param_value in params:
                # Try to parse as JSON if it looks like a number or boolean
                param_value = param_value.strip()
                if param_value.lower() in ('true', 'false'):
                    arguments[param_name] = param_value.lower() == 'true'
                elif param_value.isdigit():
                    arguments[param_name] = int(param_value)
                else:
                    try:
                        arguments[param_name] = float(param_value)
                    except ValueError:
                        arguments[param_name] = param_value

            tool_calls.append(ToolCallRequest(
                id=_short_tool_id(),
                name=function_name,
                arguments=arguments,
            ))

        return tool_calls

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        content = message.content
        finish_reason = choice.finish_reason

        # Some providers (e.g. GitHub Copilot) split content and tool_calls
        # across multiple choices. Merge them so tool_calls are not lost.
        raw_tool_calls = []
        for ch in response.choices:
            msg = ch.message
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                raw_tool_calls.extend(msg.tool_calls)
                if ch.finish_reason in ("tool_calls", "stop"):
                    finish_reason = ch.finish_reason
            if not content and msg.content:
                content = msg.content

        if len(response.choices) > 1:
            logger.debug("LiteLLM response has {} choices, merged {} tool_calls",
                         len(response.choices), len(raw_tool_calls))

        tool_calls = []
        for tc in raw_tool_calls:
            # Parse arguments from JSON string if needed
            args = tc.function.arguments
            if isinstance(args, str):
                args = json_repair.loads(args)

            provider_specific_fields = getattr(tc, "provider_specific_fields", None) or None
            function_provider_specific_fields = (
                getattr(tc.function, "provider_specific_fields", None) or None
            )

            tool_calls.append(ToolCallRequest(
                id=_short_tool_id(),
                name=tc.function.name,
                arguments=args,
                provider_specific_fields=provider_specific_fields,
                function_provider_specific_fields=function_provider_specific_fields,
            ))

        # Handle XML-format tool calls (MIMO, MiniMax, etc.)
        # If finish_reason is 'tool_calls' but tool_calls is empty, and content contains XML tool calls
        if finish_reason == "tool_calls" and not tool_calls and content and "<tool_call>" in content:
            logger.debug("Detected XML-format tool calls in content, parsing...")
            xml_tool_calls = self._parse_xml_tool_calls(content)
            if xml_tool_calls:
                tool_calls = xml_tool_calls
                content = None  # Clear content since it was a tool call, not text

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None) or None
        thinking_blocks = getattr(message, "thinking_blocks", None) or None

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
