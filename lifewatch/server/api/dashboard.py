"""
仪表盘API路由
"""

from fastapi import APIRouter, Query
from datetime import date
from lifewatch.server.schemas.dashboard import DashboardResponse
from lifewatch.server.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
dashboard_service = DashboardService()


@router.get("", response_model=DashboardResponse, summary="获取仪表盘数据")
async def get_dashboard(
    query_date: date = Query(
        default=None,
        alias="date",
        description="查询日期，默认为今天"
    )
):
    """
    获取指定日期的仪表盘数据
    
    返回包括：
    - 总活跃时长
    - Top 应用排行
    - Top 窗口标题排行
    - 分类统计（默认分类和目标分类）
    
    **当前返回 Mock 数据**
    """
    if query_date is None:
        query_date = date.today()
    
    data = dashboard_service.get_dashboard_data(query_date)
    return data
