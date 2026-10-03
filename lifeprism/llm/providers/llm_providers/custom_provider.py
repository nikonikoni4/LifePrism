"""Direct OpenAI-compatible provider — bypasses LiteLLM.
本文件部分代码源自 https://github.com/HKUDS/nanobot.git
Copyright (c) [2026.3.22] [HKUDS]
Licensed under the MIT License.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from lifeprism.llm.providers.errors import LLMProviderError
from lifeprism.llm.providers.llm_providers.base import LLMProvider, LLMResponse, ToolCallRequest


class CustomProvider(LLMProvider):
    def __init__(
        self,
        api_key: str = "no-key",
        api_base: str = "http://localhost:8000/v1",
        default_model: str = "default",
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        # Keep affinity stable for this provider instance to improve backend cache locality,
        # while still letting users attach provider-specific headers for custom gateways.
        default_headers = {
            "x-session-affinity": uuid.uuid4().hex,
            **(extra_headers or {}),
        }
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            default_headers=default_headers,
            max_retries=0,
        )

    def _build_chat_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the request kwargs shared by chat() and stream_chat().

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier; falls back to the default model.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            reasoning_effort: Optional reasoning effort hint.
            tool_choice: Tool selection strategy ("auto", "required", or specific tool dict).

        Returns:
            dict: Keyword arguments for the chat completions request.

        Raises:
            ValueError: When the last user message content is a string.
        """
        self._validate_last_user_content_is_multimodal(messages)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs.update(tools=tools, tool_choice=tool_choice or "auto")
        return kwargs

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
        kwargs = self._build_chat_kwargs(
            messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        )
        request_model = kwargs["model"]
        response = await self._call_once(
            self._client.chat.completions.create(**kwargs), model=request_model
        )
        return self._parse(response, model=request_model)

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        """Stream a chat completion, yielding raw SDK chunks without parsing.

        Exceptions propagate unchanged; no retry is attempted. The underlying
        stream is always closed, including on cancellation.

        Yields:
            Raw chunk objects from the OpenAI-compatible streaming API.
        """
        kwargs = self._build_chat_kwargs(
            messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        )
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        request_model = kwargs["model"]
        stream = await self._call_once(
            self._client.chat.completions.create(**kwargs), model=request_model
        )
        wrapped = self._stream_once(stream, model=request_model)
        try:
            async for chunk in wrapped:
                yield chunk
        finally:
            await wrapped.aclose()

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

        Also handles incomplete XML (truncated) where </tool_call> is missing.
        Uses non-greedy matching for parameter values so `<` characters in content
        (e.g. Markdown links like `` [AI](https://example.com) ``) are correctly parsed.
        """
        tool_calls = []

        # First pass: try strict pattern (complete <tool_call>...</tool_call>)
        tool_call_pattern = r"<tool_call>(.*?)</tool_call>"
        matches = re.findall(tool_call_pattern, content, re.DOTALL)

        # Second pass (fallback): if no complete blocks found, try incomplete/truncated
        if not matches and "<tool_call>" in content:
            tool_call_fallback = r"<tool_call>(.*)"
            matches = re.findall(tool_call_fallback, content, re.DOTALL)

        for match in matches:
            func_match = re.search(r"<function=([^>]+)>", match)
            if not func_match:
                continue

            function_name = func_match.group(1)

            # Extract all parameters using non-greedy matching
            param_pattern = r"<parameter=([^>]+)>(.*?)</parameter>"
            params = re.findall(param_pattern, match, re.DOTALL)

            arguments = {}
            for param_name, param_value in params:
                param_value = param_value.strip()
                if param_value.lower() in ("true", "false"):
                    arguments[param_name] = param_value.lower() == "true"
                elif param_value.isdigit():
                    arguments[param_name] = int(param_value)
                else:
                    try:
                        arguments[param_name] = float(param_value)
                    except ValueError:
                        arguments[param_name] = param_value

            tool_calls.append(
                ToolCallRequest(
                    id=str(uuid.uuid4())[:9],
                    name=function_name,
                    arguments=arguments,
                )
            )

        return tool_calls

    def _invalid_response(self, reason: str, model: str | None = None) -> LLMProviderError:
        return LLMProviderError(
            f"invalid provider response: {reason}",
            kind="invalid_response",
            reason=reason,
            provider=getattr(self, "provider_name", type(self).__name__),
            model=model or self.default_model,
            phase="response",
        )

    def _parse(self, response: Any, model: str | None = None) -> LLMResponse:
        if not response.choices:
            raise self._invalid_response("empty_choices", model)
        choice = response.choices[0]
        msg = choice.message
        content = msg.content
        finish_reason = choice.finish_reason
        if not finish_reason:
            raise self._invalid_response("missing_finish_reason", model)

        tool_calls = [
            ToolCallRequest(
                id=tc.id,
                name=tc.function.name,
                arguments=self.parse_tool_arguments(tc.function.arguments),
            )
            for tc in (msg.tool_calls or [])
        ]

        # Handle XML-format tool calls (MIMO, MiniMax, etc.)
        # If finish_reason is 'tool_calls' or 'stop' but native tool_calls is empty,
        # and content contains XML-format tool calls, parse them from content.
        if (
            finish_reason in ("tool_calls", "stop")
            and not tool_calls
            and content
            and "<tool_call>" in content
        ):
            xml_tool_calls = self._parse_xml_tool_calls(content)
            if xml_tool_calls:
                tool_calls = xml_tool_calls
                content = None  # Clear content since it was a tool call, not text

        u = response.usage
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
                "total_tokens": u.total_tokens,
            }
            if u
            else {},
            reasoning_content=getattr(msg, "reasoning_content", None) or None,
        )

    def get_default_model(self) -> str:
        return self.default_model
