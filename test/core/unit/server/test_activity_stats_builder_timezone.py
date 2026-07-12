"""activity_stats_builder UTC 时区迁移测试

验证 activity_stats_builder 在 UTC 时区迁移后的行为正确性。

测试 seam:
- Seam 1: _build_utc_time_range - 本地日期转 UTC 时间范围（用于查询）
- Seam 2: _utc_timestamp_to_local_date - UTC 时间戳转用户本地日期
- Seam 3: _add_local_date_column - pandas DataFrame 批量 UTC 转本地日期

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- .scratch/utc-timezone-migration/06-report-stats-service-migration.md
"""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

pytestmark = pytest.mark.core


def _load_activity_stats_builder_module():
    """直接按文件加载 activity_stats_builder，避免触发 services 包级导入副作用。"""
    project_root = Path(__file__).resolve().parents[4]
    module_path = project_root / "lifeprism" / "server" / "services" / "activity_stats_builder.py"
    spec = importlib.util.spec_from_file_location(
        "activity_stats_builder_under_test_tz", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ==================== Seam 1: _build_utc_time_range 本地日期转 UTC 查询范围 ====================


class TestBuildUtcTimeRange:
    """_build_utc_time_range 应将本地日期转为 UTC 时间范围用于查询"""

    def test_local_date_to_utc_range(self):
        """本地日期 2026-07-12 (UTC+8) 应转为 UTC 2026-07-11 16:00 ~ 2026-07-12 15:59"""
        builder = _load_activity_stats_builder_module()

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            start, end = builder._build_utc_time_range("2026-07-12")

        assert start == "2026-07-11 16:00:00", (
            f"本地日期 2026-07-12 的 UTC 起始应为 '2026-07-11 16:00:00'，实际为 '{start}'"
        )
        assert end == "2026-07-12 15:59:59", (
            f"本地日期 2026-07-12 的 UTC 结束应为 '2026-07-12 15:59:59'，实际为 '{end}'"
        )

    def test_date_range_to_utc_range(self):
        """本地日期范围 2026-07-09 ~ 2026-07-15 应转为 UTC 范围"""
        builder = _load_activity_stats_builder_module()

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            start, end = builder._build_utc_time_range("2026-07-09", "2026-07-15")

        assert start == "2026-07-08 16:00:00"
        assert end == "2026-07-15 15:59:59"


# ==================== Seam 2: _utc_timestamp_to_local_date UTC 转本地日期 ====================


class TestUtcTimestampToLocalDate:
    """_utc_timestamp_to_local_date 应将 UTC 时间戳转为用户本地日期"""

    def test_utc_evening_groups_to_next_local_date(self):
        """UTC 晚上时间应转到下一本地日期

        场景：UTC 2026-07-11 17:00:00 = 本地 2026-07-12 01:00
        """
        builder = _load_activity_stats_builder_module()

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            result = builder._utc_timestamp_to_local_date("2026-07-11 17:00:00")

        assert result == "2026-07-12", (
            f"UTC '2026-07-11 17:00:00' 应转为本地日期 '2026-07-12'，实际为 '{result}'"
        )

    def test_utc_morning_groups_to_same_local_date(self):
        """UTC 早上时间应留在同一本地日期"""
        builder = _load_activity_stats_builder_module()

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            result = builder._utc_timestamp_to_local_date("2026-07-12 02:00:00")

        assert result == "2026-07-12"

    def test_iso_format_utc_timestamp(self):
        """ISO 格式 UTC 时间戳也应正确转换"""
        builder = _load_activity_stats_builder_module()

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            result = builder._utc_timestamp_to_local_date(
                "2026-07-11T17:00:00.123456+00:00"
            )

        assert result == "2026-07-12"

    def test_empty_input_returns_empty(self):
        """空输入应返回空字符串"""
        builder = _load_activity_stats_builder_module()
        assert builder._utc_timestamp_to_local_date("") == ""
        assert builder._utc_timestamp_to_local_date(None) == ""


# ==================== Seam 3: _add_local_date_column pandas 批量转换 ====================


class TestAddLocalDateColumn:
    """_add_local_date_column 应为 DataFrame 添加本地日期列"""

    def test_pandas_series_conversion(self):
        """pandas Series 的 UTC 时间戳应批量转为本地日期"""
        builder = _load_activity_stats_builder_module()

        df = pd.DataFrame(
            {
                "start_time": [
                    "2026-07-11 17:00:00",  # local 2026-07-12 01:00
                    "2026-07-12 02:00:00",  # local 2026-07-12 10:00
                    "2026-07-12 18:00:00",  # local 2026-07-13 02:00
                ]
            }
        )

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            result = builder._add_local_date_column(df.copy())

        assert result["local_date"].iloc[0] == "2026-07-12"
        assert result["local_date"].iloc[1] == "2026-07-12"
        assert result["local_date"].iloc[2] == "2026-07-13"

    def test_missing_time_col_returns_empty_local_date(self):
        """缺少时间列时应返回空 local_date 列"""
        builder = _load_activity_stats_builder_module()

        df = pd.DataFrame({"other_col": [1, 2, 3]})

        with patch.object(builder, "LOCAL_TIMEZONE", "Asia/Shanghai"):
            result = builder._add_local_date_column(df.copy(), time_col="start_time")

        assert "local_date" in result.columns


# ==================== Seam 4: LOCAL_TIMEZONE 已导入 ====================


class TestLocalTimezoneImported:
    """验证 activity_stats_builder 已导入 LOCAL_TIMEZONE"""

    def test_local_timezone_is_imported(self):
        """activity_stats_builder 应导入 LOCAL_TIMEZONE"""
        builder = _load_activity_stats_builder_module()
        assert hasattr(builder, "LOCAL_TIMEZONE"), (
            "activity_stats_builder 应导入 LOCAL_TIMEZONE 常量"
        )
