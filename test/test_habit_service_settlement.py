import pytest
from datetime import date, timedelta
from lifeprism.server.services.habit_service import habit_service
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.schemas.habit_schemas import CreateHabitRequest, FrequencyObject

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

def test_check_settlements_no_expired():
    """无到期挑战 → 空列表"""
    habit_service.create_habit(CreateHabitRequest(
        name="A", frequency=FrequencyObject(type="daily"),
    ))
    resp = habit_service.check_settlements()
    assert resp.settlements == []

def test_check_settlements_success():
    """到期且达标 → succeeded 结算"""
    created = habit_service.create_habit(CreateHabitRequest(
        name="S", frequency=FrequencyObject(type="daily"),
    ))
    challenge = habit_challenge_provider.get_current_challenge(created.id)
    habit_challenge_provider.update_challenge(challenge["id"], {
        "completed_count": challenge["required_completions"],
        "end_date": (date.today() - timedelta(days=1)).isoformat(),
    })
    resp = habit_service.check_settlements()
    assert len(resp.settlements) == 1
    assert resp.settlements[0].result == "succeeded"
    detail = habit_service.get_habit_detail(created.id)
    assert detail.currentLevel == 1

def test_check_settlements_failure():
    """到期且未达标 → failed 结算"""
    created = habit_service.create_habit(CreateHabitRequest(
        name="F", frequency=FrequencyObject(type="daily"),
    ))
    challenge = habit_challenge_provider.get_current_challenge(created.id)
    habit_challenge_provider.update_challenge(challenge["id"], {
        "completed_count": 1,
        "end_date": (date.today() - timedelta(days=1)).isoformat(),
    })
    resp = habit_service.check_settlements()
    assert len(resp.settlements) == 1
    assert resp.settlements[0].result == "failed"

def test_check_settlements_idempotent():
    """幂等性：已结算的挑战不会重复结算"""
    created = habit_service.create_habit(CreateHabitRequest(
        name="I", frequency=FrequencyObject(type="daily"),
    ))
    challenge = habit_challenge_provider.get_current_challenge(created.id)
    habit_challenge_provider.update_challenge(challenge["id"], {
        "completed_count": 1,
        "end_date": (date.today() - timedelta(days=1)).isoformat(),
    })
    resp1 = habit_service.check_settlements()
    assert len(resp1.settlements) == 1
    resp2 = habit_service.check_settlements()
    assert len(resp2.settlements) == 0  # 不重复结算
