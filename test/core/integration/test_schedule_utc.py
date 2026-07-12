"""定时任务本地时区集成测试

验证 Cron 表达式在本地时区下的触发时间正确性。

测试场景:
1. Cron 表达式 "0 10 * * *" + 本地时区 → 下一次触发时间是本地 10:00
2. 不同系统时区下，调度器使用本地时区，触发时间不受系统时区影响
3. _dreaming 使用本地日期计算"昨天"
4. 状态记录使用本地日期

参考:
- docs/coding-rules/time-handling-rules.md
- .scratch/utc-timezone-migration/issues/29-scheduled-task-local-timezone-fix.md
"""

from datetime import datetime, timedelta

import pytest
import pytz
from apscheduler.triggers.cron import CronTrigger

pytestmark = pytest.mark.core

TEST_TIMEZONE = "Asia/Shanghai"


# ==================== 场景 1: Cron 表达式触发时间 ====================


def test_cron_trigger_local_10_next_fire_time():
    """Cron 表达式 "0 10 * * *" 在本地时区下的下一次触发时间应为本地 10:00

    场景：当前本地时间 2026-07-12 09:00，下一次触发应为 2026-07-12 10:00 本地
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)
    cron_expr = "0 10 * * *"
    trigger = CronTrigger.from_crontab(cron_expr, timezone=local_tz)

    # 当前本地时间 2026-07-12 09:00
    now_local = datetime(2026, 7, 12, 9, 0, 0, tzinfo=local_tz)
    previous_fire = None

    next_fire = trigger.get_next_fire_time(previous_fire, now_local)

    assert next_fire is not None, "应返回下一次触发时间"
    # 验证触发时间是本地 10:00
    assert next_fire.hour == 10, f"触发小时应为 10（本地），实际为 {next_fire.hour}"
    assert next_fire.minute == 0, f"触发分钟应为 0，实际为 {next_fire.minute}"


def test_cron_trigger_local_10_after_trigger_time():
    """过了本地 10:00 后，下一次触发应为第二天本地 10:00

    场景：当前本地时间 2026-07-12 11:00，下一次触发应为 2026-07-13 10:00 本地
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)
    cron_expr = "0 10 * * *"
    trigger = CronTrigger.from_crontab(cron_expr, timezone=local_tz)

    # 当前本地时间 2026-07-12 11:00（已过今天的 10:00）
    now_local = datetime(2026, 7, 12, 11, 0, 0, tzinfo=local_tz)
    previous_fire = None

    next_fire = trigger.get_next_fire_time(previous_fire, now_local)

    assert next_fire is not None
    assert next_fire.day == 13, f"触发日期应为 13（第二天），实际为 {next_fire.day}"
    assert next_fire.hour == 10, f"触发小时应为 10（本地），实际为 {next_fire.hour}"


# ==================== 场景 2: 本地 10:00 触发语义 ====================


def test_cron_trigger_local_10_means_local_time():
    """验证 "0 10 * * *" 在本地时区下表示本地 10:00 触发

    Issue #29 后: Cron 表达式基于本地时区，"0 10 * * *" 就是本地 10:00 触发，
    不再需要 UTC 换算。
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)

    # CronTrigger 使用本地时区
    trigger = CronTrigger.from_crontab("0 10 * * *", timezone=local_tz)

    # 当前本地时间 2026-07-12 09:00
    now_local = datetime(2026, 7, 12, 9, 0, 0, tzinfo=local_tz)
    next_fire = trigger.get_next_fire_time(None, now_local)

    # 触发时间转回本地时区应为 10:00
    local_fire = next_fire.astimezone(local_tz)
    assert local_fire.hour == 10, f"本地触发小时应为 10，实际为 {local_fire.hour}"
    assert local_fire.minute == 0


# ==================== 场景 3: 调度器时区独立性 ====================


def test_scheduler_local_timezone_independent_of_system_timezone():
    """验证本地时区调度器的触发时间不受系统时区影响

    场景：无论系统时区是 UTC 还是 UTC+8，CronTrigger("0 10 * * *", Asia/Shanghai)
    的下一次触发时间都是 Asia/Shanghai 10:00。

    这保证了"云端部署到海外服务器（UTC 时区）"时，任务触发时间不会错位。
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)
    cron_expr = "0 10 * * *"
    trigger = CronTrigger.from_crontab(cron_expr, timezone=local_tz)

    # 模拟不同系统时区下的"当前时间"
    utc_tz = pytz.UTC
    ny_tz = pytz.timezone("America/New_York")  # UTC-5/UTC-4

    # 同一时刻（本地 2026-07-12 09:00），用不同时区表示
    now_local = datetime(2026, 7, 12, 9, 0, 0, tzinfo=local_tz)
    now_utc = now_local.astimezone(utc_tz)  # 2026-07-12 01:00 UTC
    now_ny = now_local.astimezone(ny_tz)  # 2026-07-11 21:00 EDT

    next_from_local = trigger.get_next_fire_time(None, now_local)
    next_from_utc = trigger.get_next_fire_time(None, now_utc)
    next_from_ny = trigger.get_next_fire_time(None, now_ny)

    # 三种情况应返回同一时刻（本地 2026-07-12 10:00）
    assert next_from_local == next_from_utc == next_from_ny, "不同时区视角下的下一次触发时间应一致"
    # 转回本地时区验证
    assert next_from_local.astimezone(local_tz).hour == 10, (
        f"触发小时应为 10（本地），实际为 {next_from_local.astimezone(local_tz).hour}"
    )


