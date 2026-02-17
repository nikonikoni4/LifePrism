"""
Commitment API - 承诺模块路由
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path

from lifeprism.server.schemas.commitment_schemas import (
    CommitmentItem,
    CommitmentListResponse,
    CreateCommitmentRequest,
    UpdateCommitmentRequest,
)
from lifeprism.server.services import commitment_service

commitment_router = APIRouter(prefix="/commitment", tags=["Commitment"])


@commitment_router.get("/", response_model=CommitmentListResponse, summary="获取承诺列表")
async def get_commitments(
    status: Optional[str] = Query(default=None, description="状态筛选，支持逗号分隔（如 active,archived）"),
    value_id: Optional[str] = Query(default=None, description="按价值 ID 筛选"),
):
    """获取承诺列表，支持状态和价值筛选"""
    try:
        return commitment_service.get_commitments(status, value_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
