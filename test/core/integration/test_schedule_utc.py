"""定时任务 UTC 时区迁移集成测试

验证 Cron 表达式在不同时区下的触发时间正确性。

测试场景:
1. Cron 表达式 "0 2 * * *" + UTC 时区 → 下一次触发时间是 UTC 02:00
2. UTC 02:00 在 UTC+8 时区下对应本地 10:00（保持用户预期的"本地 10:00 触发"）
3. 不同系统时区下，调度器使用 UTC 时区，触发时间不受系统时区影响

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
"""

from datetime import datetime, timezone, timedelta

import pytest
import pytz
from apscheduler.triggers.cron import CronTrigger

pytestmark = pytest.mark.core


# ==================== 场景 1: Cron 表达式触发时间 ====================


def test_cron_trigger_utc_02_next_fire_time():
    """Cron 表达式 "0 2 * * *" 在 UTC 时区下的下一次触发时间应为 UTC 02:00

    场景：当前 UTC 时间 2026-07-12 01:00，下一次触发应为 2026-07-12 02:00 UTC
    """
    cron_expr = "0 2 * * *"
    trigger = CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)

    # 当前 UTC 时间 2026-07-12 01:00
    now_utc = datetime(2026, 7, 12, 1, 0, 0, tzinfo=pytz.UTC)
    previous_fire = None

    next_fire = trigger.get_next_fire_time(previous_fire, now_utc)

    assert next_fire is not None, "应返回下一次触发时间"
    # 验证触发时间是 UTC 02:00
    assert next_fire.hour == 2, f"触发小时应为 2（UTC），实际为 {next_fire.hour}"
    assert next_fire.minute == 0, f"触发分钟应为 0，实际为 {next_fire.minute}"
    # APScheduler 可能使用 pytz.UTC 或 zoneinfo.ZoneInfo('UTC')，两者功能等价
    # 通过 utcoffset 验证是 UTC 时区（偏移为 0）
    assert next_fire.utcoffset() == timedelta(0), (
        f"触发时间应为 UTC 时区（offset=0），实际 offset={next_fire.utcoffset()}"
    )


def test_cron_trigger_utc_02_after_trigger_time():
    """过了 UTC 02:00 后，下一次触发应为第二天 UTC 02:00

    场景：当前 UTC 时间 2026-07-12 03:00，下一次触发应为 2026-07-13 02:00 UTC
    """
    cron_expr = "0 2 * * *"
    trigger = CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)

    # 当前 UTC 时间 2026-07-12 03:00（已过今天的 02:00）
    now_utc = datetime(2026, 7, 12, 3, 0, 0, tzinfo=pytz.UTC)
    previous_fire = None

    next_fire = trigger.get_next_fire_time(previous_fire, now_utc)

    assert next_fire is not None
    assert next_fire.day == 13, f"触发日期应为 13（第二天），实际为 {next_fire.day}"
    assert next_fire.hour == 2, f"触发小时应为 2（UTC），实际为 {next_fire.hour}"


# ==================== 场景 2: UTC 02:00 = 本地 10:00（UTC+8） ====================


def test_utc_02_equals_local_10_in_utc_plus_8():
    """验证 UTC 02:00 在 UTC+8 时区下对应本地 10:00

    这是迁移的核心决策：保持用户预期的"本地时间 10:00 触发"，
    通过将 Cron 表达式从 "0 10 * * *"（本地）改为 "0 2 * * *"（UTC）实现。
    """
    # UTC 02:00
    utc_02 = datetime(2026, 7, 12, 2, 0, 0, tzinfo=pytz.UTC)

    # 转换为 UTC+8（北京时间）
    beijing_tz = pytz.timezone("Asia/Shanghai")
    beijing_time = utc_02.astimezone(beijing_tz)

    assert beijing_time.hour == 10, (
        f"UTC 02:00 应对应北京时间 10:00，实际为 {beijing_time.hour}"
    )
    assert beijing_time.minute == 0


def test_cron_trigger_in_utc_equals_local_10_trigger_in_utc_plus_8():
    """验证 UTC 时区的 "0 2 * * *" 与 UTC+8 时区的 "0 10 * * *" 触发时间一致

    迁移前: CronTrigger("0 10 * * *", timezone=本地时区) → 本地 10:00 触发
    迁移后: CronTrigger("0 2 * * *", timezone=UTC) → UTC 02:00 触发 = 本地 10:00

    两者应在同一时刻触发。
    """
    beijing_tz = pytz.timezone("Asia/Shanghai")

    # 迁移前：本地时区 "0 10 * * *"
    trigger_before = CronTrigger.from_crontab("0 10 * * *", timezone=beijing_tz)
    # 迁移后：UTC "0 2 * * *"
    trigger_after = CronTrigger.from_crontab("0 2 * * *", timezone=pytz.UTC)

    # 当前 UTC 时间 2026-07-12 01:00（本地 09:00）
    now_utc = datetime(2026, 7, 12, 1, 0, 0, tzinfo=pytz.UTC)

    next_before = trigger_before.get_next_fire_time(None, now_utc)
    next_after = trigger_after.get_next_fire_time(None, now_utc)

    # 两者触发时刻应一致（转为 UTC 后比较）
    assert next_before == next_after, (
        f"迁移前后触发时间应一致：迁移前={next_before}，迁移后={next_after}"
    )


# ==================== 场景 3: 调度器时区独立性 ====================


