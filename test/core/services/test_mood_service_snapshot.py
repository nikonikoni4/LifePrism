"""
Mood Service 快照测试

目的：在重构 MoodProvider 前捕获当前行为，确保重构后行为不变
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services import mood_service
from lifeprism.server.schemas.mood_schemas import (
    CreateMoodTypeRequest,
    UpdateMoodTypeRequest,
    CreateMoodEntryRequest,
    UpdateMoodEntryRequest,
    CreateMoodImpactRequest,
)


# ==================== mood_types 测试 ====================

def test_get_mood_types_snapshot(snapshot: SnapshotAssertion):
    """测试获取所有心情类型"""
    result = mood_service.get_mood_types()
    assert result == snapshot


def test_create_mood_type_snapshot(snapshot: SnapshotAssertion):
    """测试创建心情类型"""
    request = CreateMoodTypeRequest(
        name="测试心情",
        icon="😊",
        color="#FF5733",
        score=80,
        is_dark=0,
        sort_order=100
    )
    result = mood_service.create_mood_type(request)
    assert result == snapshot


def test_update_mood_type_snapshot(snapshot: SnapshotAssertion):
    """测试更新心情类型"""
    # 先创建一个心情类型
    create_request = CreateMoodTypeRequest(
        name="待更新",
        icon="😐",
        color="#000000",
        score=50,
        is_dark=0,
        sort_order=50
    )
    created = mood_service.create_mood_type(create_request)

    # 更新
    update_request = UpdateMoodTypeRequest(
        name="已更新",
        score=60
    )
    result = mood_service.update_mood_type(created.id, update_request)
    assert result == snapshot


def test_delete_mood_type_snapshot(snapshot: SnapshotAssertion):
    """测试删除心情类型（无关联记录）"""
    # 先创建一个心情类型
    create_request = CreateMoodTypeRequest(
        name="待删除",
        icon="😢",
        color="#0000FF",
        score=20,
        is_dark=0,
        sort_order=10
    )
    created = mood_service.create_mood_type(create_request)

    # 删除
    result = mood_service.delete_mood_type(created.id)
    assert result == snapshot


# ==================== mood_entries 测试 ====================

def test_get_mood_entries_snapshot(snapshot: SnapshotAssertion):
    """测试获取心情记录列表"""
    result = mood_service.get_mood_entries()
    assert result == snapshot


def test_get_mood_entries_with_date_range_snapshot(snapshot: SnapshotAssertion):
    """测试按时间范围获取心情记录"""
    result = mood_service.get_mood_entries(
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-12-31T23:59:59+00:00"
    )
    assert result == snapshot


def test_create_mood_entry_snapshot(snapshot: SnapshotAssertion):
    """测试创建心情记录"""
    # 先创建一个心情类型
    type_request = CreateMoodTypeRequest(
        name="测试1",
        icon="😊",
        color="#00FF00",
        score=75,
        is_dark=0,
        sort_order=80
    )
    mood_type = mood_service.create_mood_type(type_request)

    # 创建心情记录
    entry_request = CreateMoodEntryRequest(
        mood_type_id=mood_type.id,
        content="今天心情不错",
        factors=["天气好", "工作顺利"]
    )
    result = mood_service.create_mood_entry(entry_request)
    assert result == snapshot


def test_update_mood_entry_snapshot(snapshot: SnapshotAssertion):
    """测试更新心情记录"""
    # 先创建心情类型和记录
    type_request = CreateMoodTypeRequest(
        name="测试2",
        icon="😐",
        color="#FFFF00",
        score=50,
        is_dark=0,
        sort_order=50
    )
    mood_type = mood_service.create_mood_type(type_request)

    entry_request = CreateMoodEntryRequest(
        mood_type_id=mood_type.id,
        content="待更新的心情",
        factors=["因素1"]
    )
    created = mood_service.create_mood_entry(entry_request)

    # 更新
    update_request = UpdateMoodEntryRequest(
        content="已更新的心情",
        factors=["因素1", "因素2"]
    )
    result = mood_service.update_mood_entry(created.id, update_request)
    assert result == snapshot


def test_delete_mood_entry_snapshot(snapshot: SnapshotAssertion):
    """测试删除心情记录"""
    # 先创建心情类型和记录
    type_request = CreateMoodTypeRequest(
        name="测试3",
        icon="😢",
        color="#FF0000",
        score=30,
        is_dark=0,
        sort_order=30
    )
    mood_type = mood_service.create_mood_type(type_request)

    entry_request = CreateMoodEntryRequest(
        mood_type_id=mood_type.id,
        content="待删除的心情",
        factors=[]
    )
    created = mood_service.create_mood_entry(entry_request)

    # 删除
    result = mood_service.delete_mood_entry(created.id)
    assert result == snapshot


# ==================== mood_impacts 测试 ====================

def test_get_mood_impacts_snapshot(snapshot: SnapshotAssertion):
    """测试获取所有影响因素"""
    result = mood_service.get_mood_impacts()
    assert result == snapshot


def test_create_mood_impact_snapshot(snapshot: SnapshotAssertion):
    """测试创建影响因素"""
    import uuid
    request = CreateMoodImpactRequest(
        name=f"测试因素{uuid.uuid4().hex[:4]}",
        sort_order=100
    )
    result = mood_service.create_mood_impact(request)
    assert result == snapshot


def test_delete_mood_impact_snapshot(snapshot: SnapshotAssertion):
    """测试删除影响因素"""
    # 先创建一个影响因素
    create_request = CreateMoodImpactRequest(
        name="待删除因素",
        sort_order=50
    )
    created = mood_service.create_mood_impact(create_request)

    # 如果创建失败（表不存在），跳过测试
    if created is None:
        pytest.skip("mood_impacts 表不存在")

    # 删除
    result = mood_service.delete_mood_impact(created.id)
    assert result == snapshot
