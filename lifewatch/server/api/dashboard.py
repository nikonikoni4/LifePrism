"""
仪表盘API路由
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import date
from typing import Optional
from lifewatch.server.schemas.dashboard import DashboardResponse
from lifewatch.server.schemas.dashboard_schemas import TimeOverviewResponse
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


@router.get("/time-overview", response_model=TimeOverviewResponse, summary="获取 Time Overview 数据")
async def get_time_overview(
    date: str = Query(..., description="日期 (YYYY-MM-DD 格式)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    parent_id: Optional[str] = Query(None, description="主分类ID（用于下钻到子分类）")
):
    """
    获取 Time Overview 数据
    
    **功能：**
    - 一级分类概览：不传 parent_id，返回所有主分类的时间分布
    - 二级分类详情：传入 parent_id，返回该主分类下所有子分类的时间分布
    
    **返回数据：**
    - 饼图数据（pieData）：各分类的时长和占比
    - 柱状图配置（barKeys）：图例和颜色配置
    - 24小时分布（barData）：每2小时的活动分布
    
    **示例：**
    - 一级概览：`/api/v1/dashboard/time-overview?date=2023-10-25`
    - 二级详情：`/api/v1/dashboard/time-overview?date=2023-10-25&parent_id=work`
    """
    try:
        data = dashboard_service.get_time_overview(date, parent_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Time Overview 失败: {str(e)}")
