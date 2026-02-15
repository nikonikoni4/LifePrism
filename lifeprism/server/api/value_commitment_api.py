"""
Value & Commitment API - 承诺与价值模块路由

两个 router 放同一文件，模块紧密关联。
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path

from lifeprism.server.schemas.value_schemas import (
    ValueItem,
    ValueDetailItem,
    ValueListResponse,
    CreateValueRequest,
    UpdateValueRequest,
    CommitmentItem,
    CommitmentListResponse,
    CreateCommitmentRequest,
    UpdateCommitmentRequest,
)
from lifeprism.server.services import value_service, commitment_service

value_router = APIRouter(prefix="/value", tags=["Value"])
commitment_router = APIRouter(prefix="/commitment", tags=["Commitment"])


# ==================== Value 端点 ====================

@value_router.get("/", response_model=ValueListResponse, summary="获取价值列表")
async def get_values():
    """获取所有价值（按 sort_order 降序）"""
    return value_service.get_values()


@value_router.get("/{value_id}", response_model=ValueDetailItem, summary="获取价值详情")
async def get_value_detail(
    value_id: str = Path(..., description="价值 ID (格式: val-xxx)"),
):
    result = value_service.get_value_detail(value_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"价值不存在: {value_id}")
    return result


@value_router.post("/", response_model=ValueItem, status_code=201, summary="创建价值")
async def create_value(request: CreateValueRequest):
    result = value_service.create_value(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建价值失败")
    return result


@value_router.patch("/{value_id}", response_model=ValueItem, summary="更新价值")
async def update_value(
    request: UpdateValueRequest,
    value_id: str = Path(..., description="价值 ID (格式: val-xxx)"),
):
    result = value_service.update_value(value_id, request)
    if not result:
        raise HTTPException(status_code=404, detail=f"价值不存在: {value_id}")
    return result


@value_router.delete("/{value_id}", summary="删除价值")
async def delete_value(
    value_id: str = Path(..., description="价值 ID (格式: val-xxx)"),
    cascade: bool = Query(default=False, description="True=级联删除承诺，False=置空关联"),
):
    success = value_service.delete_value(value_id, cascade)
    if not success:
        raise HTTPException(status_code=404, detail=f"价值不存在: {value_id}")
    return {"message": f"价值 {value_id} 已删除"}


# ==================== Commitment 端点 ====================

@commitment_router.get("/", response_model=CommitmentListResponse, summary="获取承诺列表")
async def get_commitments(
    status: Optional[str] = Query(default=None, description="状态筛选，支持逗号分隔（如 active,archived）"),
    value_id: Optional[str] = Query(default=None, description="按价值 ID 筛选"),
):
    """获取承诺列表，支持状态和价值筛选"""
    return commitment_service.get_commitments(status, value_id)


@commitment_router.get("/{commitment_id}", response_model=CommitmentItem, summary="获取承诺详情")
async def get_commitment_detail(
    commitment_id: str = Path(..., description="承诺 ID (格式: cmt-xxx)"),
):
    result = commitment_service.get_commitment_detail(commitment_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"承诺不存在: {commitment_id}")
    return result


@commitment_router.post("/", response_model=CommitmentItem, status_code=201, summary="创建承诺")
async def create_commitment(request: CreateCommitmentRequest):
    try:
        result = commitment_service.create_commitment(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建承诺失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@commitment_router.patch("/{commitment_id}", response_model=CommitmentItem, summary="更新承诺")
async def update_commitment(
    request: UpdateCommitmentRequest,
    commitment_id: str = Path(..., description="承诺 ID (格式: cmt-xxx)"),
):
    try:
        result = commitment_service.update_commitment(commitment_id, request)
        if not result:
            raise HTTPException(status_code=404, detail=f"承诺不存在: {commitment_id}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@commitment_router.delete("/{commitment_id}", summary="删除承诺")
async def delete_commitment(
    commitment_id: str = Path(..., description="承诺 ID (格式: cmt-xxx)"),
):
    success = commitment_service.delete_commitment(commitment_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"承诺不存在: {commitment_id}")
    return {"message": f"承诺 {commitment_id} 已删除"}

