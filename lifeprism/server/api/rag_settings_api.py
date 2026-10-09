"""独立 RAG 设置与安全密钥接口。"""

from typing import Literal

from fastapi import APIRouter, HTTPException

from lifeprism.config.settings_manager import settings
from lifeprism.rag.config import KEYS, RagSettings, RagSettingsPatch, read_settings, validate_update
from lifeprism.rag.service import RagIndexStatus, get_rag_service
from lifeprism.server.schemas.rag_schemas import RagKeyRequest
from lifeprism.server.services.rag_index_service import start_manual_index

router = APIRouter(prefix="/settings/rag", tags=["RAG Settings"])


@router.get("/index", response_model=RagIndexStatus, summary="读取 RAG 索引状态")
async def get_rag_index_status() -> RagIndexStatus:
    """返回上次成功构建时间和运行状态，时间使用 UTC ISO 8601。"""
    result = get_rag_service().index_status()
    options = read_settings(settings)
    result.can_build = (
        settings.run_mode == "full" and options.enabled and options.embedding.configured
    )
    return result


@router.post(
    "/index", response_model=RagIndexStatus, status_code=202, summary="手动更新本地 RAG 索引"
)
async def build_rag_index() -> RagIndexStatus:
    """后台完整构建，只允许正常本地模式；云端同步仍由每日任务负责。"""
    if settings.run_mode != "full":
        raise HTTPException(403, "只有正常本地模式可以手动构建索引")
    await start_manual_index(get_rag_service())
    return await get_rag_index_status()


@router.get("", response_model=RagSettings, summary="读取 RAG 设置")
async def get_rag_settings() -> RagSettings:
    """返回只读模型和密钥配置状态。"""
    return read_settings(settings)


@router.patch("", response_model=RagSettings, summary="修改 RAG 开关和索引目录")
async def update_rag_settings(request: RagSettingsPatch) -> RagSettings:
    """只更新提供的可编辑字段，凭据不足时拒绝开启。"""
    try:
        validate_update(settings, request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    settings.update(
        {f"rag.{key}": value for key, value in request.model_dump(exclude_unset=True).items()}
    )
    return read_settings(settings)


@router.put("/keys/{purpose}", response_model=RagSettings, summary="保存独立 RAG 模型密钥")
async def update_rag_key(
    purpose: Literal["embedding", "rerank"], request: RagKeyRequest
) -> RagSettings:
    """密钥只写安全存储，清除时同时关闭对应功能。"""
    key = request.api_key.strip()
    if key:
        settings.set_storage_key(KEYS[purpose], key)
        if settings.get_storage_key(KEYS[purpose]) != key:
            raise HTTPException(500, "密钥保存失败")
    else:
        settings.delete_storage_key(KEYS[purpose])
        settings.set("rag.enabled" if purpose == "embedding" else "rag.rerank_enabled", False)
    return read_settings(settings)
