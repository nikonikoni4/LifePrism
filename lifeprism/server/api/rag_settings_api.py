"""独立 RAG 设置与安全密钥接口。"""

from typing import Literal

from fastapi import APIRouter, HTTPException

from lifeprism.config.settings_manager import settings
from lifeprism.rag.config import KEYS, RagSettings, RagSettingsPatch, read_settings, validate_update
from lifeprism.server.schemas.rag_schemas import RagKeyRequest

router = APIRouter(prefix="/settings/rag", tags=["RAG Settings"])


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
