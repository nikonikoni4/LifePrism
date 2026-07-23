"""
Usage 服务层 - Token 使用统计

提供 Token 使用统计的纯函数接口
"""

from datetime import datetime, timedelta, timezone

import pytz

from lifeprism.config import get_user_timezone
from lifeprism.config.settings_manager import settings
from lifeprism.repository import QueryOptions, tokens_usage_repository
from lifeprism.server.schemas.usage_schemas import (
    DataProcessingUsageStats,
    OtherUsageStats,
    UsageOverview,
    UsageStats7Days,
    UsageStats7DaysItem,
    UsageStatsResponse,
)

# 常量：Data Processing 的 mode
MODE_CLASSIFICATION = "classification"


def _normalize_created_at(created_at: str) -> str:
    """将 created_at 规范化为 'YYYY-MM-DD HH:MM:SS' 格式（UTC）。

    处理两种输入格式：
    - 标准 'YYYY-MM-DD HH:MM:SS'（SQLite DEFAULT 输出）
    - ISO 8601 'YYYY-MM-DDTHH:MM:SS.ffffff+00:00'（Python isoformat 输出）

    Args:
        created_at: 原始 created_at 字符串

    Returns:
        str: 规范化后的 'YYYY-MM-DD HH:MM:SS' 格式字符串
    """
    if not created_at:
        return ""
    value = str(created_at)
    # ISO 格式（含 T 分隔符）转换为标准格式
    if "T" in value:
        # 取 T 后的时间部分前 19 个字符：'YYYY-MM-DDTHH:MM:SS'
        value = value.replace("T", " ", 1)
    return value[:19]


def _to_time_range(
    date: str = None, start_time: str = None, end_time: str = None
) -> tuple[str | None, str | None]:
    """将 date 或显式时间范围统一转换为 UTC 时间范围字符串。

    当传入本地日期（YYYY-MM-DD）时，基于用户配置时区转换为 UTC 时间范围。
    例如本地 2026-07-12 (UTC+8) -> UTC 2026-07-11 16:00:00 ~ 2026-07-12 15:59:59

    Args:
        date: 本地日期 YYYY-MM-DD（用户本地时区）
        start_time: 显式起始时间（已是 UTC）
        end_time: 显式结束时间（已是 UTC）

    Returns:
        tuple[str | None, str | None]: (start, end) UTC 时间范围字符串
    """
    if date:
        local_tz = pytz.timezone(get_user_timezone())
        local_start = local_tz.localize(datetime.strptime(date, "%Y-%m-%d"))
        local_end = local_start + timedelta(days=1) - timedelta(seconds=1)
        utc_start = local_start.astimezone(timezone.utc)
        utc_end = local_end.astimezone(timezone.utc)
        return utc_start.strftime("%Y-%m-%d %H:%M:%S"), utc_end.strftime("%Y-%m-%d %H:%M:%S")
    return start_time, end_time


def _is_in_time_range(created_at: str, start_time: str = None, end_time: str = None) -> bool:
    """判断记录 created_at 是否处于指定时间范围内（闭区间）。

    created_at 可能是 UTC 标准格式或 ISO 8601 格式，统一规范化后比较。
    start_time/end_time 应为 UTC 'YYYY-MM-DD HH:MM:SS' 格式。

    Args:
        created_at: 记录创建时间（UTC，可能是标准或 ISO 格式）
        start_time: 范围起始（UTC 'YYYY-MM-DD HH:MM:SS'）
        end_time: 范围结束（UTC 'YYYY-MM-DD HH:MM:SS'）

    Returns:
        bool: 是否在范围内（闭区间）
    """
    if not created_at:
        return False
    time_value = _normalize_created_at(created_at)
    if not time_value:
        return False
    if start_time and time_value < start_time:
        return False
    return not (end_time and time_value > end_time)


def _query_tokens_usage_records(
    date: str = None, start_time: str = None, end_time: str = None, mode: str = None
) -> list[dict]:
    """查询 token 使用原始记录，并在 service 层做时间过滤。"""
    query_options = QueryOptions(order_by="created_at", order_desc=False)
    if mode:
        query_options = query_options.with_filters(mode=mode)

    records, _ = tokens_usage_repository.query_tokens_usage(query_options)
    range_start, range_end = _to_time_range(date=date, start_time=start_time, end_time=end_time)

    if not range_start and not range_end:
        return records

    return [
        record
        for record in records
        if _is_in_time_range(record.get("created_at"), range_start, range_end)
    ]


