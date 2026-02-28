"""
test_habit_api.py — habit_api 路由单元测试

测试策略：
- 正常导入 habit_api（schema/exceptions 无副作用，LazySingleton 懒加载不连接数据库）
- 导入后直接替换 habit_api 模块级变量为 MagicMock，避免 LazySingleton.__delattr__ 问题
- 每次测试前通过 setup_function 重置 mock
- 路径不带 /api/v2/habit 前缀
"""
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# 先导入 router（此时 LazySingleton 只创建代理，不触发实例化）
from lifeprism.server.api.habit_api import router
import lifeprism.server.api.habit_api as habit_api_module

# 替换模块级 service 变量为 MagicMock（路由函数通过模块变量访问）
mock_habit_service = MagicMock()
mock_habit_chain_service = MagicMock()

# habit_stats_service 是以模块方式导入的，API 里用 habit_stats_service.get_xxx()
# 我们创建一个 mock 模块对象，挂上需要的函数属性
import types
mock_stats_module = types.ModuleType("habit_stats_service_mock")
mock_stats_module.get_today_overview = MagicMock(return_value=[])
mock_stats_module.get_weekly_stats = MagicMock(return_value=0.0)
mock_stats_module.get_heatmap = MagicMock(return_value=[])

habit_api_module.habit_service = mock_habit_service
habit_api_module.habit_stats_service = mock_stats_module
habit_api_module.habit_chain_service = mock_habit_chain_service

# 创建测试 app
app_instance = FastAPI()
app_instance.include_router(router)
client = TestClient(app_instance)

# ── 便捷别名 ──
hs = mock_habit_service
hss = mock_stats_module
hcs = mock_habit_chain_service

from lifeprism.utils.exceptions import NotFoundError, ConflictError, ValidationError


def setup_function():
    """每个测试前重置 mock 状态"""
    hs.reset_mock()
    hcs.reset_mock()
    hss.get_today_overview.reset_mock()
    hss.get_today_overview.return_value = []
    hss.get_weekly_stats.reset_mock()
    hss.get_weekly_stats.return_value = 0.0
    hss.get_heatmap.reset_mock()
    hss.get_heatmap.return_value = []
    # 重要：reset_mock 不清除 side_effect，需要手动清除
    for attr in dir(hs):
        pass  # reset_mock() 已经处理了


# ============================================================================
# 习惯 CRUD
# ============================================================================

def test_list_habits_empty():
    mock_resp = MagicMock()
    mock_resp.habits = []
    hs.get_habits.return_value = mock_resp
    hs.get_habits.side_effect = None
    resp = client.get("/habits")
    assert resp.status_code == 200
    hs.get_habits.assert_called_once_with(None)


def test_list_habits_with_status_filter():
    mock_resp = MagicMock()
    mock_resp.habits = []
    hs.get_habits.return_value = mock_resp
    hs.get_habits.side_effect = None
    resp = client.get("/habits?status=active")
    assert resp.status_code == 200
    hs.get_habits.assert_called_once_with("active")


def test_create_habit_success():
    mock_habit = MagicMock()
    mock_habit.model_dump.return_value = {
        "id": "habit-abc123", "name": "读书", "status": "active"
    }
    hs.create_habit.return_value = mock_habit
    hs.create_habit.side_effect = None
    resp = client.post("/habits", json={
        "name": "读书",
        "frequency": {"type": "daily"},
    })
    assert resp.status_code == 201


def test_create_habit_missing_name():
    resp = client.post("/habits", json={"frequency": {"type": "daily"}})
    assert resp.status_code == 422


def test_get_habit_success():
    mock_habit = MagicMock()
    mock_habit.model_dump.return_value = {"id": "h-001", "name": "运动"}
    hs.get_habit_detail.return_value = mock_habit
    hs.get_habit_detail.side_effect = None
    resp = client.get("/habits/h-001")
    assert resp.status_code == 200


