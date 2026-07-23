"""
Activity Stats Builder - 纯函数模块

提供活动统计数据的构建逻辑（Activity Summary 和 Time Overview）
从 ActivityService 分离出来，保持 Service 层简洁
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz

from lifeprism.config import get_user_timezone
from lifeprism.repository import computer_usage_repository
from lifeprism.server.providers.category_color_provider import color_manager, get_log_color
from lifeprism.server.schemas.activity_schemas import (
    ActivitySummaryData,
    BarConfig,
    ChartSegment,
    DailyActivitiesData,
    TimeOverviewData,
    TopAppData,
    TopTitleData,
)
from lifeprism.server.services.category_service import category_service
from lifeprism.utils.time_utils import build_utc_time_range

# ============================================================================
# UTC 时区迁移辅助函数
# ============================================================================


def _normalize_timestamp(value: str) -> str:
    """将时间戳规范化为 'YYYY-MM-DD HH:MM:SS' 格式（UTC）。

    处理两种输入格式：
    - 标准 'YYYY-MM-DD HH:MM:SS'（SQLite DEFAULT 输出）
    - ISO 8601 'YYYY-MM-DDTHH:MM:SS.ffffff+00:00'（Python isoformat 输出）
    """
    if not value:
        return ""
    result = str(value)
    if "T" in result:
        result = result.replace("T", " ", 1)
    return result[:19]


def _utc_timestamp_to_local_date(timestamp: str) -> str:
    """将 UTC 时间戳转换为用户本地时区日期（YYYY-MM-DD）。

    用于按天分组统计，确保分组基于用户感知的日期，而非 UTC 日期。

    Args:
        timestamp: UTC 时间戳（标准 'YYYY-MM-DD HH:MM:SS' 或 ISO 8601 格式）

    Returns:
        str: 用户本地时区日期 'YYYY-MM-DD'，空输入返回空字符串
    """
    if not timestamp:
        return ""
    normalized = _normalize_timestamp(timestamp)
    if not normalized:
        return ""
    try:
        utc_dt = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        local_tz = pytz.timezone(get_user_timezone())
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _add_local_date_column(df: pd.DataFrame, time_col: str = "start_time") -> pd.DataFrame:
    """为 DataFrame 添加 local_date 列（用户本地时区日期）。

    用于 pandas 按天分组统计，将 UTC 时间戳转为用户本地时区日期。
    确保跨时区边界的数据分到正确的本地日期。

    Args:
        df: 包含时间戳列的 DataFrame
        time_col: 时间戳列名，默认 'start_time'

    Returns:
        pd.DataFrame: 添加了 'local_date' 列的 DataFrame
    """
    if time_col not in df.columns:
        df["local_date"] = ""
        return df

    local_tz = pytz.timezone(get_user_timezone())
    df = df.copy()
    utc_times = pd.to_datetime(df[time_col], format="ISO8601", utc=True, errors="coerce")
    local_times = utc_times.dt.tz_convert(local_tz)
    df["local_date"] = local_times.dt.strftime("%Y-%m-%d")
    df["local_date"] = df["local_date"].where(df["local_date"].notna(), "")
    return df


# ============================================================================
# 分类名称查找辅助函数（使用 CategoryService 缓存）
# ============================================================================


def _get_category_name_map() -> dict[str, str]:
    """获取主分类 ID -> 名称映射（使用 CategoryService 缓存）"""
    return category_service.category_name_map


def _get_sub_category_name_map() -> dict[str, str]:
    """获取子分类 ID -> 名称映射（使用 CategoryService 缓存）"""
    return category_service.sub_category_name_map


# ============================================================================
# Activity Summary
# ============================================================================


def build_activity_summary(
    date: str,
    history_number: int,
    future_number: int,
    category_id: str | None,
    sub_category_id: str | None,
) -> ActivitySummaryData:
    """
    获取活动摘要条形图数据

    迁移后（Slice 05）：业务逻辑上移到 Service 层
    - 数据查询：computer_usage_repository.load_user_app_behavior_log 取 DataFrame
    - 时区转换：复用 _add_local_date_column（pandas 向量化，等价于原 utc_to_local_display）
    - 分类筛选：Service 层 df[df["category_id"] == category_id]
    - 百分比计算：Service 层 int(total_duration * 100 / 86400)

    依据 PRD "已知风险 1"：必须保留 Python 层时区分组（_add_local_date_column），
    禁止改用 SQL DATE(start_time) 分组（会按 UTC 日期分组导致跨时区错位）。

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
    date_range: list[str] = []
    current = center_date - timedelta(days=history_number)
    end_date_obj = center_date + timedelta(days=future_number)
    while current <= end_date_obj:
        date_range.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    # 3. 查询原始数据（替代原 get_daily_active_time）
    #    时区转换上移到 Service 层：用 build_utc_time_range 将本地日期范围转为 UTC
    start_utc, _ = build_utc_time_range(start_date)
    _, end_utc = build_utc_time_range(end_date)
    df = computer_usage_repository.load_user_app_behavior_log(
        start_time=start_utc, end_time=end_utc
    )

    # 4. Python 层按本地日期分组 + 计算百分比（业务逻辑上移）
    if df is not None and not df.empty:
        # 复用已有的 _add_local_date_column（activity_stats_builder.py:75-98）
        # 将 UTC start_time 转为用户本地时区日期，确保跨时区边界的数据分到正确的本地日期
        df = _add_local_date_column(df, "start_time")
        # 按分类筛选（如果有）—— Service 层 Python 过滤
        if category_id:
            df = df[df["category_id"] == category_id]
        if sub_category_id:
            df = df[df["sub_category_id"] == sub_category_id]
        # 按本地日期分组求和
        daily_durations: dict[str, int] = df.groupby("local_date")["duration"].sum().to_dict()
    else:
        daily_durations = {}

    # 5. 获取分类颜色
    filter_color = None
    if category_id:
        filter_color = color_manager.get_main_category_color(category_id)
    elif sub_category_id:
        filter_color = color_manager.get_sub_category_color(sub_category_id)

    default_color = "#5B8FF9"

    # 6. 构建完整的数据数组，缺失的日期补全为0 + 百分比计算（Service 层）
    daily_activities: list[DailyActivitiesData] = []
    for date_str in date_range:
        total_duration = daily_durations.get(date_str, 0)
        percentage = int(total_duration * 100 / 86400) if total_duration > 0 else 0
        duration = int(percentage * 86400 / 100)

        daily_activities.append(
            DailyActivitiesData(
                date=date_str,
                duration=duration,
                active_time_percentage=percentage,
                color=filter_color or default_color,
            )
        )

    return ActivitySummaryData(daily_activities=daily_activities)


