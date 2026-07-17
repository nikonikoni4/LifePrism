"""测试 Agent 工具类的 execute 方法 - lifeprismsystem.py"""

import asyncio
from datetime import datetime

import pytest

from lifeprism.llm.agent.tools.lifeprismsystem import (
    UpdateUserBehaviorNoteTool,
    UserActivitySummaryTool,
    UserComputerLogTool,
    UserMoodCreateTool,
    UserMoodQuryTool,
)
from lifeprism.repository.aggregators import (
    computer_usage_aggregator,
    mood_aggregator,
    todo_aggregator,
)
from lifeprism.repository.providers import custom_block_provider
from lifeprism.server.services import mood_service


@pytest.fixture
def mood_type():
    """创建测试用的心情类型"""
    from lifeprism.server.schemas.mood_schemas import CreateMoodTypeRequest

    request = CreateMoodTypeRequest(
        name="测试心情", icon="😊", color="#00FF00", score=75, is_dark=0, sort_order=100
    )
    mood_type = mood_service.create_mood_type(request)
    yield mood_type.id
    try:
        mood_service.delete_mood_type(mood_type.id)
    except Exception:
        pass


@pytest.fixture
def test_data(mood_type):
    """创建测试数据"""
    created_ids = {"mood_type": mood_type}

    usage_data = {
        "id": "test-tool-usage-001",
        "start_time": "2026-04-28 10:00:00",
        "end_time": "2026-04-28 10:30:00",
        "duration": 1800,
        "app": "test_app.exe",
        "title": "Test App Window",
        "category_id": "cat-work",
    }
    computer_usage_aggregator.create_computer_usage(usage_data)
    created_ids["computer_usage"] = "test-tool-usage-001"

    custom_block_data = {
        "start_time": "2026-04-28 11:00:00",
        "end_time": "2026-04-28 11:30:00",
        "duration": 1800,
        "content": "Test behavior note content",
        "color": "#bfdbfe",
    }
    block = custom_block_provider.create_custom_block(custom_block_data)
    created_ids["custom_block"] = block["id"]

    todo_data = {
        "content": "Test todo item",
        "date": "2026-04-28",
        "state": "active",
        "order_index": 0,
    }
    todo_id = todo_aggregator.create_todo(todo_data)
    created_ids["todo"] = todo_id

    yield created_ids

    for key, data_id in reversed(list(created_ids.items())):
        if key == "mood_type":
            continue
        try:
            if key == "computer_usage":
                computer_usage_aggregator.delete_computer_usage(data_id)
            elif key == "custom_block":
                custom_block_provider.delete_custom_block(data_id)
            elif key == "mood":
                mood_aggregator.delete_mood_entry(data_id)
            elif key == "todo":
                todo_aggregator.delete_todo(data_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_user_activity_summary_tool_execute(test_data):
    """测试 UserActivitySummaryTool.execute - 查询用户行为汇总"""
    tool = UserActivitySummaryTool()

    result = await tool.execute(
        query_option=["computer_usage_stats", "user_behavior_notes", "todolist"],
        start_time="2026-04-28 00:00:00",
        end_time="2026-04-28 23:59:59",
    )

    assert isinstance(result, str)
    assert "电脑使用统计" in result
    assert "用户自定义行为备注" in result
    assert "用户待办事项" in result


@pytest.mark.asyncio
async def test_user_activity_summary_tool_execute_with_ai_notes(test_data):
    """测试 UserActivitySummaryTool.execute - 包含AI行为分析查询"""
    tool = UserActivitySummaryTool()

    result = await tool.execute(
        query_option=[
            "computer_usage_stats",
            "user_behavior_notes",
            "ai_behavior_notes",
            "todolist",
        ],
        start_time="2026-04-28 00:00:00",
        end_time="2026-04-28 23:59:59",
    )

    assert isinstance(result, str)
    assert "AI分析行为备注" in result


@pytest.mark.asyncio
async def test_user_activity_summary_tool_execute_empty_range():
    """测试 UserActivitySummaryTool.execute - 查询无数据的时间范围"""
    tool = UserActivitySummaryTool()

    result = await tool.execute(
        query_option=["computer_usage_stats", "user_behavior_notes", "todolist"],
        start_time="2025-01-01 00:00:00",
        end_time="2025-01-02 00:00:00",
    )

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_user_computer_log_tool_execute(test_data):
    """测试 UserComputerLogTool.execute - 查询用户电脑使用日志"""
    tool = UserComputerLogTool()

    result = await tool.execute(
        start_time="2026-04-28 09:00:00", end_time="2026-04-28 11:00:00", duration_min=30
    )

    assert isinstance(result, str)
    assert "test_app" in result or "查询结果" in result


@pytest.mark.asyncio
async def test_user_computer_log_tool_execute_no_params():
    """测试 UserComputerLogTool.execute - 缺少参数"""
    tool = UserComputerLogTool()

    result = await tool.execute(start_time="", end_time="")

    assert isinstance(result, str)
    assert "error" in result.lower()
    assert "参数错误" in result


@pytest.mark.asyncio
async def test_update_user_behavior_note_tool_execute_create():
    """测试 UpdateUserBehaviorNoteTool.execute - 创建新备注"""
    tool = UpdateUserBehaviorNoteTool()

    result = await tool.execute(
        start_time="2026-04-28 15:00:00",
        end_time="2026-04-28 15:30:00",
        content="Testing create behavior note",
    )

    assert isinstance(result, str)
    assert "成功创建行为备注" in result
    assert "Testing create behavior note" in result


@pytest.mark.asyncio
async def test_update_user_behavior_note_tool_execute_update(test_data):
    """测试 UpdateUserBehaviorNoteTool.execute - 更新现有备注"""
    tool = UpdateUserBehaviorNoteTool()
    block_id = test_data["custom_block"]

    result = await tool.execute(
        start_time="2026-04-28 11:00:00",
        end_time="2026-04-28 11:30:00",
        content="Updated behavior note content",
        block_id=block_id,
    )

    assert isinstance(result, str)
    assert "成功更新行为备注" in result or "更新失败" in result


@pytest.mark.asyncio
async def test_update_user_behavior_note_tool_execute_missing_params():
    """测试 UpdateUserBehaviorNoteTool.execute - 缺少参数"""
    tool = UpdateUserBehaviorNoteTool()

    result = await tool.execute(start_time="2026-04-28 15:00:00", end_time="2026-04-28 15:30:00")

    assert isinstance(result, str)
    assert "error" in result.lower()
    assert "参数错误" in result


@pytest.mark.asyncio
async def test_user_mood_query_tool_execute_empty_range():
    """测试 UserMoodQuryTool.execute - 查询无数据范围"""
    tool = UserMoodQuryTool()

    result = await tool.execute(start_date="2025-01-01", end_date="2025-01-02")

    assert isinstance(result, str)
    assert "无心情记录" in result


@pytest.mark.asyncio
async def test_user_mood_create_tool_execute(mood_type):
    """测试 UserMoodCreateTool.execute - 创建心情记录"""
    tool = UserMoodCreateTool()

    result = await tool.execute(
        content="Test mood creation", mood_type_id=mood_type, factors=["work", "exercise"]
    )

    assert isinstance(result, str)
    assert "创建心情记录成功" in result or "ID" in result


@pytest.mark.asyncio
async def test_user_mood_create_tool_execute_missing_mood_type():
    """测试 UserMoodCreateTool.execute - 缺少心情类型"""
    tool = UserMoodCreateTool()

    result = await tool.execute(content="Test mood creation")

    assert isinstance(result, str)
    assert "error" in result.lower()
    assert "请输入心情类型ID" in result


@pytest.mark.asyncio
async def test_user_mood_create_tool_execute_invalid_mood_type():
    """测试 UserMoodCreateTool.execute - 无效的心情类型ID"""
    tool = UserMoodCreateTool()

    result = await tool.execute(content="Test mood creation", mood_type_id="invalid-type-id")

    assert isinstance(result, str)
    assert "error" in result.lower()
    assert "不存在" in result


@pytest.mark.asyncio
async def test_all_tools_schema():
    """测试所有工具的 to_schema 方法"""
    tools = [
        UserActivitySummaryTool(),
        UserComputerLogTool(),
        UpdateUserBehaviorNoteTool(),
        UserMoodQuryTool(),
        UserMoodCreateTool(),
    ]

    for tool in tools:
        schema = tool.to_schema()
        assert "type" in schema
        assert "function" in schema
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]
