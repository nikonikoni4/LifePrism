"""测试 habit_tool.py 中的习惯打卡 Agent 工具"""

import sqlite3
from datetime import date, timedelta

import pytest

from lifeprism.llm.agent.tools.base import ERROR, SUCCESS
from lifeprism.llm.agent.tools.habit_tool import (
    BackfillCheckinTool,
    CancelCheckinHabitTool,
    CheckinHabitTool,
    QueryUserHabitsTool,
)
from lifeprism.repository import habit_repository
from lifeprism.server.schemas.habit_schemas import CreateHabitRequest, FrequencyObject
from lifeprism.server.services.habit_service import habit_service

pytestmark = pytest.mark.core


def _rewind_challenge_start(habit_id: str, days: int = 7):
    """将当前挑战 start_date 提前 N 天，使补签日期落入挑战周期内

    update_challenge 的字段白名单不允许修改 start_date，故直接走 SQL
    """
    challenge = habit_repository.get_current_challenge(habit_id)
    new_start = (date.today() - timedelta(days=days)).isoformat()
    from lifeprism.config import settings

    con = sqlite3.connect(settings.lw_db_path)
    try:
        con.execute(
            "UPDATE habit_challenges SET start_date = ? WHERE id = ?",
            (new_start, challenge["id"]),
        )
        con.commit()
    finally:
        con.close()


@pytest.fixture
def test_habit():
    """创建测试用的习惯（daily 频率，等级 0），用例结束后级联清理"""
    request = CreateHabitRequest(
        name="测试打卡习惯",
        description="habit_tool 测试专用",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)
    yield created
    try:
        habit_service.delete_habit(created.id)
    except Exception:
        pass


class TestQueryUserHabitsTool:
    """query_user_habits 工具"""

    async def test_query_contains_habit_info(self, test_habit):
        """查询结果包含习惯关键信息（id/等级/频率/挑战进度/今日打卡状态）"""
        result = await QueryUserHabitsTool().execute()
        assert result.startswith(SUCCESS)
        assert test_habit.name in result
        assert test_habit.id in result
        assert "0级(萌芽)" in result
        assert "daily" in result
        assert "进度 0/" in result
        assert "今日已打卡: 否" in result

    async def test_query_by_status(self, test_habit):
        """按状态过滤"""
        result = await QueryUserHabitsTool().execute(status="active")
        assert test_habit.name in result
        result_paused = await QueryUserHabitsTool().execute(status="paused")
        assert test_habit.name not in result_paused

    async def test_query_invalid_status(self):
        """非法 status 参数返回错误"""
        result = await QueryUserHabitsTool().execute(status="invalid")
        assert result.startswith(ERROR)


class TestCheckinHabitTool:
    """checkin_habit 工具"""

    async def test_checkin_success(self, test_habit):
        """打卡成功，输出含习惯名与更新后的进度"""
        result = await CheckinHabitTool().execute(habit_id=test_habit.id)
        assert result.startswith(SUCCESS)
        assert test_habit.name in result
        assert "进度 1/" in result
        assert "今日已打卡: 是" in result

    async def test_checkin_duplicate(self, test_habit):
        """重复打卡返回冲突错误"""
        await CheckinHabitTool().execute(habit_id=test_habit.id)
        result = await CheckinHabitTool().execute(habit_id=test_habit.id)
        assert result.startswith(ERROR)
        assert "打卡冲突" in result

    async def test_checkin_not_found(self):
        """不存在的 habit_id 返回错误"""
        result = await CheckinHabitTool().execute(habit_id="habit-notexist")
        assert result.startswith(ERROR)
        assert "习惯不存在" in result

    async def test_checkin_missing_param(self):
        """缺少 habit_id 返回参数错误"""
        result = await CheckinHabitTool().execute()
        assert result.startswith(ERROR)


class TestCancelCheckinHabitTool:
    """cancel_checkin_habit 工具"""

    async def test_cancel_today_success(self, test_habit):
        """取消今日打卡成功，进度回退"""
        await CheckinHabitTool().execute(habit_id=test_habit.id)
        result = await CancelCheckinHabitTool().execute(habit_id=test_habit.id)
        assert result.startswith(SUCCESS)
        assert "已取消今日打卡" in result
        assert "今日已打卡: 否" in result

    async def test_cancel_without_checkin(self, test_habit):
        """当日无打卡记录时取消返回错误"""
        result = await CancelCheckinHabitTool().execute(habit_id=test_habit.id)
        assert result.startswith(ERROR)


class TestBackfillCheckinTool:
    """backfill_checkin 工具"""

    async def test_backfill_success(self, test_habit):
        """补签昨日成功"""
        _rewind_challenge_start(test_habit.id)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        result = await BackfillCheckinTool().execute(habit_id=test_habit.id, dates=[yesterday])
        assert result.startswith(SUCCESS)
        assert f"- {yesterday}: 补签成功" in result
        assert "成功 1/1" in result

    async def test_backfill_out_of_window(self, test_habit):
        """超出 6 天窗口的日期补签失败并带原因"""
        old_date = (date.today() - timedelta(days=10)).isoformat()
        result = await BackfillCheckinTool().execute(habit_id=test_habit.id, dates=[old_date])
        assert result.startswith(SUCCESS)  # 批量接口整体成功，逐项失败
        assert f"- {old_date}: 失败" in result
        assert "成功 0/1" in result

    async def test_backfill_today_rejected(self, test_habit):
        """补签今日日期被拒绝（应使用打卡接口）"""
        today = date.today().isoformat()
        result = await BackfillCheckinTool().execute(habit_id=test_habit.id, dates=[today])
        assert "成功 0/1" in result
        assert "今日打卡请使用打卡接口" in result

    async def test_backfill_not_found(self):
        """不存在的 habit_id 返回错误"""
        result = await BackfillCheckinTool().execute(
            habit_id="habit-notexist", dates=["2026-01-01"]
        )
        assert result.startswith(ERROR)
