# test/test_habit_service.py
import pytest
from unittest.mock import patch
from lifeprism.server.services.habit_service import habit_service
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.providers.habit_chain_provider import habit_chain_provider
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest, UpdateHabitRequest, FrequencyObject,
)

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

# --- 辅助函数测试 ---

def test_calculate_challenge_params_daily_lv0():
    from lifeprism.server.services.habit_service import calculate_challenge_params
    freq = FrequencyObject(type="daily")
    result = calculate_challenge_params(0, freq)
    assert result["challengeWeeks"] == 2
    assert result["requiredCompletions"] == 12  # ceil(14 * 0.85)

def test_calculate_challenge_params_custom_lv1():
    from lifeprism.server.services.habit_service import calculate_challenge_params
    freq = FrequencyObject(type="custom", specificDays=[1, 3, 5])
    result = calculate_challenge_params(1, freq)
    assert result["challengeWeeks"] == 3
    assert result["requiredCompletions"] == 8  # ceil(9 * 0.85)

# --- CRUD 测试 ---

def test_create_habit_with_challenge():
    req = CreateHabitRequest(
        name="冥想", frequency=FrequencyObject(type="daily"), initialLevel=0,
    )
    result = habit_service.create_habit(req)
    assert result is not None
    assert result.name == "冥想"
    assert result.currentLevel == 0
    assert result.currentChallenge is not None
    assert result.currentChallenge.status == "in_progress"
    assert result.currentChallenge.fromLevel == 0
    assert result.currentChallenge.toLevel == 1
    assert result.streak == 0

def test_get_habits_list():
    habit_service.create_habit(CreateHabitRequest(
        name="A", frequency=FrequencyObject(type="daily"),
    ))
    habit_service.create_habit(CreateHabitRequest(
        name="B", frequency=FrequencyObject(type="weekdays"),
    ))
    resp = habit_service.get_habits(None)
    assert len(resp.habits) == 2

def test_update_habit_name_only():
    req = CreateHabitRequest(name="X", frequency=FrequencyObject(type="daily"))
    created = habit_service.create_habit(req)
    old_challenge_id = created.currentChallenge.id
    updated = habit_service.update_habit(
        created.id, UpdateHabitRequest(name="Y"),
    )
    assert updated.name == "Y"
    assert updated.currentChallenge.id == old_challenge_id  # 挑战不变

def test_update_habit_level_resets_challenge():
    created = habit_service.create_habit(CreateHabitRequest(
        name="X", frequency=FrequencyObject(type="daily"),
    ))
    old_challenge_id = created.currentChallenge.id
    updated = habit_service.update_habit(created.id, UpdateHabitRequest(level=2))
    assert updated.currentLevel == 2
    assert updated.currentChallenge.id != old_challenge_id
    assert updated.currentChallenge.fromLevel == 2

def test_delete_habit_cascade():
    created = habit_service.create_habit(CreateHabitRequest(
        name="Del", frequency=FrequencyObject(type="daily"),
    ))
    # 关联到链条节点
    cid = habit_chain_provider.create_chain({"name": "C"})
    habit_chain_provider.create_node({
        "chain_id": cid, "sort_order": 0, "name": "N", "habit_id": created.id,
    })
    assert habit_service.delete_habit(created.id) is True
    assert habit_provider.get_habit_by_id(created.id) is None
    nodes = habit_chain_provider.get_nodes_by_chain(cid)
    assert nodes[0]["habit_id"] is None  # 降级为锚点

# --- 状态变更测试 ---

def test_pause_and_resume():
    created = habit_service.create_habit(CreateHabitRequest(
        name="P", frequency=FrequencyObject(type="daily"),
    ))
    paused = habit_service.pause_habit(created.id)
    assert paused.status == "paused"
    assert paused.currentChallenge is None  # cancelled 后无 in_progress

    resumed = habit_service.resume_habit(created.id)
    assert resumed.status == "active"
    assert resumed.currentChallenge is not None
    assert resumed.currentChallenge.status == "in_progress"
