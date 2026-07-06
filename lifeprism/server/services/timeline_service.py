"""
Timeline V2 服务层 - 缩略图统计

提供 Timeline 缩略图统计和时间块详情的服务接口
"""

import re
from datetime import datetime
from typing import Literal

from lifeprism.repository import (
    behavior_analysis_repository,
    custom_block_repository,
    todo_repository,
)
from lifeprism.server.schemas.timeline_schemas import (
    BehaviorAnalysisItem,
    BehaviorAnalysisResponse,
    BehaviorItem,
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
    UserCustomBlock,
    UserCustomBlockCreate,
    UserCustomBlockListResponse,
    UserCustomBlockResponse,
    UserCustomBlockUpdate,
)
from lifeprism.server.services.category_service import category_service
from lifeprism.server.services.timeline_builder import (
    build_time_overview_from_df,
    build_timeline_stats,
    load_day_events,
    slice_events_by_time_range,
)


def parse_behavior_text(behavior_text: str) -> list[BehaviorItem]:
    """
    解析behavior文本为BehaviorItem列表

    原始文本格式示例：
    2026-04-26 21:04:01 ~ 2026-04-26 21:19:01
     behavior: 1. 修正函数和SQL拼写错误
    2. 正确处理数据拼接
    2026-04-26 21:19:01 ~ 2026-04-26 21:34:01
     behavior: 1. Fixed the typo...

    Args:
        behavior_text: 原始behavior文本

    Returns:
        List[BehaviorItem]: 解析后的BehaviorItem列表
    """
    if not behavior_text or not behavior_text.strip():
        return []

    # 正则表达式匹配时间区间模式：YYYY-MM-DD HH:MM:SS ~ YYYY-MM-DD HH:MM:SS
    time_range_pattern = (
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*~\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    )

    # 查找所有时间区间的位置
    time_ranges = list(re.finditer(time_range_pattern, behavior_text))

    if not time_ranges:
        # 如果没有找到时间区间，返回整个文本作为一个item
        return [BehaviorItem(time_range="", behavior_items=behavior_text.strip())]

    behavior_items = []

    for i, match in enumerate(time_ranges):
        time_range = match.group(1).strip()
        start_pos = match.end()

        # 获取当前时间区间到下一个时间区间之间的文本
        end_pos = time_ranges[i + 1].start() if i + 1 < len(time_ranges) else len(behavior_text)

        # 提取behavior内容
        content = behavior_text[start_pos:end_pos].strip()

        # 移除开头的 "behavior:" 前缀（如果有）
        if content.lower().startswith("behavior:") or content.lower().startswith("behavior："):
            content = content[9:].strip()

        if content:
            behavior_items.append(BehaviorItem(time_range=time_range, behavior_items=content))

    return behavior_items


def get_behavior_analysis(
    date: str,
) -> BehaviorAnalysisResponse:
    """
    获取行为分析结果

    Args:
        date: 查询日期 (YYYY-MM-DD)

    Returns:
        BehaviorAnalysisResponse: 行为分析响应
    """
    response = BehaviorAnalysisResponse()
    screent_analysis_summary_list = behavior_analysis_repository.get_behaviors_by_date(date)
    for item in screent_analysis_summary_list:
        # 解析behavior文本为结构化数据
        behavior_items = parse_behavior_text(item["behavior"])

        response.behavior_list.append(
            BehaviorAnalysisItem(
                start_time=item["start_time"],
                end_time=item["end_time"],
                screen_count=item["screen_count"],
                behavior_summary=item["behavior_summary"],
                behavior=behavior_items,
                title=item["title"],
            )
        )
    return response


def get_timeline_stats(
    date: str, hour_granularity: int = 1, category_level: Literal["main", "sub"] = "main"
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
    date: str, start_hour: int, end_hour: int
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
        range_end=range_end,
    )

    return TimelineTimeOverviewResponse(data=overview)


# ============================================================================
# UserCustomBlock 服务层函数
# ============================================================================


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
    category_id = record.get("category_id")
    sub_category_id = record.get("sub_category_id")

    # 获取分类名称（如果有）
    category_name = None
    sub_category_name = None
    if category_id:
        category_name = category_service.category_name_map.get(category_id)
    if sub_category_id:
        sub_category_name = category_service.sub_category_name_map.get(sub_category_id)

    # 获取 todo 内容（如果绑定了）
    todo_id = record.get("todo_id")
    todo_content = None
    if todo_id:
        todo = todo_repository.get_todo_by_id(todo_id)
        if todo:
            todo_content = todo.get("content")

    # 返回丰富后的记录
    return {
        **record,
        "category": category_name,
        "sub_category": sub_category_name,
        "todo_content": todo_content,
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
    record = custom_block_repository.create_custom_block(data.model_dump())
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
    record = custom_block_repository.get_custom_block_by_id(block_id)
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
    records = custom_block_repository.get_custom_blocks_by_date(date)
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
    record = custom_block_repository.update_custom_block(
        block_id, data.model_dump(exclude_unset=True)
    )
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
    return custom_block_repository.delete_custom_block(block_id)


if __name__ == "__main__":
    behaviors = behavior_analysis_repository.get_behaviors_by_date("2026-04-21")
    print(behaviors)
