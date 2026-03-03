import pytest
from datetime import date, timedelta
from unittest.mock import patch
from lifeprism.server.services.habit_service import habit_service
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest, FrequencyObject, BackfillCheckInRequest, BackfillAvailabilityRequest,
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
    habit_service.pause_habit(active_habit.id, None)
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
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            "UPDATE habit_challenges SET start_date = ? WHERE id = ?",
            (yesterday, challenge["id"]),
        )
    resp = habit_service.backfill_checkin(
        active_habit.id, BackfillCheckInRequest(challengeId=challenge["id"], date=yesterday),
    )
    assert resp.checkin.date == yesterday
    assert resp.habit.currentChallenge.completedCount == 1

def test_backfill_today_fails(active_habit):
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with pytest.raises(ValidationError):
        habit_service.backfill_checkin(
            active_habit.id,
            BackfillCheckInRequest(
                challengeId=challenge["id"], date=date.today().isoformat(),
            ),
        )

def test_backfill_out_of_window_fails(active_habit):
    old_date = (date.today() - timedelta(days=8)).isoformat()
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with pytest.raises(ValidationError):
        habit_service.backfill_checkin(
            active_habit.id, BackfillCheckInRequest(challengeId=challenge["id"], date=old_date),
        )


def test_backfill_should_not_finalize_failed_challenge_immediately(active_habit):
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            """
            UPDATE habit_challenges
            SET required_completions = ?, completed_count = ?, start_date = ?, end_date = ?
            WHERE id = ?
            """,
            (
                6,
                0,
                (date.today() - timedelta(days=7)).isoformat(),
                (date.today() - timedelta(days=1)).isoformat(),
                challenge["id"],
            ),
        )

    d1 = (date.today() - timedelta(days=1)).isoformat()
    d2 = (date.today() - timedelta(days=2)).isoformat()

    resp1 = habit_service.backfill_checkin(
        active_habit.id, BackfillCheckInRequest(challengeId=challenge["id"], date=d1),
    )
    assert resp1.settlement is not None
    assert resp1.settlement.result == "failed"

    latest = habit_challenge_provider.get_challenge_by_id(challenge["id"])
    assert latest["status"] == "in_progress"

    resp2 = habit_service.backfill_checkin(
        active_habit.id, BackfillCheckInRequest(challengeId=challenge["id"], date=d2),
    )
    assert resp2.checkin.date == d2


def test_get_backfill_availability_marks_checked_dates_unselectable(active_habit):
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            "UPDATE habit_challenges SET start_date = ? WHERE id = ?",
            ((date.today() - timedelta(days=7)).isoformat(), challenge["id"]),
        )
    checked_date = (date.today() - timedelta(days=1)).isoformat()
    habit_checkin_provider.create_checkin({
        "habit_id": active_habit.id,
        "challenge_id": challenge["id"],
        "date": checked_date,
    })

    availability = habit_service.get_backfill_availability(
        BackfillAvailabilityRequest(habitId=active_habit.id, challengeId=challenge["id"]),
    )
    day_map = {d.date: d for d in availability.days}
    assert day_map[checked_date].selectable is False
    assert day_map[checked_date].reason == "already_checked_in"

def test_checkin_triggers_success_settlement(active_habit):
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
    result = habit_service._judge_challenge_result(
        created.id, challenge["id"], True, True,
    )
    assert result is not None
    assert result.result == "failed"


def test_checkin_settles_success_on_end_date(active_habit):
    # endDate 当天且达标时应成功结算
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            "UPDATE habit_challenges SET completed_count = ?, end_date = ? WHERE id = ?",
            (
                challenge["required_completions"] - 1,
                date.today().isoformat(),
                challenge["id"],
            ),
        )

    resp = habit_service.checkin_today(active_habit.id)
    assert resp.settlement is not None
    assert resp.settlement.result == "succeeded"


def test_checkin_triggers_premature_failure_before_end_date(active_habit):
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            """
            UPDATE habit_challenges
            SET required_completions = ?, completed_count = ?, end_date = ?
            WHERE id = ?
            """,
            (
                5,  # 浠婃棩鎵撳崱鍚庢渶澶?1锛屾湭鏉ュ彧鍓?1 澶╋紝涓嶅彲鑳借揪鍒?5
                0,
                (date.today() + timedelta(days=1)).isoformat(),
                challenge["id"],
            ),
        )

    resp = habit_service.checkin_today(active_habit.id)
    assert resp.settlement is not None
    assert resp.settlement.result == "failed"


def test_premature_failure_can_save_should_include_future_days(active_habit):
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            """
            UPDATE habit_challenges
            SET required_completions = ?, completed_count = ?, start_date = ?, end_date = ?
            WHERE id = ?
            """,
            (
                4,
                0,
                (date.today() - timedelta(days=1)).isoformat(),
                (date.today() + timedelta(days=2)).isoformat(),
                challenge["id"],
            ),
        )

    resp = habit_service.checkin_today(active_habit.id)
    assert resp.settlement is not None
    assert resp.settlement.result == "failed"
    assert resp.settlement.canSaveByBackfill is True


def test_judge_on_end_date_boundary_equal_should_not_fail():
    created = habit_service.create_habit(CreateHabitRequest(
        name="enddate-same-day-no-fail", frequency=FrequencyObject(type="daily"),
    ))
    challenge = habit_challenge_provider.get_current_challenge(created.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            """
            UPDATE habit_challenges
            SET required_completions = ?, completed_count = ?, end_date = ?
            WHERE id = ?
            """,
            (
                12,
                11,
                date.today().isoformat(),
                challenge["id"],
            ),
        )

    result = habit_service._judge_challenge_result(
        created.id, challenge["id"], True, True,
    )
    assert result is None
    latest = habit_challenge_provider.get_challenge_by_id(challenge["id"])
    assert latest["status"] == "in_progress"


def test_checkin_on_end_date_should_fail_when_still_unreachable(active_habit):
    challenge = habit_challenge_provider.get_current_challenge(active_habit.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            """
            UPDATE habit_challenges
            SET required_completions = ?, completed_count = ?, end_date = ?
            WHERE id = ?
            """,
            (
                4,
                1,
                date.today().isoformat(),
                challenge["id"],
            ),
        )

    resp = habit_service.checkin_today(active_habit.id)
    assert resp.settlement is not None
    assert resp.settlement.result == "failed"
    latest = habit_challenge_provider.get_challenge_by_id(challenge["id"])
    assert latest["status"] == "failed"
