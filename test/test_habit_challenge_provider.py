# test/test_habit_challenge_provider.py
import pytest
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with habit_challenge_provider.db.get_connection() as conn:
        conn.execute("DELETE FROM habit_checkins")
        conn.execute("DELETE FROM habit_challenges")
        conn.execute("DELETE FROM habits")


@pytest.fixture
def sample_habit():
    hid = habit_provider.create_habit({"name": "Test", "frequency_type": "daily", "status": "active"})
    return hid


def test_create_and_get_challenge(sample_habit):
    data = {
        "habit_id": sample_habit,
        "challenge_weeks": 2,
        "required_completions": 12,
        "from_level": 0,
        "to_level": 1,
        "start_date": "2026-03-01",
        "end_date": "2026-03-14",
        "completed_count": 0,
        "streak_base": 0,
        "status": "in_progress",
    }
    cid = habit_challenge_provider.create_challenge(data)
    assert cid is not None
    assert cid.startswith("challenge-")
    c = habit_challenge_provider.get_challenge_by_id(cid)
    assert c["habit_id"] == sample_habit
    assert c["required_completions"] == 12


def test_get_current_challenge(sample_habit):
    habit_challenge_provider.create_challenge({
        "habit_id": sample_habit, "challenge_weeks": 2, "required_completions": 12,
        "from_level": 0, "to_level": 1, "start_date": "2026-03-01", "end_date": "2026-03-14",
        "completed_count": 0, "streak_base": 0, "status": "in_progress",
    })
    current = habit_challenge_provider.get_current_challenge(sample_habit)
    assert current is not None
    assert current["status"] == "in_progress"


def test_update_challenge_status(sample_habit):
    cid = habit_challenge_provider.create_challenge({
        "habit_id": sample_habit, "challenge_weeks": 2, "required_completions": 12,
        "from_level": 0, "to_level": 1, "start_date": "2026-03-01", "end_date": "2026-03-14",
        "completed_count": 5, "streak_base": 0, "status": "in_progress",
    })
    result = habit_challenge_provider.update_challenge(
        cid, {"status": "succeeded", "finished_at": "2026-03-14T23:59:59"}
    )
    assert result is True
    c = habit_challenge_provider.get_challenge_by_id(cid)
    assert c["status"] == "succeeded"


def test_get_expired_in_progress(sample_habit):
    habit_challenge_provider.create_challenge({
        "habit_id": sample_habit, "challenge_weeks": 2, "required_completions": 12,
        "from_level": 0, "to_level": 1, "start_date": "2026-01-01", "end_date": "2026-01-14",
        "completed_count": 5, "streak_base": 0, "status": "in_progress",
    })
    expired = habit_challenge_provider.get_expired_in_progress_challenges("2026-02-28")
    assert len(expired) == 1


def test_get_challenge_history(sample_habit):
    for s in ["succeeded", "failed", "cancelled"]:
        habit_challenge_provider.create_challenge({
            "habit_id": sample_habit, "challenge_weeks": 2, "required_completions": 12,
            "from_level": 0, "to_level": 1, "start_date": "2026-01-01", "end_date": "2026-01-14",
            "completed_count": 5, "streak_base": 0, "status": s,
        })
    history = habit_challenge_provider.get_challenge_history(sample_habit)
    assert len(history) == 2  # 只返回 succeeded 和 failed，不含 cancelled