def _empty_usage_data() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "result_items_count": 0}


def _utc_created_at_to_local_date(created_at: str) -> str:
    """将 UTC created_at 转换为用户本地时区日期（YYYY-MM-DD）。

    用于按"天"分组统计，确保分组基于用户感知的日期，而非 UTC 日期。

    Args:
        created_at: UTC 时间戳（标准 'YYYY-MM-DD HH:MM:SS' 或 ISO 8601 格式）

    Returns:
        str: 用户本地时区日期 'YYYY-MM-DD'，空输入返回空字符串
    """
    if not created_at:
        return ""
    normalized = _normalize_created_at(created_at)
    if not normalized:
        return ""
    try:
        utc_dt = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        local_tz = pytz.timezone(get_user_timezone())
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _aggregate_tokens_usage_by_date(records: list[dict]) -> dict[str, dict]:
    """按用户本地日期聚合 token 使用记录。

    created_at 是 UTC 时间戳，需先转换为用户本地时区日期再分组，
    确保跨时区边界的数据分到正确的本地日期。
    """
    usage_dict: dict[str, dict] = {}
    for record in records:
        created_at = record.get("created_at", "")
        usage_date = _utc_created_at_to_local_date(created_at)
        if not usage_date:
            continue
        if usage_date not in usage_dict:
            usage_dict[usage_date] = _empty_usage_data()
        usage_dict[usage_date]["input_tokens"] += record.get("input_tokens", 0) or 0
        usage_dict[usage_date]["output_tokens"] += record.get("output_tokens", 0) or 0
        usage_dict[usage_date]["total_tokens"] += record.get("total_tokens", 0) or 0
        usage_dict[usage_date]["result_items_count"] += record.get("result_items_count", 0) or 0
    return usage_dict


def _aggregate_tokens_usage_by_mode(records: list[dict]) -> dict[str, dict]:
    """按 mode 聚合 token 使用记录。"""
    usage_dict: dict[str, dict] = {}
    for record in records:
        mode = record.get("mode")
        if mode not in usage_dict:
            usage_dict[mode] = _empty_usage_data()
        usage_dict[mode]["input_tokens"] += record.get("input_tokens", 0) or 0
        usage_dict[mode]["output_tokens"] += record.get("output_tokens", 0) or 0
        usage_dict[mode]["total_tokens"] += record.get("total_tokens", 0) or 0
        usage_dict[mode]["result_items_count"] += record.get("result_items_count", 0) or 0
    return usage_dict


def _aggregate_all_tokens_usage(records: list[dict]) -> dict:
    """聚合全部 token 使用记录。"""
    total_data = _empty_usage_data()
    for record in records:
        total_data["input_tokens"] += record.get("input_tokens", 0) or 0
        total_data["output_tokens"] += record.get("output_tokens", 0) or 0
        total_data["total_tokens"] += record.get("total_tokens", 0) or 0
        total_data["result_items_count"] += record.get("result_items_count", 0) or 0
    return total_data


def get_usage_stats(date: str) -> UsageStatsResponse:
    """
    获取完整的使用统计数据

    Args:
        date: 日期（YYYY-MM-DD 格式）

    Returns:
        UsageStatsResponse: 包含总览、7天统计、数据处理统计和其他消耗统计
    """
    # 获取单日数据用于总览和数据处理统计
    tokens_usage_data = _aggregate_tokens_usage_by_date(_query_tokens_usage_records(date=date))

    # 获取按 mode 分组的今日数据
    tokens_by_mode_today = _aggregate_tokens_usage_by_mode(_query_tokens_usage_records(date=date))

    # 获取全部数据（不限日期范围）
    all_tokens_data = _aggregate_all_tokens_usage(_query_tokens_usage_records())

    # 获取按 mode 分组的全部数据
    all_tokens_by_mode = _aggregate_tokens_usage_by_mode(_query_tokens_usage_records())

    return UsageStatsResponse(
        usage_overview=get_usage_overview(date, tokens_usage_data, all_tokens_data),
        data_processing_usage_stats=get_data_processing_usage_stats(
            date, tokens_by_mode_today, all_tokens_by_mode
        ),
        other_usage_stats=get_other_usage_stats(date, tokens_by_mode_today, all_tokens_by_mode),
        usage_stats_7days=get_usage_stats_7days(date),
    )


