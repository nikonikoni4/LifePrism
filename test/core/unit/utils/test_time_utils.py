"""time_utils 单元测试 - 验证 UTC 时区迁移后的时间工具函数行为"""

import re
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from lifeprism.utils.time_utils import (
    build_local_datetime,
    build_utc_time_range,
    get_local_today,
    get_utc_now_iso,
    local_to_utc_iso,
    parse_iso_to_aware,
    utc_to_local_display,
)


@pytest.mark.core
class TestGetLocalToday:
    """get_local_today 应返回用户本地时区的今天日期"""

    def test_returns_date_object(self):
        """get_local_today 返回 date 类型对象"""
        result = get_local_today()
        assert isinstance(result, date)

    def test_returns_today_not_none(self):
        """get_local_today 返回值不早于 UTC 今天（本地今天可能等于或晚一天）"""
        result = get_local_today()
        utc_today = datetime.now(timezone.utc).date()
        # 本地日期最多比 UTC 日期多一天（UTC+ 时区）
        diff = (result - utc_today).days
        assert -1 <= diff <= 1

    def test_isoformat_is_yyyy_mm_dd(self):
        """get_local_today().isoformat() 符合 YYYY-MM-DD 格式"""
        result = get_local_today().isoformat()
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result)


@pytest.mark.core
class TestGetUtcNowIso:
    """get_utc_now_iso 应返回 UTC ISO 8601 格式时间戳"""

    def test_returns_string(self):
        """get_utc_now_iso 返回字符串"""
        result = get_utc_now_iso()
        assert isinstance(result, str)

    def test_contains_utc_timezone_marker(self):
        """返回值包含 UTC 时区标识（+00:00）"""
        result = get_utc_now_iso()
        assert "+00:00" in result

    def test_matches_iso8601_pattern(self):
        """返回值匹配 ISO 8601 格式"""
        result = get_utc_now_iso()
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}\+00:00$"
        assert re.match(pattern, result), f"Value {result} does not match ISO 8601 UTC pattern"

    def test_parseable_to_aware_datetime(self):
        """返回值可被 fromisoformat 解析为 aware datetime"""
        result = get_utc_now_iso()
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None, "Parsed datetime should be timezone-aware"
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)

    def test_close_to_current_utc_time(self):
        """返回值应接近当前 UTC 时间（1 秒内）"""
        before = datetime.now(timezone.utc)
        result_str = get_utc_now_iso()
        after = datetime.now(timezone.utc)
        parsed = datetime.fromisoformat(result_str)
        assert before <= parsed <= after or abs((parsed - before).total_seconds()) < 1


@pytest.mark.core
class TestParseIsoToAware:
    """parse_iso_to_aware 应将 ISO 8601 字符串解析为 aware datetime

    API 层接收到的时间参数可能是：
    - 带 UTC 时区标识: "2026-07-01T10:00:00+00:00"
    - 带 Z 后缀: "2026-07-01T10:00:00Z"
    - 不带时区（naive）: "2026-07-01T10:00:00"

    对于 naive 字符串，应假设为 UTC 并补充时区信息。
    """

    def test_returns_datetime_object(self):
        """返回 datetime 类型对象"""
        result = parse_iso_to_aware("2026-07-01T10:00:00+00:00")
        assert isinstance(result, datetime)

    def test_aware_input_preserves_timezone(self):
        """带时区标识的输入应保留时区信息"""
        result = parse_iso_to_aware("2026-07-01T10:00:00+00:00")
        assert result.tzinfo is not None

    def test_z_suffix_parsed_as_utc(self):
        """带 Z 后缀的输入应解析为 UTC aware datetime"""
        result = parse_iso_to_aware("2026-07-01T10:00:00Z")
        assert result.tzinfo is not None
        assert result.utcoffset() == timezone.utc.utcoffset(result)

    def test_naive_input_assumed_utc(self):
        """naive 输入应被假设为 UTC 并补充时区信息"""
        result = parse_iso_to_aware("2026-07-01T10:00:00")
        assert result.tzinfo is not None, "naive datetime 应被补充为 aware"
        assert result.utcoffset() == timezone.utc.utcoffset(result)

    def test_naive_input_value_preserved(self):
        """naive 输入的时间值应被保留（仅补充时区，不转换时间）"""
        result = parse_iso_to_aware("2026-07-01T10:00:00")
        assert result.year == 2026
        assert result.month == 7
        assert result.day == 1
        assert result.hour == 10
        assert result.minute == 0
        assert result.second == 0

    def test_aware_input_value_preserved(self):
        """带时区输入的时间值应被保留"""
        result = parse_iso_to_aware("2026-07-01T10:00:00+00:00")
        assert result.hour == 10

    def test_microseconds_preserved(self):
        """微秒应被保留"""
        result = parse_iso_to_aware("2026-07-01T10:00:00.123456+00:00")
        assert result.microsecond == 123456

    def test_naive_with_microseconds(self):
        """naive 带微秒的输入也应正确处理"""
        result = parse_iso_to_aware("2026-07-01T10:00:00.123456")
        assert result.tzinfo is not None
        assert result.microsecond == 123456


