# test/test_habit_provider.py
import pytest
from lifeprism.server.providers.habit_provider import habit_provider


@pytest.fixture(autouse=True)
def cleanup():
    """每个测试后清理习惯相关数据"""
    yield
    with habit_provider.db.get_connection() as conn:
        conn.execute("DELETE FROM habit_chain_nodes")
        conn.execute("DELETE FROM habit_chains")
        conn.execute("DELETE FROM habit_checkins")
        conn.execute("DELETE FROM habit_challenges")
        conn.execute("DELETE FROM habits")


def test_create_and_get_habit():
    """创建习惯并通过 ID 查询"""
    data = {
        "name": "冥想",
        "description": "每天冥想5分钟",
        "frequency_type": "daily",
        "frequency_config": None,
        "current_level": 0,
        "status": "active",
        "value_id": None,
        "commitment_id": None,
    }
    habit_id = habit_provider.create_habit(data)
    assert habit_id is not None
    assert habit_id.startswith("habit-")

    habit = habit_provider.get_habit_by_id(habit_id)
    assert habit is not None
    assert habit["name"] == "冥想"
    assert habit["status"] == "active"


def test_get_habits_filter_by_status():
    """按 status 过滤习惯列表"""
    habit_provider.create_habit({"name": "A", "frequency_type": "daily", "status": "active"})
    habit_provider.create_habit({"name": "B", "frequency_type": "daily", "status": "paused"})

    active = habit_provider.get_habits(status="active")
    assert len(active) == 1
    assert active[0]["name"] == "A"

    all_habits = habit_provider.get_habits()
    assert len(all_habits) == 2


def test_update_habit():
    """更新习惯字段"""
    hid = habit_provider.create_habit({"name": "X", "frequency_type": "daily", "status": "active"})
    result = habit_provider.update_habit(hid, {"name": "Y", "description": "updated"})
    assert result is True
    h = habit_provider.get_habit_by_id(hid)
    assert h["name"] == "Y"
    assert h["description"] == "updated"


def test_delete_habit():
    """删除习惯"""
    hid = habit_provider.create_habit({"name": "Z", "frequency_type": "daily", "status": "active"})
    assert habit_provider.delete_habit(hid) is True
    assert habit_provider.get_habit_by_id(hid) is None
