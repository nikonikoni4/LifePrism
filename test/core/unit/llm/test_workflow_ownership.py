"""生产 InboundMessage 构造的 workflow_id 归属测试

用 AST 读取生产源码，确认每一处 InboundMessage 构造都显式携带预期
workflow_id 字面量。测试不导入生产模块，只做静态结构校验。

覆盖范围：
- lifeprism/llm/classify/classify_graph.py      全部构造 -> classify-graph
- lifeprism/llm/classify/classify_simple.py             -> classify-simple
- lifeprism/llm/function/agent_schedule_job.py  记忆任务 -> daily-memory，聊天提取 -> chat-extraction
- lifeprism/llm/function/diary_summary.py               -> diary-summary
- lifeprism/llm/function/screenshot_analysis.py  第一个 -> screenshot-analysis
                                                 第二个 -> behavior-summary
- lifeprism/sync/sync_client.py CONFLICT_RESOLVE        -> file-conflict-resolve

TDD: 先 RED（缺少 workflow_id 字段），接线后 GREEN。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.core


def _repo_root() -> Path:
    """向上查找包含 pyproject.toml 的仓库根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("未找到仓库根目录（pyproject.toml）")


REPO_ROOT = _repo_root()


# 每个文件按源码顺序列出预期 workflow_id
EXPECTED_OWNERSHIP: dict[str, list[str]] = {
    "lifeprism/llm/classify/classify_graph.py": [
        "classify-graph",
        "classify-graph",
        "classify-graph",
        "classify-graph",
        "classify-graph",
    ],
    "lifeprism/llm/classify/classify_simple.py": [
        "classify-simple",
    ],
    "lifeprism/llm/function/agent_schedule_job.py": [
        "daily-memory",
        "daily-memory",
        "daily-memory",
        "chat-extraction",
    ],
    "lifeprism/llm/function/diary_summary.py": [
        "diary-summary",
    ],
    "lifeprism/llm/function/screenshot_analysis.py": [
        "screenshot-analysis",
        "behavior-summary",
    ],
    "lifeprism/sync/sync_client.py": [
        "file-conflict-resolve",
    ],
}


def _collect_inbound_calls(tree: ast.AST) -> list[ast.Call]:
    """按源码顺序收集所有 InboundMessage(...) 调用节点。"""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_inbound = (isinstance(func, ast.Name) and func.id == "InboundMessage") or (
            isinstance(func, ast.Attribute) and func.attr == "InboundMessage"
        )
        if is_inbound:
            calls.append(node)
    calls.sort(key=lambda c: (c.lineno, c.col_offset))
    return calls


def _keyword_value(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _literal_str(call: ast.Call, name: str) -> str | None:
    """取出关键字参数的字面量字符串；非字面量字符串返回 None。"""
    value = _keyword_value(call, name)
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


@pytest.fixture(scope="module")
def parsed_sources() -> dict[str, list[ast.Call]]:
    result: dict[str, list[ast.Call]] = {}
    for rel_path in EXPECTED_OWNERSHIP:
        source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        result[rel_path] = _collect_inbound_calls(ast.parse(source, filename=rel_path))
    return result


@pytest.mark.parametrize("rel_path", list(EXPECTED_OWNERSHIP))
def test_inbound_message_count(parsed_sources, rel_path: str) -> None:
    """每个文件的生产 InboundMessage 构造数量必须与预期一致。"""
    expected = EXPECTED_OWNERSHIP[rel_path]
    actual = parsed_sources[rel_path]
    assert len(actual) == len(expected), (
        f"{rel_path}: 预期 {len(expected)} 处 InboundMessage 构造，"
        f"实际 {len(actual)} 处（行号 {[c.lineno for c in actual]}）"
    )


@pytest.mark.parametrize("rel_path", list(EXPECTED_OWNERSHIP))
def test_inbound_message_has_workflow_id(parsed_sources, rel_path: str) -> None:
    """每处构造都必须携带 workflow_id 关键字参数。"""
    missing = [
        call.lineno
        for call in parsed_sources[rel_path]
        if _keyword_value(call, "workflow_id") is None
    ]
    assert not missing, f"{rel_path}: 以下行缺少 workflow_id -> {missing}"


@pytest.mark.parametrize("rel_path", list(EXPECTED_OWNERSHIP))
def test_inbound_message_workflow_id_is_expected_literal(parsed_sources, rel_path: str) -> None:
    """每处构造的 workflow_id 必须是预期字面量，且顺序与预期一致。"""
    expected = EXPECTED_OWNERSHIP[rel_path]
    calls = parsed_sources[rel_path]
    assert len(calls) == len(expected), f"{rel_path}: 构造数量与预期不一致，无法比对顺序"

    actual = [_literal_str(call, "workflow_id") for call in calls]
    for call, got, want in zip(calls, actual, expected):
        assert got == want, f"{rel_path}:{call.lineno}: workflow_id 预期 {want!r}，实际 {got!r}"
