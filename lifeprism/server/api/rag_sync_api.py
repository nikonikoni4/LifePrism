"""云端接收完整 RAG 索引；认证、限量、暂存后校验发布。"""

import asyncio
import base64
import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from lifeprism.config.settings_manager import settings
from lifeprism.rag.service import MAX_INDEX_BYTES, IndexManifest, get_rag_service
from lifeprism.server.api.sync_cloud_api import verify_sync_api_key

router = APIRouter(
    prefix="/api/sync/rag-index", tags=["RAG Sync"], dependencies=[Depends(verify_sync_api_key)]
)


@router.post("", summary="接收本地 RAG 索引并原子发布")
async def receive_index(request: Request) -> dict:
    """仅云端接收，文件由服务端命名，验证失败保留旧索引。"""
    if settings.run_mode != "agent_only":
        raise HTTPException(403, "仅云端 agent_only 模式接收 RAG 索引")
    encoded = request.headers.get("X-RAG-Manifest", "")
    if len(encoded) > 8192:
        raise HTTPException(422, "索引 manifest 过大")
    try:
        manifest = IndexManifest.model_validate_json(base64.b64decode(encoded, validate=True))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, "索引 manifest 无效") from exc
    service = get_rag_service()
    service.root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="upload-", dir=service.root) as workspace:
        target = Path(workspace) / "index.db"
        size = 0
        with target.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > min(MAX_INDEX_BYTES, manifest.size):
                    raise HTTPException(413, "索引超过允许大小")
                await asyncio.to_thread(handle.write, chunk)
        try:
            await asyncio.to_thread(service.install, target, manifest)
        except (ValueError, sqlite3.DatabaseError) as exc:
            raise HTTPException(422, "RAG 索引校验失败") from exc
    return {"version": manifest.version, "sha256": manifest.sha256}


@router.get("", summary="读取当前云端索引版本")
async def get_index_manifest() -> dict:
    """用于同步诊断，不返回模型凭据。"""
    if settings.run_mode != "agent_only":
        raise HTTPException(403, "仅云端 agent_only 模式支持此接口")
    manifest = get_rag_service().current()
    return {"manifest": manifest.model_dump(mode="json") if manifest else None}
