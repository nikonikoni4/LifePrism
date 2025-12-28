"""
Timeline V2 服务层 - 缩略图统计

提供 Timeline 缩略图统计和时间块详情的服务接口
"""

from typing import Literal
from datetime import datetime

from lifewatch.server.schemas.timeline_schemas import (
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
)
from lifewatch.server.services.timeline_builder import (
    load_day_events,
    slice_events_by_time_range,
    build_timeline_stats,
    build_time_overview_from_df,
)


def get_timeline_stats(
    date: str,
    hour_granularity: int = 1,
    category_level: Literal["main", "sub"] = "main"
) -> TimelineStatsResponse:
    """
    获取缩略图 Timeline 统计数据
    
    Args:
        date: 查询日期 (YYYY-MM-DD)
        hour_granularity: 时间粒度（1/2/3/4/6 小时）
        category_level: 分类级别（main=主分类, sub=子分类）
        
    Returns:
        TimelineStatsResponse: 缩略图统计响应
    """
    return build_timeline_stats(date, hour_granularity, category_level)


def get_timeline_time_overview(
    date: str,
    start_hour: int,
    end_hour: int
) -> TimelineTimeOverviewResponse:
    """
    获取指定时间块的 Time Overview 详情
    
    Args:
        date: 查询日期 (YYYY-MM-DD)
        start_hour: 开始小时（0-23）
        end_hour: 结束小时（1-24）
        
    Returns:
        TimelineTimeOverviewResponse: 时间块详情响应
    """
    from datetime import timedelta
    
    # 1. 加载并切割事件
    df = load_day_events(date)
    
    range_start = datetime.strptime(f"{date} {start_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
    
    # 处理 end_hour=24 的情况
    if end_hour == 24:
        next_day = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        range_end = next_day.replace(hour=0, minute=0, second=0)
        end_hour_display = "24:00"
    else:
        range_end = datetime.strptime(f"{date} {end_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
        end_hour_display = f"{end_hour:02d}:00"
    
    block_df = slice_events_by_time_range(df, range_start, range_end)
    
    # 2. 构建 TimeOverview（复用 builder 函数，传递时间范围用于动态刻度和空闲时间计算）
    overview = build_time_overview_from_df(
        block_df,
        title=f"{start_hour:02d}:00 - {end_hour_display}",
        sub_title="Time block breakdown",
        range_start=range_start,
        range_end=range_end
    )
    
    return TimelineTimeOverviewResponse(data=overview)


# ============================================================================
# UserCustomBlock 服务层函数
# ============================================================================

from lifewatch.server.schemas.timeline_schemas import (
    UserCustomBlock,
    UserCustomBlockCreate,
    UserCustomBlockUpdate,
    UserCustomBlockResponse,
    UserCustomBlockListResponse,
)
from lifewatch.server.providers.timeline_provider import TimelineProvider
from lifewatch.server.services.category_service import CategoryService
from lifewatch.server.providers.todo_provider import todo_provider

# 创建 provider 和 service 实例
_timeline_provider = TimelineProvider()
_category_service = CategoryService()


def _enrich_block_record(record: dict) -> dict:
    """
    丰富数据库记录，添加分类名称和 todo 内容
    
    将数据库中存储的 category_id/sub_category_id 转换为前端需要的
    category/sub_category 名称，并查询绑定的 todo 内容
    
    Args:
        record: dict, 数据库原始记录
    
    Returns:
        dict: 丰富后的记录（含 category, sub_category, todo_content）
    """
    category_id = record.get('category_id')
    sub_category_id = record.get('sub_category_id')
    
    # 获取分类名称（如果有）
    category_name = None
    sub_category_name = None
    if category_id:
        category_name = _category_service.category_name_map.get(category_id)
    if sub_category_id:
        sub_category_name = _category_service.sub_category_name_map.get(sub_category_id)
    
    # 获取 todo 内容（如果绑定了）
    todo_id = record.get('todo_id')
    todo_content = None
    if todo_id:
        todo = todo_provider.get_todo_by_id(todo_id)
        if todo:
            todo_content = todo.get('content')
    
    # 返回丰富后的记录
    return {
        **record,
        'category': category_name,
        'sub_category': sub_category_name,
        'todo_content': todo_content,
        # color 直接使用数据库中的值，不再映射
    }


def create_custom_block(data: UserCustomBlockCreate) -> UserCustomBlockResponse:
    """
    创建用户自定义时间块
    
    Args:
        data: UserCustomBlockCreate, 创建请求数据（含 category_id, sub_category_id）
    
    Returns:
        UserCustomBlockResponse: 创建后的记录（含名称和颜色）
    """
    record = _timeline_provider.create_custom_block(data.model_dump())
    enriched_record = _enrich_block_record(record)
    return UserCustomBlockResponse(data=UserCustomBlock(**enriched_record))


def get_custom_block(block_id: int) -> UserCustomBlockResponse:
    """
    获取单条用户自定义时间块
    
    Args:
        block_id: int, 时间块 ID
    
    Returns:
        UserCustomBlockResponse: 时间块记录（含名称和颜色）
    
    Raises:
        ValueError: 如果记录不存在
    """
    record = _timeline_provider.get_custom_block_by_id(block_id)
    if not record:
        raise ValueError(f"Custom block with id {block_id} not found")
    enriched_record = _enrich_block_record(record)
    return UserCustomBlockResponse(data=UserCustomBlock(**enriched_record))


def get_custom_blocks_by_date(date: str) -> UserCustomBlockListResponse:
    """
    获取指定日期的所有自定义时间块
    
    Args:
        date: str, 日期（YYYY-MM-DD 格式）
    
    Returns:
        UserCustomBlockListResponse: 时间块列表（每条含名称和颜色）
    """
    records = _timeline_provider.get_custom_blocks_by_date(date)
    blocks = [UserCustomBlock(**_enrich_block_record(r)) for r in records]
    return UserCustomBlockListResponse(data=blocks, total=len(blocks))


def update_custom_block(block_id: int, data: UserCustomBlockUpdate) -> UserCustomBlockResponse:
    """
    更新用户自定义时间块
    
    Args:
        block_id: int, 时间块 ID
        data: UserCustomBlockUpdate, 更新请求数据
    
    Returns:
        UserCustomBlockResponse: 更新后的记录（含名称和颜色）
    
    Raises:
        ValueError: 如果记录不存在
    """
    record = _timeline_provider.update_custom_block(block_id, data.model_dump(exclude_unset=True))
    if not record:
        raise ValueError(f"Custom block with id {block_id} not found")
    enriched_record = _enrich_block_record(record)
    return UserCustomBlockResponse(data=UserCustomBlock(**enriched_record))


def delete_custom_block(block_id: int) -> bool:
    """
    删除用户自定义时间块
    
    Args:
        block_id: int, 时间块 ID
    
    Returns:
        bool: 是否删除成功
    """
    return _timeline_provider.delete_custom_block(block_id)

