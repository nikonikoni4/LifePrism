"""
Timeline Builder - 纯函数模块

提供 Timeline 缩略图统计数据的构建逻辑
从 activity_stats_builder.py 分离的复用函数也放在这里
"""

from datetime import datetime
from typing import List, Dict, Optional, Literal
from collections import defaultdict
import pandas as pd

from lifewatch.server.schemas.timeline_schemas import (
    TimelineStatsResponse,
    TimelineBlockStats,
    TimelineCategoryStats,
)
from lifewatch.server.schemas.activity_schemas import (
    TimeOverviewData,
    ChartSegment,
    BarConfig,
)
from lifewatch.server.providers import server_lw_data_provider
from lifewatch.server.providers.category_color_provider import color_manager, get_log_color, get_timeline_category_color


# ============================================================================
# 分类名称查找辅助函数
# ============================================================================

def _get_category_name_map() -> Dict[str, str]:
    """获取主分类 ID -> 名称映射（从 category 表加载）"""
    categories_df = server_lw_data_provider.load_categories()
    if categories_df is None or categories_df.empty:
        return {}
    return {str(row['id']): row['name'] for _, row in categories_df.iterrows()}

def _get_sub_category_name_map() -> Dict[str, str]:
    """获取子分类 ID -> 名称映射（从 sub_category 表加载）"""
    sub_categories_df = server_lw_data_provider.load_sub_categories()
    if sub_categories_df is None or sub_categories_df.empty:
        return {}
    return {str(row['id']): row['name'] for _, row in sub_categories_df.iterrows()}


# ============================================================================
# 通用工具函数
# ============================================================================

