"""QueryCustomRecordEntriesTool 单元测试

复现 bug：query_entries 返回 tuple(list, int)，Tool 层误当 list 处理，
遍历到 int 时触发 `argument of type 'int' is not iterable`。
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lifeprism.llm.agent.tools.base import ERROR, SUCCESS
from lifeprism.llm.agent.tools.custom_records_tool import QueryCustomRecordEntriesTool


@pytest.mark.core
class TestQueryCustomRecordEntriesTool:
    """QueryCustomRecordEntriesTool 测试类"""

    @pytest.mark.asyncio
    async def test_query_entries_handles_tuple_return(self):
        """复现 bug：repository.query_entries 返回 (list, int) 元组，Tool 应正确解包

        修复前：Tool 直接 `for entry in entries` 遍历元组，第二次迭代 entry 为 int，
        触发 `argument of type 'int' is not iterable`。
        """
        tool = QueryCustomRecordEntriesTool()

        # 模拟 repository.query_entries 的真实返回签名：tuple(list[dict], int)
        fake_entries = [
            {
                "id": "cre-abc12345",
                "event_time": "2026-07-24T02:45:00+00:00",
                "created_at": "2026-07-24T02:45:00+00:00",
                "updated_at": "2026-07-24T02:45:00+00:00",
                "amount": 100,
            },
            {
                "id": "cre-def67890",
                "event_time": "2026-07-23T10:00:00+00:00",
                "created_at": "2026-07-23T10:00:00+00:00",
                "updated_at": "2026-07-23T10:00:00+00:00",
                "amount": 50,
            },
        ]
        fake_total = 2

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.return_value = (fake_entries, fake_total)

            result = await tool.execute(type_id="crt-967af5cc", limit=50)

        # 不应以 ERROR 开头
        assert not result.startswith(ERROR), f"工具返回错误: {result}"
        assert result.startswith(SUCCESS)

        # 解析返回的 JSON
        payload = json.loads(result[len(SUCCESS):])
        # 修复后应返回 dict（含 entries 和 total），而非裸 list
        assert isinstance(payload, dict)
        assert payload["total"] == 2
        assert len(payload["entries"]) == 2
        # 时间字段应转换为本地显示格式（YYYY-MM-DD HH:MM:SS）
        assert payload["entries"][0]["event_time"] == "2026-07-24 10:45:00"

    @pytest.mark.asyncio
    async def test_query_entries_empty_result(self):
        """空结果场景：返回 (list, int=0) 元组"""
        tool = QueryCustomRecordEntriesTool()

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.return_value = ([], 0)

            result = await tool.execute(type_id="crt-967af5cc")

        assert result.startswith(SUCCESS)
        payload = json.loads(result[len(SUCCESS):])
        assert payload["total"] == 0
        assert payload["entries"] == []

    @pytest.mark.asyncio
    async def test_query_entries_missing_type_id(self):
        """缺少 type_id 参数应返回错误"""
        tool = QueryCustomRecordEntriesTool()

        result = await tool.execute()

        assert result.startswith(ERROR)
        assert "type_id" in result
