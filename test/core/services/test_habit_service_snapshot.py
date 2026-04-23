"""
Habit Service 快照测试

目的：在重构 HabitProvider 前捕获当前行为，确保重构后行为不变
"""
import pytest
from syrupy.assertion import SnapshotAssertion
from datetime import date, timedelta

from lifeprism.server.services.habit_service import habit_service
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest,
    UpdateHabitRequest,
    FrequencyObject,
)


# ==================== habits 测试 ====================

def test_get_habits_snapshot(snapshot: SnapshotAssertion):
    """测试获取习惯列表"""
    result = habit_service.get_habits(status=None)
    assert result == snapshot


def test_get_habits_active_snapshot(snapshot: SnapshotAssertion):
    """测试获取激活状态的习惯"""
    result = habit_service.get_habits(status="active")
    assert result == snapshot


def test_create_habit_snapshot(snapshot: SnapshotAssertion):
    """测试创建习惯"""
    request = CreateHabitRequest(
        name="测试习惯1",
        description="这是一个测试习惯",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
        value_id=None,
        commitment_id=None,
    )
    result = habit_service.create_habit(request)
    assert result == snapshot


def test_create_habit_with_custom_frequency_snapshot(snapshot: SnapshotAssertion):
    """测试创建自定义频率的习惯"""
    request = CreateHabitRequest(
        name="测试习惯2",
        description="自定义频率习惯",
        frequency=FrequencyObject(type="custom", specific_days=[1, 3, 5]),
        initial_level=1,
        value_id=None,
        commitment_id=None,
    )
    result = habit_service.create_habit(request)
    assert result == snapshot


def test_get_habit_detail_snapshot(snapshot: SnapshotAssertion):
    """测试获取习惯详情"""
    # 先创建一个习惯
    request = CreateHabitRequest(
        name="测试习惯3",
        description="用于测试详情",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)

    # 获取详情
    result = habit_service.get_habit_detail(created.id)
    assert result == snapshot


def test_update_habit_snapshot(snapshot: SnapshotAssertion):
    """测试更新习惯"""
    # 先创建一个习惯
    create_request = CreateHabitRequest(
        name="待更新习惯",
        description="原始描述",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(create_request)

    # 更新习惯
    update_request = UpdateHabitRequest(
        name="已更新习惯",
        description="新描述",
    )
    result = habit_service.update_habit(created.id, update_request)
    assert result == snapshot


def test_pause_habit_snapshot(snapshot: SnapshotAssertion):
    """测试暂停习惯"""
    # 先创建一个习惯
    request = CreateHabitRequest(
        name="待暂停习惯",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)

    # 暂停习惯
    result = habit_service.pause_habit(created.id)
    assert result == snapshot


def test_resume_habit_snapshot(snapshot: SnapshotAssertion):
    """测试恢复习惯"""
    # 先创建并暂停一个习惯
    request = CreateHabitRequest(
        name="待恢复习惯",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)
    habit_service.pause_habit(created.id)

    # 恢复习惯
    result = habit_service.resume_habit(created.id)
    assert result == snapshot


def test_delete_habit_snapshot(snapshot: SnapshotAssertion):
    """测试删除习惯"""
    # 先创建一个习惯
    request = CreateHabitRequest(
        name="待删除习惯",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)

    # 删除习惯
    result = habit_service.delete_habit(created.id)
    assert result == snapshot


# ==================== checkin 测试 ====================

def test_checkin_today_snapshot(snapshot: SnapshotAssertion):
    """测试今日打卡"""
    # 先创建一个习惯
    request = CreateHabitRequest(
        name="打卡测试习惯",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)

    # 今日打卡
    result = habit_service.checkin_today(created.id)
    assert result == snapshot


def test_cancel_checkin_snapshot(snapshot: SnapshotAssertion):
    """测试取消打卡"""
    # 先创建习惯并打卡
    request = CreateHabitRequest(
        name="取消打卡测试",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)
    habit_service.checkin_today(created.id)

    # 取消今日打卡
    today_str = date.today().isoformat()
    result = habit_service.cancel_checkin(created.id, today_str)
    assert result == snapshot


# ==================== challenge 测试 ====================

def test_get_challenge_history_snapshot(snapshot: SnapshotAssertion):
    """测试获取挑战历史"""
    # 先创建一个习惯（会自动创建挑战）
    request = CreateHabitRequest(
        name="挑战历史测试",
        frequency=FrequencyObject(type="daily"),
        initial_level=0,
    )
    created = habit_service.create_habit(request)

    # 获取挑战历史
    result = habit_service.get_challenge_history(created.id, status=None)
    assert result == snapshot