def test_get_habit_not_found():
    hs.get_habit_detail.side_effect = NotFoundError("not found")
    resp = client.get("/habits/habit-notexist")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_update_habit_success():
    mock_habit = MagicMock()
    mock_habit.model_dump.return_value = {"id": "h-001", "name": "新名称"}
    hs.update_habit.return_value = mock_habit
    hs.update_habit.side_effect = None
    resp = client.patch("/habits/h-001", json={"name": "新名称"})
    assert resp.status_code == 200


def test_update_habit_not_found():
    hs.update_habit.side_effect = NotFoundError("not found")
    resp = client.patch("/habits/habit-notexist", json={"name": "X"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_delete_habit_success():
    hs.delete_habit.return_value = True
    hs.delete_habit.side_effect = None
    resp = client.delete("/habits/h-001")
    assert resp.status_code == 204


def test_delete_habit_not_found():
    hs.delete_habit.side_effect = NotFoundError("not found")
    resp = client.delete("/habits/habit-notexist")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_pause_habit_success():
    hs.pause_habit.return_value = MagicMock()
    hs.pause_habit.side_effect = None
    resp = client.post("/habits/h-001/pause")
    assert resp.status_code == 200


def test_pause_habit_not_found():
    hs.pause_habit.side_effect = NotFoundError("not found")
    resp = client.post("/habits/h-notexist/pause")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_pause_habit_invalid_transition():
    hs.pause_habit.side_effect = ValidationError("已暂停")
    resp = client.post("/habits/h-001/pause")
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "INVALID_STATUS_TRANSITION"


def test_resume_habit_success():
    hs.resume_habit.return_value = MagicMock()
    hs.resume_habit.side_effect = None
    resp = client.post("/habits/h-001/resume")
    assert resp.status_code == 200


def test_resume_habit_not_found():
    hs.resume_habit.side_effect = NotFoundError("not found")
    resp = client.post("/habits/h-notexist/resume")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_resume_habit_invalid_transition():
    hs.resume_habit.side_effect = ValidationError("已激活")
    resp = client.post("/habits/h-001/resume")
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "INVALID_STATUS_TRANSITION"


# ============================================================================
# 打卡操作
# ============================================================================

def test_checkin_today():
    mock_resp = MagicMock()
    mock_resp.model_dump.return_value = {"checkin_id": "c-001", "settlement": None}
    hs.checkin_today.return_value = mock_resp
    hs.checkin_today.side_effect = None
    resp = client.post("/habits/h-001/checkin")
    assert resp.status_code == 200


def test_checkin_conflict():
    hs.checkin_today.side_effect = ConflictError("already exists")
    resp = client.post("/habits/h-001/checkin")
    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "CHECKIN_ALREADY_EXISTS"


def test_checkin_habit_not_found():
    hs.checkin_today.side_effect = NotFoundError("not found")
    resp = client.post("/habits/h-notexist/checkin")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_checkin_habit_not_active():
    hs.checkin_today.side_effect = ValidationError("习惯处于暂停状态")
    resp = client.post("/habits/h-001/checkin")
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_ACTIVE"


def test_cancel_checkin_success():
    mock_resp = MagicMock()
    mock_resp.model_dump.return_value = {"habit": {}, "settlement": None}
    hs.cancel_checkin.return_value = mock_resp
    hs.cancel_checkin.side_effect = None
    resp = client.delete("/habits/h-001/checkin/2026-03-01")
    assert resp.status_code == 200


def test_cancel_checkin_not_found():
    hs.cancel_checkin.side_effect = NotFoundError("该日期无打卡记录")
    resp = client.delete("/habits/h-001/checkin/2026-03-01")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "CHECKIN_NOT_FOUND"


def test_cancel_checkin_past_date():
    hs.cancel_checkin.side_effect = ValidationError("只能取消当天")
    resp = client.delete("/habits/h-001/checkin/2026-02-01")
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "CANNOT_CANCEL_PAST_CHECKIN"


def test_backfill_checkin_success():
    hs.backfill_checkin.return_value = MagicMock()
    hs.backfill_checkin.side_effect = None
    resp = client.post("/habits/h-001/checkin/backfill", json={"date": "2026-02-28"})
    assert resp.status_code == 200


def test_backfill_checkin_invalid_date_format():
    resp = client.post("/habits/h-001/checkin/backfill", json={"date": "not-a-date"})
    assert resp.status_code == 422


# ============================================================================
# 挑战历史 & 结算
# ============================================================================

def test_get_challenge_history_success():
    hs.get_challenge_history.return_value = []
    hs.get_challenge_history.side_effect = None
    resp = client.get("/habits/h-001/challenges")
    assert resp.status_code == 200
    assert "challenges" in resp.json()


def test_get_challenge_history_not_found():
    hs.get_challenge_history.side_effect = NotFoundError("not found")
    resp = client.get("/habits/h-notexist/challenges")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "HABIT_NOT_FOUND"


def test_check_settlements():
    mock_resp = MagicMock()
    mock_resp.model_dump.return_value = {"settlements": []}
    hs.check_settlements.return_value = mock_resp
    hs.check_settlements.side_effect = None
    resp = client.post("/habits/check-settlements")
    assert resp.status_code == 200


# ============================================================================
# 统计
# ============================================================================

def test_today_overview():
    mock_habits_resp = MagicMock()
    mock_habits_resp.habits = []
    hs.get_habits.return_value = mock_habits_resp
    hs.get_habits.side_effect = None
    hss.get_today_overview.return_value = []
    resp = client.get("/stats/today")
    assert resp.status_code == 200
    assert "overview" in resp.json()


def test_weekly_stats():
    mock_habits_resp = MagicMock()
    mock_habits_resp.habits = []
    hs.get_habits.return_value = mock_habits_resp
    hs.get_habits.side_effect = None
    hss.get_weekly_stats.return_value = 0.75
    resp = client.get("/stats/weekly")
    assert resp.status_code == 200
    assert "completion_rate" in resp.json()
    assert resp.json()["completion_rate"] == 0.75


def test_heatmap_default_days():
    mock_habits_resp = MagicMock()
    mock_habits_resp.habits = []
    hs.get_habits.return_value = mock_habits_resp
    hs.get_habits.side_effect = None
    hss.get_heatmap.return_value = []
    resp = client.get("/stats/heatmap")
    assert resp.status_code == 200
    assert "heatmap" in resp.json()
    call_args = hss.get_heatmap.call_args
    assert call_args[0][2] == 365


def test_heatmap_custom_days():
    mock_habits_resp = MagicMock()
    mock_habits_resp.habits = []
    hs.get_habits.return_value = mock_habits_resp
    hs.get_habits.side_effect = None
    hss.get_heatmap.return_value = []
    resp = client.get("/stats/heatmap?days=90")
    assert resp.status_code == 200
    call_args = hss.get_heatmap.call_args
    assert call_args[0][2] == 90


def test_heatmap_days_out_of_range():
    resp = client.get("/stats/heatmap?days=5")  # ge=7
    assert resp.status_code == 422


# ============================================================================
# 链式习惯
# ============================================================================

def test_list_chains():
    mock_resp = MagicMock()
    mock_resp.chains = []
    hcs.get_chains.return_value = mock_resp
    hcs.get_chains.side_effect = None
    resp = client.get("/chains")
    assert resp.status_code == 200


def test_list_chains_with_filter():
    mock_resp = MagicMock()
    mock_resp.chains = []
    hcs.get_chains.return_value = mock_resp
    hcs.get_chains.side_effect = None
    resp = client.get("/chains?show_in_timeline=true")
    assert resp.status_code == 200
    hcs.get_chains.assert_called_once_with(True)


def test_create_chain():
    mock_chain = MagicMock()
    mock_chain.model_dump.return_value = {"id": 1, "name": "晨间链"}
    hcs.create_chain.return_value = mock_chain
    hcs.create_chain.side_effect = None
    resp = client.post("/chains", json={"name": "晨间链"})
    assert resp.status_code == 201


def test_create_chain_missing_name():
    resp = client.post("/chains", json={})
    assert resp.status_code == 422


def test_get_timeline():
    mock_resp = MagicMock()
    mock_resp.chains = []
    hcs.get_timeline.return_value = mock_resp
    hcs.get_timeline.side_effect = None
    resp = client.get("/chains/timeline")
    assert resp.status_code == 200


def test_get_chain_success():
    hcs.get_chain_detail.return_value = MagicMock()
    hcs.get_chain_detail.side_effect = None
    resp = client.get("/chains/1")
    assert resp.status_code == 200


def test_get_chain_not_found():
    hcs.get_chain_detail.side_effect = NotFoundError("Chain 999 not found")
    resp = client.get("/chains/999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "CHAIN_NOT_FOUND"


def test_update_chain_success():
    hcs.update_chain.return_value = MagicMock()
    hcs.update_chain.side_effect = None
    resp = client.patch("/chains/1", json={"name": "新链名"})
    assert resp.status_code == 200


def test_update_chain_not_found():
    hcs.update_chain.side_effect = NotFoundError("Chain 999 not found")
    resp = client.patch("/chains/999", json={"name": "X"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "CHAIN_NOT_FOUND"


def test_update_chain_validation_failed():
    hcs.update_chain.side_effect = ValidationError("没有节点")
    resp = client.patch("/chains/1", json={"showInTimeline": True})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "CHAIN_VALIDATION_FAILED"


def test_delete_chain_success():
    hcs.delete_chain.return_value = None
    hcs.delete_chain.side_effect = None
    resp = client.delete("/chains/1")
    assert resp.status_code == 204


def test_delete_chain_not_found():
    hcs.delete_chain.side_effect = NotFoundError("Chain 999 not found")
    resp = client.delete("/chains/999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "CHAIN_NOT_FOUND"


def test_create_node_success():
    mock_node = {"id": 1, "name": "起床", "sort_order": 1}
    hcs.create_node.return_value = mock_node
    hcs.create_node.side_effect = None
    resp = client.post("/chains/1/nodes", json={"name": "起床"})
    assert resp.status_code == 201


def test_create_node_chain_not_found():
    hcs.create_node.side_effect = NotFoundError("Chain 999 not found")
    resp = client.post("/chains/999/nodes", json={"name": "节点"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "CHAIN_NOT_FOUND"


def test_update_node_success():
    mock_node = {"id": 1, "name": "新名称"}
    hcs.update_node.return_value = mock_node
    hcs.update_node.side_effect = None
    resp = client.patch("/chains/1/nodes/1", json={"name": "新名称"})
    assert resp.status_code == 200


def test_update_node_not_found():
    hcs.update_node.side_effect = NotFoundError("Node 999 not found")
    resp = client.patch("/chains/1/nodes/999", json={"name": "X"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "NODE_NOT_FOUND"


def test_delete_node_success():
    hcs.delete_node.return_value = None
    hcs.delete_node.side_effect = None
    resp = client.delete("/chains/1/nodes/1")
    assert resp.status_code == 204


def test_delete_node_not_found():
    hcs.delete_node.side_effect = NotFoundError("Node 999 not found")
    resp = client.delete("/chains/1/nodes/999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "NODE_NOT_FOUND"


def test_reorder_nodes_success():
    hcs.reorder_nodes.return_value = None
    hcs.reorder_nodes.side_effect = None
    resp = client.post("/chains/1/nodes/reorder", json={
        "items": [{"nodeId": 1, "sortOrder": 2}, {"nodeId": 2, "sortOrder": 1}]
    })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_reorder_nodes_validation_failed():
    hcs.reorder_nodes.side_effect = ValidationError("节点 ID 集合不匹配")
    resp = client.post("/chains/1/nodes/reorder", json={
        "items": [{"nodeId": 99, "sortOrder": 1}]
    })
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "REORDER_VALIDATION_FAILED"
