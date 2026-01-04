"""
Being API - 时间悖论测试接口

提供过去/现在/未来自我探索测试的 RESTful API
"""
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, Query, HTTPException, Path
from pydantic import BaseModel, Field

from lifeprism.server.services import being_service
from lifeprism.utils import get_logger
from lifeprism.server.schemas.being_schemas import (
    BeingTestContent,
    BeingTestResponse,
    VersionListResponse,
    SuccessResponse
)
logger = get_logger(__name__)

router = APIRouter(prefix="/being", tags=["Being"])




# ==================== 查询接口 ====================

@router.get(
    "/{mode}",
    response_model=BeingTestResponse,
    summary="获取最新版本测试"
)
def get_latest_test(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    获取用户指定模式下的最新版本测试结果
    
    - **mode**: 测试模式 (past/present/future)
    - **user_id**: 用户 ID，默认为 1
    """
    result = being_service.get_test_result(user_id, mode)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到 {mode} 模式的测试记录")
    return result


@router.get(
    "/{mode}/versions",
    response_model=VersionListResponse,
    summary="获取所有版本列表"
)
def get_versions(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    获取用户指定模式下的所有版本列表
    
    返回简要信息，不包含完整测试内容
    """
    versions = being_service.get_version_list(user_id, mode)
    return VersionListResponse(mode=mode, versions=versions)


@router.get(
    "/{mode}/{version}",
    response_model=BeingTestResponse,
    summary="获取指定版本测试"
)
def get_test_by_version(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    version: int = Path(..., description="版本号"),
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    获取用户指定模式和版本的测试结果
    """
    result = being_service.get_test_result(user_id, mode, version)
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"未找到 {mode} 模式版本 {version} 的测试记录"
        )
    return result


# ==================== 创建/更新接口 ====================

@router.post(
    "/{mode}",
    response_model=BeingTestResponse,
    summary="创建新版本测试"
)
def create_test(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    body: BeingTestContent = None,
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    创建新版本的测试记录
    
    版本号自动递增
    """
    result = being_service.save_test_result(user_id, mode, body.content)
    if not result:
        raise HTTPException(status_code=500, detail="创建测试记录失败")
    return result


@router.put(
    "/{mode}/{version}",
    response_model=SuccessResponse,
    summary="更新指定版本测试"
)
def update_test(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    version: int = Path(..., description="版本号"),
    body: BeingTestContent = None,
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    更新指定版本的测试内容
    """
    success = being_service.update_test_result(user_id, mode, version, body.content)
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"更新失败，未找到 {mode} 模式版本 {version} 的记录"
        )
    return SuccessResponse(success=True, message="更新成功")


# ==================== 删除接口 ====================

@router.delete(
    "/{mode}/{version}",
    response_model=SuccessResponse,
    summary="删除指定版本测试"
)
def delete_test(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    version: int = Path(..., description="版本号"),
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    删除指定版本的测试记录
    """
    success = being_service.delete_test_result(user_id, mode, version)
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"删除失败，未找到 {mode} 模式版本 {version} 的记录"
        )
    return SuccessResponse(success=True, message="删除成功")


# ==================== AI 总结接口（预留） ====================

@router.post(
    "/{mode}/{version}/ai-abstract",
    response_model=SuccessResponse,
    summary="生成 AI 总结"
)
def generate_ai_abstract(
    mode: Literal["past", "present", "future"] = Path(..., description="模式"),
    version: int = Path(..., description="版本号"),
    user_id: int = Query(default=1, description="用户 ID")
):
    """
    为指定版本的测试内容生成 AI 总结
    
    注意：此功能待接入 LLM 后实现
    """
    result = being_service.generate_ai_abstract(user_id, mode, version)
    if result is None:
        raise HTTPException(status_code=501, detail="AI 总结功能待实现")
    return SuccessResponse(success=True, message="AI 总结生成成功")
