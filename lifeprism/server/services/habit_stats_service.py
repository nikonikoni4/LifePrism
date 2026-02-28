"""习惯统计服务：Streak 计算 + 统计接口"""
import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

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
        return d.weekday() in (freq.specificDays or [])
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

def calculate_daily_streak(checkin_dates: set, challenge: dict, today: date) -> int:
    """逐天判定 streak（适用于 daily 频率）"""
    challenge_start = date.fromisoformat(challenge["start_date"])
    streak = 0
    current = today
    while current >= challenge_start:
        if current.isoformat() in checkin_dates:
            streak += 1
        else:
            break
        current -= timedelta(days=1)
    return streak


def calculate_weekly_streak(checkin_dates: set, challenge: dict, freq: FrequencyObject, today: date) -> int:
    """逐周判定 streak（适用于非 daily 频率）"""
    challenge_start = date.fromisoformat(challenge["start_date"])
    challenge_end = date.fromisoformat(challenge["end_date"])
    streak = 0
    week_start = today - timedelta(days=today.weekday())
    while True:
        week_end = week_start + timedelta(days=6)
        eff_start, eff_end = get_effective_range(week_start, week_end, challenge_start, challenge_end, today)
        if eff_end < eff_start:
            break
        scheduled = count_scheduled_days_in_range(eff_start, eff_end, freq)
        completed = sum(
            1 for i in range((eff_end - eff_start).days + 1)
            if (eff_start + timedelta(days=i)).isoformat() in checkin_dates
        )
        if scheduled > 0 and completed >= scheduled:
            streak += 1
            week_start -= timedelta(days=7)
        else:
            break
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
        current = calculate_daily_streak(checkin_set, challenge, today)
    else:
        current = calculate_weekly_streak(checkin_set, challenge, freq, today)
    return streak_base + current


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
    return FrequencyObject(type=row["frequency_type"], specificDays=specific_days)


def get_today_overview(habits: List[Dict[str, Any]], today: date) -> List[Dict[str, Any]]:
    """计算今日概览，仅返回今日有计划的习惯"""
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


def get_weekly_stats(habits: List[Dict[str, Any]], today: date) -> float:
    """计算本周完成率（所有习惯的算术平均值）"""
    if not habits:
        return 0.0
    week_start = today - timedelta(days=today.weekday())
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
    if not rates:
        return 0.0
    return round(sum(rates) / len(rates), 4)


def get_heatmap(habit_ids: List[str], today: date, days: int) -> List[Dict[str, Any]]:
    """获取过去 days 天热力图数据"""
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()
    raw = habit_checkin_provider.get_checkins_in_date_range(start, end, habit_ids)
    counter = defaultdict(int)
    for row in raw:
        counter[row["date"]] += 1
    result = []
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        result.append({"date": d, "count": counter.get(d, 0)})
    return result
