"""
Activity Stats Builder - 纯函数模块

提供活动统计数据的构建逻辑（Activity Summary 和 Time Overview）
从 ActivityService 分离出来，保持 Service 层简洁
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
from collections import defaultdict
import pandas as pd

from lifewatch.server.schemas.activity_schemas import (
    ActivitySummaryData,
    DailyActivitiesData,
    TimeOverviewData,
    ChartSegment,
    BarConfig,
    TopTitleData,
    TopAppData,
    TodoListData,
)
from lifewatch.server.providers import server_lw_data_provider
from lifewatch.server.providers.category_color_provider import color_manager


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
# Activity Summary
# ============================================================================

def build_activity_summary(
    date: str,
    history_number: int,
    future_number: int,
    category_id: Optional[str],
    sub_category_id: Optional[str]
) -> ActivitySummaryData:
    """
    获取活动摘要条形图数据
    
    Args:
        date: 中心日期 (YYYY-MM-DD 格式)
        history_number: 历史数据天数
        future_number: 未来数据天数
        category_id: 主分类ID筛选（可选）
        sub_category_id: 子分类ID筛选（可选）
        
    Returns:
        ActivitySummaryData: 活动摘要数据
    """
    # 1. 计算日期范围
    center_date = datetime.strptime(date, "%Y-%m-%d")
    start_date = (center_date - timedelta(days=history_number)).strftime("%Y-%m-%d")
    end_date = (center_date + timedelta(days=future_number)).strftime("%Y-%m-%d")
    
    # 2. 生成完整的日期列表（包含无数据的日期）
    date_range: List[str] = []
    current = center_date - timedelta(days=history_number)
    end_date_obj = center_date + timedelta(days=future_number)
    while current <= end_date_obj:
        date_range.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    # 3. 查询数据库获取每日活动数据（带分类筛选）
    daily_data = server_lw_data_provider.get_daily_active_time(
        start_date, end_date, category_id, sub_category_id
    )
    
    # 4. 创建日期到数据的映射
    activity_map = {
        item["date"]: item["active_time_percentage"] 
        for item in daily_data
    }
    
    # 5. 获取分类颜色
    filter_color = None
    if category_id:
        filter_color = color_manager.get_main_category_color(category_id)
    elif sub_category_id:
        filter_color = color_manager.get_sub_category_color(sub_category_id)
    
    default_color = "#5B8FF9"
    
    # 6. 构建完整的数据数组，缺失的日期补全为0
    daily_activities: List[DailyActivitiesData] = []
    for date_str in date_range:
        percentage = activity_map.get(date_str, 0)
        duration = int(percentage * 86400 / 100)
        
        daily_activities.append(DailyActivitiesData(
            date=date_str,
            duration=duration,
            active_time_percentage=percentage,
            color=filter_color or default_color
        ))
    
    return ActivitySummaryData(daily_activities=daily_activities)


# ============================================================================
# Time Overview
# ============================================================================

def build_time_overview(date: str) -> TimeOverviewData:
    """
    获取时间概览数据（三层嵌套结构：Category → SubCategory → App）
    
    Args:
        date: 查询日期 (YYYY-MM-DD 格式)
        
    Returns:
        TimeOverviewData: 时间概览数据
    """
    # 1. 加载数据
    start_time = f"{date} 00:00:00"
    end_time = f"{date} 23:59:59"
    df = server_lw_data_provider.load_user_app_behavior_log(start_time=start_time, end_time=end_time)
    
    if df is None or df.empty:
        return _build_empty_time_overview(date)
    
    # 预计算时长（分钟）
    df['start_dt'] = pd.to_datetime(df['start_time'])
    df['end_dt'] = pd.to_datetime(df['end_time'])
    df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
    
    # 获取分类名称映射（从分类表加载，确保使用最新名称）
    category_name_map = _get_category_name_map()
    sub_category_name_map = _get_sub_category_name_map()
    
    # 2. 构建 Level 1 (Category)
    root_data = _build_category_level_data(
        df, 
        group_field='category_id',
        name_field='category',
        title="Time Overview", 
        sub_title="Activity breakdown & timeline",
        is_main_category=True
    )
    
    root_data['details'] = {}
    
    # 3. 构建 Level 2 (Sub-category)
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
            is_main_category=False
        )
        
        cat_data['details'] = {}
        root_data['details'][category_name] = cat_data
        
        # 4. 构建 Level 3 (Apps)
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
                parent_sub_category_id=str(sub_cat_id)
            )
            
            cat_data['details'][sub_cat_name] = app_data
    
    return _dict_to_time_overview_data(root_data)


# ============================================================================
# Top N
# ============================================================================

def get_top_title(date: str, top_n: int) -> List[TopTitleData]:
    """获取热门标题数据
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        top_n: int, Top N
        
    Returns:
        list[TopTitleData], Top窗口标题排行:
            name: str, 窗口标题
            duration: int, 活跃时长(秒)
    """
    title_list = server_lw_data_provider.get_top_title(date, top_n)
    total_duration = server_lw_data_provider.get_active_time(date)
    
    # 构建TopTitleData列表
    result = []
    for title in title_list:
        result.append(TopTitleData(
            name=title['name'], 
            duration=int(title['duration']), 
            percentage=int(title['duration'] / total_duration * 100) if total_duration > 0 else 0
        ))
    return result


def get_top_app(date: str, top_n: int) -> List[TopAppData]:
    """获取热门应用数据
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        top_n: int, Top N
        
    Returns:
        list[TopAppData], Top应用排行:
            name: str, 应用名称
            duration: int, 活跃时长(秒)
    """
    app_list = server_lw_data_provider.get_top_applications(date, top_n)
    total_duration = server_lw_data_provider.get_active_time(date)
    
    # 构建TopAppData列表
    result = []
    for app in app_list:
        result.append(TopAppData(
            name=app['name'], 
            duration=int(app['duration']), 
            percentage=int(app['duration'] / total_duration * 100) if total_duration > 0 else 0
        ))
    return result


def get_todolist(date: str) -> List[TodoListData]:
    """获取待办事项数据
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        
    Returns:
        list[TodoListData], 待办事项列表:
            name: str, 待办事项名称
            is_completed: bool, 是否完成
    """
    # Mock
    todo_list = [
        {"id": 1, "name": "待办事项1", "is_completed": False, "link_to_goal_id": None},
        {"id": 2, "name": "待办事项2", "is_completed": True, "link_to_goal_id": None},
        {"id": 3, "name": "待办事项3", "is_completed": False, "link_to_goal_id": None},
    ]

    result = []
    for todo in todo_list:
        result.append(TodoListData(
            id=todo['id'], 
            name=todo['name'], 
            is_completed=todo['is_completed'], 
            link_to_goal_id=todo['link_to_goal_id']
        ))
    return result


# ============================================================================
# 私有辅助函数
# ============================================================================

def _build_category_level_data(
    df: pd.DataFrame, 
    group_field: str, 
    name_field: str,
    title: str, 
    sub_title: str,
    is_main_category: bool
) -> Dict:
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
    
    # 构建 id -> id_str 的映射（确保使用字符串格式的 ID）
    # barData 直接使用 category_id 进行分组，避免名称不一致问题
    bar_data = _calculate_time_distribution(df, group_field=group_field)
    
    return {
        "title": title,
        "subTitle": sub_title,
        "totalTrackedMinutes": int(total_minutes),
        "pieData": pie_data,
        "barKeys": bar_keys,
        "barData": bar_data
    }


def _build_app_level_data(
    df: pd.DataFrame, 
    title: str, 
    sub_title: str,
    parent_sub_category_id: str
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
        app_color = base_color
        
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
    
    bar_data = _calculate_time_distribution(df, top_items=top_5.index.tolist())
    
    return {
        "title": title,
        "subTitle": sub_title,
        "totalTrackedMinutes": int(total_minutes),
        "pieData": pie_data,
        "barKeys": bar_keys,
        "barData": bar_data
    }


def _calculate_time_distribution(
    df: pd.DataFrame, 
    group_field: str = None,
    top_items: List[str] = None
) -> List[Dict]:
    """
    计算24小时分布数据（按2小时间隔）
    
    Args:
        df: 数据DataFrame（需包含 start_dt, end_dt 列）
        group_field: 分组字段名（如 'category_id', 'sub_category_id'）
        top_items: Top N 项目列表（用于应用层级，其他归为 'Other'）
        
    Returns:
        List[Dict]: 24小时分布数据
        
    Note:
        group_field 和 top_items 二选一：
        - 分类层级：传 group_field（使用 ID 字段如 'category_id'）
        - 应用层级：传 top_items
    """
    time_slots = defaultdict(lambda: defaultdict(int))
    
    for _, row in df.iterrows():
        start = row['start_dt']
        end = row['end_dt']
        
        # 确定分组 key
        if top_items is not None:
            # 应用层级：使用 app 字段，不在 top_items 中的归为 Other
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
        
        # 计算每个2小时时间槽的重叠时长
        for hour in range(0, 24, 2):
            slot_start = start.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=2)
            
            overlap_start = max(start, slot_start)
            overlap_end = min(end, slot_end)
            
            if overlap_start < overlap_end:
                overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
                time_slots[hour][key] += overlap_minutes
    
    # 构建结果
    bar_data = []
    for hour in range(0, 24, 2):
        slot_data = {"timeRange": f"{hour}-{hour+2}"}
        for key, minutes in time_slots[hour].items():
            slot_data[key] = int(minutes)
        bar_data.append(slot_data)
    
    return bar_data


def _build_empty_time_overview(date: str) -> TimeOverviewData:
    """构建空的时间概览响应"""
    empty_bar_data = [{"timeRange": f"{h}-{h+2}"} for h in range(0, 24, 2)]
    return TimeOverviewData(
        title="Time Overview",
        sub_title=f"No activity data for {date}",
        total_tracked_minutes=0,
        pie_data=[],
        bar_keys=[],
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
        pie_data=pie_data,
        bar_keys=bar_keys,
        bar_data=data['barData'],
        details=details if details else None
    )
