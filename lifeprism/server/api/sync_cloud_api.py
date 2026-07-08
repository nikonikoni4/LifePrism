"""
云端数据同步 API 路由

提供 Pull + Push 双向同步的 REST API 端点：
- POST /api/sync/pull: 从云端拉取增量数据
- POST /api/sync/push: 推送本地变更到云端

API 层不直接编写 SQL，所有数据库操作通过 SyncRepository。
API 层不使用 try/except，异常自然冒泡到全局异常处理器。

认证方式：Authorization: Bearer {api_key} HTTP Header
"""

import secrets
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from lifeprism.repository.sync_repository import SyncRepository
from lifeprism.sync.sync_config import get_sync_api_key
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sync", tags=["Sync Cloud"])

# 创建 SyncRepository 单例
sync_repository = SyncRepository()


# ==================== 请求/响应模型 ====================


class SyncPullRequest(BaseModel):
    """拉取同步数据请求"""

    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")
    tables: list[str] = Field(..., description="需要拉取的表名列表")


class SyncPushRequest(BaseModel):
    """推送同步数据请求"""

    changes: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict, description="变更数据，key 为表名，value 为行列表"
    )


# ==================== 认证依赖 ====================


def verify_sync_api_key(authorization: str | None = Header(default=None)) -> None:
    """验证同步 API Key（FastAPI 依赖）

    从 Authorization: Bearer {key} Header 读取 API Key，
    使用 sync_config.get_sync_api_key() 获取期望的 Key，
    使用 secrets.compare_digest() 进行常量时间比较（防时序攻击）。

    Raises:
        ValidationError: API Key 无效时抛出（code=INVALID_SYNC_API_KEY）
    """
    expected_key = get_sync_api_key()
    if not expected_key:
        raise ValidationError(
            message="无效的同步 API Key",
            code="INVALID_SYNC_API_KEY",
        )

    # 解析 Authorization Header
    if not authorization or not authorization.startswith("Bearer "):
        raise ValidationError(
            message="无效的同步 API Key",
            code="INVALID_SYNC_API_KEY",
        )

    provided_key = authorization[7:]  # 去掉 "Bearer " 前缀

    if not secrets.compare_digest(provided_key, expected_key):
        raise ValidationError(
            message="无效的同步 API Key",
            code="INVALID_SYNC_API_KEY",
        )


# ==================== API 端点 ====================


@router.post("/pull", summary="从云端拉取增量数据")
async def sync_pull(request: SyncPullRequest, _: None = Depends(verify_sync_api_key)):
    """从云端拉取增量数据

    对每个请求的表执行增量查询（updated_at > last_sync_time），
    返回所有变更记录。

    **请求参数**:
    - last_sync_time: 上次同步时间
    - tables: 需要拉取的表名列表

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - changes: {table_name: [rows]} 变更数据
    - sync_time: 本次同步时间
    """
    logger.info(
        "同步 Pull 请求开始: last_sync_time=%s, tables=%s",
        request.last_sync_time,
        request.tables,
    )
    start_time = time.perf_counter()

    # 对每个表执行增量查询
    changes: dict[str, list[dict[str, Any]]] = {}
    for table_name in request.tables:
        rows = sync_repository.query_incremental(table_name, request.last_sync_time)
        if rows:
            changes[table_name] = rows

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    record_counts = {table: len(rows) for table, rows in changes.items()}
    logger.info(
        "同步 Pull 完成: 记录数=%s, 耗时=%.2fms",
        record_counts,
        elapsed_ms,
    )

    return {
        "changes": changes,
        "sync_time": datetime.now().isoformat(),
    }


@router.post("/push", summary="推送本地变更到云端")
async def sync_push(request: SyncPushRequest, _: None = Depends(verify_sync_api_key)):
    """推送本地变更到云端

    对每个表执行带 LWW 冲突解决的批量写入。
    如果本地记录的 updated_at 大于传入记录的 updated_at，
    则跳过该行（Last-Write-Wins）。

    **请求参数**:
    - changes: {table_name: [rows]} 变更数据

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - status: 同步状态（"ok"）
    - sync_time: 本次同步时间
    """
    record_counts = {table: len(rows) for table, rows in request.changes.items()}
    logger.info("同步 Push 请求开始: 记录数=%s", record_counts)
    start_time = time.perf_counter()

    # 对每个表执行带 LWW 的批量写入
    for table_name, rows in request.changes.items():
        sync_repository.upsert_rows_with_lww(table_name, rows)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("同步 Push 完成: 耗时=%.2fms", elapsed_ms)

    return {
        "status": "ok",
        "sync_time": datetime.now().isoformat(),
    }
