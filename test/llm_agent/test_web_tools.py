"""WebSearchTool / WebFetchTool 测试。

单元测试：mock 内部方法，不访问网络。
集成测试：标记 @pytest.mark.network，需真实网络，默认不运行。
运行集成测试：pytest -m network test/llm_agent/test_web_tools.py
"""
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifeprism.llm.agent.tools.web import (
    WebFetchTool,
    WebSearchTool,
    _format_results,
    _normalize,
    _strip_tags,
    _validate_url,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

class TestStripTags:

    def test_removes_basic_tags(self):
        assert _strip_tags("<b>hello</b>") == "hello"

    def test_removes_script_block(self):
        result = _strip_tags("<script>alert(1)</script>text")
        assert "alert" not in result
        assert "text" in result

    def test_removes_style_block(self):
        result = _strip_tags("<style>.cls{}</style>text")
        assert ".cls" not in result

    def test_decodes_html_entities(self):
        assert _strip_tags("&lt;p&gt;") == "<p>"
        assert _strip_tags("a &amp; b") == "a & b"


class TestNormalize:

    def test_collapses_multiple_spaces(self):
        assert _normalize("a  b   c") == "a b c"

    def test_collapses_tabs(self):
        assert _normalize("a\t\tb") == "a b"

    def test_collapses_multiple_blank_lines(self):
        result = _normalize("a\n\n\n\nb")
        assert result == "a\n\nb"


class TestValidateUrl:

    def test_valid_https(self):
        ok, _ = _validate_url("https://example.com/path")
        assert ok

    def test_valid_http(self):
        ok, _ = _validate_url("http://example.com")
        assert ok

    def test_rejects_ftp(self):
        ok, msg = _validate_url("ftp://example.com")
        assert not ok
        assert "http" in msg

    def test_rejects_no_domain(self):
        ok, msg = _validate_url("https://")
        assert not ok

    def test_rejects_empty(self):
        ok, _ = _validate_url("")
        assert not ok


class TestFormatResults:

    def test_empty_items(self):
        result = _format_results("q", [], 5)
        assert "No results" in result

    def test_formats_title_url_snippet(self):
        items = [{"title": "Test", "url": "https://example.com", "content": "snippet"}]
        result = _format_results("q", items, 5)
        assert "Test" in result
        assert "https://example.com" in result
        assert "snippet" in result

    def test_strips_html_in_title(self):
        items = [{"title": "<b>Bold</b>", "url": "https://x.com", "content": ""}]
        result = _format_results("q", items, 5)
        assert "<b>" not in result
        assert "Bold" in result

    def test_respects_n_limit(self):
        items = [{"title": str(i), "url": "https://x.com", "content": ""} for i in range(10)]
        result = _format_results("q", items, 3)
        assert "1." in result
        assert "4." not in result


# ---------------------------------------------------------------------------
# WebSearchTool 单元测试（mock 内部 _search_* 方法）
# ---------------------------------------------------------------------------

class TestWebSearchToolSchema:

    def test_name(self):
        assert WebSearchTool().name == "web_search"

    def test_required_fields(self):
        assert "query" in WebSearchTool().parameters["required"]

    def test_count_bounds(self):
        p = WebSearchTool().parameters["properties"]["count"]
        assert p["minimum"] == 1
        assert p["maximum"] == 10

    def test_to_schema_format(self):
        schema = WebSearchTool().to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "web_search"


class TestWebSearchToolRouting:
    """execute() 正确路由到对应 provider 方法。"""

    async def _run(self, tool: WebSearchTool, query: str = "test", count: int = 3) -> str:
        return await tool.execute(query=query, count=count)

    async def test_routes_to_duckduckgo(self):
        tool = WebSearchTool(provider="duckduckgo")
        with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="ddg")) as m:
            result = await self._run(tool)
        m.assert_called_once_with("test", 3)
        assert result == "ddg"

    async def test_routes_to_searxng(self):
        tool = WebSearchTool(provider="searxng", base_url="https://searx.example.com")
        with patch.object(tool, "_search_searxng", new=AsyncMock(return_value="searxng")) as m:
            result = await self._run(tool)
        m.assert_called_once()
        assert result == "searxng"

    async def test_unknown_provider_returns_error(self):
        tool = WebSearchTool(provider="unknown_xyz")
        result = await self._run(tool)
        assert "Error" in result
        assert "unknown_xyz" in result

    async def test_count_clamped_to_minimum(self):
        tool = WebSearchTool(provider="duckduckgo")
        with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="ok")) as m:
            await tool.execute(query="q", count=0)
        _, called_n = m.call_args.args
        assert called_n >= 1

    async def test_count_clamped_to_maximum(self):
        tool = WebSearchTool(provider="duckduckgo")
        with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="ok")) as m:
            await tool.execute(query="q", count=99)
        _, called_n = m.call_args.args
        assert called_n <= 10