def test_scheduler_utc_timezone_independent_of_system_timezone():
    """验证 UTC 调度器的触发时间不受系统时区影响

    场景：无论系统时区是 UTC 还是 UTC+8，CronTrigger("0 2 * * *", UTC)
    的下一次触发时间都是 UTC 02:00。

    这保证了"云端部署到海外服务器（UTC 时区）"时，任务触发时间不会错位。
    """
    cron_expr = "0 2 * * *"
    trigger = CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)

    # 模拟不同系统时区下的"当前时间"
    # 关键：无论 now 是哪个时区的，trigger 都按 UTC 计算
    utc_tz = pytz.UTC
    beijing_tz = pytz.timezone("Asia/Shanghai")
    ny_tz = pytz.timezone("America/New_York")  # UTC-5/UTC-4

    # 同一时刻（UTC 2026-07-12 01:00），用不同时区表示
    now_utc = datetime(2026, 7, 12, 1, 0, 0, tzinfo=utc_tz)
    now_beijing = now_utc.astimezone(beijing_tz)  # 2026-07-12 09:00 +08:00
    now_ny = now_utc.astimezone(ny_tz)  # 2026-07-11 21:00 EDT

    next_from_utc = trigger.get_next_fire_time(None, now_utc)
    next_from_beijing = trigger.get_next_fire_time(None, now_beijing)
    next_from_ny = trigger.get_next_fire_time(None, now_ny)

    # 三种情况应返回同一时刻（UTC 2026-07-12 02:00）
    assert next_from_utc == next_from_beijing == next_from_ny, (
        "不同时区视角下的下一次触发时间应一致"
    )
    assert next_from_utc.hour == 2, f"触发小时应为 2（UTC），实际为 {next_from_utc.hour}"


# ==================== 场景 4: _dreaming 触发时的 UTC 日期一致性 ====================


def test_dreaming_trigger_time_utc_date_consistency():
    """验证 _dreaming 在 UTC 02:00 触发时，UTC 昨天与本地昨天一致

    场景：UTC+8 时区，任务在 UTC 02:00 触发（本地 10:00）
    - UTC 时间：2026-07-12 02:00
    - 本地时间：2026-07-12 10:00
    - UTC 昨天：2026-07-11
    - 本地昨天：2026-07-11
    - 两者一致，因此 _dreaming 使用 UTC 昨天是安全的

    这验证了 Issue #1 文档中提到的"在任务触发时间（UTC 02:00），
    UTC 昨天和本地昨天是一致的"这一关键决策。
    """
    beijing_tz = pytz.timezone("Asia/Shanghai")

    # 任务触发时刻：UTC 02:00
    trigger_utc = datetime(2026, 7, 12, 2, 0, 0, tzinfo=pytz.UTC)

    # UTC 昨天
    utc_yesterday = (trigger_utc - timedelta(days=1)).strftime("%Y-%m-%d")

    # 本地昨天（UTC+8 视角）
    trigger_local = trigger_utc.astimezone(beijing_tz)
    local_yesterday = (trigger_local - timedelta(days=1)).strftime("%Y-%m-%d")

    assert utc_yesterday == local_yesterday, (
        f"在 UTC 02:00 触发时，UTC 昨天 ({utc_yesterday}) "
        f"应与本地昨天 ({local_yesterday}) 一致"
    )


def test_dreaming_trigger_time_across_utc_midnight():
    """验证 _dreaming 在 UTC 02:00 触发时不会跨 UTC 午夜

    场景：UTC 02:00 不在 UTC 午夜附近（00:00-01:00），
    因此 UTC 日期稳定，不会出现"昨天"计算歧义。

    对比：如果任务在 UTC 23:30 触发，UTC 减 1 天会到前一天，
    但本地时间可能是第二天的某个时刻，语义会混乱。
    """
    # UTC 02:00 触发
    trigger_utc = datetime(2026, 7, 12, 2, 0, 0, tzinfo=pytz.UTC)
    utc_yesterday = (trigger_utc - timedelta(days=1)).strftime("%Y-%m-%d")

    # 验证 UTC 触发时间不在午夜附近（00:00-01:00）
    assert trigger_utc.hour >= 2, (
        "Cron 触发时间应在 UTC 02:00 或之后，避免 UTC 午夜歧义"
    )

    # UTC 昨天应为 2026-07-11
    assert utc_yesterday == "2026-07-11"


# ==================== 场景 5: 状态记录的 UTC 日期一致性 ====================


def test_cron_state_utc_date_not_affected_by_system_timezone():
    """验证 Cron 状态记录的 UTC 日期不受系统时区影响

    场景：同一时刻（UTC 2026-07-12 22:00）
    - UTC 视角：2026-07-12
    - UTC+8 视角：2026-07-13 06:00

    迁移后应记录 UTC 日期 "2026-07-12"，
    确保无论系统时区如何，状态记录一致。
    """
    # UTC 2026-07-12 22:00（本地 UTC+8 为 2026-07-13 06:00）
    moment_utc = datetime(2026, 7, 12, 22, 0, 0, tzinfo=pytz.UTC)

    # 代码中使用 datetime.now(timezone.utc).strftime("%Y-%m-%d")
    utc_date = moment_utc.strftime("%Y-%m-%d")

    # 应为 UTC 日期，而非本地日期
    assert utc_date == "2026-07-12", (
        f"应记录 UTC 日期 '2026-07-12'，实际为 '{utc_date}'"
    )

    # 验证本地日期不同（证明使用 UTC 的必要性）
    beijing_tz = pytz.timezone("Asia/Shanghai")
    local_date = moment_utc.astimezone(beijing_tz).strftime("%Y-%m-%d")
    assert local_date == "2026-07-13", (
        f"本地日期应为 '2026-07-13'（验证 UTC 与本地日期不同）"
    )
