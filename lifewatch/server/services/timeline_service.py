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

