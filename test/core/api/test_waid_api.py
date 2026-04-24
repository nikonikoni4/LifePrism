"""
WAID (What Am I Doing) 浮窗 API 测试

测试 WAID 浮窗相关的 API 接口：
- POST /api/v2/todos - 创建任务（WAID 浮窗场景）
- GET /api/v2/todos/waid - 获取 WAID 浮窗任务列表
- PUT /api/v2/todos/{todo_id}/waid - 添加任务到 WAID 浮窗
- DELETE /api/v2/todos/{todo_id}/waid - 从 WAID 浮窗移除任务
- PUT /api/v2/todos/waid/reorder - WAID 浮窗任务重排序
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from lifeprism.server.main import app
from lifeprism.repository import lw_db_manager


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def clean_test_data():
    """清理测试数据"""
    yield
    # 测试后清理：删除测试创建的 todo
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM todo_list WHERE content LIKE '[TEST]%'")


@pytest.mark.core
def test_create_waid_todo_with_daily_goal(client, clean_test_data):
    """
    测试从 WAID 浮窗创建任务（关联每日目标）

    这是前端 WhatAmIDoingFloat.tsx 的真实请求数据：
    {
        content: "任务内容",
        state: "scheduled",
        date: "2026-04-20",
        link_to_goal_id: "goal-daily",
        plan_doc_id: "每日目标-docs"
    }
    """
    # 准备请求数据（模拟前端真实请求）
    today = datetime.now().strftime("%Y-%m-%d")
    request_data = {
        "content": "[TEST] WAID 浮窗测试任务",
        "state": "scheduled",
        "date": today,
        "link_to_goal_id": "goal-daily",
        "plan_doc_id": "每日目标-docs"
    }

    # 发送创建请求
    response = client.post("/api/v2/todos", json=request_data)

    # 验证响应
    assert response.status_code == 200
    data = response.json()
    assert "item" in data

    # 验证返回的任务数据
    item = data["item"]
    assert item["content"] == "[TEST] WAID 浮窗测试任务"
    assert item["state"] == "scheduled"
    assert item["date"] == today
    assert item["link_to_goal_id"] == "goal-daily"
    assert item["plan_doc_id"] == "每日目标-docs"
    assert "id" in item
    assert item["id"].startswith("t-")


@pytest.mark.core
def test_create_waid_todo_without_goal(client, clean_test_data):
    """测试创建任务时不关联目标（兼容性测试）"""
    today = datetime.now().strftime("%Y-%m-%d")
    request_data = {
        "content": "[TEST] 无目标任务",
        "state": "scheduled",
        "date": today
    }

    response = client.post("/api/v2/todos", json=request_data)

    assert response.status_code == 200
    data = response.json()
    item = data["item"]
    assert item["content"] == "[TEST] 无目标任务"
    assert item["link_to_goal_id"] is None
    assert item["plan_doc_id"] is None


@pytest.mark.core
def test_get_waid_todos_empty(client):
    """测试获取空的 WAID 浮窗任务列表"""
    response = client.get("/api/v2/todos/waid")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.core
def test_add_todo_to_waid(client, clean_test_data):
    """测试添加任务到 WAID 浮窗"""
    # 1. 先创建一个任务
    today = datetime.now().strftime("%Y-%m-%d")
    create_response = client.post("/api/v2/todos", json={
        "content": "[TEST] 待添加到 WAID 的任务",
        "state": "scheduled",
        "date": today,
        "link_to_goal_id": "goal-daily",
        "plan_doc_id": "每日目标-docs"
    })
    assert create_response.status_code == 200
    todo_id = create_response.json()["item"]["id"]

    # 2. 添加到 WAID 浮窗
    add_response = client.put(f"/api/v2/todos/{todo_id}/waid")
    assert add_response.status_code == 200
    add_data = add_response.json()
    assert add_data["success"] is True
    assert "waid_order" in add_data

    # 3. 验证任务出现在 WAID 列表中
    waid_response = client.get("/api/v2/todos/waid")
    assert waid_response.status_code == 200
    waid_items = waid_response.json()["items"]
    assert any(item["id"] == todo_id for item in waid_items)


@pytest.mark.core
def test_remove_todo_from_waid(client, clean_test_data):
    """测试从 WAID 浮窗移除任务"""
    # 1. 创建任务并添加到 WAID
    today = datetime.now().strftime("%Y-%m-%d")
    create_response = client.post("/api/v2/todos", json={
        "content": "[TEST] 待移除的任务",
        "state": "scheduled",
        "date": today,
        "link_to_goal_id": "goal-daily",
        "plan_doc_id": "每日目标-docs"
    })
    todo_id = create_response.json()["item"]["id"]
    client.put(f"/api/v2/todos/{todo_id}/waid")

    # 2. 从 WAID 移除
    remove_response = client.delete(f"/api/v2/todos/{todo_id}/waid")
    assert remove_response.status_code == 200
    assert remove_response.json()["success"] is True

    # 3. 验证任务不在 WAID 列表中
    waid_response = client.get("/api/v2/todos/waid")
    waid_items = waid_response.json()["items"]
    assert not any(item["id"] == todo_id for item in waid_items)


@pytest.mark.core
def test_reorder_waid_todos(client, clean_test_data):
    """测试 WAID 浮窗任务重排序"""
    # 1. 创建多个任务并添加到 WAID
    today = datetime.now().strftime("%Y-%m-%d")
    todo_ids = []
    for i in range(3):
        create_response = client.post("/api/v2/todos", json={
            "content": f"[TEST] 任务 {i+1}",
            "state": "scheduled",
            "date": today,
            "link_to_goal_id": "goal-daily",
            "plan_doc_id": "每日目标-docs"
        })
        todo_id = create_response.json()["item"]["id"]
        todo_ids.append(todo_id)
        client.put(f"/api/v2/todos/{todo_id}/waid")

    # 2. 重排序（反转顺序）
    reversed_ids = list(reversed(todo_ids))
    reorder_response = client.put("/api/v2/todos/waid/reorder", json={
        "todo_ids": reversed_ids
    })
    assert reorder_response.status_code == 200
    assert reorder_response.json()["success"] is True

    # 3. 验证顺序已更新
    waid_response = client.get("/api/v2/todos/waid")
    waid_items = waid_response.json()["items"]
    waid_ids = [item["id"] for item in waid_items if item["id"] in todo_ids]
    assert waid_ids == reversed_ids


@pytest.mark.core
def test_create_waid_todo_with_invalid_goal_id(client, clean_test_data):
    """测试创建任务时使用不存在的 goal_id（应该成功，因为外键约束未启用）"""
    today = datetime.now().strftime("%Y-%m-%d")
    request_data = {
        "content": "[TEST] 无效 goal_id 任务",
        "state": "scheduled",
        "date": today,
        "link_to_goal_id": "goal-nonexistent",
        "plan_doc_id": "nonexistent-docs"
    }

    response = client.post("/api/v2/todos", json=request_data)

    # 当前实现：外键约束未启用，应该成功
    assert response.status_code == 200
    data = response.json()
    assert data["item"]["link_to_goal_id"] == "goal-nonexistent"


@pytest.mark.core
def test_waid_todo_state_transition(client, clean_test_data):
    """测试 WAID 任务状态转换（scheduled -> completed）"""
    # 1. 创建 scheduled 任务
    today = datetime.now().strftime("%Y-%m-%d")
    create_response = client.post("/api/v2/todos", json={
        "content": "[TEST] 待完成任务",
        "state": "scheduled",
        "date": today,
        "link_to_goal_id": "goal-daily",
        "plan_doc_id": "每日目标-docs"
    })
    todo_id = create_response.json()["item"]["id"]
    client.put(f"/api/v2/todos/{todo_id}/waid")

    # 2. 标记为完成
    update_response = client.put(f"/api/v2/todos/{todo_id}", json={
        "state": "completed"
    })
    assert update_response.status_code == 200
    updated_item = update_response.json()["item"]
    assert updated_item["state"] == "completed"
    assert updated_item["actual_finished_at"] is not None


@pytest.mark.core
def test_waid_todo_date_format_validation(client, clean_test_data):
    """测试日期格式验证（YYYY-MM-DD）"""
    request_data = {
        "content": "[TEST] 日期格式测试",
        "state": "scheduled",
        "date": "2026-04-20",  # 正确格式
        "link_to_goal_id": "goal-daily",
        "plan_doc_id": "每日目标-docs"
    }

    response = client.post("/api/v2/todos", json=request_data)
    assert response.status_code == 200
    assert response.json()["item"]["date"] == "2026-04-20"


@pytest.mark.core
def test_waid_integration_workflow(client, clean_test_data):
    """
    测试完整的 WAID 工作流程

    模拟用户在 WAID 浮窗中的完整操作流程：
    1. 创建任务（自动关联每日目标）
    2. 任务自动添加到 WAID 浮窗
    3. 查看 WAID 任务列表
    4. 完成任务
    5. 任务从 WAID 移除
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 创建任务
    create_response = client.post("/api/v2/todos", json={
        "content": "[TEST] 完整流程测试",
        "state": "scheduled",
        "date": today,
        "link_to_goal_id": "goal-daily",
        "plan_doc_id": "每日目标-docs"
    })
    assert create_response.status_code == 200
    todo_id = create_response.json()["item"]["id"]

    # 2. 添加到 WAID
    add_response = client.put(f"/api/v2/todos/{todo_id}/waid")
    assert add_response.status_code == 200

    # 3. 查看 WAID 列表
    waid_response = client.get("/api/v2/todos/waid")
    assert waid_response.status_code == 200
    waid_items = waid_response.json()["items"]
    assert any(item["id"] == todo_id for item in waid_items)

    # 4. 完成任务
    complete_response = client.put(f"/api/v2/todos/{todo_id}", json={
        "state": "completed"
    })
    assert complete_response.status_code == 200

    # 5. 从 WAID 移除
    remove_response = client.delete(f"/api/v2/todos/{todo_id}/waid")
    assert remove_response.status_code == 200

    # 6. 验证任务不在 WAID 列表中
    final_waid_response = client.get("/api/v2/todos/waid")
    final_waid_items = final_waid_response.json()["items"]
    assert not any(item["id"] == todo_id for item in final_waid_items)
