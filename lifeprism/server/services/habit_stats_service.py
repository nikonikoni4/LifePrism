"""习惯统计服务：Streak 计算 + 统计接口"""
import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.schemas.habit_schemas import FrequencyObject
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ValidationError

logger = get_logger(__name__)


# ============================================================================
# 辅助函数：频率判断
# ============================================================================

def is_scheduled_day(d: date, freq: FrequencyObject) -> bool:
    """判断指定日期是否为计划执行日"""
    if freq.type == "daily":
        return True
    elif freq.type == "weekdays":
        return d.weekday() < 5  # Mon=0 ~ Fri=4
    elif freq.type == "weekend":
        return d.weekday() >= 5  # Sat=5, Sun=6
    elif freq.type == "custom":
        return (d.weekday() + 1) in (freq.specific_days or [])
    return True


def get_effective_range(
    week_start: date, week_end: date, challenge_start: date, challenge_end: date, today: date
) -> Tuple[date, date]:
    """计算有效范围: 自然周 ∩ 挑战期 ∩ 今天及以前"""
    eff_start = max(week_start, challenge_start)
    eff_end = min(week_end, challenge_end, today)
    return eff_start, eff_end


def count_scheduled_days_in_range(start: date, end: date, freq: FrequencyObject) -> int:
    """统计范围内计划执行天数"""
    count = 0
    current = start
    while current <= end:
        if is_scheduled_day(current, freq):
            count += 1
        current += timedelta(days=1)
    return count


# ============================================================================
# Streak 计算核心
# ============================================================================

def _get_daily_anchor_date(checkin_dates: set, challenge_start: date, today: date) -> Optional[date]:
    """daily 连续段锚点：今日已打卡用 today，否则从 yesterday 回溯。"""
    if today.isoformat() in checkin_dates:
        anchor = today
    else:
        anchor = today - timedelta(days=1)
    if anchor < challenge_start:
        return None
    return anchor


def _has_daily_gap_between_challenge_start_and_anchor(
    checkin_dates: set, challenge_start: date, anchor: date
) -> bool:
    """若在 [challenge_start, 锚点] 内存在漏打卡日，则视为断链（旧 streak_base 失效）。"""
    current = challenge_start
    while current <= anchor:
        if current.isoformat() not in checkin_dates:
            return True
        current += timedelta(days=1)
    return False


def calculate_daily_streak(checkin_dates: set, challenge: dict, today: date) -> int:
    """逐天判定 streak（适用于 daily 频率）。"""
    challenge_start = date.fromisoformat(challenge["start_date"])
    anchor = _get_daily_anchor_date(checkin_dates, challenge_start, today)
    if anchor is None:
        return 0

    streak = 0
    current = anchor
    while current >= challenge_start:
        if current.isoformat() in checkin_dates:
            streak += 1
        else:
            break
        current -= timedelta(days=1)
    return streak


def calculate_weekly_streak(
    checkin_dates: set, challenge: dict, freq: FrequencyObject, today: date
) -> int:
    """非 daily streak：按天累加，按周结算清零。"""
    challenge_start = date.fromisoformat(challenge["start_date"])
    challenge_end = date.fromisoformat(challenge["end_date"])
    timeline_end = min(today, challenge_end)
    if timeline_end < challenge_start:
        return 0

    checkin_day_set = {
        date.fromisoformat(d)
        for d in checkin_dates
        if challenge_start <= date.fromisoformat(d) <= timeline_end
    }
    streak = challenge.get("streak_base") or 0
    current = challenge_start
    while current <= timeline_end:
        # 每周一先结算上一自然周（Mon~Sun），未达标则清零。
        if current.weekday() == 0:
            prev_week_start = current - timedelta(days=7)
            prev_week_end = current - timedelta(days=1)
            eff_start = max(prev_week_start, challenge_start)
            eff_end = min(prev_week_end, challenge_end)
            if eff_end >= eff_start:
                scheduled = count_scheduled_days_in_range(eff_start, eff_end, freq)
                if scheduled > 0:
                    completed = sum(
                        1
                        for i in range((eff_end - eff_start).days + 1)
                        if (eff_start + timedelta(days=i)) in checkin_day_set
                    )
                    if completed < scheduled:
                        streak = 0

        # 打卡实时累加（不限制必须在 specificDays 打卡）。
        if current in checkin_day_set:
            streak += 1
        current += timedelta(days=1)

    return streak


def get_habit_streak(habit_id: str, freq: FrequencyObject, challenge: Optional[dict]) -> int:
    """获取习惯当前 Streak（含 streak_base）"""
    if not challenge:
        return 0
    today = date.today()
    checkin_list = habit_checkin_provider.get_checkin_dates_by_challenge(habit_id, challenge["id"])
    checkin_set = set(checkin_list)
    streak_base = challenge.get("streak_base") or 0
    if freq.type == "daily":
        challenge_start = date.fromisoformat(challenge["start_date"])
        anchor = _get_daily_anchor_date(checkin_set, challenge_start, today)
        current = calculate_daily_streak(checkin_set, challenge, today)
        if current <= 0:
            return 0

        # daily 仅在可连续回溯到 challenge_start 时叠加 streak_base。
        if anchor is not None and _has_daily_gap_between_challenge_start_and_anchor(
            checkin_set, challenge_start, anchor
        ):
            return current
        return streak_base + current
    else:
        return calculate_weekly_streak(checkin_set, challenge, freq, today)