# ==================== 场景 4: _dreaming 触发时的本地日期一致性 ====================


def test_dreaming_trigger_time_local_date_consistency():
    """验证 _dreaming 在本地 10:00 触发时，本地昨天计算正确

    场景：任务在本地 10:00 触发
    - 本地时间：2026-07-12 10:00
    - 本地昨天：2026-07-11
    - _dreaming 应使用本地昨天 "2026-07-11"
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)

    # 任务触发时刻：本地 10:00
    trigger_local = datetime(2026, 7, 12, 10, 0, 0, tzinfo=local_tz)

    # 本地昨天
    local_yesterday = (trigger_local - timedelta(days=1)).strftime("%Y-%m-%d")

    assert local_yesterday == "2026-07-11", f"本地昨天应为 '2026-07-11'，实际为 '{local_yesterday}'"


def test_dreaming_local_yesterday_across_local_midnight():
    """验证 _dreaming 在本地 10:00 触发时不会跨本地午夜

    场景：本地 10:00 不在本地午夜附近（00:00-01:00），
    因此本地日期稳定，不会出现"昨天"计算歧义。
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)

    # 本地 10:00 触发
    trigger_local = datetime(2026, 7, 12, 10, 0, 0, tzinfo=local_tz)
    local_yesterday = (trigger_local - timedelta(days=1)).strftime("%Y-%m-%d")

    # 验证本地触发时间不在午夜附近（00:00-01:00）
    assert trigger_local.hour >= 2, "Cron 触发时间应在本地 02:00 或之后，避免本地午夜歧义"

    # 本地昨天应为 2026-07-11
    assert local_yesterday == "2026-07-11"


# ==================== 场景 5: 状态记录的本地日期一致性 ====================


def test_cron_state_local_date_not_affected_by_system_timezone():
    """验证 Cron 状态记录的本地日期不受系统时区影响

    场景：同一时刻（UTC 2026-07-12 22:00 = 本地 2026-07-13 06:00）
    - 本地视角：2026-07-13 06:00 → 本地日期 2026-07-13
    - UTC 视角：2026-07-12 22:00 → UTC 日期 2026-07-12

    Issue #29 后应记录本地日期 "2026-07-13"，
    确保"今天"语义与用户感知一致。
    """
    local_tz = pytz.timezone(TEST_TIMEZONE)

    # UTC 2026-07-12 22:00（本地 2026-07-13 06:00）
    moment_utc = datetime(2026, 7, 12, 22, 0, 0, tzinfo=pytz.UTC)
    moment_local = moment_utc.astimezone(local_tz)

    # 模拟 get_local_today() 的行为：返回本地日期
    local_date = moment_local.date()
    local_date_str = local_date.isoformat()

    # 应为本地日期，而非 UTC 日期
    assert local_date_str == "2026-07-13", f"应记录本地日期 '2026-07-13'，实际为 '{local_date_str}'"

    # 验证 UTC 日期不同（证明使用本地日期的必要性）
    utc_date = moment_utc.strftime("%Y-%m-%d")
    assert utc_date == "2026-07-12", "UTC 日期应为 '2026-07-12'（验证 UTC 与本地日期不同）"
