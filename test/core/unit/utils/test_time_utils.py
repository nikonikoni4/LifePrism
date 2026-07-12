"""time_utils 单元测试 - 验证 UTC 时区迁移后的时间工具函数行为"""
import re
from datetime import date, datetime, timezone

import pytest

from lifeprism.utils.time_utils import get_local_today, get_utc_now_iso, parse_iso_to_aware


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
