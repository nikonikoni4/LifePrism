"""
Usage 服务层 - Token 使用统计

提供 Token 使用统计的纯函数接口
"""

from datetime import datetime, timedelta

from lifewatch.server.schemas.usage_schemas import (
    UsageOverview,
    DataProcessingUsageStats,
    UsageStats7Days,
    UsageStats7DaysItem,
    UsageStatsResponse
)
from lifewatch.server.providers import server_lw_data_provider
from lifewatch.config.settings import INPUT_TOKEN_PRICE_PER_1K, OUTPUT_TOKEN_PRICE_PER_1K


def get_usage_stats(date: str) -> UsageStatsResponse:
    """
    获取完整的使用统计数据
    
    Args:
        date: 日期（YYYY-MM-DD 格式）
    
    Returns:
        UsageStatsResponse: 包含总览、7天统计和数据处理统计
    """
    # 获取单日数据用于总览和数据处理统计
    tokens_usage_data = server_lw_data_provider.get_tokens_usage(date=date)
    
    return UsageStatsResponse(
        usage_overview=get_usage_overview(date, tokens_usage_data),
        data_processing_usage_stats=get_data_processing_usage_stats(date, tokens_usage_data),
        usage_stats_7days=get_usage_stats_7days(date)
    )


def get_usage_stats_7days(date: str) -> UsageStats7Days:
    """
    获取最近7天的使用统计
    
    Args:
        date: 结束日期（YYYY-MM-DD 格式）
    
    Returns:
        UsageStats7Days: 7天的使用统计列表
    """
    # 计算7天的日期范围
    end_date = datetime.strptime(date, "%Y-%m-%d")
    start_date = end_date - timedelta(days=6)  # 包括今天共7天
    
    # 获取7天的数据
    start_time = start_date.strftime("%Y-%m-%d 00:00:00")
    end_time = end_date.strftime("%Y-%m-%d 23:59:59")
    
    usage_data = server_lw_data_provider.get_tokens_usage(start_time=start_time, end_time=end_time)
    
    # 构建7天的统计列表
    items = []
    current_date = start_date
    
    for _ in range(7):
        date_str = current_date.strftime("%Y-%m-%d")
        day_data = usage_data.get(date_str, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "result_items_count": 0
        })
        
        # 计算总价格
        total_cost = (
            day_data["input_tokens"] * INPUT_TOKEN_PRICE_PER_1K / 1000 +
            day_data["output_tokens"] * OUTPUT_TOKEN_PRICE_PER_1K / 1000
        )
        
        items.append(UsageStats7DaysItem(
            day=date_str,
            total_cost=round(total_cost, 4),
            total_tokens=day_data["total_tokens"]
        ))
        
        current_date += timedelta(days=1)
    
    return UsageStats7Days(items=items)


def get_usage_overview(date: str, tokens_usage_data: dict[str, dict] = None) -> UsageOverview:
    """
    获取单日使用总览
    
    Args:
        date: 日期（YYYY-MM-DD 格式）
        tokens_usage_data: 可选的预加载数据，避免重复查询
    
    Returns:
        UsageOverview: 使用总览数据
    """
    # 如果没有提供数据，则获取
    if not tokens_usage_data:
        tokens_usage_data = server_lw_data_provider.get_tokens_usage(date=date)
    
    # 获取当天的数据
    day_data = tokens_usage_data.get(date, {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "result_items_count": 0
    })
    
    input_tokens = day_data["input_tokens"]
    output_tokens = day_data["output_tokens"]
    total_tokens = day_data["total_tokens"]
    
    # 计算价格
    input_price = input_tokens * INPUT_TOKEN_PRICE_PER_1K / 1000
    output_price = output_tokens * OUTPUT_TOKEN_PRICE_PER_1K / 1000
    total_price = input_price + output_price
    
    return UsageOverview(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_tokens_price=INPUT_TOKEN_PRICE_PER_1K,
        output_tokens_price=OUTPUT_TOKEN_PRICE_PER_1K,
        total_price=round(total_price, 4)
    )


def get_data_processing_usage_stats(date: str, tokens_usage_data: dict[str, dict] = None) -> DataProcessingUsageStats:
    """
    获取数据处理使用统计
    
    Args:
        date: 日期（YYYY-MM-DD 格式）
        tokens_usage_data: 可选的预加载数据，避免重复查询
    
    Returns:
        DataProcessingUsageStats: 数据处理统计
    """
    # 如果没有提供数据，则获取
    if not tokens_usage_data:
        tokens_usage_data = server_lw_data_provider.get_tokens_usage(date=date)
    
    # 获取当天的数据
    day_data = tokens_usage_data.get(date, {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "result_items_count": 0
    })
    
    processing_items = day_data["result_items_count"]
    total_tokens = day_data["total_tokens"]
    
    # 计算平均值
    avg_processing_tokens = total_tokens / processing_items if processing_items > 0 else 0
    
    # 计算总价格
    input_price = day_data["input_tokens"] * INPUT_TOKEN_PRICE_PER_1K / 1000
    output_price = day_data["output_tokens"] * OUTPUT_TOKEN_PRICE_PER_1K / 1000
    total_cost = input_price + output_price
    
    # 计算平均价格
    avg_cost = total_cost / processing_items if processing_items > 0 else 0
    
    return DataProcessingUsageStats(
        processing_items=processing_items,
        avg_processing_tokens=round(avg_processing_tokens, 2),
        avg_cost=round(avg_cost, 6),
        total_cost=round(total_cost, 4)
    )