# ============================================================================
# Time Overview
# ============================================================================


def build_time_overview(date: str) -> TimeOverviewData:
    """
    获取时间概览数据（三层嵌套结构：Category → SubCategory → App）

    Args:
        date: 查询日期 (YYYY-MM-DD 格式，本地时区)

    Returns:
        TimeOverviewData: 时间概览数据
    """
    # 1. 加载数据（将本地日期转换为 UTC ISO 8601 时间范围，符合 time-handling-rules 规则 3.7）
    start_time, end_time = build_utc_time_range(date)
    df = computer_usage_repository.load_user_app_behavior_log(
        start_time=start_time, end_time=end_time
    )

    if df is None or df.empty:
        return _build_empty_time_overview(date)

    # 预计算时长（分钟）
    df["start_dt"] = pd.to_datetime(df["start_time"], format="ISO8601", utc=True)
    df["end_dt"] = pd.to_datetime(df["end_time"], format="ISO8601", utc=True)
    df["duration_minutes"] = (df["end_dt"] - df["start_dt"]).dt.total_seconds() / 60

    # 获取分类名称映射（从分类表加载，确保使用最新名称）
    category_name_map = _get_category_name_map()
    sub_category_name_map = _get_sub_category_name_map()

    # 2. 构建 Level 1 (Category)
    root_data = _build_category_level_data(
        df,
        group_field="category_id",
        name_field="category",
        title="Time Overview",
        sub_title="Activity breakdown & timeline",
        is_main_category=True,
    )

    root_data["details"] = {}

    # 3. 构建 Level 2 (动态层级：有子分类时构建子分类层，无子分类时直接构建 App 层)
    categories = df["category_id"].dropna().unique()

    for category_id in categories:
        cat_df = df[df["category_id"] == category_id]
        if cat_df.empty:
            continue

        # 从分类表查找名称（不再从 DataFrame 读取）
        category_name = category_name_map.get(str(category_id), "Uncategorized")

        # 检测该主分类下是否有子分类
        sub_categories = cat_df["sub_category_id"].dropna().unique()

        if len(sub_categories) == 0:
            # 无子分类 → 直接构建 App 层作为 Level 2
            app_data = _build_app_level_data(
                cat_df,
                title=f"{category_name} Apps",
                sub_title=f"Top applications in {category_name}",
                parent_category_id=str(category_id),  # 使用主分类 ID 作为颜色基准
            )
            root_data["details"][category_name] = app_data
        else:
            # 有子分类 → 正常构建子分类层
            cat_data = _build_category_level_data(
                cat_df,
                group_field="sub_category_id",
                name_field="sub_category",
                title=f"{category_name} Details",
                sub_title=f"Detailed breakdown of {category_name}",
                is_main_category=False,
            )

            cat_data["details"] = {}
            root_data["details"][category_name] = cat_data

            # 4. 构建 Level 3 (Apps)
            for sub_cat_id in sub_categories:
                sub_df = cat_df[cat_df["sub_category_id"] == sub_cat_id]
                if sub_df.empty:
                    continue

                # 从分类表查找名称（不再从 DataFrame 读取）
                sub_cat_name = sub_category_name_map.get(str(sub_cat_id), "Uncategorized")

                app_data = _build_app_level_data(
                    sub_df,
                    title=f"{sub_cat_name} Apps",
                    sub_title=f"Top applications in {sub_cat_name}",
                    parent_sub_category_id=str(sub_cat_id),
                )

                cat_data["details"][sub_cat_name] = app_data

    return _dict_to_time_overview_data(root_data)


