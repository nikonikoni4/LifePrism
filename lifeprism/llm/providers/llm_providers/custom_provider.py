"""Direct OpenAI-compatible provider — bypasses LiteLLM.
本文件部分代码源自 https://github.com/HKUDS/nanobot.git
Copyright (c) [2026.3.22] [HKUDS]
Licensed under the MIT License.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import json_repair
from openai import AsyncOpenAI

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
        )

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
        try:
            return self._parse(await self._client.chat.completions.create(**kwargs))
        except Exception as e:
            # JSONDecodeError.doc / APIError.response.text may carry the raw body
            # (e.g. "unsupported model: xxx") which is far more useful than the
            # generic "Expecting value …" message.  Truncate to avoid huge HTML pages.
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(content=f"Error: {body.strip()[:500]}", finish_reason="error")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

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
        tool_calls = []
        tool_call_pattern = r"<tool_call>(.*?)</tool_call>"
        matches = re.findall(tool_call_pattern, content, re.DOTALL)

        for match in matches:
            func_match = re.search(r"<function=([^>]+)>", match)
            if not func_match:
                continue

            function_name = func_match.group(1)

            param_pattern = r"<parameter=([^>]+)>([^<]*)</parameter>"
            params = re.findall(param_pattern, match)

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

    def _parse(self, response: Any) -> LLMResponse:
        if not response.choices:
            return LLMResponse(
                content="Error: API returned empty choices. This may indicate a temporary service issue or an invalid model response.",
                finish_reason="error",
            )
        choice = response.choices[0]
        msg = choice.message
        content = msg.content
        finish_reason = choice.finish_reason

        tool_calls = [
            ToolCallRequest(
                id=tc.id,
                name=tc.function.name,
                arguments=json_repair.loads(tc.function.arguments)
                if isinstance(tc.function.arguments, str)
                else tc.function.arguments,
            )
            for tc in (msg.tool_calls or [])
        ]

        # Handle XML-format tool calls (MIMO, MiniMax, etc.)
        # If finish_reason is 'tool_calls' but native tool_calls is empty,
        # and content contains XML-format tool calls, parse them from content.
        if (
            finish_reason == "tool_calls"
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
            finish_reason=finish_reason or "stop",
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
