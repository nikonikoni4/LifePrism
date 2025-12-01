"""
统计分析API路由
"""

from fastapi import APIRouter, Query
from datetime import date, timedelta
from lifewatch.server.schemas.analytics import AnalyticsResponse
from lifewatch.server.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])
analytics_service = AnalyticsService()


@router.get("/summary", response_model=AnalyticsResponse, summary="获取统计分析摘要")
async def get_analytics_summary(
    start_date: date = Query(
        default=None,
        description="起始日期，默认为30天前"
    ),
    end_date: date = Query(
        default=None,
        description="结束日期，默认为今天"
    ),
    group_by: str = Query(
        default="day",
        regex="^(day|week|month)$",
        description="分组方式（day/week/month）"
    )
):
    """
    获取指定时间范围的统计分析数据
    
    **参数**:
    - start_date: 起始日期
    - end_date: 结束日期
    - group_by: 分组方式
      - day: 按天统计
      - week: 按周统计
      - month: 按月统计
    
    **返回数据**:
    - 每日/周/月的总时长
    - 工作/娱乐时长分布
    - Top 应用和分类
    
    **当前返回 Mock 数据**
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    
    data = analytics_service.get_analytics_summary(start_date, end_date, group_by)
    return {"summary": data}
