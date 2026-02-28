"""Streak 计算测试（Task 10）"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from lifeprism.server.services.habit_stats_service import (
    is_scheduled_day,
    get_effective_range,
    calculate_daily_streak,
    calculate_weekly_streak,
    get_habit_streak,
)
from lifeprism.server.schemas.habit_schemas import FrequencyObject


def test_is_scheduled_day_daily_always_true():
    freq = FrequencyObject(type="daily")
    assert is_scheduled_day(date(2026, 2, 28), freq) is True  # Saturday


def test_is_scheduled_day_weekdays_matches():
    # weekdays = Mon~Fri; date(2026,2,28) is Saturday = weekday 5 → False
    freq = FrequencyObject(type="weekdays")
    assert is_scheduled_day(date(2026, 2, 28), freq) is False  # Saturday
    assert is_scheduled_day(date(2026, 2, 27), freq) is True   # Friday


def test_is_scheduled_day_weekend_matches():
    freq = FrequencyObject(type="weekend")
    assert is_scheduled_day(date(2026, 2, 28), freq) is True   # Saturday
    assert is_scheduled_day(date(2026, 2, 27), freq) is False  # Friday


def test_is_scheduled_day_custom_matches():
    # custom: specificDays=[1, 5]  → Tue=1, Sat=5
    freq = FrequencyObject(type="custom", specificDays=[1, 5])
    assert is_scheduled_day(date(2026, 2, 28), freq) is True   # Saturday=5
    assert is_scheduled_day(date(2026, 2, 27), freq) is False  # Friday=4


def test_get_effective_range_normal():
    week_start = date(2026, 2, 23)
    week_end   = date(2026, 3,  1)
    ch_start   = date(2026, 2, 25)
    ch_end     = date(2026, 3,  5)
    today      = date(2026, 2, 28)
    s, e = get_effective_range(week_start, week_end, ch_start, ch_end, today)
    assert s == date(2026, 2, 25)
    assert e == date(2026, 2, 28)


def test_get_effective_range_no_overlap():
    week_start = date(2026, 1, 5)
    week_end   = date(2026, 1, 11)
    ch_start   = date(2026, 2, 1)
    ch_end     = date(2026, 2, 28)
    today      = date(2026, 2, 28)
    s, e = get_effective_range(week_start, week_end, ch_start, ch_end, today)
    assert e < s


def test_calculate_daily_streak_consecutive():
    today = date(2026, 2, 28)
    challenge = {"start_date": "2026-02-20", "end_date": "2026-03-06"}
    checkins = {"2026-02-26", "2026-02-27", "2026-02-28"}
    assert calculate_daily_streak(checkins, challenge, today) == 3


def test_calculate_daily_streak_broken():
    today = date(2026, 2, 28)
    challenge = {"start_date": "2026-02-20", "end_date": "2026-03-06"}
    checkins = {"2026-02-26", "2026-02-28"}  # missing 2/27
    assert calculate_daily_streak(checkins, challenge, today) == 1


def test_calculate_daily_streak_today_not_checked():
    today = date(2026, 2, 28)
    challenge = {"start_date": "2026-02-20", "end_date": "2026-03-06"}
    checkins = {"2026-02-26", "2026-02-27"}
    assert calculate_daily_streak(checkins, challenge, today) == 0


def test_calculate_weekly_streak_one_full_week():
    # custom: Mon/Tue/Wed (0,1,2); today=Wed, all 3 checked → streak=1
    freq = FrequencyObject(type="custom", specificDays=[0, 1, 2])
    challenge = {"start_date": "2026-02-16", "end_date": "2026-03-15"}
    today = date(2026, 2, 18)
    checkins = {"2026-02-16", "2026-02-17", "2026-02-18"}
    assert calculate_weekly_streak(checkins, challenge, freq, today) == 1


def test_calculate_weekly_streak_breaks_on_incomplete_week():
    freq = FrequencyObject(type="custom", specificDays=[0, 1, 2])
    challenge = {"start_date": "2026-02-09", "end_date": "2026-03-15"}
    today = date(2026, 2, 18)
    checkins = {"2026-02-16", "2026-02-17", "2026-02-18", "2026-02-09", "2026-02-11"}
    assert calculate_weekly_streak(checkins, challenge, freq, today) == 1


def test_get_habit_streak_with_base():
    from lifeprism.server.services.habit_stats_service import habit_checkin_provider as hcp
    today = date(2026, 2, 28)
    freq = FrequencyObject(type="daily")
    challenge = {
        "id": "c-001",
        "start_date": "2026-02-20",
        "end_date": "2026-03-06",
        "streak_base": 5,
    }
    checkins = ["2026-02-26", "2026-02-27", "2026-02-28"]
    # LazySingleton 将属性访问转发到内部实例，patch 内部实例上的方法
    inner = hcp._ensure_initialized()
    with patch.object(inner, "get_checkin_dates_by_challenge", return_value=checkins):
        with patch("lifeprism.server.services.habit_stats_service.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.fromisoformat = date.fromisoformat
            result = get_habit_streak("h-001", freq, challenge)
    assert result == 8  # 5 + 3
