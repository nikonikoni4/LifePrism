"""Capture MiMo SSE before parsing and replay it through the production adapter.

Run explicitly with --live; pytest cases use synthetic chunks and make no API calls.
Tools are never executed. Captures contain synthetic prompts, not credentials.
"""

import argparse
import asyncio
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


def adapter_class():
    # Loading the leaf avoids runtime/__init__.py starting unrelated services.
    spec = importlib.util.spec_from_file_location(
        "mimo_diagnostic_adapter", ROOT / "lifeprism/llm/runtime/provider.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ProviderAdapter


async def replay(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    from myagent.agent.core.provider import LLMResponse, Message

    from lifeprism.llm.providers.llm_providers.base import GenerationSettings
    from lifeprism.llm.providers.llm_providers.custom_provider import CustomProvider

    class CapturedProvider:
        generation = GenerationSettings()
        _parse_xml_tool_calls = staticmethod(CustomProvider._parse_xml_tool_calls)

        def get_default_model(self) -> str:
            return "mimo-v2.5"

        async def stream_chat(self, **kwargs):
            for chunk in chunks:
                yield chunk

    async for item in adapter_class()(CapturedProvider()).stream_chat(
        [Message(role="user", content="synthetic replay")]
    ):
        if isinstance(item, LLMResponse):
            return {
                "content": item.content,
                "finish_reason": item.finish_reason,
                "tool_calls": [call.to_dict() for call in item.tool_call_requests],
            }
    raise AssertionError("No final response")


def inspect_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    events = []
    ids_by_index: dict[Any, list[str]] = {}
    for position, chunk in enumerate(chunks):
        for choice in chunk.get("choices", []):
            for call in choice.get("delta", {}).get("tool_calls", []) or []:
                index = call.get("index")
                call_id = call.get("id")
                if call_id and call_id not in ids_by_index.setdefault(index, []):
                    ids_by_index[index].append(call_id)
                events.append({"chunk": position, **call})
    return {
        "tool_deltas": events,
        "index_conflicts": {str(index): ids for index, ids in ids_by_index.items() if len(ids) > 1},
    }


def invalid_arguments(result: dict[str, Any]) -> list[str]:
    invalid = []
    for call in result["tool_calls"]:
        try:
            value = json.loads(call["function"]["arguments"])
            if not isinstance(value, dict):
                invalid.append(call["id"])
        except json.JSONDecodeError:
            invalid.append(call["id"])
    return invalid


def delta(call: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"delta": {"tool_calls": [call]}}]}


@pytest.mark.debug
def test_distinct_indices_remain_separate():
    chunks = [
        delta({"index": 0, "id": "a", "function": {"name": "first", "arguments": "{}"}}),
        delta({"index": 1, "id": "b", "function": {"name": "second", "arguments": "{}"}}),
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    ]
    result = asyncio.run(replay(chunks))
    assert [c["function"]["name"] for c in result["tool_calls"]] == ["first", "second"]
    assert not inspect_chunks(chunks)["index_conflicts"]


@pytest.mark.debug
def test_reused_index_reproduces_observed_merge():
    chunks = [
        delta(
            {
                "index": 0,
                "id": "a",
                "function": {"name": "query_user_mood", "arguments": '{"by_mood_type_id": '},
            }
        ),
        delta(
            {
                "index": 0,
                "id": "b",
                "function": {"name": "query_custom_record_entries", "arguments": '{"limit": 10}'},
            }
        ),
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    ]
    result = asyncio.run(replay(chunks))
    assert inspect_chunks(chunks)["index_conflicts"] == {"0": ["a", "b"]}
    assert (
        result["tool_calls"][0]["function"]["name"] == "query_user_moodquery_custom_record_entries"
    )
    assert result["tool_calls"][0]["id"] == "b"
    assert invalid_arguments(result) == ["b"]


async def live(repeats: int) -> None:
    from lifeprism.llm.providers.llm_providers.build_llm_client import create_llm_client

    provider = create_llm_client()
    if provider.get_default_model() != "mimo-v2.5":
        raise RuntimeError("Current model must be mimo-v2.5 for this diagnostic")
    source = json.loads(
        (ROOT / "localData/debug_logs/llm_errors/llm_error_20261008_074137_112.json").read_text(
            encoding="utf-8"
        )
    )
    names = {"query_user_mood", "query_custom_record_entries"}
    tools = [t for t in source["request"]["tools"] if t["function"]["name"] in names]
    prompt = (
        "这是合成数据测试，请直接调用工具，不要先回答或追问。一次发起以下五个调用："
        "1. query_user_mood，by_mood_type_id=joy，start_time=2026-09-01 00:00:00，end_time=2026-10-08 15:21:31。"
        "2. query_custom_record_entries，type_id=crt-967af5cc，date_range=[2026-09-01,2026-10-08]，limit=10。"
        "3. 同一工具，type_id=crt-df3979d5，limit=5。"
        "4. 同一工具，type_id=crt-fd530ed1，filters=[{field_key:duration_min,op:gte,value:15}]。"
        "5. 同一工具，type_id=crt-21c31ee6，date_range=[2026-09-01,2026-10-08]。"
    )
    folder = (
        ROOT
        / "localData/debug_logs/mimo_stream_diagnostic"
        / datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    )
    folder.mkdir(parents=True)
    summaries = []
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            for mode in ("default", "disabled"):
                for run in range(repeats):
                    request = {
                        "model": provider.get_default_model(),
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}]}
                        ],
                        "tools": tools,
                        "tool_choice": "auto",
                        "temperature": 0.7,
                        "max_tokens": 1536,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    }
                    if mode == "disabled":
                        request["thinking"] = {"type": "disabled"}
                    stem = f"{mode}_{run + 1}"
                    (folder / f"{stem}_request.json").write_text(
                        json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    chunks = []
                    summary = {"mode": mode, "run": run + 1}
                    try:
                        async with client.stream(
                            "POST",
                            str(provider._client.base_url).rstrip("/") + "/chat/completions",
                            headers={"Authorization": f"Bearer {provider._client.api_key}"},
                            json=request,
                        ) as response:
                            summary["status"] = response.status_code
                            # Save SSE lines before JSON parsing or production aggregation.
                            with (folder / f"{stem}_raw.sse").open("w", encoding="utf-8") as raw:
                                async for line in response.aiter_lines():
                                    raw.write(line + "\n")
                                    raw.flush()
                                    if line.startswith("data:"):
                                        data = line[5:].strip()
                                        if data and data != "[DONE]":
                                            chunks.append(json.loads(data))
                        if summary["status"] == 200:
                            analysis = inspect_chunks(chunks)
                            result = await replay(chunks)
                            analysis["adapter_result"] = result
                            (folder / f"{stem}_analysis.json").write_text(
                                json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
                            )
                            summary.update(
                                index_conflicts=analysis["index_conflicts"],
                                invalid_arguments=invalid_arguments(result),
                                tool_names=[c["function"]["name"] for c in result["tool_calls"]],
                                finish_reason=result["finish_reason"],
                            )
                    except (httpx.HTTPError, ValueError, AssertionError) as exc:
                        summary["error_type"] = type(exc).__name__
                    summaries.append(summary)
                    print(json.dumps(summary, ensure_ascii=False), flush=True)
                    (folder / "summary.json").write_text(
                        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
        print(f"Captures: {folder}", flush=True)
    finally:
        await provider._client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--repeats", type=int, default=2, choices=range(1, 6))
    args = parser.parse_args()
    if not args.live:
        parser.error("Use pytest for offline checks, or --live for API calls")
    asyncio.run(live(args.repeats))
