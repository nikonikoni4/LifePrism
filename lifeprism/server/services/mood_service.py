"""
Mood 服务层 - 心情模块业务逻辑

架构：纯函数模块（无内存缓存，不需要单例）
"""
import json
from typing import Optional, List

from lifeprism.server.schemas.mood_schemas import (
    MoodTypeItem,
    MoodTypeListResponse,
    MoodEntryItem,
    MoodEntryListResponse,
    MoodImpactItem,
    MoodImpactListResponse,
    CreateMoodTypeRequest,
    UpdateMoodTypeRequest,
    CreateMoodEntryRequest,
    UpdateMoodEntryRequest,
    CreateMoodImpactRequest,
)
from lifeprism.storage.providers import (
    mood_type_provider,
    mood_entry_provider,
    mood_impact_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ==================== 工具函数 ====================

def _parse_factors(json_str: Optional[str]) -> List[str]:
    """JSON 字符串 → List[str]"""
    if not json_str:
        return []
    try:
        result = json.loads(json_str)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _convert_to_mood_type_item(item: dict) -> MoodTypeItem:
    """将数据库记录转换为 MoodTypeItem"""
    return MoodTypeItem(
        id=item['id'],
        name=item['name'],
        icon=item['icon'],
        color=item['color'],
        score=item['score'],
        is_dark=item.get('is_dark', 0),
        sort_order=item.get('sort_order', 0),
        created_at=item.get('created_at', ''),
    )


def _convert_to_mood_entry_item(item: dict) -> MoodEntryItem:
    """将数据库记录转换为 MoodEntryItem"""
    return MoodEntryItem(
        id=item['id'],
        mood_type_id=item['mood_type_id'],
        score=item['score'],
        content=item.get('content'),
        factors=_parse_factors(item.get('factors')),
        created_at=item.get('created_at', ''),
    )


def _convert_to_mood_impact_item(item: dict) -> MoodImpactItem:
    """将数据库记录转换为 MoodImpactItem"""
    return MoodImpactItem(
        id=item['id'],
        name=item['name'],
        sort_order=item.get('sort_order', 0),
        created_at=item.get('created_at', ''),
    )


# ==================== 心情类型 ====================

def get_mood_types() -> MoodTypeListResponse:
    """获取所有心情类型"""
    items = mood_type_provider.get_mood_types()
    return MoodTypeListResponse(
        items=[_convert_to_mood_type_item(item) for item in items]
    )


def create_mood_type(request: CreateMoodTypeRequest) -> Optional[MoodTypeItem]:
    """
    创建心情类型

    Args:
        request: 创建请求

    Returns:
        Optional[MoodTypeItem]: 新创建的心情类型，失败返回 None
    """
    data = request.model_dump()
    new_id = mood_type_provider.create_mood_type(data)
    if not new_id:
        return None
    item = mood_type_provider.get_mood_type_by_id(new_id)
    if not item:
        return None
    return _convert_to_mood_type_item(item)


def update_mood_type(mood_type_id: str, request: UpdateMoodTypeRequest) -> Optional[MoodTypeItem]:
    """
    更新心情类型（部分更新）

    Args:
        mood_type_id: 心情类型 ID
        request: 更新请求

    Returns:
        Optional[MoodTypeItem]: 更新后的心情类型，不存在返回 None
    """
    existing = mood_type_provider.get_mood_type_by_id(mood_type_id)
    if not existing:
        return None

    explicitly_set = request.model_fields_set
    update_data = {}
    for field in ['name', 'icon', 'color', 'score', 'is_dark', 'sort_order']:
        if field in explicitly_set:
            update_data[field] = getattr(request, field)

    if update_data:
        mood_type_provider.update_mood_type(mood_type_id, update_data)

    item = mood_type_provider.get_mood_type_by_id(mood_type_id)
    return _convert_to_mood_type_item(item) if item else None


def delete_mood_type(mood_type_id: str) -> bool:
    """
    删除心情类型（有关联记录时抛 ValueError）

    Args:
        mood_type_id: 心情类型 ID

    Returns:
        bool: 是否成功

    Raises:
        ValueError: 有关联的心情记录
    """
    existing = mood_type_provider.get_mood_type_by_id(mood_type_id)
    if not existing:
        return False

    count = mood_type_provider.count_entries_by_type(mood_type_id)
    if count < 0:
        raise ValueError("查询关联记录失败")
    if count > 0:
        raise ValueError(f"该心情类型下有 {count} 条记录，无法删除")

    return mood_type_provider.delete_mood_type(mood_type_id)


# ==================== 心情记录 ====================

def get_mood_entries(start_date: Optional[str] = None, end_date: Optional[str] = None) -> MoodEntryListResponse:
    """
    获取心情记录列表

    Args:
        start_date: 开始日期 YYYY-MM-DD（可选）
        end_date: 结束日期 YYYY-MM-DD（可选）

    Returns:
        MoodEntryListResponse: 心情记录列表
    """
    items = mood_entry_provider.get_mood_entries(start_date, end_date)
    return MoodEntryListResponse(
        items=[_convert_to_mood_entry_item(item) for item in items]
    )


def get_mood_entry(entry_id: str) -> Optional[MoodEntryItem]:
    """
    获取单条心情记录

    Args:
        entry_id: 心情记录 ID

    Returns:
        Optional[MoodEntryItem]: 心情记录，不存在返回 None
    """
    item = mood_entry_provider.get_mood_entry_by_id(entry_id)
    if not item:
        return None
    return _convert_to_mood_entry_item(item)


def create_mood_entry(request: CreateMoodEntryRequest) -> Optional[MoodEntryItem]:
    """
    创建心情记录（自动从 mood_type 获取 score）

    Args:
        request: 创建请求

    Returns:
        Optional[MoodEntryItem]: 新创建的心情记录，失败返回 None
    """
    mood_type = mood_type_provider.get_mood_type_by_id(request.mood_type_id)
    if not mood_type:
        raise ValueError(f"无效的心情类型 ID: {request.mood_type_id}")

    data = {
        'mood_type_id': request.mood_type_id,
        'score': mood_type['score'],
        'content': request.content,
        'factors': json.dumps(request.factors, ensure_ascii=False) if request.factors else None,
    }
    new_id = mood_entry_provider.create_mood_entry(data)
    if not new_id:
        return None
    item = mood_entry_provider.get_mood_entry_by_id(new_id)
    return _convert_to_mood_entry_item(item) if item else None


def update_mood_entry(entry_id: str, request: UpdateMoodEntryRequest) -> Optional[MoodEntryItem]:
    """
    更新心情记录（部分更新，如果更新了 mood_type_id 则重新获取 score）

    Args:
        entry_id: 心情记录 ID
        request: 更新请求

    Returns:
        Optional[MoodEntryItem]: 更新后的心情记录，不存在返回 None
    """
    existing = mood_entry_provider.get_mood_entry_by_id(entry_id)
    if not existing:
        return None

    explicitly_set = request.model_fields_set
    update_data = {}

    if 'mood_type_id' in explicitly_set and request.mood_type_id is not None:
        mood_type = mood_type_provider.get_mood_type_by_id(request.mood_type_id)
        if not mood_type:
            raise ValueError(f"无效的心情类型 ID: {request.mood_type_id}")
        update_data['mood_type_id'] = request.mood_type_id
        update_data['score'] = mood_type['score']

    if 'content' in explicitly_set:
        update_data['content'] = request.content

    if 'factors' in explicitly_set:
        update_data['factors'] = json.dumps(request.factors, ensure_ascii=False) if request.factors else None

    if update_data:
        mood_entry_provider.update_mood_entry(entry_id, update_data)

    item = mood_entry_provider.get_mood_entry_by_id(entry_id)
    return _convert_to_mood_entry_item(item) if item else None


def delete_mood_entry(entry_id: str) -> bool:
    """
    删除心情记录

    Args:
        entry_id: 心情记录 ID

    Returns:
        bool: 是否成功
    """
    return mood_entry_provider.delete_mood_entry(entry_id)


# ==================== 影响因素 ====================

def get_mood_impacts() -> MoodImpactListResponse:
    """获取所有影响因素"""
    items = mood_impact_provider.get_mood_impacts()
    return MoodImpactListResponse(
        items=[_convert_to_mood_impact_item(item) for item in items]
    )


def create_mood_impact(request: CreateMoodImpactRequest) -> Optional[MoodImpactItem]:
    """
    创建影响因素

    Args:
        request: 创建请求

    Returns:
        Optional[MoodImpactItem]: 新创建的影响因素，失败返回 None

    Raises:
        ValueError: 名称已存在
    """
    existing = mood_impact_provider.get_mood_impacts()
    if any(item['name'] == request.name for item in existing):
        raise ValueError(f"影响因素名称已存在: {request.name}")

    data = request.model_dump()
    new_id = mood_impact_provider.create_mood_impact(data)
    if new_id is None:
        return None
    # 查询刚创建的记录
    items = mood_impact_provider.get_mood_impacts()
    for item in items:
        if item['id'] == new_id:
            return _convert_to_mood_impact_item(item)
    return None


def delete_mood_impact(impact_id: int) -> bool:
    """
    删除影响因素

    Args:
        impact_id: 影响因素 ID

    Returns:
        bool: 是否成功
    """
    return mood_impact_provider.delete_mood_impact(impact_id)
