"""
Journal 服务层 - Goal Journal 日志业务逻辑

纯函数模块，无状态缓存
"""

import json

from lifeprism.server.providers.journal_provider import journal_provider
from lifeprism.server.schemas.goal_schemas import (
    CreateJournalRequest,
    JournalEntry,
    JournalListResponse,
    UpdateJournalRequest,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def _convert_db_item_to_journal_entry(item: dict) -> JournalEntry:
    """
    将数据库记录转换为 JournalEntry
    """
    tags = item.get("tags", "[]")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    return JournalEntry(
        id=item["id"],
        date=item["date"],
        time=item.get("time"),
        content=item["content"],
        mood=item.get("mood", "neutral"),
        duration=item.get("duration", 0),
        tags=tags,
    )


def get_journals_by_goal(goal_id: str) -> JournalListResponse:
    """
    获取指定目标的所有日志

    Args:
        goal_id: 目标 ID

    Returns:
        JournalListResponse: 日志列表响应
    """
    items = journal_provider.get_journals_by_goal(goal_id)
    journal_entries = [_convert_db_item_to_journal_entry(item) for item in items]
    return JournalListResponse(items=journal_entries)


def get_journals(
    goal_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> JournalListResponse:
    """
    获取日志列表（支持筛选）

    Args:
        goal_id: 按目标筛选
        start_date: 开始日期
        end_date: 结束日期
        page: 页码
        page_size: 每页数量

    Returns:
        JournalListResponse: 日志列表响应
    """
    items = journal_provider.get_journals_by_goal(goal_id) if goal_id else []

    # 日期筛选
    if start_date or end_date:
        filtered_items = []
        for item in items:
            item_date = item.get("date", "")
            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue
            filtered_items.append(item)
        items = filtered_items

    # 分页
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    items = items[start_idx:end_idx]

    journal_entries = [_convert_db_item_to_journal_entry(item) for item in items]
    return JournalListResponse(items=journal_entries)


def get_journal_detail(journal_id: str) -> JournalEntry | None:
    """
    获取日志详情

    Args:
        journal_id: 日志 ID

    Returns:
        Optional[JournalEntry]: 日志详情，不存在返回 None
    """
    item = journal_provider.get_journal_by_id(journal_id)
    if not item:
        return None
    return _convert_db_item_to_journal_entry(item)


def create_journal(request: CreateJournalRequest) -> JournalEntry | None:
    """
    创建日志

    Args:
        request: 创建日志请求

    Returns:
        Optional[JournalEntry]: 新创建的日志，失败返回 None
    """
    data = {
        "goal_id": request.goal_id,
        "date": request.date,
        "time": request.time,
        "content": request.content,
        "mood": request.mood,
        "duration": request.duration,
        "tags": request.tags if request.tags else "[]",
    }

    new_id = journal_provider.create_journal(data)
    if new_id is None:
        return None

    # 获取新创建的日志
    item = journal_provider.get_journal_by_id(new_id)
    if not item:
        return None

    return _convert_db_item_to_journal_entry(item)


def update_journal(journal_id: str, request: UpdateJournalRequest) -> JournalEntry | None:
    """
    更新日志

    Args:
        journal_id: 日志 ID
        request: 更新日志请求

    Returns:
        Optional[JournalEntry]: 更新后的日志，失败返回 None
    """
    update_data = {}
    explicitly_set_fields = request.model_fields_set

    if "date" in explicitly_set_fields:
        update_data["date"] = request.date
    if "time" in explicitly_set_fields:
        update_data["time"] = request.time
    if "content" in explicitly_set_fields:
        update_data["content"] = request.content
    if "mood" in explicitly_set_fields:
        update_data["mood"] = request.mood
    if "duration" in explicitly_set_fields:
        update_data["duration"] = request.duration
    if "tags" in explicitly_set_fields:
        update_data["tags"] = request.tags

    success = journal_provider.update_journal(journal_id, update_data)
    if not success:
        return None

    # 获取更新后的日志
    item = journal_provider.get_journal_by_id(journal_id)
    if not item:
        return None

    return _convert_db_item_to_journal_entry(item)


def delete_journal(journal_id: str) -> bool:
    """
    删除日志

    Args:
        journal_id: 日志 ID

    Returns:
        bool: 是否成功
    """
    return journal_provider.delete_journal(journal_id)
