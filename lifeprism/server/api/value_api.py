"""
Value API - 价值模块路由
"""
from fastapi import APIRouter, Query, HTTPException, Path

from lifeprism.server.schemas.value_schemas import (
    ValueItem,
    ValueDetailItem,
    ValueListResponse,
    CreateValueRequest,
    UpdateValueRequest,
)
from lifeprism.server.services import value_service
from lifeprism.utils.exceptions import LWBaseError, ConflictError
from lifeprism.utils import get_logger

logger = get_logger(__name__)

value_router = APIRouter(prefix="/value", tags=["Value"])


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
    try:
        result = value_service.create_value(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建价值失败")
        return result
    except ConflictError:
        raise
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("创建价值失败: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


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
    cascade: bool = Query(
        default=False,
        description=(
            "级联策略。"
            "True: 级联删除该价值下所有承诺；"
            "False（默认）: 保留承诺但将其 value_id 置为 NULL（成为无主承诺）"
        ),
    ),
):
    success = value_service.delete_value(value_id, cascade)
    if not success:
        raise HTTPException(status_code=404, detail=f"价值不存在: {value_id}")
    return {"message": f"价值 {value_id} 已删除"}