def get_usage_stats_7days(date: str) -> UsageStats7Days:
    """
    获取最近7天的使用统计

    Args:
        date: 结束日期（YYYY-MM-DD 格式，用户本地时区）

    Returns:
        UsageStats7Days: 7天的使用统计列表
    """
    # 计算7天的日期范围（本地日期）
    end_date = datetime.strptime(date, "%Y-%m-%d")
    start_date = end_date - timedelta(days=6)  # 包括今天共7天

    # 将本地日期范围转为 UTC 时间范围进行查询
    utc_start, _ = _to_time_range(date=start_date.strftime("%Y-%m-%d"))
    _, utc_end = _to_time_range(date=end_date.strftime("%Y-%m-%d"))

    usage_data = _aggregate_tokens_usage_by_date(
        _query_tokens_usage_records(start_time=utc_start, end_time=utc_end)
    )

    # 构建7天的统计列表
    items = []
    current_date = start_date

    for _ in range(7):
        date_str = current_date.strftime("%Y-%m-%d")
        day_data = usage_data.get(
            date_str,
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "result_items_count": 0},
        )

        # 计算总价格
        total_cost = (
            day_data["input_tokens"] * settings.input_tokens_cost / 1000
            + day_data["output_tokens"] * settings.output_tokens_cost / 1000
        )

        items.append(
            UsageStats7DaysItem(
                day=date_str, total_cost=round(total_cost, 4), total_tokens=day_data["total_tokens"]
            )
        )

        current_date += timedelta(days=1)

    return UsageStats7Days(items=items)


def get_usage_overview(
    date: str, tokens_usage_data: dict[str, dict] = None, all_tokens_data: dict = None
) -> UsageOverview:
    """
    获取单日使用总览

    Args:
        date: 日期（YYYY-MM-DD 格式）
        tokens_usage_data: 可选的预加载数据，避免重复查询
        all_tokens_data: 可选的全部数据，避免重复查询

    Returns:
        UsageOverview: 使用总览数据
    """
    # 如果没有提供数据，则获取
    if tokens_usage_data is None:
        tokens_usage_data = _aggregate_tokens_usage_by_date(_query_tokens_usage_records(date=date))

    if all_tokens_data is None:
        all_tokens_data = _aggregate_all_tokens_usage(_query_tokens_usage_records())

    # 获取当天的数据
    day_data = tokens_usage_data.get(
        date, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "result_items_count": 0}
    )

    input_tokens = day_data["input_tokens"]
    output_tokens = day_data["output_tokens"]
    total_tokens = day_data["total_tokens"]

    # 计算今日价格
    input_price = input_tokens * settings.input_tokens_cost / 1000
    output_price = output_tokens * settings.output_tokens_cost / 1000
    total_price = input_price + output_price

    # 计算全部价格
    all_input_price = all_tokens_data["input_tokens"] * settings.input_tokens_cost / 1000
    all_output_price = all_tokens_data["output_tokens"] * settings.output_tokens_cost / 1000
    all_total_price = all_input_price + all_output_price

    return UsageOverview(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_tokens_price=settings.input_tokens_cost,
        output_tokens_price=settings.output_tokens_cost,
        total_price=round(total_price, 4),
        all_total_tokens=all_tokens_data["total_tokens"],
        all_total_price=round(all_total_price, 4),
    )


