"""
Usage API 路由

Token 使用统计 API：
- /usage/stats - 获取使用统计数据（总览、7天趋势、数据处理统计）
"""

from fastapi import APIRouter, Query, HTTPException

from lifeprism.server.schemas.usage_schemas import UsageStatsResponse
from lifeprism.server.services import usage_service
from lifeprism.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/usage", tags=["Usage"])


# ============================================================================
# Stats API - 统计数据（只读）
# ============================================================================

@router.get("/stats", summary="获取 Token 使用统计", response_model=UsageStatsResponse)
async def get_usage_stats(
    date: str = Query(
        ..., 
        description="查询日期 (YYYY-MM-DD 格式)", 
        regex=r"^\d{4}-\d{2}-\d{2}$"
    )
) -> UsageStatsResponse:
    """
    获取 Token 使用统计数据
    
    **功能：**
    - 获取指定日期的 Token 使用总览
    - 获取最近7天的使用趋势（以指定日期为结束日期）
    - 获取数据处理统计（平均消耗、总成本等）
    
    **返回数据包含：**
    - `usage_overview`: 使用总览
        - input_tokens: 输入 token 数
        - output_tokens: 输出 token 数
        - total_tokens: 总 token 数
        - input_tokens_price: 输入 token 单价（每1000个）
        - output_tokens_price: 输出 token 单价（每1000个）
        - total_price: 总价格
    
    - `data_processing_usage_stats`: 数据处理统计
        - processing_items: 处理项目数
        - avg_processing_tokens: 平均每项处理的 token 数
        - avg_cost: 平均每项成本
        - total_cost: 总成本
    
    - `usage_stats_7days`: 7天使用趋势
        - items: 每天的统计列表
            - day: 日期
            - total_cost: 总成本
            - total_tokens: 总 token 数
    
    **示例：**
    - `/api/v2/usage/stats?date=2025-12-20`
    - 返回 2025-12-20 当天的使用总览，以及从 2025-12-14 到 2025-12-20 的7天趋势
    """
    try:
        return usage_service.get_usage_stats(date=date)
    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取使用统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取使用统计失败: {str(e)}")

