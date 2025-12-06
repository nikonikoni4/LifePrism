"""
Timeline API 路由
独立的时间线相关 API 端点
"""

from fastapi import APIRouter, Query, HTTPException
from lifewatch.server.services.timeline_service import TimelineService
from lifewatch.server.schemas.timeline_schemas import TimelineResponse, TimelineOverviewResponse

router = APIRouter(prefix="/timeline", tags=["Timeline"])
timeline_service = TimelineService()


@router.get("", response_model=TimelineResponse, summary="获取时间线事件数据")
async def get_timeline(
    date: str = Query(..., description="日期 (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    device_filter: str = Query(..., description="设备过滤：all/pc/mobile")
):
    """
    获取指定日期的时间线数据
    
    **功能：**
    - 返回指定日期的所有活动事件
    - 支持按设备类型过滤（PC/Mobile/All）
    - 包含事件的详细信息（分类、描述等）
    
    **时间格式：**
    - 时间以小时浮点数表示，如 9.5 表示 09:30
    """
    try:
        if device_filter not in ['all', 'pc', 'mobile']:
            raise HTTPException(status_code=400, detail="device_filter 必须是 'all'、'pc' 或 'mobile'")
        
        data = timeline_service.get_timeline_events(date, device_filter)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取时间线数据失败: {str(e)}")


@router.get("/overview", response_model=TimelineOverviewResponse, summary="获取指定时间范围的 Overview 数据")
async def get_timeline_overview(
    date: str = Query(..., description="日期 (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    start_hour: float = Query(..., description="开始小时 (浮点数，如 12.5 = 12:30)", ge=0, le=24),
    end_hour: float = Query(..., description="结束小时 (浮点数)", ge=0, le=24)
):
    """
    获取指定时间范围的 Overview 数据
    
    **功能：**
    - 返回指定时间范围内的分类统计数据
    - 包含饼图数据（Sunburst）和柱状图数据（6 个固定刻度）
    - 支持下钻到子分类
    
    **参数示例：**
    - `start_hour=12` 表示 12:00
    - `start_hour=12.5` 表示 12:30
    - `end_hour=13` 表示 13:00
    
    **柱状图刻度：**
    - 固定 6 个刻度，按时间范围均分
    - 例如 12:00-13:00 会显示 12:00, 12:10, 12:20, 12:30, 12:40, 12:50
    """
    try:
        if start_hour >= end_hour:
            raise HTTPException(status_code=400, detail="start_hour 必须小于 end_hour")
        
        data = timeline_service.get_timeline_overview(date, start_hour, end_hour)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Timeline Overview 失败: {str(e)}")
