"""原生工具默认 vec，明确关键词才启用 BM25。"""

import importlib
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.core


@pytest.mark.asyncio
async def test_default_vec_and_explicit_bm25_parameter():
    module = importlib.import_module("lifeprism.llm.runtime_tools.rag_tool")
    calls = []

    async def search(query, k, use_bm25=False):
        calls.append((query, k, use_bm25))
        return []

    tool = module.RagSearchTool(SimpleNamespace(search=search))
    assert tool.parameters["properties"]["use_bm25"]["default"] is False
    assert "明确关键词" in tool.description
    await tool.execute("最近的状态")
    await tool.execute("LifePrism", use_bm25=True)
    assert calls == [("最近的状态", 5, False), ("LifePrism", 5, True)]
