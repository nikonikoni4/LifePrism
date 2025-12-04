"""
仪表盘API路由
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import date
from typing import Optional
from lifewatch.server.schemas.dashboard import DashboardResponse
from lifewatch.server.schemas.dashboard_schemas import TimeOverviewResponse
from lifewatch.server.services import DashboardService


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


@router.get("/homepage", response_model=None, summary="获取首页统一数据")
async def get_homepage(
    date: str = Query(..., description="日期 (YYYY-MM-DD 格式)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    history_number: int = Query(15, description="历史数据天数", ge=0, le=365),
    future_number: int = Query(14, description="未来数据天数", ge=0, le=365)
):
    """
    获取首页统一数据（整合三个API调用）
    
    **功能：**
    - 一次性返回首页所有组件所需的数据
    - 整合 activity_summary、dashboard 和 time_overview 三个接口
    
    **返回数据：**
    - activity_summary: 活动总结条形图数据
    - dashboard: 仪表盘数据（top应用、top标题、分类统计）
    - time_overview: 时间概览图表数据
    
    **优势：**
    - 减少网络请求次数（从3次降为1次）
    - 提高页面加载速度
    - 优化数据库查询（可复用查询结果）
    
    **示例：**
    - `/api/v1/dashboard/homepage?date=2023-10-25&history_number=15&future_number=14`
    """
    try:
        data = dashboard_service.get_homepage_data(date, history_number, future_number)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取首页数据失败: {str(e)}")
