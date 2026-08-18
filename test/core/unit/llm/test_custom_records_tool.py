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
from lifeprism.utils.exceptions import ValidationError


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


# ==================== filters 字段级过滤测试（2026-08-18 新增） ====================


@pytest.mark.core
class TestQueryEntriesFilters:
    """QueryCustomRecordEntriesTool filters 参数测试"""

    @pytest.mark.asyncio
    async def test_filters_passed_through_to_repository(self):
        """filters 参数应原样透传给 repository.query_entries"""
        tool = QueryCustomRecordEntriesTool()
        filters = [{"field_key": "heart_rate", "op": "gt", "value": 100}]

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.return_value = ([], 0)

            result = await tool.execute(type_id="crt-abc12345", filters=filters)

        assert result.startswith(SUCCESS)
        mock_repo.query_entries.assert_called_once()
        call_kwargs = mock_repo.query_entries.call_args.kwargs
        assert call_kwargs["filters"] == filters
        assert call_kwargs["type_id"] == "crt-abc12345"

    @pytest.mark.asyncio
    async def test_filters_omitted_passes_none(self):
        """不传 filters：透传 None（向后兼容）"""
        tool = QueryCustomRecordEntriesTool()

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.return_value = ([], 0)

            await tool.execute(type_id="crt-abc12345")

        call_kwargs = mock_repo.query_entries.call_args.kwargs
        assert call_kwargs["filters"] is None

    @pytest.mark.asyncio
    async def test_filters_not_list_returns_plain_error(self):
        """filters 非数组：返回普通错误提示（非 JSON）"""
        tool = QueryCustomRecordEntriesTool()

        result = await tool.execute(type_id="crt-abc12345", filters={"field_key": "x"})

        assert result.startswith(ERROR)
        assert "filters" in result

    @pytest.mark.asyncio
    async def test_invalid_field_key_returns_structured_error(self):
        """field_key 无效：ValidationError 转为结构化 JSON（含 valid_fields）"""
        tool = QueryCustomRecordEntriesTool()

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.side_effect = ValidationError(
                message="过滤字段不存在: wrong_field",
                code="INVALID_FIELD_KEY",
                details={
                    "invalid_keys": ["wrong_field"],
                    "valid_fields": [
                        {"field_key": "heart_rate", "field_name": "心率(bpm)", "field_type": "integer"}
                    ],
                },
            )

            result = await tool.execute(
                type_id="crt-abc12345",
                filters=[{"field_key": "wrong_field", "op": "eq", "value": 1}],
            )

        assert result.startswith(ERROR)
        payload = json.loads(result[len(ERROR):])
        assert payload["error"] == "INVALID_FIELD_KEY"
        assert payload["valid_fields"][0]["field_key"] == "heart_rate"

    @pytest.mark.asyncio
    async def test_invalid_op_returns_allowed_ops(self):
        """op 无效：结构化错误含 allowed_ops，引导 AI 修正"""
        tool = QueryCustomRecordEntriesTool()

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.side_effect = ValidationError(
                message="过滤操作符无效: contains（字段 heart_rate 类型 integer）",
                code="INVALID_FILTER_OP",
                details={
                    "field_key": "heart_rate",
                    "op": "contains",
                    "allowed_ops": ["eq", "gt", "gte", "lt", "lte", "ne", "in"],
                },
            )

            result = await tool.execute(
                type_id="crt-abc12345",
                filters=[{"field_key": "heart_rate", "op": "contains", "value": "12"}],
            )

        assert result.startswith(ERROR)
        payload = json.loads(result[len(ERROR):])
        assert payload["error"] == "INVALID_FILTER_OP"
        assert "contains" not in payload["allowed_ops"]
        assert "gte" in payload["allowed_ops"]

    @pytest.mark.asyncio
    async def test_invalid_value_returns_invalid_fields(self):
        """value 类型不匹配：结构化错误含 invalid_fields"""
        tool = QueryCustomRecordEntriesTool()

        with patch(
            "lifeprism.llm.agent.tools.custom_records_tool.custom_record_repository"
        ) as mock_repo:
            mock_repo.query_entries.side_effect = ValidationError(
                message="过滤值类型不匹配: heart_rate",
                code="INVALID_FIELD_VALUE",
                details={
                    "invalid_fields": [
                        {"field_key": "heart_rate", "value": "abc", "expected_type": "integer"}
                    ]
                },
            )

            result = await tool.execute(
                type_id="crt-abc12345",
                filters=[{"field_key": "heart_rate", "op": "eq", "value": "abc"}],
            )

        assert result.startswith(ERROR)
        payload = json.loads(result[len(ERROR):])
        assert payload["error"] == "INVALID_FIELD_VALUE"
        assert payload["invalid_fields"][0]["field_key"] == "heart_rate"

    @pytest.mark.asyncio
    async def test_filters_schema_declared_in_parameters(self):
        """parameters schema 应声明 filters 参数及全部操作符枚举"""
        params = QueryCustomRecordEntriesTool().parameters
        assert "filters" in params["properties"]
        items = params["properties"]["filters"]["items"]
        assert set(items["properties"]["op"]["enum"]) == {
            "eq",
            "ne",
            "gt",
            "gte",
            "lt",
            "lte",
            "contains",
            "in",
        }
        assert set(items["required"]) == {"field_key", "op", "value"}
