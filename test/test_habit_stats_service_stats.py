"""统计接口测试（Task 11）"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from lifeprism.server.services.habit_stats_service import (
    get_today_overview,
    get_weekly_stats,
    get_heatmap,
)
from lifeprism.server.schemas.habit_schemas import FrequencyObject


def test_today_overview_scheduled_and_checked():
    habits = [{"id": "h-001", "name": "读书", "frequency_type": "daily", "frequency_config": None, "status": "active"}]
    from lifeprism.server.services.habit_stats_service import habit_checkin_provider as hcp
    inner = hcp._ensure_initialized()
    with patch.object(inner, "get_today_checkins", return_value={"h-001": True}):
        result = get_today_overview(habits, date.today())
    assert len(result) == 1
    assert result[0]["habitId"] == "h-001"
    assert result[0]["todayCheckedIn"] is True
    assert result[0]["isScheduledToday"] is True


def test_today_overview_not_scheduled():
    # weekdays only on Mon~Fri; Saturday is not scheduled
    today = date(2026, 2, 28)  # Saturday
    habits = [{"id": "h-002", "name": "运动", "frequency_type": "weekdays", "frequency_config": None, "status": "active"}]
    from lifeprism.server.services.habit_stats_service import habit_checkin_provider as hcp
    inner = hcp._ensure_initialized()
    with patch.object(inner, "get_today_checkins", return_value={}):
        result = get_today_overview(habits, today)
    assert len(result) == 0


def test_weekly_stats_single_habit_full_week():
    today = date(2026, 2, 26)  # Thursday
    habits = [{"id": "h-001", "frequency_type": "daily", "frequency_config": None, "status": "active"}]
    challenge = {"id": "c-001", "start_date": "2026-02-01", "end_date": "2026-03-31"}
    checkins = ["2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26"]
    from lifeprism.server.services.habit_stats_service import habit_checkin_provider as hcp
    from lifeprism.server.services.habit_stats_service import habit_challenge_provider as chal_p
    inner_hcp = hcp._ensure_initialized()
    inner_chal = chal_p._ensure_initialized()
    with patch.object(inner_chal, "get_current_challenge", return_value=challenge):
        with patch.object(inner_hcp, "get_checkin_dates_by_challenge", return_value=checkins):
            rate = get_weekly_stats(habits, today)
    assert rate == 1.0


def test_weekly_stats_no_habits():
    assert get_weekly_stats([], date.today()) == 0.0


def test_get_heatmap_basic():
    today = date(2026, 2, 28)
    habit_ids = ["h-001", "h-002"]
    raw = [
        {"date": "2026-02-28", "habit_id": "h-001"},
        {"date": "2026-02-27", "habit_id": "h-001"},
        {"date": "2026-02-27", "habit_id": "h-002"},
    ]
    from lifeprism.server.services.habit_stats_service import habit_checkin_provider as hcp
    inner = hcp._ensure_initialized()
    with patch.object(inner, "get_checkins_in_date_range", return_value=raw):
        result = get_heatmap(habit_ids, today, days=7)
    date_map = {item["date"]: item["count"] for item in result}
    assert date_map["2026-02-28"] == 1
    assert date_map["2026-02-27"] == 2
    assert date_map.get("2026-02-26", 0) == 0