# ============================================================================
# 统计接口
# ============================================================================

def _parse_freq_from_row(row: Dict[str, Any]) -> FrequencyObject:
    """从数据库行解析 FrequencyObject（读取 frequency_type + frequency_config 两个字段）"""
    config = None
    if row.get("frequency_config"):
        try:
            config = json.loads(row["frequency_config"])
        except (json.JSONDecodeError, TypeError) as e:
            raise ValidationError(f"习惯频率配置损坏: {e}") from e
    specific_days = config.get("specificDays") if config else None
    return FrequencyObject(type=row["frequency_type"], specific_days=specific_days)


def get_today_overview(today: date) -> List[Dict[str, Any]]:
    """计算今日概览，仅返回今日有计划的习惯"""
    habits = habit_provider.get_habits(status="active")
    habit_ids = [h["id"] for h in habits]
    today_checkins = habit_checkin_provider.get_today_checkins(habit_ids)
    result = []
    for h in habits:
        freq = _parse_freq_from_row(h)
        if not is_scheduled_day(today, freq):
            continue
        result.append({
            "habitId": h["id"],
            "name": h["name"],
            "isScheduledToday": True,
            "todayCheckedIn": today_checkins.get(h["id"], False),
        })
    return result


def _calc_weekly_rate_item(today: date, week_start: date, habits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算单周完成率条目。"""
    week_end = week_start + timedelta(days=6)
    rates = []
    for h in habits:
        freq = _parse_freq_from_row(h)
        challenge = habit_challenge_provider.get_current_challenge(h["id"])
        if not challenge:
            continue

        ch_start = date.fromisoformat(challenge["start_date"])
        ch_end = date.fromisoformat(challenge["end_date"])
        eff_start, eff_end = get_effective_range(week_start, week_end, ch_start, ch_end, today)
        if eff_end < eff_start:
            continue

        scheduled = count_scheduled_days_in_range(eff_start, eff_end, freq)
        if scheduled == 0:
            continue

        checkin_list = habit_checkin_provider.get_checkin_dates_by_challenge(h["id"], challenge["id"])
        checkin_set = set(checkin_list)
        completed = sum(
            1 for i in range((eff_end - eff_start).days + 1)
            if (eff_start + timedelta(days=i)).isoformat() in checkin_set
        )
        rates.append(min(completed / scheduled, 1.0))

    rate = round(sum(rates) / len(rates), 4) if rates else 0.0
    return {
        "weekStartDate": week_start.isoformat(),
        "weekEndDate": week_end.isoformat(),
        "rate": rate,
        "habitCount": len(rates),
    }


def get_weekly_stats(today: date, weeks: int) -> List[Dict[str, Any]]:
    """计算近 N 周完成率趋势（当前周在前）。"""
    habits = habit_provider.get_habits(status="active")
    if not habits or weeks <= 0:
        return []

    current_week_start = today - timedelta(days=today.weekday())
    result = []
    for i in range(weeks):
        week_start = current_week_start - timedelta(days=7 * i)
        result.append(_calc_weekly_rate_item(today, week_start, habits))
    return result


def get_heatmap(today: date, days: int) -> List[Dict[str, Any]]:
    """获取过去 days 天热力图数据。"""
    habits = habit_provider.get_habits(status="active")
    if not habits:
        result = []
        for i in range(days):
            d = (today - timedelta(days=days - 1 - i)).isoformat()
            result.append({
                "date": d,
                "totalHabits": 0,
                "completedHabits": 0,
                "completionRate": None,
                "isRestDay": True,
            })
        return result

    parsed_habits = [(h["id"], _parse_freq_from_row(h)) for h in habits]
    habit_ids = [h["id"] for h in habits]
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()
    raw = habit_checkin_provider.get_checkins_in_date_range(start, end, habit_ids)
    counter = defaultdict(int)
    for row in raw:
        counter[row["date"]] += 1
    result = []
    for i in range(days):
        day_obj = today - timedelta(days=days - 1 - i)
        date_str = day_obj.isoformat()
        total_habits = sum(1 for _, freq in parsed_habits if is_scheduled_day(day_obj, freq))
        completed_habits = counter.get(date_str, 0)
        completion_rate = None if total_habits == 0 else round(min(completed_habits / total_habits, 1.0), 4)
        result.append({
            "date": date_str,
            "totalHabits": total_habits,
            "completedHabits": completed_habits,
            "completionRate": completion_rate,
            "isRestDay": total_habits == 0,
        })
    return result