@pytest.mark.core
class TestLocalToUtcIso:
    """local_to_utc_iso 应将本地时间字符串转换为 UTC ISO 8601 格式

    偏移量由 get_user_timezone() 动态决定。
    """

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_shanghai_utc8_offset(self, _mock_tz):
        """UTC+8 时区：本地时间减 8 小时为 UTC"""
        result = local_to_utc_iso("2026-07-12 04:00:00")
        assert result == "2026-07-11T20:00:00+00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="America/Los_Angeles")
    def test_los_angeles_utc_minus_8_offset(self, _mock_tz):
        """UTC-8 时区（PST 冬令时）：本地时间加 8 小时为 UTC"""
        result = local_to_utc_iso("2026-01-15 04:00:00")
        assert result == "2026-01-15T12:00:00+00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="UTC")
    def test_utc_zero_offset(self, _mock_tz):
        """UTC+0 时区：本地时间等于 UTC"""
        result = local_to_utc_iso("2026-07-12 04:00:00")
        assert result == "2026-07-12T04:00:00+00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_cross_date_boundary(self, _mock_tz):
        """跨日期边界：本地 00:30 → UTC 前一天 16:30"""
        result = local_to_utc_iso("2026-07-12 00:30:00")
        assert result == "2026-07-11T16:30:00+00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_custom_format(self, _mock_tz):
        """支持自定义解析格式"""
        result = local_to_utc_iso("2026-07-12", "%Y-%m-%d")
        assert result == "2026-07-11T16:00:00+00:00"

    def test_invalid_input_raises_value_error(self):
        """无效输入应抛出 ValueError"""
        with pytest.raises(ValueError):
            local_to_utc_iso("invalid time string")


@pytest.mark.core
class TestBuildLocalDatetime:
    """build_local_datetime 应根据日期和时间构造本地时间字符串"""

    def test_basic_construction(self):
        """正常构造日期 + 时间"""
        result = build_local_datetime("2026-07-12", "04:00:00")
        assert result == "2026-07-12 04:00:00"

    def test_default_time_is_zero(self):
        """省略 time_str 时默认为 00:00:00"""
        result = build_local_datetime("2026-07-12")
        assert result == "2026-07-12 00:00:00"

    def test_invalid_date_raises_value_error(self):
        """无效日期应抛出 ValueError"""
        with pytest.raises(ValueError):
            build_local_datetime("invalid-date", "04:00:00")

    def test_invalid_time_raises_value_error(self):
        """无效时间应抛出 ValueError"""
        with pytest.raises(ValueError):
            build_local_datetime("2026-07-12", "invalid-time")


@pytest.mark.core
class TestUtcToLocalDisplay:
    """utc_to_local_display 应将 UTC ISO 8601 转为本地时区显示格式"""

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_utc_plus8_with_offset_suffix(self, _mock_tz):
        """UTC+8：处理 +00:00 后缀输入"""
        result = utc_to_local_display("2026-07-11T20:00:00+00:00")
        assert result == "2026-07-12 04:00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_utc_plus8_with_z_suffix(self, _mock_tz):
        """UTC+8：处理 Z 后缀输入"""
        result = utc_to_local_display("2026-07-11T20:00:00Z")
        assert result == "2026-07-12 04:00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_utc_plus8_with_nonzero_offset(self, _mock_tz):
        """UTC+8：处理带非零偏移的输入（-08:00 → UTC 20:00 → 本地 04:00 次日）"""
        result = utc_to_local_display("2026-07-11T12:00:00-08:00")
        assert result == "2026-07-12 04:00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="UTC")
    def test_utc_zero_offset(self, _mock_tz):
        """UTC+0：UTC 时间等于本地时间"""
        result = utc_to_local_display("2026-07-12T04:00:00+00:00")
        assert result == "2026-07-12 04:00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="America/Los_Angeles")
    def test_utc_minus8_offset(self, _mock_tz):
        """UTC-8（PST 冬令时）：UTC 时间减 8 小时为本地时间"""
        result = utc_to_local_display("2026-01-15T20:00:00+00:00")
        assert result == "2026-01-15 12:00:00"

    def test_invalid_input_raises_value_error(self):
        """无效输入应抛出 ValueError"""
        with pytest.raises(ValueError):
            utc_to_local_display("invalid time string")


@pytest.mark.core
class TestBuildUtcTimeRange:
    """build_utc_time_range 应根据本地日期构造当天 UTC 时间范围"""

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="Asia/Shanghai")
    def test_shanghai_range_crosses_date(self, _mock_tz):
        """UTC+8：本地日期范围跨 UTC 日期（前一日 16:00 ~ 当日 15:59:59）"""
        start, end = build_utc_time_range("2026-07-12")
        assert start == "2026-07-11T16:00:00+00:00"
        assert end == "2026-07-12T15:59:59+00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="UTC")
    def test_utc_range_same_date(self, _mock_tz):
        """UTC+0：本地日期范围等于 UTC 日期范围"""
        start, end = build_utc_time_range("2026-07-12")
        assert start == "2026-07-12T00:00:00+00:00"
        assert end == "2026-07-12T23:59:59+00:00"

    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="America/Los_Angeles")
    def test_los_angeles_range_crosses_date(self, _mock_tz):
        """UTC-8（PST 冬令时）：本地日期范围跨 UTC 日期（当日 08:00 ~ 次日 07:59:59）"""
        start, end = build_utc_time_range("2026-01-15")
        assert start == "2026-01-15T08:00:00+00:00"
        assert end == "2026-01-16T07:59:59+00:00"

    def test_invalid_date_raises_value_error(self):
        """无效日期应抛出 ValueError"""
        with pytest.raises(ValueError):
            build_utc_time_range("invalid-date")
