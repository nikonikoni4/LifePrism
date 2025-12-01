"""
行为日志API路由
"""

from fastapi import APIRouter, Query
from datetime import date
from typing import Optional
from lifewatch.server.schemas.behavior import BehaviorLogsResponse, TimelineResponse
from lifewatch.server.services.behavior_service import BehaviorService

router = APIRouter(prefix="/behavior", tags=["Behavior Logs"])
behavior_service = BehaviorService()


@router.get("/logs", response_model=BehaviorLogsResponse, summary="查询行为日志")
async def get_behavior_logs(
    start_time: Optional[str] = Query(
        default=None,
        description="起始时间（格式：YYYY-MM-DD HH:MM:SS）"
    ),
    end_time: Optional[str] = Query(
        default=None,
        description="结束时间（格式：YYYY-MM-DD HH:MM:SS）"
    ),
    app: Optional[str] = Query(
        default=None,
        description="应用名称过滤"
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="页码"
    ),
    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
        description="每页大小"
    )
):
    """
    查询行为日志列表（支持分页和筛选）
    
    **筛选条件**:
    - start_time/end_time: 时间范围
    - app: 指定应用名称
    
    **分页参数**:
    - page: 页码（从1开始）
    - page_size: 每页记录数（1-200）
    
    **当前返回 Mock 数据**
    """
    data = behavior_service.get_behavior_logs(
        start_time=start_time,
        end_time=end_time,
        app=app,
        page=page,
        page_size=page_size
    )
    return data


@router.get("/timeline", response_model=TimelineResponse, summary="获取时间线数据")
async def get_timeline(
    query_date: date = Query(
        default=None,
        alias="date",
        description="查询日期，默认为今天"
    ),
    interval: str = Query(
        default="1h",
        regex="^(1h|30m|15m)$",
        description="时间间隔（1h, 30m, 15m）"
    )
):
    """
    获取指定日期的时间线数据
    
    时间线以指定间隔（1小时、30分钟或15分钟）展示用户行为。
    每个时间槽包含该时段内的所有事件。
    
    **参数**:
    - date: 查询日期
    - interval: 时间间隔
      - 1h: 1小时（适合全天概览）
      - 30m: 30分钟（适合半天详细查看）
      - 15m: 15分钟（适合精细分析）
    
    **当前返回 Mock 数据**
    """
    if query_date is None:
        query_date = date.today()
    
    data = behavior_service.get_timeline(query_date, interval)
    return data
