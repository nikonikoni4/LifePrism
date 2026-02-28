# test/test_habit_checkin_provider.py
import pytest
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with habit_checkin_provider.db.get_connection() as conn:
        conn.execute("DELETE FROM habit_checkins")
        conn.execute("DELETE FROM habit_challenges")
        conn.execute("DELETE FROM habits")


@pytest.fixture
def habit_and_challenge():
    hid = habit_provider.create_habit({"name": "Test", "frequency_type": "daily", "status": "active"})
    cid = habit_challenge_provider.create_challenge({
        "habit_id": hid, "challenge_weeks": 2, "required_completions": 12,
        "from_level": 0, "to_level": 1, "start_date": "2026-03-01", "end_date": "2026-03-14",
        "completed_count": 0, "streak_base": 0, "status": "in_progress",
    })
    return hid, cid


def test_create_and_get_checkin(habit_and_challenge):
    hid, cid = habit_and_challenge
    checkin_id = habit_checkin_provider.create_checkin({
        "habit_id": hid, "challenge_id": cid, "date": "2026-03-01",
    })
    assert checkin_id is not None
    assert checkin_id.startswith("checkin-")
    record = habit_checkin_provider.get_checkin_by_date(hid, "2026-03-01")
    assert record is not None
    assert record["challenge_id"] == cid


def test_duplicate_checkin_returns_none(habit_and_challenge):
    hid, cid = habit_and_challenge
    habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": "2026-03-01"})
    dup = habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": "2026-03-01"})
    assert dup is None  # UNIQUE 约束，不抛异常


def test_delete_checkin(habit_and_challenge):
    hid, cid = habit_and_challenge
    habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": "2026-03-01"})
    assert habit_checkin_provider.delete_checkin(hid, "2026-03-01") is True
    assert habit_checkin_provider.get_checkin_by_date(hid, "2026-03-01") is None


def test_get_checkin_dates_by_challenge(habit_and_challenge):
    hid, cid = habit_and_challenge
    for d in ["2026-03-01", "2026-03-02", "2026-03-03"]:
        habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": d})
    dates = habit_checkin_provider.get_checkin_dates_by_challenge(hid, cid)
    assert len(dates) == 3
    assert "2026-03-01" in dates


def test_count_checkins_by_challenge(habit_and_challenge):
    hid, cid = habit_and_challenge
    for d in ["2026-03-01", "2026-03-02"]:
        habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": d})
    assert habit_checkin_provider.count_checkins_by_challenge(cid) == 2


def test_get_today_checkins(habit_and_challenge):
    hid, cid = habit_and_challenge
    from datetime import date
    today = date.today().isoformat()
    habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": today})
    result = habit_checkin_provider.get_today_checkins([hid])
    assert result.get(hid) is True


def test_get_checkins_in_date_range(habit_and_challenge):
    hid, cid = habit_and_challenge
    for d in ["2026-03-01", "2026-03-05", "2026-03-10"]:
        habit_checkin_provider.create_checkin({"habit_id": hid, "challenge_id": cid, "date": d})
    records = habit_checkin_provider.get_checkins_in_date_range("2026-03-01", "2026-03-07")
    assert len(records) == 2  # 只有 03-01 和 03-05 在范围内
