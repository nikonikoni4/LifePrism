from fastapi import APIRouter

from lifeprism.server.schemas.system_schemas import SystemWarningsResponse
from lifeprism.server.services import system_service

router = APIRouter(prefix="/system", tags=["System - 系统信息"])


@router.get("/warnings", response_model=SystemWarningsResponse, summary="获取系统警告列表")
async def get_warnings():
    """获取系统警告列表"""
    return SystemWarningsResponse(warnings=system_service.get_warnings())