# ============================================================================
# Top N
# ============================================================================


def get_top_title(date: str, top_n: int) -> list[TopTitleData]:
    """获取热门标题数据

    迁移后（Slice 05）：业务逻辑上移到 Service 层
    - 时区转换：build_utc_time_range 在 Service 层完成
    - 字段映射：tuple 解包替代原 dict 访问
    - 百分比计算：Service 层 int(duration / total_duration * 100)

    Args:
        date: 日期字符串 (YYYY-MM-DD)
        top_n: int, Top N

    Returns:
        list[TopTitleData], Top窗口标题排行:
            name: str, 窗口标题
            duration: int, 活跃时长(秒)
    """
    # 时区转换上移到 Service 层
    start_utc, end_utc = build_utc_time_range(date)
    # Provider 返回 list[tuple[str, int]]，字段映射在 Service 层
    raw_list = computer_usage_repository.get_top_groups_by_duration(
        "title", start_utc, end_utc, top_n
    )
    # total_duration 是所有记录的总和（不是 top_n 的总和），用于百分比计算
    total_duration = computer_usage_repository.get_total_duration(start_utc, end_utc)

    # 构建 TopTitleData 列表（tuple 解包，替代原 dict 访问）
    result = []
    for name, duration in raw_list:
        result.append(
            TopTitleData(
                name=name,
                duration=int(duration),
                percentage=int(duration / total_duration * 100) if total_duration > 0 else 0,
            )
        )
    return result


def get_top_app(date: str, top_n: int) -> list[TopAppData]:
    """获取热门应用数据

    迁移后（Slice 05）：业务逻辑上移到 Service 层
    - 时区转换：build_utc_time_range 在 Service 层完成
    - 字段映射：tuple 解包替代原 dict 访问
    - 百分比计算：Service 层 int(duration / total_duration * 100)

    Args:
        date: 日期字符串 (YYYY-MM-DD)
        top_n: int, Top N

    Returns:
        list[TopAppData], Top应用排行:
            name: str, 应用名称
            duration: int, 活跃时长(秒)
    """
    # 时区转换上移到 Service 层
    start_utc, end_utc = build_utc_time_range(date)
    # Provider 返回 list[tuple[str, int]]，字段映射在 Service 层
    raw_list = computer_usage_repository.get_top_groups_by_duration(
        "app", start_utc, end_utc, top_n
    )
    # total_duration 是所有记录的总和（不是 top_n 的总和），用于百分比计算
    total_duration = computer_usage_repository.get_total_duration(start_utc, end_utc)

    # 构建 TopAppData 列表（tuple 解包，替代原 dict 访问）
    result = []
    for name, duration in raw_list:
        result.append(
            TopAppData(
                name=name,
                duration=int(duration),
                percentage=int(duration / total_duration * 100) if total_duration > 0 else 0,
            )
        )
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
    is_main_category: bool,
) -> dict:
    # 获取分类名称映射（从分类表加载，确保使用最新的名称）
    name_map = _get_category_name_map() if is_main_category else _get_sub_category_name_map()

    # 只按 id 分组（不需要读取名称列，从 name_map 查找）
    stats = df.groupby(group_field).agg({"duration_minutes": "sum"}).reset_index()
    stats.columns = ["id", "minutes"]
    stats = stats.sort_values("minutes", ascending=False)

    total_minutes = stats["minutes"].sum()

    pie_data = []
    bar_keys = []

    for _, row in stats.iterrows():
        cat_id = str(row["id"]) if pd.notna(row["id"]) else "unknown"
        # 从分类表查找名称，而不是使用日志中可能过时的名称
        name = name_map.get(cat_id, "Uncategorized")
        minutes = int(row["minutes"])

        if is_main_category:
            item_color = color_manager.get_main_category_color(cat_id)
        else:
            item_color = color_manager.get_sub_category_color(cat_id)

        pie_data.append(
            {"key": cat_id, "name": name, "value": minutes, "color": item_color, "title": ""}
        )

        bar_keys.append({"key": cat_id, "label": name, "color": item_color})

    # 构建 id -> id_str 的映射（确保使用字符串格式的 ID）
    # barData 直接使用 category_id 进行分组，避免名称不一致问题
    bar_data = _calculate_time_distribution(df, group_field=group_field)

    return {
        "title": title,
        "subTitle": sub_title,
        "totalTrackedMinutes": int(total_minutes),
        "pieData": pie_data,
        "barKeys": bar_keys,
        "barData": bar_data,
    }