def get_data_processing_usage_stats(
    date: str,
    tokens_by_mode_today: dict[str, dict] = None,
    all_tokens_by_mode: dict[str, dict] = None,
) -> DataProcessingUsageStats:
    """
    获取数据处理使用统计

    Args:
        date: 日期（YYYY-MM-DD 格式）
        tokens_by_mode_today: 可选的按 mode 分组的今日数据
        all_tokens_by_mode: 可选的按 mode 分组的全部数据

    Returns:
        DataProcessingUsageStats: 数据处理统计
    """
    # 如果没有提供数据，则获取
    if tokens_by_mode_today is None:
        tokens_by_mode_today = _aggregate_tokens_usage_by_mode(
            _query_tokens_usage_records(date=date)
        )

    if all_tokens_by_mode is None:
        all_tokens_by_mode = _aggregate_tokens_usage_by_mode(_query_tokens_usage_records())

    # 获取今日 classification 数据
    today_data = tokens_by_mode_today.get(
        MODE_CLASSIFICATION,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "result_items_count": 0},
    )

    # 获取全部 classification 数据
    all_data = all_tokens_by_mode.get(
        MODE_CLASSIFICATION,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "result_items_count": 0},
    )

    processing_items = today_data["result_items_count"]
    total_tokens = today_data["total_tokens"]

    # 计算今日平均值
    avg_processing_tokens = total_tokens / processing_items if processing_items > 0 else 0

    # 计算今日总价格
    input_price = today_data["input_tokens"] * settings.input_tokens_cost / 1000
    output_price = today_data["output_tokens"] * settings.output_tokens_cost / 1000
    total_cost = input_price + output_price

    # 计算今日平均价格
    avg_cost = total_cost / processing_items if processing_items > 0 else 0

    # 计算全部价格
    all_input_price = all_data["input_tokens"] * settings.input_tokens_cost / 1000
    all_output_price = all_data["output_tokens"] * settings.output_tokens_cost / 1000
    all_total_cost = all_input_price + all_output_price

    return DataProcessingUsageStats(
        processing_items=processing_items,
        avg_processing_tokens=round(avg_processing_tokens, 2),
        avg_cost=round(avg_cost, 6),
        total_tokens=total_tokens,
        total_cost=round(total_cost, 4),
        all_total_tokens=all_data["total_tokens"],
        all_total_cost=round(all_total_cost, 4),
    )


def get_other_usage_stats(
    date: str,
    tokens_by_mode_today: dict[str, dict] = None,
    all_tokens_by_mode: dict[str, dict] = None,
) -> OtherUsageStats:
    """
    获取其他消耗使用统计（非 classification 的所有消耗）

    Args:
        date: 日期（YYYY-MM-DD 格式）
        tokens_by_mode_today: 可选的按 mode 分组的今日数据
        all_tokens_by_mode: 可选的按 mode 分组的全部数据

    Returns:
        OtherUsageStats: 其他消耗统计
    """
    # 如果没有提供数据，则获取
    if tokens_by_mode_today is None:
        tokens_by_mode_today = _aggregate_tokens_usage_by_mode(
            _query_tokens_usage_records(date=date)
        )

    if all_tokens_by_mode is None:
        all_tokens_by_mode = _aggregate_tokens_usage_by_mode(_query_tokens_usage_records())

    # 计算今日其他消耗（排除 classification）
    today_input_tokens = 0
    today_output_tokens = 0
    today_total_tokens = 0

    for mode, data in tokens_by_mode_today.items():
        if mode != MODE_CLASSIFICATION:
            today_input_tokens += data["input_tokens"]
            today_output_tokens += data["output_tokens"]
            today_total_tokens += data["total_tokens"]

    # 计算今日其他消耗总价格
    today_input_price = today_input_tokens * settings.input_tokens_cost / 1000
    today_output_price = today_output_tokens * settings.output_tokens_cost / 1000
    today_total_cost = today_input_price + today_output_price

    # 计算全部其他消耗（排除 classification）
    all_input_tokens = 0
    all_output_tokens = 0
    all_total_tokens = 0

    for mode, data in all_tokens_by_mode.items():
        if mode != MODE_CLASSIFICATION:
            all_input_tokens += data["input_tokens"]
            all_output_tokens += data["output_tokens"]
            all_total_tokens += data["total_tokens"]

    # 计算全部其他消耗总价格
    all_input_price = all_input_tokens * settings.input_tokens_cost / 1000
    all_output_price = all_output_tokens * settings.output_tokens_cost / 1000
    all_total_cost = all_input_price + all_output_price

    return OtherUsageStats(
        total_tokens=today_total_tokens,
        total_cost=round(today_total_cost, 4),
        all_total_tokens=all_total_tokens,
        all_total_cost=round(all_total_cost, 4),
    )
