"""跨时区数据同步和午夜场景集成测试

验证 UTC 时区迁移后，在 UTC+8 午夜边界（本地 23:59 和 00:01）日期选择正确。

测试 seam:
- Seam 1: 日期字段（YYYY-MM-DD）在 UTC+8 午夜边界使用本地日期，不使用 UTC 日期
- Seam 2: 时间戳字段（ISO 8601）在 UTC+8 午夜边界使用 UTC 时间
- Seam 3: 跨时区 LWW 比较在午夜边界正确工作

背景:
- 迁移前：date.today() 和 datetime.now() 都基于本地时区，午夜边界无问题
- 迁移后：时间戳字段使用 UTC，但日期字段仍应使用本地时区
- 风险：如果在午夜边界误用 UTC 日期，会导致用户在本地 00:01 打卡时
  记录到"昨天"而非"今天"

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md (3.3 节 习惯打卡日期错位)
- docs/coding-rules/time-handling-rules.md (2.1/2.2 字段分类)
- test/core/integration/sync/test_sync_timezone_utc.py (跨时区同步 LWW 测试)
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytz

pytestmark = pytest.mark.core


# ==================== Helpers ====================

# 测试用固定时区：UTC+8（北京时间）
# PRD 假设用户在 UTC+8 时区
TEST_TIMEZONE = "Asia/Shanghai"


def _make_mock_now(simulated_utc: datetime):
    """构建 mock datetime.now 的 side_effect 函数

    模拟 datetime.now(tz) 的行为：返回 simulated_utc 在指定时区的表示。
    这样 get_local_today() 和 get_utc_now_iso() 都能正确工作。

    Args:
        simulated_utc: 模拟的当前 UTC 时间（必须带 tzinfo=timezone.utc）
    """

    def _mock_now(tz=None):
        if tz is None:
            return simulated_utc.replace(tzinfo=None)
        return simulated_utc.astimezone(tz)

    return _mock_now


# ==================== Seam 1: 午夜边界日期字段使用本地日期 ====================


class TestMidnightDateFieldUsesLocalDate:
    """Seam 1: 日期字段在 UTC+8 午夜边界使用本地日期

    验证：get_local_today() 在本地 00:01 和 23:59 时返回正确的本地日期，
    而非 UTC 日期。

    场景：
    - 本地 00:01 (UTC+8) = UTC 16:01 前一天 → 本地日期是"今天"，UTC 日期是"昨天"
    - 本地 23:59 (UTC+8) = UTC 15:59 当天 → 本地日期是"今天"，UTC 日期也是"今天"

    这验证了 docs/coding-rules/time-handling-rules.md 2.2 节的规则：
    "日期字段记录用户语义的某一天，保持用户本地时区日期，不使用 UTC 日期"
    """

    def test_local_00_01_returns_today_not_utc_yesterday(self):
        """本地 00:01（UTC+8）应返回本地今天，而非 UTC 昨天

        场景：用户在 UTC+8 的 2026-07-12 00:01 打卡
        - UTC 时间：2026-07-11 16:01（前一天）
        - 本地日期：2026-07-12（今天）
        - UTC 日期：2026-07-11（昨天）

        如果误用 UTC 日期，用户查看"今日打卡"时看不到刚打的卡。
        """
        # UTC 2026-07-11 16:01 = 本地 UTC+8 2026-07-12 00:01
        simulated_utc = datetime(2026, 7, 11, 16, 1, 0, tzinfo=timezone.utc)

        with patch("lifeprism.utils.time_utils.datetime") as mock_datetime:
            mock_datetime.now.side_effect = _make_mock_now(simulated_utc)
            mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

            from lifeprism.utils.time_utils import get_local_today

            local_today = get_local_today()

        # 本地日期应为 2026-07-12（今天）
        assert local_today == date(2026, 7, 12), (
            f"本地 00:01 时 get_local_today 应返回 2026-07-12（本地今天），实际为 {local_today}"
        )
        # 验证与 UTC 日期不同（证明使用本地时区的必要性）
        utc_date = simulated_utc.date()
        assert utc_date == date(2026, 7, 11), f"UTC 日期应为 2026-07-11（昨天），实际为 {utc_date}"
        assert local_today != utc_date, (
            "本地 00:01 时，本地日期与 UTC 日期应不同（本地今天 vs UTC 昨天）"
        )

    def test_local_23_59_returns_today_same_as_utc(self):
        """本地 23:59（UTC+8）应返回本地今天，与 UTC 日期相同

        场景：用户在 UTC+8 的 2026-07-12 23:59 打卡
        - UTC 时间：2026-07-12 15:59（当天）
        - 本地日期：2026-07-12（今天）
        - UTC 日期：2026-07-12（今天）

        两者相同，但时间戳字段仍应使用 UTC。
        """
        # UTC 2026-07-12 15:59 = 本地 UTC+8 2026-07-12 23:59
        simulated_utc = datetime(2026, 7, 12, 15, 59, 0, tzinfo=timezone.utc)

        with patch("lifeprism.utils.time_utils.datetime") as mock_datetime:
            mock_datetime.now.side_effect = _make_mock_now(simulated_utc)
            mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

            from lifeprism.utils.time_utils import get_local_today

            local_today = get_local_today()

        # 本地日期应为 2026-07-12
        assert local_today == date(2026, 7, 12), (
            f"本地 23:59 时 get_local_today 应返回 2026-07-12，实际为 {local_today}"
        )

    def test_local_00_00_exact_midnight_returns_today(self):
        """本地 00:00:00（UTC+8）精确午夜应返回本地今天

        场景：用户在 UTC+8 的 2026-07-12 00:00:00 打卡
        - UTC 时间：2026-07-11 16:00:00（前一天）
        - 本地日期：2026-07-12（今天）

        这是午夜边界的精确测试点。
        """
        # UTC 2026-07-11 16:00 = 本地 UTC+8 2026-07-12 00:00
        simulated_utc = datetime(2026, 7, 11, 16, 0, 0, tzinfo=timezone.utc)

        with patch("lifeprism.utils.time_utils.datetime") as mock_datetime:
            mock_datetime.now.side_effect = _make_mock_now(simulated_utc)
            mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

            from lifeprism.utils.time_utils import get_local_today

            local_today = get_local_today()

        assert local_today == date(2026, 7, 12), (
            f"本地午夜 00:00 时 get_local_today 应返回 2026-07-12，实际为 {local_today}"
        )

    def test_utc_date_would_be_wrong_at_local_midnight(self):
        """验证：如果误用 UTC 日期，本地 00:01 会得到错误的日期

        这是一个对比测试：展示使用 UTC 日期 vs 本地日期的差异。
        迁移前用 date.today() 不会出错，迁移后如果误用
        datetime.now(timezone.utc).date() 会导致日期错位。
        """
        # UTC 2026-07-11 16:01 = 本地 UTC+8 2026-07-12 00:01
        simulated_utc = datetime(2026, 7, 11, 16, 1, 0, tzinfo=timezone.utc)
        beijing_tz = pytz.timezone(TEST_TIMEZONE)
        local_time = simulated_utc.astimezone(beijing_tz)

        # 正确做法：本地日期
        correct_date = local_time.date()
        # 错误做法：UTC 日期
        wrong_date = simulated_utc.date()

        assert correct_date == date(2026, 7, 12), "本地日期应为 2026-07-12"
        assert wrong_date == date(2026, 7, 11), "UTC 日期应为 2026-07-11"
        assert correct_date != wrong_date, (
            "本地 00:01 时，本地日期和 UTC 日期应不同，证明误用 UTC 日期会导致错位"
        )


# ==================== Seam 2: 午夜边界时间戳字段使用 UTC ====================


class TestMidnightTimestampFieldUsesUtc:
    """Seam 2: 时间戳字段在 UTC+8 午夜边界使用 UTC 时间

    验证：get_utc_now_iso() 在本地午夜边界返回 UTC ISO 8601 格式时间戳，
    包含 +00:00 时区标识。

    场景：
    - 本地 00:01 (UTC+8) → 时间戳应为 UTC 16:01 前一天 + "+00:00"
    - 本地 23:59 (UTC+8) → 时间戳应为 UTC 15:59 当天 + "+00:00"
    """

    def test_timestamp_at_local_midnight_is_utc_iso(self):
        """本地 00:01 时，时间戳应为 UTC ISO 8601 格式（前一天 16:01）"""
        # UTC 2026-07-11 16:01 = 本地 UTC+8 2026-07-12 00:01
        simulated_utc = datetime(2026, 7, 11, 16, 1, 0, tzinfo=timezone.utc)

        with patch("lifeprism.utils.time_utils.datetime") as mock_datetime:
            mock_datetime.now.side_effect = _make_mock_now(simulated_utc)
            mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

            from lifeprism.utils.time_utils import get_utc_now_iso

            utc_iso = get_utc_now_iso()

        # 验证是 UTC ISO 8601 格式
        assert "+00:00" in utc_iso, f"时间戳应包含 UTC 时区标识 +00:00，实际: {utc_iso}"
        # 验证可解析为 aware datetime
        parsed = datetime.fromisoformat(utc_iso)
        assert parsed.tzinfo is not None, "时间戳解析后应为 aware datetime"
        assert parsed.utcoffset() == timedelta(0), "时间戳时区应为 UTC"
        # 验证时间是 UTC 16:01（而非本地 00:01）
        assert parsed.hour == 16, f"UTC 小时应为 16，实际为 {parsed.hour}"
        assert parsed.day == 11, f"UTC 日期应为 11，实际为 {parsed.day}"

    def test_timestamp_and_date_field_differ_at_midnight(self):
        """本地 00:01 时，时间戳字段和日期字段应反映不同的日期

        场景：用户在 UTC+8 的 2026-07-12 00:01 操作
        - date 字段（本地日期）：2026-07-12
        - created_at 字段（UTC ISO）：2026-07-11T16:01:...+00:00

        两者日期部分不同（12 vs 11），这是正确的行为：
        - date 字段记录"用户语义的某一天"（本地今天）
        - created_at 字段记录"精确时刻"（UTC）
        """
        # UTC 2026-07-11 16:01 = 本地 UTC+8 2026-07-12 00:01
        simulated_utc = datetime(2026, 7, 11, 16, 1, 0, tzinfo=timezone.utc)

        with patch("lifeprism.utils.time_utils.datetime") as mock_datetime:
            mock_datetime.now.side_effect = _make_mock_now(simulated_utc)
            mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

            from lifeprism.utils.time_utils import get_local_today, get_utc_now_iso

            local_today = get_local_today()
            utc_iso = get_utc_now_iso()

        # date 字段：本地日期 2026-07-12
        assert local_today == date(2026, 7, 12)
        # created_at 字段：UTC ISO，日期部分是 2026-07-11
        parsed_utc = datetime.fromisoformat(utc_iso)
        assert parsed_utc.date() == date(2026, 7, 11)
        # 两者日期不同（这是正确行为）
        assert local_today != parsed_utc.date(), (
            "本地 00:01 时，date 字段（本地今天 07-12）和 "
            "created_at 字段（UTC 07-11）的日期部分应不同"
        )


# ==================== Seam 3: 跨时区 LWW 比较在午夜边界正确工作 ====================


class TestMidnightLwwComparison:
    """Seam 3: 跨时区 LWW 比较在午夜边界正确工作

    验证：当两条记录的 updated_at 分别在 UTC 午夜两侧时，
    UTC ISO 8601 字符串比较仍能正确判断新旧。

    背景：迁移前本地用 naive 本地时间，UTC 午夜附近字符串比较可能出错。
    迁移后统一用 UTC ISO 8601，字符串字典序与时间顺序一致。
    """

    def test_lww_across_utc_midnight(self):
        """LWW: UTC 午夜前后的时间戳比较正确

        场景：
        - 记录 A: updated_at = UTC 2026-07-11 23:59:00+00:00（午夜前）
        - 记录 B: updated_at = UTC 2026-07-12 00:01:00+00:00（午夜后）
        - B 应比 A 新（字符串比较 B > A）
        """
        before_midnight = datetime(2026, 7, 11, 23, 59, 0, tzinfo=timezone.utc).isoformat()
        after_midnight = datetime(2026, 7, 12, 0, 1, 0, tzinfo=timezone.utc).isoformat()

        # 字符串比较应与时间顺序一致
        assert before_midnight < after_midnight, (
            f"UTC 午夜前 ({before_midnight}) 应小于 UTC 午夜后 ({after_midnight})"
        )
        assert after_midnight > before_midnight

    def test_lww_across_local_midnight(self):
        """LWW: 本地午夜（UTC 16:00）前后的时间戳比较正确

        场景（UTC+8）：
        - 记录 A: 本地 2026-07-12 00:01 = UTC 2026-07-11 16:01:00+00:00
        - 记录 B: 本地 2026-07-12 00:02 = UTC 2026-07-11 16:02:00+00:00
        - B 应比 A 新

        这验证了在本地午夜边界，UTC ISO 字符串比较仍正确。
        """
        a_utc = datetime(2026, 7, 11, 16, 1, 0, tzinfo=timezone.utc).isoformat()
        b_utc = datetime(2026, 7, 11, 16, 2, 0, tzinfo=timezone.utc).isoformat()

        assert a_utc < b_utc, f"本地午夜后 1 分钟 ({a_utc}) 应小于本地午夜后 2 分钟 ({b_utc})"

    def test_lww_same_instant_different_timezone_format(self):
        """LWW: 同一时刻的 UTC ISO 字符串比较相等

        场景：同一时刻用不同时区表示
        - UTC: 2026-07-11T16:01:00+00:00
        - 北京: 2026-07-12T00:01:00+08:00

        迁移后统一用 UTC，不应出现混合时区比较。
        但验证同一时刻的 UTC 表示是唯一的。
        """
        utc_time = datetime(2026, 7, 11, 16, 1, 0, tzinfo=timezone.utc)
        beijing_tz = pytz.timezone(TEST_TIMEZONE)
        beijing_time = utc_time.astimezone(beijing_tz)

        utc_iso = utc_time.isoformat()
        # 两者代表同一时刻
        assert utc_time == beijing_time, "UTC 16:01 和 北京 00:01 应是同一时刻"

        # UTC ISO 格式是统一的（迁移后所有时间戳都用 UTC）
        assert "+00:00" in utc_iso
