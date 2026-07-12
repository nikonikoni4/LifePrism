"""report_service UTC 时区迁移测试

验证 report_service 在 UTC 时区迁移后的行为正确性。

测试 seam:
- Seam 1: _get_local_today_str - "今天"判断基于用户本地时区，而非 UTC
- Seam 2: _utc_timestamp_to_local_date - UTC 时间戳转用户本地日期（用于 pandas 分组）
- Seam 3: _build_utc_time_range - 本地日期转 UTC 时间范围（用于查询）

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


def _load_report_service_module():
    """直接按文件加载 report_service，避免触发 services 包级导入副作用。"""
    project_root = Path(__file__).resolve().parents[4]
    module_path = project_root / "lifeprism" / "server" / "services" / "report_service.py"
    spec = importlib.util.spec_from_file_location("report_service_under_test_tz", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ==================== Seam 1: _get_local_today_str 本地今天 ====================


class TestGetLocalTodayStr:
    """_get_local_today_str 应返回用户本地时区的今天日期"""

    def test_returns_local_today_not_utc(self):
        """_get_local_today_str 应基于用户本地时区返回今天日期

        场景：UTC 时间 2026-07-12 20:00（本地 UTC+8 为 2026-07-13 04:00）
        - UTC 日期：2026-07-12
        - 本地日期：2026-07-13
        - 应返回本地日期 '2026-07-13'，而非 UTC 日期 '2026-07-12'
        """
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            with patch.object(report_service, "get_local_today") as mock_get_local:
                from datetime import date

                mock_get_local.return_value = date(2026, 7, 13)
                result = report_service._get_local_today_str()

        assert result == "2026-07-13", f"应返回本地日期 '2026-07-13'，实际为 '{result}'"

    def test_returns_correct_date_at_utc_midnight(self):
        """UTC 午夜前后应返回正确的本地日期

        场景：UTC 时间 2026-07-12 00:30（本地 UTC+8 为 2026-07-12 08:30）
        - UTC 日期：2026-07-12
        - 本地日期：2026-07-12
        - 两者一致
        """
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            with patch.object(report_service, "get_local_today") as mock_get_local:
                from datetime import date

                mock_get_local.return_value = date(2026, 7, 12)
                result = report_service._get_local_today_str()

        assert result == "2026-07-12"


# ==================== Seam 2: _utc_timestamp_to_local_date UTC 转本地日期 ====================


class TestUtcTimestampToLocalDate:
    """_utc_timestamp_to_local_date 应将 UTC 时间戳转为用户本地日期"""

    def test_utc_evening_groups_to_next_local_date(self):
        """UTC 晚上时间应转到下一本地日期

        场景：UTC 2026-07-11 17:00:00 = 本地 2026-07-12 01:00
        - 应返回本地日期 '2026-07-12'，而非 UTC 日期 '2026-07-11'
        """
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = report_service._utc_timestamp_to_local_date("2026-07-11 17:00:00")

        assert result == "2026-07-12", (
            f"UTC '2026-07-11 17:00:00' 应转为本地日期 '2026-07-12'，实际为 '{result}'"
        )

    def test_utc_morning_groups_to_same_local_date(self):
        """UTC 早上时间应留在同一本地日期

        场景：UTC 2026-07-12 02:00:00 = 本地 2026-07-12 10:00
        """
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = report_service._utc_timestamp_to_local_date("2026-07-12 02:00:00")

        assert result == "2026-07-12"

    def test_iso_format_utc_timestamp(self):
        """ISO 格式 UTC 时间戳也应正确转换

        场景：created_at = '2026-07-11T17:00:00.123456+00:00'
        - 应转为本地日期 '2026-07-12'
        """
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = report_service._utc_timestamp_to_local_date("2026-07-11T17:00:00.123456+00:00")

        assert result == "2026-07-12", (
            f"ISO 格式 UTC 时间戳应转为本地日期 '2026-07-12'，实际为 '{result}'"
        )

    def test_empty_input_returns_empty(self):
        """空输入应返回空字符串"""
        report_service = _load_report_service_module()
        assert report_service._utc_timestamp_to_local_date("") == ""
        assert report_service._utc_timestamp_to_local_date(None) == ""

    def test_pandas_series_conversion(self):
        """pandas Series 的 UTC 时间戳应批量转为本地日期

        场景：DataFrame 的 start_time 列包含 UTC 时间戳
        - '2026-07-11 17:00:00' → 本地 '2026-07-12'
        - '2026-07-12 02:00:00' → 本地 '2026-07-12'
        - '2026-07-12 18:00:00' → 本地 '2026-07-13'
        """
        report_service = _load_report_service_module()

        df = pd.DataFrame(
            {
                "start_time": [
                    "2026-07-11 17:00:00",  # local 2026-07-12 01:00
                    "2026-07-12 02:00:00",  # local 2026-07-12 10:00
                    "2026-07-12 18:00:00",  # local 2026-07-13 02:00
                ]
            }
        )

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            result = report_service._add_local_date_column(df.copy())

        assert result["local_date"].iloc[0] == "2026-07-12"
        assert result["local_date"].iloc[1] == "2026-07-12"
        assert result["local_date"].iloc[2] == "2026-07-13"


# ==================== Seam 3: _build_utc_time_range 本地日期转 UTC 查询范围 ====================


class TestBuildUtcTimeRange:
    """_build_utc_time_range 应将本地日期转为 UTC 时间范围用于查询"""

    def test_local_date_to_utc_range(self):
        """本地日期 2026-07-12 (UTC+8) 应转为 UTC 2026-07-11 16:00 ~ 2026-07-12 15:59"""
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            start, end = report_service._build_utc_time_range("2026-07-12")

        assert start == "2026-07-11 16:00:00", (
            f"本地日期 2026-07-12 的 UTC 起始应为 '2026-07-11 16:00:00'，实际为 '{start}'"
        )
        assert end == "2026-07-12 15:59:59", (
            f"本地日期 2026-07-12 的 UTC 结束应为 '2026-07-12 15:59:59'，实际为 '{end}'"
        )

    def test_date_range_to_utc_range(self):
        """本地日期范围 2026-07-09 ~ 2026-07-15 应转为 UTC 范围"""
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_user_timezone", return_value="Asia/Shanghai"):
            start, end = report_service._build_utc_time_range("2026-07-09", "2026-07-15")

        # 本地 2026-07-09 00:00 (UTC+8) = UTC 2026-07-08 16:00
        assert start == "2026-07-08 16:00:00"
        # 本地 2026-07-15 23:59:59 (UTC+8) = UTC 2026-07-15 15:59:59
        assert end == "2026-07-15 15:59:59"


# ==================== Seam 4: 不再使用 datetime.now() 计算"今天" ====================


class TestNoDatetimeNowForToday:
    """验证 report_service 不再直接使用 datetime.now() 计算今天日期"""

    def test_get_local_today_is_imported(self):
        """report_service 应从 time_utils 导入 get_local_today"""
        report_service = _load_report_service_module()
        assert hasattr(report_service, "get_local_today"), (
            "report_service 应导入 get_local_today 函数"
        )

    def test_get_local_today_str_uses_get_local_today(self):
        """_get_local_today_str 应调用 get_local_today，而非 datetime.now()"""
        report_service = _load_report_service_module()

        with patch.object(report_service, "get_local_today") as mock_get_local:
            from datetime import date

            mock_get_local.return_value = date(2026, 7, 15)
            result = report_service._get_local_today_str()

            mock_get_local.assert_called_once()
            assert result == "2026-07-15"