def slice_events_by_time_range(
    df: pd.DataFrame, 
    range_start: datetime, 
    range_end: datetime
) -> pd.DataFrame:
    """
    将事件切割到指定时间范围，跨边界的事件会被截断
    
    Args:
        df: 事件 DataFrame（需包含 start_dt, end_dt 列）
        range_start: 时间范围开始
        range_end: 时间范围结束
        
    Returns:
        pd.DataFrame: 切割后的事件，时间被限制在指定范围内
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    
    # 确保有 datetime 列
    if 'start_dt' not in df.columns:
        df['start_dt'] = pd.to_datetime(df['start_time'])
    if 'end_dt' not in df.columns:
        df['end_dt'] = pd.to_datetime(df['end_time'])
    
    # 过滤完全不在范围内的事件
    df = df[(df['end_dt'] > range_start) & (df['start_dt'] < range_end)]
    
    if df.empty:
        return pd.DataFrame()
    
    # 截断边界
    df['start_dt'] = df['start_dt'].clip(lower=range_start)
    df['end_dt'] = df['end_dt'].clip(upper=range_end)
    
    # 重新计算时长（分钟）
    df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
    
    return df


def load_day_events(date: str) -> pd.DataFrame:
    """
    加载当天所有事件并预处理
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        
    Returns:
        pd.DataFrame: 预处理后的事件 DataFrame
    """
    start_time = f"{date} 00:00:00"
    end_time = f"{date} 23:59:59"
    df = server_lw_data_provider.load_user_app_behavior_log(
        start_time=start_time, 
        end_time=end_time
    )
    
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 预处理时间字段
    df['start_dt'] = pd.to_datetime(df['start_time'])
    df['end_dt'] = pd.to_datetime(df['end_time'])
    df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
    
    return df


# ============================================================================
# Timeline Stats（缩略图统计）
# ============================================================================

def build_timeline_stats(
    date: str,
    hour_granularity: int = 1,
    category_level: Literal["main", "sub"] = "main"
) -> TimelineStatsResponse:
    """
    构建缩略图 Timeline 统计数据
    
    Args:
        date: 查询日期 (YYYY-MM-DD)
        hour_granularity: 时间粒度（1/2/3/4/6 小时）
        category_level: 分类级别（main=主分类, sub=子分类）
        
    Returns:
        TimelineStatsResponse: 缩略图统计响应
    """
    # 1. 加载当天所有事件
    df = load_day_events(date)
    
    # 2. 按时间块切割并聚合
    blocks: List[TimelineBlockStats] = []
    total_tracked = 0
    
    for start_hour in range(0, 24, hour_granularity):
        end_hour = start_hour + hour_granularity
        block = _calculate_block_stats(df, date, start_hour, end_hour, category_level)
        blocks.append(block)
        total_tracked += block.total_duration
    
    return TimelineStatsResponse(
        date=date,
        hour_granularity=hour_granularity,
        category_level=category_level,
        blocks=blocks,
        total_tracked_duration=total_tracked
    )


def _calculate_block_stats(
    df: pd.DataFrame,
    date: str,
    start_hour: int,
    end_hour: int,
    category_level: str
) -> TimelineBlockStats:
    """
    计算单个时间块的统计数据
    
    Args:
        df: 当天所有事件的 DataFrame
        date: 日期字符串
        start_hour: 开始小时（0-23）
        end_hour: 结束小时（1-24）
        category_level: 分类级别 ("main" 或 "sub")
        
    Returns:
        TimelineBlockStats: 时间块统计
    """
    # 1. 切割事件到时间块范围
    range_start = datetime.strptime(f"{date} {start_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
    
    # 处理 end_hour=24 的情况（视为次日 00:00）
    if end_hour == 24:
        from datetime import timedelta
        next_day = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        range_end = next_day.replace(hour=0, minute=0, second=0)
    else:
        range_end = datetime.strptime(f"{date} {end_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
    
    block_df = slice_events_by_time_range(df, range_start, range_end)
    
    # 2. 确定分组字段、颜色获取函数和名称映射
    #    缩略图使用柔和颜色版本 (get_timeline_category_color)
    if category_level == "main":
        group_field = "category_id"
        color_getter = lambda cat_id: get_timeline_category_color(cat_id, is_sub_category=False)
        name_map = _get_category_name_map()
    else:
        group_field = "sub_category_id"
        color_getter = lambda cat_id: get_timeline_category_color(cat_id, is_sub_category=True)
        name_map = _get_sub_category_name_map()
    
    # 3. 聚合分类统计
    block_seconds = (end_hour - start_hour) * 3600
    categories: List[TimelineCategoryStats] = []
    
    if not block_df.empty:
        # 转换为秒并聚合
        block_df = block_df.copy()
        block_df['duration_seconds'] = block_df['duration_minutes'] * 60
        
        # 按分类 id 聚合（只需要 duration_seconds）
        stats = block_df.groupby(group_field).agg({
            'duration_seconds': 'sum'
        }).reset_index()
        stats.columns = ['id', 'duration']
        stats = stats.sort_values('duration', ascending=False)
        
        for _, row in stats.iterrows():
            cat_id = str(row['id']) if pd.notna(row['id']) else "unknown"
            # 从分类表查找名称，而不是使用日志中可能过时的名称
            cat_name = name_map.get(cat_id, "Uncategorized")
            duration = int(row['duration'])
            
            categories.append(TimelineCategoryStats(
                id=cat_id,
                name=cat_name,
                color=color_getter(cat_id),
                duration=duration,
                percentage=round(duration / block_seconds * 100, 2)
            ))
    
    total_duration = sum(c.duration for c in categories)
    empty_duration = block_seconds - total_duration
    
    return TimelineBlockStats(
        start_hour=start_hour,
        end_hour=end_hour,
        categories=categories,
        total_duration=total_duration,
        empty_duration=max(0, empty_duration),
        empty_percentage=round(max(0, empty_duration) / block_seconds * 100, 2)
    )


# ============================================================================
# Time Overview（从 DataFrame 构建，可复用）
# ============================================================================

def build_time_overview_from_df(
    df: pd.DataFrame,
    title: str = "Time Overview",
    sub_title: str = "Activity breakdown & timeline",
    range_start: datetime = None,
    range_end: datetime = None
) -> TimeOverviewData:
    """
    从 DataFrame 构建 TimeOverview（纯计算，无数据加载）
    
    可用于：
    - 整天的 TimeOverview
    - 某个时间块的 TimeOverview（传入切割后的 df）
    
    Args:
        df: 事件 DataFrame（需包含 start_dt, end_dt, duration_minutes 等列）
        title: 概览标题
        sub_title: 概览副标题
        range_start: 时间范围开始（用于计算动态时间刻度和空闲时间）
        range_end: 时间范围结束（用于计算动态时间刻度和空闲时间）
        
    Returns:
        TimeOverviewData: 时间概览数据
    """
    if df is None or df.empty:
        return _build_empty_time_overview(title, sub_title, range_start, range_end)
    
    # 确保有 duration_minutes 列
    if 'duration_minutes' not in df.columns:
        df = df.copy()
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
    
    # 获取分类名称映射（从分类表加载，确保使用最新名称）
    category_name_map = _get_category_name_map()
    sub_category_name_map = _get_sub_category_name_map()
    
    # 构建 Level 1 (Category)
    root_data = _build_category_level_data(
        df, 
        group_field='category_id',
        name_field='category',
        title=title, 
        sub_title=sub_title,
        is_main_category=True,
        range_start=range_start,
        range_end=range_end
    )
    
    root_data['details'] = {}
    
    # 构建 Level 2 (Sub-category)
    categories = df['category_id'].dropna().unique()
    
    for category_id in categories:
        cat_df = df[df['category_id'] == category_id]
        if cat_df.empty:
            continue
        
        # 从分类表查找名称（不再从 DataFrame 读取）
        category_name = category_name_map.get(str(category_id), "Uncategorized")
        
        cat_data = _build_category_level_data(
            cat_df,
            group_field='sub_category_id',
            name_field='sub_category',
            title=f"{category_name} Details",
            sub_title=f"Detailed breakdown of {category_name}",
            is_main_category=False,
            range_start=range_start,
            range_end=range_end,
            include_idle=False  # 子分类层不显示空闲时间
        )
        
        cat_data['details'] = {}
        root_data['details'][category_name] = cat_data
        
        # 构建 Level 3 (Apps)
        sub_categories = cat_df['sub_category_id'].dropna().unique()
        for sub_cat_id in sub_categories:
            sub_df = cat_df[cat_df['sub_category_id'] == sub_cat_id]
            if sub_df.empty:
                continue
            
            # 从分类表查找名称（不再从 DataFrame 读取）
            sub_cat_name = sub_category_name_map.get(str(sub_cat_id), "Uncategorized")
            
            app_data = _build_app_level_data(
                sub_df,
                title=f"{sub_cat_name} Apps",
                sub_title=f"Top applications in {sub_cat_name}",
                parent_sub_category_id=str(sub_cat_id),
                range_start=range_start,
                range_end=range_end,
                include_idle=False  # 应用层不显示空闲时间
            )
            
            cat_data['details'][sub_cat_name] = app_data
    
    return _dict_to_time_overview_data(root_data)


# ============================================================================
# 私有辅助函数
# ============================================================================

def _build_category_level_data(
    df: pd.DataFrame, 
    group_field: str, 
    name_field: str,
    title: str, 
    sub_title: str,
    is_main_category: bool,
    range_start: datetime = None,
    range_end: datetime = None,
    include_idle: bool = True  # 是否包含空闲时间
) -> Dict:
    """构建分类层级的视图数据（只在根层级包含空闲时间）"""
    # 获取分类名称映射（从分类表加载，确保使用最新的名称）
    if is_main_category:
        name_map = _get_category_name_map()
    else:
        name_map = _get_sub_category_name_map()
    
    # 只按 id 分组（不需要读取名称列，从 name_map 查找）
    stats = df.groupby(group_field).agg({
        'duration_minutes': 'sum'
    }).reset_index()
    stats.columns = ['id', 'minutes']
    stats = stats.sort_values('minutes', ascending=False)
    
    total_minutes = stats['minutes'].sum()
    
    # 计算空闲时间（只在根层级且 include_idle=True 时添加）
    idle_minutes = 0
    total_range_minutes = None
    if range_start and range_end:
        total_range_minutes = (range_end - range_start).total_seconds() / 60
        if include_idle:
            idle_minutes = max(0, total_range_minutes - total_minutes)
    
    pie_data = []
    bar_keys = []
    
    for _, row in stats.iterrows():
        cat_id = str(row['id']) if pd.notna(row['id']) else "unknown"
        # 从分类表查找名称，而不是使用日志中可能过时的名称
        name = name_map.get(cat_id, "Uncategorized")
        minutes = int(row['minutes'])
        
        if is_main_category:
            item_color = color_manager.get_main_category_color(cat_id)
        else:
            item_color = color_manager.get_sub_category_color(cat_id)
        
        pie_data.append({
            "key": cat_id,
            "name": name,
            "value": minutes,
            "color": item_color,
            "title": ""
        })
        
        bar_keys.append({
            "key": cat_id,
            "label": name,
            "color": item_color
        })
    
    # 只在 include_idle=True 时添加空闲时间到饼图和柱状图
    if include_idle and idle_minutes > 0:
        idle_color = "#E5E7EB"  # 浅灰色表示空闲
        pie_data.append({
            "key": "idle",
            "name": "Idle",
            "value": int(idle_minutes),
            "color": idle_color,
            "title": ""
        })
        bar_keys.append({
            "key": "Idle",
            "label": "Idle",
            "color": idle_color
        })
    
    # barData 直接使用 category_id 进行分组，避免名称不一致问题
    bar_data = _calculate_time_distribution(
        df, 
        group_field=group_field,  # 使用 ID 字段（如 category_id）
        range_start=range_start, 
        range_end=range_end,
        include_idle=include_idle
    )
    
    return {
        "title": title,
        "subTitle": sub_title,
        "totalTrackedMinutes": int(total_minutes),
        "totalRangeMinutes": int(total_range_minutes) if total_range_minutes else None,
        "pieData": pie_data,
        "barKeys": bar_keys,
        "barData": bar_data
    }


def _build_app_level_data(
    df: pd.DataFrame, 
    title: str, 
    sub_title: str,
    parent_sub_category_id: str,
    range_start: datetime = None,
    range_end: datetime = None,
    include_idle: bool = True  # 是否包含空闲时间
) -> Dict:
    """构建应用级别数据（Top 5 + Other，包含 top 3 titles）"""
    stats = df.groupby('app')['duration_minutes'].sum().sort_values(ascending=False)
    total_minutes = stats.sum()
    
    top_5 = stats.head(5)
    other_value = stats.iloc[5:].sum() if len(stats) > 5 else 0
    
    base_color = color_manager.get_sub_category_color(parent_sub_category_id)
    
    pie_data = []
    bar_keys = []
    
    for i, (app_name, minutes) in enumerate(top_5.items()):
        # 为每个 App 即时生成随机浅色（level=3）
        app_color = get_log_color(base_color)
        
        app_df = df[df['app'] == app_name]
        title_stats = app_df.groupby('title')['duration_minutes'].sum().sort_values(ascending=False).head(3)
        top_titles = "-split-".join(title_stats.index.tolist())
        
        pie_data.append({
            "key": app_name,
            "name": app_name,
            "value": int(minutes),
            "color": app_color,
            "title": top_titles
        })
        
        bar_keys.append({
            "key": app_name,
            "label": app_name,
            "color": app_color
        })
    
    if other_value > 0:
        other_color = "#9CA3AF"
        pie_data.append({
            "key": "Other",
            "name": "Other Apps",
            "value": int(other_value),
            "color": other_color,
            "title": ""
        })
        bar_keys.append({
            "key": "Other",
            "label": "Other",
            "color": other_color
        })
    
    bar_data = _calculate_time_distribution(
        df, 
        top_items=top_5.index.tolist(), 
        range_start=range_start, 
        range_end=range_end,
        include_idle=include_idle
    )
    
    # 计算 totalRangeMinutes
    total_range_minutes = None
    if range_start and range_end:
        total_range_minutes = int((range_end - range_start).total_seconds() / 60)
    
    return {
        "title": title,
        "subTitle": sub_title,
        "totalTrackedMinutes": int(total_minutes),
        "totalRangeMinutes": total_range_minutes,
        "pieData": pie_data,
        "barKeys": bar_keys,
        "barData": bar_data
    }


def _calculate_time_distribution(
    df: pd.DataFrame, 
    group_field: str = None,
    top_items: List[str] = None,
    range_start: datetime = None,
    range_end: datetime = None,
    include_idle: bool = True  # 是否包含空闲时间
) -> List[Dict]:
    """
    计算时间分布数据（动态时间刻度，6个格子）
    
    根据时间范围动态计算刻度：
    - 1小时 -> 每格10分钟
    - 2小时 -> 每格20分钟
    - 3小时 -> 每格30分钟
    - 以此类推
    
    Args:
        df: 数据DataFrame（需包含 start_dt, end_dt 列）
        group_field: 分组字段名（如 'category_id', 'sub_category_id'）
        top_items: Top N 项目列表（用于应用层级，其他归为 'Other'）
        range_start: 时间范围开始
        range_end: 时间范围结束
        include_idle: 是否包含空闲时间
        
    Returns:
        List[Dict]: 时间分布数据（6个格子）
    """
    from datetime import timedelta
    
    # 如果没有提供时间范围，使用 df 的时间范围或默认整天
    if range_start is None or range_end is None:
        if df is not None and not df.empty and 'start_dt' in df.columns:
            range_start = df['start_dt'].min().replace(hour=0, minute=0, second=0, microsecond=0)
            range_end = range_start + timedelta(days=1)
        else:
            # 默认使用当天 00:00 - 24:00
            range_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            range_end = range_start + timedelta(days=1)
    
    # 计算时间范围（分钟）和每格的间隔
    total_minutes = (range_end - range_start).total_seconds() / 60
    num_slots = 6  # 固定6个格子
    slot_minutes = total_minutes / num_slots
    
    time_slots = defaultdict(lambda: defaultdict(float))
    slot_idle_minutes = defaultdict(float)  # 记录每个 slot 的空闲时间
    
    # 初始化每个 slot 的总时长（用于计算空闲时间）
    for slot_idx in range(num_slots):
        slot_idle_minutes[slot_idx] = slot_minutes  # 初始假设全部空闲
    
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            start = row['start_dt']
            end = row['end_dt']
            
            # 确定分组 key
            if top_items is not None:
                raw_key = row['app']
                key = raw_key if raw_key in top_items else "Other"
            else:
                # 分类层级：直接使用 ID 字段（如 category_id）
                raw_key = row[group_field]
                if raw_key is None or pd.isna(raw_key):
                    key = "unknown"
                else:
                    # 转换为字符串格式，与 barKeys 中的 key 保持一致
                    key = str(raw_key)
            
            # 计算每个时间槽的重叠时长
            for slot_idx in range(num_slots):
                slot_start = range_start + timedelta(minutes=slot_idx * slot_minutes)
                slot_end = slot_start + timedelta(minutes=slot_minutes)
                
                overlap_start = max(start, slot_start)
                overlap_end = min(end, slot_end)
                
                if overlap_start < overlap_end:
                    overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
                    time_slots[slot_idx][key] += overlap_minutes
                    slot_idle_minutes[slot_idx] -= overlap_minutes  # 减少空闲时间
    
    # 构建结果
    bar_data = []
    for slot_idx in range(num_slots):
        slot_start = range_start + timedelta(minutes=slot_idx * slot_minutes)
        slot_end = slot_start + timedelta(minutes=slot_minutes)
        
        # 格式化时间标签
        time_range = f"{slot_start.strftime('%H:%M')}-{slot_end.strftime('%H:%M')}"
        
        slot_data = {"timeRange": time_range}
        for key, minutes in time_slots[slot_idx].items():
            slot_data[key] = int(minutes)
        
        # 只在 include_idle=True 时添加空闲时间
        if include_idle:
            idle = max(0, slot_idle_minutes[slot_idx])
            if idle > 0:
                slot_data["Idle"] = int(idle)
        
        bar_data.append(slot_data)
    
    return bar_data


def _build_empty_time_overview(
    title: str, 
    sub_title: str,
    range_start: datetime = None,
    range_end: datetime = None
) -> TimeOverviewData:
    """构建空的时间概览响应（包含空闲时间）"""
    from datetime import timedelta
    
    # 计算动态时间刻度
    if range_start and range_end:
        total_minutes = (range_end - range_start).total_seconds() / 60
        num_slots = 6
        slot_minutes = total_minutes / num_slots
        
        empty_bar_data = []
        for slot_idx in range(num_slots):
            slot_start = range_start + timedelta(minutes=slot_idx * slot_minutes)
            slot_end = slot_start + timedelta(minutes=slot_minutes)
            time_range = f"{slot_start.strftime('%H:%M')}-{slot_end.strftime('%H:%M')}"
            empty_bar_data.append({"timeRange": time_range, "Idle": int(slot_minutes)})
        
        # 空时间范围时全部为空闲
        idle_minutes = int(total_minutes)
        pie_data = [ChartSegment(
            key="idle",
            name="Idle",
            value=idle_minutes,
            color="#E5E7EB",
            title=""
        )]
        bar_keys = [BarConfig(
            key="Idle",
            label="Idle",
            color="#E5E7EB"
        )]
    else:
        # 默认 24 小时显示
        empty_bar_data = [{"timeRange": f"{h}-{h+2}"} for h in range(0, 24, 2)]
        pie_data = []
        bar_keys = []
    
    # 计算 totalRangeMinutes
    total_range_min = None
    if range_start and range_end:
        total_range_min = int((range_end - range_start).total_seconds() / 60)
    
    return TimeOverviewData(
        title=title,
        sub_title=sub_title,
        total_tracked_minutes=0,
        total_range_minutes=total_range_min,
        pie_data=pie_data,
        bar_keys=bar_keys,
        bar_data=empty_bar_data,
        details={}
    )


def _dict_to_time_overview_data(data: Dict) -> TimeOverviewData:
    """将字典转换为 TimeOverviewData Pydantic 模型"""
    pie_data = [ChartSegment(**item) for item in data.get('pieData', [])]
    bar_keys = [BarConfig(**item) for item in data.get('barKeys', [])]
    
    details = {}
    for key, value in data.get('details', {}).items():
        details[key] = _dict_to_time_overview_data(value)
    
    return TimeOverviewData(
        title=data['title'],
        sub_title=data['subTitle'],
        total_tracked_minutes=data['totalTrackedMinutes'],
        total_range_minutes=data.get('totalRangeMinutes'),
        pie_data=pie_data,
        bar_keys=bar_keys,
        bar_data=data['barData'],
        details=details if details else None
    )
