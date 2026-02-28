import pytest
from datetime import date, timedelta
from unittest.mock import patch
from lifeprism.server.services.habit_service import habit_service
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest, FrequencyObject, BackfillCheckInRequest,
)
from lifeprism.utils.exceptions import NotFoundError, ValidationError, ConflictError

@pytest.fixture(autouse=True)
def cleanup():
    yield
    with habit_provider.db.get_connection() as conn:
        conn.execute("DELETE FROM habit_chain_nodes")
        conn.execute("DELETE FROM habit_chains")
        conn.execute("DELETE FROM habit_checkins")
        conn.execute("DELETE FROM habit_challenges")
        conn.execute("DELETE FROM habits")
    habit_service._refresh_cache()

@pytest.fixture
def active_habit():
    return habit_service.create_habit(CreateHabitRequest(
        name="Test", frequency=FrequencyObject(type="daily"),
    ))

def test_checkin_today(active_habit):
    resp = habit_service.checkin_today(active_habit.id)
    assert resp.checkin.habitId == active_habit.id
    assert resp.checkin.date == date.today().isoformat()
    assert resp.habit.currentChallenge.completedCount == 1
    assert resp.settlement is None

def test_checkin_duplicate_fails(active_habit):
    habit_service.checkin_today(active_habit.id)
    with pytest.raises(ConflictError):
        habit_service.checkin_today(active_habit.id)

def test_checkin_paused_fails(active_habit):
    habit_service.pause_habit(active_habit.id)
    with pytest.raises(ValidationError):
        habit_service.checkin_today(active_habit.id)

def test_cancel_checkin(active_habit):
    habit_service.checkin_today(active_habit.id)
    resp = habit_service.cancel_checkin(active_habit.id, date.today().isoformat())
    assert resp.habit.currentChallenge.completedCount == 0
    assert resp.settlement is None

def test_cancel_checkin_not_today_fails(active_habit):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        habit_service.cancel_checkin(active_habit.id, yesterday)

def test_backfill_checkin(active_habit):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    resp = habit_service.backfill_checkin(
        active_habit.id, BackfillCheckInRequest(date=yesterday),
    )
    assert resp.checkin.date == yesterday
    assert resp.habit.currentChallenge.completedCount == 1

def test_backfill_today_fails(active_habit):
    with pytest.raises(ValidationError, match="今日打卡请使用打卡接口"):
        habit_service.backfill_checkin(
            active_habit.id, BackfillCheckInRequest(date=date.today().isoformat()),
        )

def test_backfill_out_of_window_fails(active_habit):
    old_date = (date.today() - timedelta(days=8)).isoformat()
    with pytest.raises(ValidationError, match="只能补签过去 7 天内的日期"):
        habit_service.backfill_checkin(
            active_habit.id, BackfillCheckInRequest(date=old_date),
        )

def test_checkin_triggers_success_settlement(active_habit):
    """打满 requiredCompletions 且 endDate 已过 → succeeded"""
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    habit_challenge_provider.update_challenge(challenge["id"], {
        "completed_count": challenge["required_completions"] - 1,
    })
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            "UPDATE habit_challenges SET end_date = ? WHERE id = ?",
            ((date.today() - timedelta(days=1)).isoformat(), challenge["id"]),
        )
    resp = habit_service.checkin_today(active_habit.id)
    assert resp.settlement is not None
    assert resp.settlement.result == "succeeded"

def test_judge_challenge_failed():
    """endDate 已过且未达标 → failed"""
    created = habit_service.create_habit(CreateHabitRequest(
        name="F", frequency=FrequencyObject(type="daily"),
    ))
    challenge = habit_challenge_provider.get_current_challenge(created.id)
    habit_challenge_provider.update_challenge(challenge["id"], {
        "completed_count": 1,
    })
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            "UPDATE habit_challenges SET end_date = ? WHERE id = ?",
            ((date.today() - timedelta(days=1)).isoformat(), challenge["id"]),
        )
    result = habit_service._judge_challenge_result(created.id, challenge["id"])
    assert result is not None
    assert result.result == "failed"
