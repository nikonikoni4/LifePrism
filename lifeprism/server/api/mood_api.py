"""
Mood API - 心情模块路由

路由分组：心情类型 → 影响因素 → 心情记录
固定路径在参数化路径之前，避免路径冲突。
"""

from fastapi import APIRouter, HTTPException, Path, Query

from lifeprism.server.schemas.mood_schemas import (
    CreateMoodEntryRequest,
    CreateMoodImpactRequest,
    CreateMoodTypeRequest,
    MoodEntryItem,
    MoodEntryListResponse,
    MoodImpactItem,
    MoodImpactListResponse,
    MoodTypeItem,
    MoodTypeListResponse,
    UpdateMoodEntryRequest,
    UpdateMoodTypeRequest,
)
from lifeprism.server.services import mood_service

router = APIRouter(prefix="/mood", tags=["Mood"])


# ==================== 心情类型 ====================


@router.get("/types", response_model=MoodTypeListResponse, summary="获取心情类型列表")
async def get_mood_types():
    """获取所有心情类型（按 sort_order 降序）"""
    return mood_service.get_mood_types()


@router.post("/types", response_model=MoodTypeItem, status_code=201, summary="创建心情类型")
async def create_mood_type(request: CreateMoodTypeRequest):
    result = mood_service.create_mood_type(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建心情类型失败")
    return result


@router.patch("/types/{mood_type_id}", response_model=MoodTypeItem, summary="更新心情类型")
async def update_mood_type(
    request: UpdateMoodTypeRequest,
    mood_type_id: str = Path(..., description="心情类型 ID"),
):
    result = mood_service.update_mood_type(mood_type_id, request)
    if not result:
        raise HTTPException(status_code=404, detail=f"心情类型不存在: {mood_type_id}")
    return result


@router.delete("/types/{mood_type_id}", summary="删除心情类型")
async def delete_mood_type(
    mood_type_id: str = Path(..., description="心情类型 ID"),
):
    try:
        success = mood_service.delete_mood_type(mood_type_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"心情类型不存在: {mood_type_id}")
        return {"message": f"心情类型 {mood_type_id} 已删除"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ==================== 影响因素 ====================


@router.get("/impacts", response_model=MoodImpactListResponse, summary="获取影响因素列表")
async def get_mood_impacts():
    """获取所有影响因素（按 sort_order 降序）"""
    return mood_service.get_mood_impacts()


@router.post("/impacts", response_model=MoodImpactItem, status_code=201, summary="创建影响因素")
async def create_mood_impact(request: CreateMoodImpactRequest):
    try:
        result = mood_service.create_mood_impact(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建影响因素失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/impacts/{impact_id}", summary="删除影响因素")
async def delete_mood_impact(
    impact_id: int = Path(..., description="影响因素 ID"),
):
    success = mood_service.delete_mood_impact(impact_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"影响因素不存在: {impact_id}")
    return {"message": f"影响因素 {impact_id} 已删除"}


# ==================== 心情记录 ====================


@router.get("/entries", response_model=MoodEntryListResponse, summary="获取心情记录列表")
async def get_mood_entries(
    start_date: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
):
    """获取心情记录列表，支持日期范围过滤"""
    return mood_service.get_mood_entries(start_date, end_date)


@router.get("/entries/{entry_id}", response_model=MoodEntryItem, summary="获取单条心情记录")
async def get_mood_entry(
    entry_id: str = Path(..., description="心情记录 ID"),
):
    result = mood_service.get_mood_entry(entry_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"心情记录不存在: {entry_id}")
    return result


@router.post("/entries", response_model=MoodEntryItem, status_code=201, summary="创建心情记录")
async def create_mood_entry(request: CreateMoodEntryRequest):
    try:
        result = mood_service.create_mood_entry(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建心情记录失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/entries/{entry_id}", response_model=MoodEntryItem, summary="更新心情记录")
async def update_mood_entry(
    request: UpdateMoodEntryRequest,
    entry_id: str = Path(..., description="心情记录 ID"),
):
    try:
        result = mood_service.update_mood_entry(entry_id, request)
        if not result:
            raise HTTPException(status_code=404, detail=f"心情记录不存在: {entry_id}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/entries/{entry_id}", summary="删除心情记录")
async def delete_mood_entry(
    entry_id: str = Path(..., description="心情记录 ID"),
):
    success = mood_service.delete_mood_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"心情记录不存在: {entry_id}")
    return {"message": f"心情记录 {entry_id} 已删除"}
