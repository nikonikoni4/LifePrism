from fastapi import APIRouter, Query, HTTPException
from typing import Literal
import json
from pathlib import Path

from lifeprism.server.schemas.timeline_schemas import (
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
    UserCustomBlockCreate,
    UserCustomBlockUpdate,
    UserCustomBlockResponse,
    UserCustomBlockListResponse,
    TodoDurationResponse,
    BehaviorAnalysisResponse,
)
from lifeprism.server.schemas.todo_schemas import BatchDurationRequest, BatchDurationResponse
from lifeprism.server.services import timeline_service
from lifeprism.repository import timeline_repository

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
    return timeline_service.get_timeline_stats(
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
    return timeline_service.get_timeline_time_overview(
        date=date,
        start_hour=start_hour,
        end_hour=end_hour
    )


# ============================================================================
# UserCustomBlock API 端点
# ============================================================================

@router.post("/custom-blocks", response_model=UserCustomBlockResponse)
async def create_custom_block(data: UserCustomBlockCreate):
    """
    创建用户自定义时间块
    
    在 Timeline 上添加用户手动记录的活动。
    
    - **value**: 活动内容描述
    - **start_time**: 开始时间（ISO格式：YYYY-MM-DDTHH:MM:SS）
    - **end_time**: 结束时间（ISO格式：YYYY-MM-DDTHH:MM:SS）
    - **duration**: 持续时长（分钟）
    - **category_id**: 主分类ID
    - **sub_category_id**: 子分类ID
    
    返回的数据会包含分类名称（category, sub_category）和颜色（color）。
    """
    return timeline_service.create_custom_block(data)


@router.get("/custom-blocks", response_model=UserCustomBlockListResponse)
async def get_custom_blocks(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)")
):
    """
    获取指定日期的所有自定义时间块
    
    - **date**: 查询日期，格式 YYYY-MM-DD
    """
    return timeline_service.get_custom_blocks_by_date(date)


# ============================================================================
# WAID 累计时长查询
# ============================================================================

@router.get("/custom-blocks/duration-by-todo", response_model=TodoDurationResponse,
            summary="查询 todo 累计时长")
async def get_duration_by_todo(
    todo_id: str = Query(..., description="待办事项 ID"),
    date: str = Query(..., description="查询日期（YYYY-MM-DD）")
):
    """查询指定 todo 在指定日期的累计时长（分钟）"""
    duration = timeline_repository.get_duration_by_todo(todo_id, date)
    return TodoDurationResponse(todo_id=todo_id, date=date, duration=duration)


@router.post("/custom-blocks/batch-duration", response_model=BatchDurationResponse,
             summary="批量查询 todo 累计时长")
async def batch_get_duration(request: BatchDurationRequest):
    """批量查询多个 todo 的累计时长。返回 { "data": { "1": 45, "2": 0 } }"""
    result = timeline_repository.batch_get_duration_by_todos(request.todo_ids, request.date)
    return BatchDurationResponse(data=result)


@router.get("/custom-blocks/{block_id}", response_model=UserCustomBlockResponse)
async def get_custom_block(block_id: int):
    """
    获取单条自定义时间块
    
    - **block_id**: 时间块ID
    """
    try:
        return timeline_service.get_custom_block(block_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/custom-blocks/{block_id}", response_model=UserCustomBlockResponse)
async def update_custom_block(block_id: int, data: UserCustomBlockUpdate):
    """
    更新自定义时间块
    
    支持部分更新，只传需要修改的字段。
    
    - **block_id**: 时间块ID
    """
    try:
        return timeline_service.update_custom_block(block_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/custom-blocks/{block_id}")
async def delete_custom_block(block_id: int):
    """
    删除自定义时间块

    - **block_id**: 时间块ID
    """
    success = timeline_service.delete_custom_block(block_id)
    return {"success": success, "message": "Deleted successfully" if success else "Block not found"}


@router.get("/behavior_summary", response_model=BehaviorAnalysisResponse)
async def get_behavior_summary(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)")
):
    """
    获取指定日期的行为分析数据（第一阶段：Mock 数据）

    - **date**: 查询日期，格式 YYYY-MM-DD
    """
    try :
        return timeline_service.get_behavior_analysis(date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
