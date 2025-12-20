"""
仪表盘API路由
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import date
from typing import Optional
# from lifewatch.server.schemas.dashboard import DashboardResponse
# from lifewatch.server.schemas.dashboard_schemas import TimeOverviewResponse
from lifewatch.server.schemas.timeline_schemas import TimelineResponse
from lifewatch.server.services import DashboardService
from lifewatch.server.services.timeline_service import TimelineService


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
dashboard_service = DashboardService()
timeline_service = TimelineService()


# @router.get("", response_model=DashboardResponse, summary="获取仪表盘数据")
# async def get_dashboard(
#     query_date: date = Query(
#         default=None,
#         alias="date",
#         description="查询日期，默认为今天"
#     )
# ):
#     """
#     获取指定日期的仪表盘数据
    
#     返回包括：
#     - 总活跃时长
#     - Top 应用排行
#     - Top 窗口标题排行
#     - 分类统计（默认分类和目标分类）
    
#     **当前返回 Mock 数据**
#     """
#     if query_date is None:
#         query_date = date.today()
    
#     data = dashboard_service.get_dashboard_data(query_date)
#     return data


# @router.get("/time-overview", response_model=TimeOverviewResponse, summary="获取 Time Overview 数据")
# async def get_time_overview(
#     date: str = Query(..., description="日期 (YYYY-MM-DD 格式)", regex=r"^\d{4}-\d{2}-\d{2}$")
# ):
#     """
#     获取 Time Overview 数据
    
#     **功能：**
#     - 一次性返回所有层级的时间分布数据（Category -> Sub-category -> Apps）
    
#     **返回数据：**
#     - 包含嵌套的 details 字段，支持前端本地下钻
#     """
#     try:
#         data = dashboard_service.get_time_overview(date)
#         return data
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"获取 Time Overview 失败: {str(e)}")


# @router.get("/homepage", response_model=None, summary="获取首页统一数据")
# async def get_homepage(
#     date: str = Query(..., description="日期 (YYYY-MM-DD 格式)", regex=r"^\d{4}-\d{2}-\d{2}$"),
#     history_number: int = Query(15, description="历史数据天数", ge=0, le=365),
#     future_number: int = Query(14, description="未来数据天数", ge=0, le=365)
# ):
#     """
#     获取首页统一数据（整合三个API调用）
    
#     **功能：**
#     - 一次性返回首页所有组件所需的数据
#     - 整合 activity_summary、dashboard 和 time_overview 三个接口
    
#     **返回数据：**
#     - activity_summary: 活动总结条形图数据
#     - dashboard: 仪表盘数据（top应用、top标题、分类统计）
#     - time_overview: 时间概览图表数据
    
#     **优势：**
#     - 减少网络请求次数（从3次降为1次）
#     - 提高页面加载速度
#     - 优化数据库查询（可复用查询结果）
    
#     **示例：**
#     - `/api/v1/dashboard/homepage?date=2023-10-25&history_number=15&future_number=14`
#     """
#     try:
#         data = dashboard_service.get_homepage_data(date, history_number, future_number)
#         return data
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"获取首页数据失败: {str(e)}")


@router.get("/timeline", response_model=TimelineResponse, summary="获取时间线数据")
async def get_timeline(
    date: str = Query(..., description="日期，格式：YYYY-MM-DD", regex=r"^\d{4}-\d{2}-\d{2}$"),
    device_filter: str = Query('all', description="设备过滤：all/pc/mobile")
):
    """
    获取指定日期的时间线数据
    
    **功能：**
    - 返回指定日期的所有活动事件
    - 支持按设备类型过滤（PC/Mobile/All）
    - 包含事件的详细信息（分类、描述等）
    
    **返回数据：**
    - date: 查询的日期
    - events: 事件列表，包含开始/结束时间（小时浮点数）、分类、描述等
    - currentTime: 当前时间（仅当查询今天时返回）
    
    **时间格式：**
    - 时间以小时浮点数表示，如 9.5 表示 09:30
    
    **示例：**
    - `/api/v1/dashboard/timeline?date=2023-10-25\u0026device_filter=all`
    """
    try:
        # 验证 device_filter 参数
        if device_filter not in ['all', 'pc', 'mobile']:
            raise HTTPException(status_code=400, detail="device_filter 必须是 'all'、'pc' 或 'mobile'")
        
        data = timeline_service.get_timeline_events(date, device_filter)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取时间线数据失败: {str(e)}")


@router.patch("/timeline/events/{event_id}", summary="更新事件分类")
async def update_event_category(
    event_id: str,
    category_id: str = Query(..., description="主分类ID"),
    sub_category_id: Optional[str] = Query(None, description="子分类ID")
):
    """
    更新指定事件的分类信息
    
    **功能：**
    - 更新 user_app_behavior_log 表中的 category_id 和 sub_category_id
    
    **参数：**
    - event_id: 事件ID（路径参数）
    - category_id: 主分类ID（查询参数）
    - sub_category_id: 子分类ID（查询参数，可选）
    
    **返回：**
    - success: 是否成功
    - message: 操作消息
    """
    try:
        success = timeline_service.update_event_category(event_id, category_id, sub_category_id)
        if success:
            return {"success": True, "message": "事件分类更新成功"}
        else:
            raise HTTPException(status_code=404, detail=f"事件 '{event_id}' 未找到")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新事件分类失败: {str(e)}")