def _build_app_level_data(
    df: pd.DataFrame,
    title: str,
    sub_title: str,
    parent_sub_category_id: str = None,
    parent_category_id: str = None,
) -> dict:
    """构建应用级别数据（Top 5 + Other，包含 top 3 titles）

    Args:
        df: 数据 DataFrame
        title: 标题
        sub_title: 副标题
        parent_sub_category_id: 父子分类 ID（用于获取颜色基准，有子分类时使用）
        parent_category_id: 父主分类 ID（用于获取颜色基准，无子分类时使用）
    """
    stats = df.groupby("app")["duration_minutes"].sum().sort_values(ascending=False)
    total_minutes = stats.sum()

    top_5 = stats.head(5)
    other_value = stats.iloc[5:].sum() if len(stats) > 5 else 0

    # 根据传入的参数决定使用主分类或子分类颜色作为基准
    if parent_sub_category_id:
        base_color = color_manager.get_sub_category_color(parent_sub_category_id)
    elif parent_category_id:
        base_color = color_manager.get_main_category_color(parent_category_id)
    else:
        base_color = "#5B8FF9"  # 默认颜色

    pie_data = []
    bar_keys = []

    for _i, (app_name, minutes) in enumerate(top_5.items()):
        # 为每个 App 即时生成随机浅色（level=3）
        app_color = get_log_color(base_color)

        app_df = df[df["app"] == app_name]
        title_stats = (
            app_df.groupby("title")["duration_minutes"].sum().sort_values(ascending=False).head(3)
        )
        top_titles = "-split-".join(title_stats.index.tolist())

        pie_data.append(
            {
                "key": app_name,
                "name": app_name,
                "value": int(minutes),
                "color": app_color,
                "title": top_titles,
            }
        )

        bar_keys.append({"key": app_name, "label": app_name, "color": app_color})

    if other_value > 0:
        other_color = "#9CA3AF"
        pie_data.append(
            {
                "key": "Other",
                "name": "Other Apps",
                "value": int(other_value),
                "color": other_color,
                "title": "",
            }
        )
        bar_keys.append({"key": "Other", "label": "Other", "color": other_color})

    bar_data = _calculate_time_distribution(df, top_items=top_5.index.tolist())

    return {
        "title": title,
        "subTitle": sub_title,
        "totalTrackedMinutes": int(total_minutes),
        "pieData": pie_data,
        "barKeys": bar_keys,
        "barData": bar_data,
    }


def _calculate_time_distribution(
    df: pd.DataFrame, group_field: str = None, top_items: list[str] = None
) -> list[dict]:
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
        start = row["start_dt"]
        end = row["end_dt"]

        # 确定分组 key
        if top_items is not None:
            # 应用层级：使用 app 字段，不在 top_items 中的归为 Other
            raw_key = row["app"]
            key = raw_key if raw_key in top_items else "Other"
        else:
            # 分类层级：直接使用 ID 字段（如 category_id）
            raw_key = row[group_field]
            key = "unknown" if raw_key is None or pd.isna(raw_key) else str(raw_key)

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
        slot_data = {"timeRange": f"{hour}-{hour + 2}"}
        for key, minutes in time_slots[hour].items():
            slot_data[key] = int(minutes)
        bar_data.append(slot_data)

    return bar_data


def _build_empty_time_overview(date: str) -> TimeOverviewData:
    """构建空的时间概览响应"""
    empty_bar_data = [{"timeRange": f"{h}-{h + 2}"} for h in range(0, 24, 2)]
    return TimeOverviewData(
        title="Time Overview",
        sub_title=f"No activity data for {date}",
        total_tracked_minutes=0,
        pie_data=[],
        bar_keys=[],
        bar_data=empty_bar_data,
        details={},
    )


def _dict_to_time_overview_data(data: dict) -> TimeOverviewData:
    """将字典转换为 TimeOverviewData Pydantic 模型"""
    pie_data = [ChartSegment(**item) for item in data.get("pieData", [])]
    bar_keys = [BarConfig(**item) for item in data.get("barKeys", [])]

    details = {}
    for key, value in data.get("details", {}).items():
        details[key] = _dict_to_time_overview_data(value)

    return TimeOverviewData(
        title=data["title"],
        sub_title=data["subTitle"],
        total_tracked_minutes=data["totalTrackedMinutes"],
        pie_data=pie_data,
        bar_keys=bar_keys,
        bar_data=data["barData"],
        details=details if details else None,
    )
