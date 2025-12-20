"""
Timeline V2 API - 缩略图统计

提供 Timeline 缩略图统计和时间块详情的 API 端点
"""

from fastapi import APIRouter, Query
from typing import Literal

from lifewatch.server.schemas.timeline_v2_schemas import (
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
)
from lifewatch.server.services import timeline_v2_service

router = APIRouter(prefix="/timeline", tags=["Timeline V2"])


@router.get("/stats", response_model=TimelineStatsResponse)
async def get_timeline_stats(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)"),
    hour_granularity: int = Query(1, ge=1, le=6, description="时间粒度（1-6 小时）"),
    category_level: Literal["main", "sub"] = Query("main", description="分类级别")
):
    """
    获取缩略图 Timeline 统计数据
    
    返回按时间块聚合的分类统计，用于前端渲染缩略图视图。
    
    - **date**: 查询日期，格式 YYYY-MM-DD
    - **hour_granularity**: 时间粒度，1/2/3/4/6 小时
    - **category_level**: 分类级别，main=主分类，sub=子分类
    """
    return timeline_v2_service.get_timeline_stats(
        date=date,
        hour_granularity=hour_granularity,
        category_level=category_level
    )


@router.get("/overview", response_model=TimelineTimeOverviewResponse)
async def get_timeline_overview(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)"),
    start_hour: int = Query(..., ge=0, le=23, description="开始小时（0-23）"),
    end_hour: int = Query(..., ge=1, le=24, description="结束小时（1-24）")
):
    """
    获取指定时间块的 Time Overview 详情
    
    点击缩略图时间块后，获取该时间范围内的详细活动分布。
    
    - **date**: 查询日期，格式 YYYY-MM-DD
    - **start_hour**: 时间块开始小时（0-23）
    - **end_hour**: 时间块结束小时（1-24）
    """
    return timeline_v2_service.get_timeline_time_overview(
        date=date,
        start_hour=start_hour,
        end_hour=end_hour
    )
