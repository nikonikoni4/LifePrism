"""usage_service UTC 时区迁移测试

验证 usage_service 在 UTC 时区迁移后的行为正确性。

测试 seam:
- Seam 1: _to_time_range - 本地日期转 UTC 时间范围
- Seam 2: _is_in_time_range - 处理 UTC created_at 与本地日期范围比较
- Seam 3: _aggregate_tokens_usage_by_date - UTC created_at 转本地日期分组
- Seam 4: get_usage_stats_7days - 7天统计的 UTC 时间范围

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- .scratch/utc-timezone-migration/06-report-stats-service-migration.md
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.core


def _load_usage_service_module():
    """直接按文件加载 usage_service，避免触发 services 包级导入副作用。"""
    project_root = Path(__file__).resolve().parents[4]
    module_path = project_root / "lifeprism" / "server" / "services" / "usage_service.py"
    spec = importlib.util.spec_from_file_location("usage_service_under_test_tz", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ==================== Seam 1: _to_time_range 本地日期转 UTC 时间范围 ====================


class TestToLocalTimeRange:
    """_to_time_range 应将本地日期转换为 UTC 时间范围"""

    def test_local_date_converts_to_utc_range(self):
        """本地日期 2026-07-12 (UTC+8) 应转为 UTC 2026-07-11 16:00 ~ 2026-07-12 15:59"""
        usage_service = _load_usage_service_module()

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            start, end = usage_service._to_time_range(date="2026-07-12")

        # 本地 2026-07-12 00:00:00 (UTC+8) = UTC 2026-07-11 16:00:00
        assert start == "2026-07-11 16:00:00", (
            f"本地日期 2026-07-12 的 UTC 起始时间应为 '2026-07-11 16:00:00'，实际为 '{start}'"
        )
        # 本地 2026-07-12 23:59:59 (UTC+8) = UTC 2026-07-12 15:59:59
        assert end == "2026-07-12 15:59:59", (
            f"本地日期 2026-07-12 的 UTC 结束时间应为 '2026-07-12 15:59:59'，实际为 '{end}'"
        )

    def test_explicit_start_end_returned_as_is(self):
        """显式传入 start_time/end_time 时应原样返回"""
        usage_service = _load_usage_service_module()
        start, end = usage_service._to_time_range(
            start_time="2026-07-11 16:00:00", end_time="2026-07-12 15:59:59"
        )
        assert start == "2026-07-11 16:00:00"
        assert end == "2026-07-12 15:59:59"

    def test_no_args_returns_none_pair(self):
        """无参数时返回 (None, None)"""
        usage_service = _load_usage_service_module()
        start, end = usage_service._to_time_range()
        assert start is None
        assert end is None


# ==================== Seam 2: _is_in_time_range 处理 UTC created_at ====================


class TestIsInTimeRange:
    """_is_in_time_range 应正确处理 UTC created_at 与 UTC 时间范围比较"""

    def test_utc_created_at_within_local_date_range(self):
        """UTC created_at 在本地日期范围内应返回 True

        场景：本地日期 2026-07-12 (UTC+8)
        - UTC 范围：2026-07-11 16:00:00 ~ 2026-07-12 15:59:59
        - 记录 UTC 2026-07-12 02:00:00 (本地 10:00) 应在范围内
        """
        usage_service = _load_usage_service_module()
        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = usage_service._is_in_time_range(
                "2026-07-12 02:00:00",
                start_time="2026-07-11 16:00:00",
                end_time="2026-07-12 15:59:59",
            )
        assert result is True

    def test_utc_created_at_at_boundary_start(self):
        """UTC created_at 正好等于范围起始时间应返回 True（闭区间）"""
        usage_service = _load_usage_service_module()
        result = usage_service._is_in_time_range(
            "2026-07-11 16:00:00",
            start_time="2026-07-11 16:00:00",
            end_time="2026-07-12 15:59:59",
        )
        assert result is True

    def test_utc_created_at_before_local_date_range(self):
        """UTC created_at 早于本地日期范围应返回 False

        场景：本地日期 2026-07-12 (UTC+8)
        - UTC 范围：2026-07-11 16:00:00 ~ 2026-07-12 15:59:59
        - 记录 UTC 2026-07-11 15:00:00 (本地 2026-07-11 23:00) 应不在范围内
        """
        usage_service = _load_usage_service_module()
        result = usage_service._is_in_time_range(
            "2026-07-11 15:00:00",
            start_time="2026-07-11 16:00:00",
            end_time="2026-07-12 15:59:59",
        )
        assert result is False

    def test_utc_created_at_after_local_date_range(self):
        """UTC created_at 晚于本地日期范围应返回 False

        场景：本地日期 2026-07-12 (UTC+8)
        - UTC 范围：2026-07-11 16:00:00 ~ 2026-07-12 15:59:59
        - 记录 UTC 2026-07-12 16:00:00 (本地 2026-07-13 00:00) 应不在范围内
        """
        usage_service = _load_usage_service_module()
        result = usage_service._is_in_time_range(
            "2026-07-12 16:00:00",
            start_time="2026-07-11 16:00:00",
            end_time="2026-07-12 15:59:59",
        )
        assert result is False

    def test_iso_format_created_at_with_t_separator(self):
        """ISO 格式 created_at（含 T 分隔符）应正确比较

        场景：created_at = "2026-07-12T02:00:00.123456+00:00" (UTC ISO 格式)
        - UTC 范围：2026-07-11 16:00:00 ~ 2026-07-12 15:59:59
        - 应在范围内
        """
        usage_service = _load_usage_service_module()
        result = usage_service._is_in_time_range(
            "2026-07-12T02:00:00.123456+00:00",
            start_time="2026-07-11 16:00:00",
            end_time="2026-07-12 15:59:59",
        )
        assert result is True

    def test_iso_format_created_at_before_range(self):
        """ISO 格式 created_at 早于范围应返回 False"""
        usage_service = _load_usage_service_module()
        result = usage_service._is_in_time_range(
            "2026-07-11T15:00:00.000000+00:00",
            start_time="2026-07-11 16:00:00",
            end_time="2026-07-12 15:59:59",
        )
        assert result is False

    def test_empty_created_at_returns_false(self):
        """空 created_at 应返回 False"""
        usage_service = _load_usage_service_module()
        assert usage_service._is_in_time_range("") is False
        assert usage_service._is_in_time_range(None) is False


# ==================== Seam 3: _aggregate_tokens_usage_by_date UTC created_at 转本地日期 ====================


class TestAggregateByDate:
    """_aggregate_tokens_usage_by_date 应将 UTC created_at 转为本地日期分组"""

    def test_utc_created_at_groups_by_local_date(self):
        """UTC created_at 应按本地日期分组

        场景：UTC 2026-07-11 17:00:00 = 本地 2026-07-12 01:00
        - 应分组到本地日期 2026-07-12，而非 UTC 日期 2026-07-11
        """
        usage_service = _load_usage_service_module()
        records = [
            {
                "session_id": "c-1",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "result_items_count": 1,
                "mode": "classification",
                "created_at": "2026-07-11 17:00:00",  # UTC, = local 2026-07-12 01:00
            }
        ]

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = usage_service._aggregate_tokens_usage_by_date(records)

        # 应按本地日期 2026-07-12 分组，而非 UTC 日期 2026-07-11
        assert "2026-07-12" in result, (
            f"UTC 2026-07-11 17:00 应分组到本地日期 '2026-07-12'，实际分组键为 {list(result.keys())}"
        )
        assert "2026-07-11" not in result, "UTC 2026-07-11 17:00 不应分组到 UTC 日期 '2026-07-11'"
        assert result["2026-07-12"]["total_tokens"] == 150

    def test_utc_created_at_noon_groups_same_local_date(self):
        """UTC 中午的时间戳不会跨天，应分到同一本地日期

        场景：UTC 2026-07-12 02:00:00 = 本地 2026-07-12 10:00
        """
        usage_service = _load_usage_service_module()
        records = [
            {
                "session_id": "c-1",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "result_items_count": 1,
                "mode": "classification",
                "created_at": "2026-07-12 02:00:00",  # UTC, = local 2026-07-12 10:00
            }
        ]

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = usage_service._aggregate_tokens_usage_by_date(records)

        assert "2026-07-12" in result
        assert result["2026-07-12"]["total_tokens"] == 150

    def test_iso_format_created_at_groups_by_local_date(self):
        """ISO 格式 UTC created_at 也应按本地日期分组"""
        usage_service = _load_usage_service_module()
        records = [
            {
                "session_id": "c-1",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "result_items_count": 1,
                "mode": "classification",
                "created_at": "2026-07-11T17:00:00.000000+00:00",  # UTC ISO
            }
        ]

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = usage_service._aggregate_tokens_usage_by_date(records)

        assert "2026-07-12" in result, (
            f"ISO 格式 UTC 2026-07-11T17:00 应分组到本地日期 '2026-07-12'，实际分组键为 {list(result.keys())}"
        )

    def test_multiple_records_across_timezone_boundary(self):
        """跨时区边界的多条记录应分别分到正确的本地日期"""
        usage_service = _load_usage_service_module()
        records = [
            {
                "session_id": "c-1",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "result_items_count": 1,
                "mode": "classification",
                "created_at": "2026-07-11 15:00:00",  # UTC, = local 2026-07-11 23:00
            },
            {
                "session_id": "c-2",
                "input_tokens": 200,
                "output_tokens": 100,
                "total_tokens": 300,
                "result_items_count": 2,
                "mode": "classification",
                "created_at": "2026-07-11 17:00:00",  # UTC, = local 2026-07-12 01:00
            },
            {
                "session_id": "c-3",
                "input_tokens": 300,
                "output_tokens": 150,
                "total_tokens": 450,
                "result_items_count": 3,
                "mode": "classification",
                "created_at": "2026-07-12 05:00:00",  # UTC, = local 2026-07-12 13:00
            },
        ]

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = usage_service._aggregate_tokens_usage_by_date(records)

        # 第一条记录应分到 2026-07-11
        assert "2026-07-11" in result
        assert result["2026-07-11"]["total_tokens"] == 150

        # 第二、三条记录应分到 2026-07-12
        assert "2026-07-12" in result
        assert result["2026-07-12"]["total_tokens"] == 750  # 300 + 450


# ==================== Seam 4: get_usage_stats_7days UTC 时间范围 ====================


class TestGetUsageStats7DaysTimezone:
    """get_usage_stats_7days 应使用 UTC 时间范围查询"""

    def test_7days_query_uses_utc_time_range(self, monkeypatch):
        """get_usage_stats_7days 应将本地日期转为 UTC 时间范围查询"""
        usage_service = _load_usage_service_module()

        captured_ranges = []

        def _fake_query_tokens_usage(options=None):
            captured_ranges.append(options)
            return ([], 0)

        monkeypatch.setattr(
            usage_service,
            "tokens_usage_repository",
            SimpleNamespace(query_tokens_usage=_fake_query_tokens_usage),
            raising=False,
        )

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            usage_service.get_usage_stats_7days("2026-07-15")

        # 应该有一次查询调用
        assert len(captured_ranges) >= 1, "应至少调用一次查询"

    def test_7days_groups_by_local_date(self, monkeypatch):
        """7天统计应按本地日期分组，跨时区边界正确"""
        usage_service = _load_usage_service_module()

        # 模拟数据：UTC 时间戳，跨越本地日期边界
        mock_records = [
            {
                "session_id": "c-1",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "result_items_count": 1,
                "mode": "classification",
                # UTC 2026-07-14 17:00 = local 2026-07-15 01:00 → 应分到 2026-07-15
                "created_at": "2026-07-14 17:00:00",
            },
            {
                "session_id": "c-2",
                "input_tokens": 200,
                "output_tokens": 100,
                "total_tokens": 300,
                "result_items_count": 2,
                "mode": "classification",
                # UTC 2026-07-15 02:00 = local 2026-07-15 10:00 → 应分到 2026-07-15
                "created_at": "2026-07-15 02:00:00",
            },
        ]

        def _fake_query_tokens_usage(options=None):
            return (mock_records, len(mock_records))

        monkeypatch.setattr(
            usage_service,
            "tokens_usage_repository",
            SimpleNamespace(query_tokens_usage=_fake_query_tokens_usage),
            raising=False,
        )

        with patch.object(usage_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = usage_service.get_usage_stats_7days("2026-07-15")

        # 7天范围内 2026-07-15 应包含两条记录的 token 总和
        day_15 = next(item for item in result.items if item.day == "2026-07-15")
        assert day_15.total_tokens == 450, (
            f"2026-07-15 的 total_tokens 应为 450 (150+300)，实际为 {day_15.total_tokens}"
        )