class TestWebSearchFallback:
    """付费 provider 缺少 key 时自动 fallback 到 DuckDuckGo。"""

    async def test_brave_falls_back_without_key(self):
        tool = WebSearchTool(provider="brave", api_key="")
        with patch.dict("os.environ", {}, clear=False):
            # 确保环境变量里也没有 key
            import os
            os.environ.pop("BRAVE_API_KEY", None)
            with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="fallback")) as m:
                result = await tool.execute(query="q", count=3)
        assert result == "fallback"
        m.assert_called_once()

    async def test_tavily_falls_back_without_key(self):
        tool = WebSearchTool(provider="tavily", api_key="")
        import os
        os.environ.pop("TAVILY_API_KEY", None)
        with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="fallback")) as m:
            result = await tool.execute(query="q", count=3)
        assert result == "fallback"
        m.assert_called_once()

    async def test_jina_falls_back_without_key(self):
        tool = WebSearchTool(provider="jina", api_key="")
        import os
        os.environ.pop("JINA_API_KEY", None)
        with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="fallback")) as m:
            result = await tool.execute(query="q", count=3)
        assert result == "fallback"
        m.assert_called_once()

    async def test_searxng_falls_back_without_base_url(self):
        tool = WebSearchTool(provider="searxng", base_url="")
        import os
        os.environ.pop("SEARXNG_BASE_URL", None)
        with patch.object(tool, "_search_duckduckgo", new=AsyncMock(return_value="fallback")) as m:
            result = await tool.execute(query="q", count=3)
        assert result == "fallback"
        m.assert_called_once()


class TestDuckDuckGoUnit:
    """_search_duckduckgo 的单元测试（mock DDGS）。"""

    async def test_returns_formatted_results(self):
        tool = WebSearchTool()
        fake_results = [
            {"title": "Result 1", "href": "https://a.com", "body": "snippet a"},
            {"title": "Result 2", "href": "https://b.com", "body": "snippet b"},
        ]
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = fake_results
        with patch("ddgs.DDGS", return_value=mock_ddgs):
            result = await tool._search_duckduckgo("python", 2)
        assert "Result 1" in result
        assert "https://a.com" in result
        assert "snippet a" in result

    async def test_empty_results(self):
        tool = WebSearchTool()
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        with patch("ddgs.DDGS", return_value=mock_ddgs):
            result = await tool._search_duckduckgo("nothing", 5)
        assert "No results" in result

    async def test_ddgs_not_installed(self):
        tool = WebSearchTool()
        with patch.dict(sys.modules, {"ddgs": None}):
            result = await tool._search_duckduckgo("q", 3)
        assert "Error" in result
        assert "ddgs" in result.lower()


# ---------------------------------------------------------------------------
# WebFetchTool 单元测试
# ---------------------------------------------------------------------------

class TestWebFetchToolSchema:

    def test_name(self):
        assert WebFetchTool().name == "web_fetch"

    def test_required_fields(self):
        assert "url" in WebFetchTool().parameters["required"]

    def test_extract_mode_enum(self):
        p = WebFetchTool().parameters["properties"]["extractMode"]
        assert "markdown" in p["enum"]
        assert "text" in p["enum"]


class TestWebFetchUrlValidation:

    async def test_rejects_ftp_url(self):
        tool = WebFetchTool()
        import json
        result = json.loads(await tool.execute(url="ftp://example.com"))
        assert "error" in result

    async def test_rejects_no_scheme(self):
        tool = WebFetchTool()
        import json
        result = json.loads(await tool.execute(url="example.com/page"))
        assert "error" in result


class TestWebFetchReadability:
    """_fetch_readability 的单元测试（mock httpx）。"""

    def _make_mock_response(self, html: str, url: str = "https://example.com") -> MagicMock:
        resp = MagicMock()
        resp.text = html
        resp.url = url
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        return resp

    async def test_returns_text_content(self):
        tool = WebFetchTool()
        html = "<html><body><p>Hello world</p></body></html>"
        mock_resp = self._make_mock_response(html)
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await tool._fetch_readability("https://example.com", "text", 50000)
        import json
        data = json.loads(result)
        assert "Hello world" in data["text"]
        assert data["untrusted"] is True

    async def test_markdown_mode_preserves_links(self):
        tool = WebFetchTool()
        html = '<a href="https://link.com">Click here</a>'
        mock_resp = self._make_mock_response(html)
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await tool._fetch_readability("https://example.com", "markdown", 50000)
        import json
        data = json.loads(result)
        assert "https://link.com" in data["text"]
        assert "Click here" in data["text"]

    async def test_truncates_at_max_chars(self):
        tool = WebFetchTool()
        html = "<p>" + "x" * 1000 + "</p>"
        mock_resp = self._make_mock_response(html)
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await tool._fetch_readability("https://example.com", "text", 100)
        import json
        data = json.loads(result)
        assert data["truncated"] is True
        # banner 在截断后拼接，总长 = len(banner) + 2 + max_chars，只验证已截断即可

    async def test_untrusted_banner_prepended(self):
        tool = WebFetchTool()
        html = "<p>content</p>"
        mock_resp = self._make_mock_response(html)
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await tool._fetch_readability("https://example.com", "text", 50000)
        import json
        data = json.loads(result)
        assert data["text"].startswith("[External content")

    async def test_returns_error_on_exception(self):
        tool = WebFetchTool()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("connection refused")
            )
            result = await tool._fetch_readability("https://example.com", "text", 50000)
        import json
        data = json.loads(result)
        assert "error" in data


class TestToMarkdown:
    """_to_markdown 转换逻辑。"""

    def test_converts_heading(self):
        tool = WebFetchTool()
        result = tool._to_markdown("<h1>Title</h1>")
        assert "# Title" in result

    def test_converts_h2(self):
        tool = WebFetchTool()
        result = tool._to_markdown("<h2>Sub</h2>")
        assert "## Sub" in result

    def test_converts_list_item(self):
        tool = WebFetchTool()
        result = tool._to_markdown("<ul><li>item</li></ul>")
        assert "- item" in result

    def test_converts_link(self):
        tool = WebFetchTool()
        result = tool._to_markdown('<a href="https://x.com">click</a>')
        assert "[click](https://x.com)" in result

    def test_strips_remaining_tags(self):
        tool = WebFetchTool()
        result = tool._to_markdown("<div><span>text</span></div>")
        assert "<" not in result
        assert "text" in result


# ---------------------------------------------------------------------------
# 集成测试（真实网络，需要 -m network 才运行）
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestDuckDuckGoIntegration:

    async def test_returns_results_for_common_query(self):
        tool = WebSearchTool(provider="duckduckgo")
        result = await tool.execute(query="Python programming language", count=3)
        # DuckDuckGo 可能因限速返回空，只验证没有崩溃且包含查询词
        assert isinstance(result, str)
        assert "Python" in result or "No results" in result

    async def test_count_respected(self):
        tool = WebSearchTool(provider="duckduckgo")
        result = await tool.execute(query="openai", count=2)
        # 最多返回 2 条，验证第 3 条不存在
        assert "3." not in result


@pytest.mark.network
class TestWebFetchIntegration:

    async def test_fetches_plain_text_page(self):
        tool = WebFetchTool()
        import json
        result = json.loads(await tool.execute(url="https://example.com"))
        assert "text" in result
        assert len(result["text"]) > 0
        assert result["untrusted"] is True

    async def test_fetch_and_extract_markdown(self):
        tool = WebFetchTool()
        import json
        result = json.loads(await tool.execute(url="https://example.com", extractMode="markdown"))
        assert "text" in result




