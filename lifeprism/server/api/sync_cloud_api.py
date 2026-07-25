"""
云端数据同步 API 路由

提供 Pull + Push 双向同步的 REST API 端点：
- GET  /api/sync/health: 健康检查（无需认证）
- POST /api/sync/pull: 从云端拉取增量数据（同时更新心跳）
- POST /api/sync/push: 推送本地变更到云端
- POST /api/sync/heartbeat: 接收本地心跳/生命周期事件
- POST /api/sync/pull-files: 从云端拉取增量文件
- POST /api/sync/push-files: 推送本地文件到云端

API 层不直接编写 SQL，所有数据库操作通过 SyncRepository。
API 层不使用 try/except，异常自然冒泡到全局异常处理器。

认证方式：Authorization: Bearer {api_key} HTTP Header
"""

import base64
import contextlib
import gzip
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from lifeprism.config.settings_manager import settings
from lifeprism.repository import (
    SyncRepository,
    deletion_log_repository,
    file_sync_state_repository,
)
from lifeprism.sync.constants import EXCLUDED_FILENAMES as _EXCLUDED_FILENAMES
from lifeprism.sync.constants import SYNC_DIRECTORIES, SYNC_TABLES, safe_gzip_decompress
from lifeprism.sync.hash_utils import compute_file_hash
from lifeprism.sync.sync_config import get_sync_api_key
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError, ValidationError
from lifeprism.utils.time_utils import parse_iso_to_aware

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sync", tags=["Sync Cloud"])

# 创建 SyncRepository 单例
sync_repository = SyncRepository()


# ==================== 请求/响应模型 ====================


class SyncPullRequest(BaseModel):
    """拉取同步数据请求"""

    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")
    tables: list[str] = Field(..., description="需要拉取的表名列表")
    offset: int = Field(default=0, ge=0, description="分页偏移量")
    limit: int | None = Field(default=None, gt=0, description="每页记录数（None 表示不分页）")


class SyncPushRequest(BaseModel):
    """推送同步数据请求"""

    changes: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict, description="变更数据，key 为表名，value 为行列表"
    )


class SyncPullFilesRequest(BaseModel):
    """文件拉取请求"""

    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")
    directories: list[str] = Field(..., description="需要拉取的目录列表")


class FilePushItem(BaseModel):
    """单个文件推送项"""

    path: str = Field(..., description="相对 lifeprism_data_path 的路径")
    content: str = Field(..., description="gzip 压缩 + base64 编码的内容")
    parent_hash: str | None = Field(
        default=None, description="推送方的 parent_hash（仅用于判断是否新文件，不覆盖云端值）"
    )
    current_hash: str = Field(..., description="推送方的 current_hash")


class SyncPushFilesRequest(BaseModel):
    """文件推送请求"""

    files: list[FilePushItem] = Field(..., description="待推送的文件列表")


class SyncPullFilesCheckRequest(BaseModel):
    """文件同步 check 请求（Phase 1：快照交换）"""

    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")
    directories: list[str] = Field(..., description="需要检查的目录列表")


class SyncPullFilesPathsRequest(BaseModel):
    """文件同步 fetch / verify / commit 请求（按路径列表操作）"""

    paths: list[str] = Field(..., description="文件相对路径列表（相对 lifeprism_data_path）")


class HeartbeatRequest(BaseModel):
    """心跳请求"""

    event: str = Field(..., description="事件类型（online/offline/ping）")


class SyncPullDeletionLogRequest(BaseModel):
    """墓碑拉取请求"""

    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")


class SyncPushDeletionLogRequest(BaseModel):
    """墓碑推送请求"""

    tombstones: list[dict[str, Any]] = Field(
        ..., description="待推送的墓碑列表（每条含 target_table/record_id/created_at）"
    )


class SyncCleanupDeletionLogRequest(BaseModel):
    """墓碑清理请求"""

    last_sync_time: str = Field(..., description="上次同步时间（ISO 8601 格式）")


class DynamicTableFieldDef(BaseModel):
    """动态表字段定义"""

    field_key: str = Field(..., description="字段 key（^[a-z][a-z0-9_]*$）")
    field_type: str = Field(default="text", description="字段类型（text/integer/float）")


class DynamicTypeDef(BaseModel):
    """动态表类型定义"""

    slug: str = Field(..., description="类型 slug（^[a-z][a-z0-9_]*$）")
    fields: list[DynamicTableFieldDef] = Field(..., description="字段定义列表")


class RebuildDynamicTablesRequest(BaseModel):
    """重建动态表请求"""

    types: list[DynamicTypeDef] = Field(
        ..., description="自定义记录类型定义列表（含 slug 和 fields）"
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


@router.get("/health", summary="健康检查")
def health_check():
    """健康检查端点（无需认证）

    用于测试云端服务连通性，直接返回服务状态。

    **响应**:
    - status: 服务状态
    - mode: 运行模式
    """
    return {
        "status": "ok",
        "mode": "agent-only",
    }


@router.post("/pull", summary="从云端拉取增量数据")
def sync_pull(request: SyncPullRequest, _: None = Depends(verify_sync_api_key)):
    """从云端拉取增量数据

    对每个请求的表执行增量查询（updated_at > last_sync_time），
    返回所有变更记录。支持 offset / limit 分页参数。

    **请求参数**:
    - last_sync_time: 上次同步时间
    - tables: 需要拉取的表名列表
    - offset: 分页偏移量（默认 0）
    - limit: 每页记录数（None 表示不分页）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - changes: {table_name: [rows]} 变更数据
    - sync_time: 本次同步时间
    """
    # 第一步：更新心跳（必须在请求开头，确保实时生效）
    from lifeprism.sync.heartbeat_manager import heartbeat_manager

    heartbeat_manager.update_heartbeat()

    logger.debug(
        "同步 Pull 请求开始: last_sync_time=%s, tables=%s, offset=%d, limit=%s",
        request.last_sync_time,
        request.tables,
        request.offset,
        request.limit,
    )
    start_time = time.perf_counter()

    # 对每个表执行增量查询（支持分页）
    changes: dict[str, list[dict[str, Any]]] = {}
    for table_name in request.tables:
        rows = sync_repository.query_incremental(
            table_name,
            request.last_sync_time,
            offset=request.offset,
            limit=request.limit,
        )
        if rows:
            changes[table_name] = rows

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    record_counts = {table: len(rows) for table, rows in changes.items()}
    if changes:
        logger.info(
            "同步 Pull 完成: 记录数=%s, 耗时=%.2fms",
            record_counts,
            elapsed_ms,
        )
    else:
        logger.debug(
            "同步 Pull 完成: 无新记录, 耗时=%.2fms",
            elapsed_ms,
        )

    return {
        "changes": changes,
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/push", summary="推送本地变更到云端")
def sync_push(request: SyncPushRequest, _: None = Depends(verify_sync_api_key)):
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
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/pull-deletion-log", summary="拉取云端墓碑列表")
def sync_pull_deletion_log(
    request: SyncPullDeletionLogRequest,
    _: None = Depends(verify_sync_api_key),
):
    """拉取云端 created_at > last_sync_time 的墓碑列表

    供本地 _pull_deletion_log 调用，获取云端新增的墓碑，
    在本地事务内执行 LWW 检查 + DELETE + 写本地副本。

    **请求参数**:
    - last_sync_time: 上次同步时间（ISO 8601 格式，空字符串表示全量）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - tombstones: [{id, target_table, record_id, source, created_at, updated_at}] 墓碑列表
    """
    tombstones = deletion_log_repository.get_tombstones_since(request.last_sync_time)
    logger.info("墓碑 Pull: 返回 %d 条墓碑", len(tombstones))
    return {"tombstones": tombstones}


@router.post("/push-deletion-log", summary="推送本地墓碑到云端")
def sync_push_deletion_log(
    request: SyncPushDeletionLogRequest,
    _: None = Depends(verify_sync_api_key),
):
    """云端对每条墓碑（单事务）：存在性检查 + DELETE + 写副本

    每条墓碑独立事务处理，单条失败不影响已应用的墓碑，
    但会立即 raise 终止后续墓碑处理（由调用方决定是否重试）。

    **请求参数**:
    - tombstones: 待推送的墓碑列表（每条含 target_table/record_id/created_at）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - success: True
    - applied_count: 成功应用的墓碑数
    - skipped_count: 因已存在跳过的墓碑数（INSERT OR IGNORE 存在性检查）
    """
    applied_count = 0
    skipped_count = 0
    for t in request.tombstones:
        target_table = t["target_table"]
        record_id = t["record_id"]
        original_created_at = t["created_at"]
        # 每条墓碑独立事务：try/except 仅用于事务 rollback（资源清理），
        # 异常 re-raise 由全局异常处理器统一转换（符合 API 层规范）
        with sync_repository.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # a. 存在性检查：云端已有同 (target_table, record_id) 则跳过
                existing = deletion_log_repository.get_tombstone_with_cursor(
                    cursor, target_table, record_id
                )
                if existing is not None:
                    skipped_count += 1
                    continue
                # b. 执行 DELETE（不写墓碑）
                sync_repository.execute_tombstone_delete_with_cursor(
                    cursor, target_table, record_id
                )
                # c. 写云端副本（source=cloud，保留原 created_at）
                deletion_log_repository.create_tombstone_with_cursor(
                    cursor,
                    target_table,
                    record_id,
                    source="cloud",
                    created_at=original_created_at,
                )
                conn.commit()
                applied_count += 1
            except Exception:
                conn.rollback()
                logger.error(
                    "push-deletion-log 处理墓碑失败: target_table=%s, record_id=%s",
                    target_table,
                    record_id,
                )
                raise
    logger.info(
        "墓碑 Push: 共 %d 条, 应用 %d, 跳过 %d",
        len(request.tombstones),
        applied_count,
        skipped_count,
    )
    return {
        "success": True,
        "applied_count": applied_count,
        "skipped_count": skipped_count,
    }


@router.post("/cleanup-deletion-log", summary="清理云端过期墓碑")
def sync_cleanup_deletion_log(
    request: SyncCleanupDeletionLogRequest,
    _: None = Depends(verify_sync_api_key),
):
    """清理云端 created_at <= last_sync_time 的墓碑记录

    供本地 sync_once 在两端都已应用所有墓碑后调用，
    清理已传播完成的墓碑避免无限累积。

    **请求参数**:
    - last_sync_time: 上次同步时间（ISO 8601 格式）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - success: True
    - cleaned_count: 已清理的墓碑数
    """
    cleaned_count = deletion_log_repository.cleanup_before(request.last_sync_time)
    logger.info("墓碑 Cleanup: 清理 %d 条墓碑", cleaned_count)
    return {"success": True, "cleaned_count": cleaned_count}


@router.get("/dynamic-tables-definitions", summary="查询云端动态表定义（types + fields）")
def sync_get_dynamic_tables_definitions(
    _: None = Depends(verify_sync_api_key),
):
    """查询云端动态表定义（两张 meta 表的完整内容）

    本地在 pull 之前调用此端点拉取云端动态表定义，用于本地 slug 集合对比，
    触发双向建表（本地新增云端缺失的表 + 云端新增本地缺失的表）。

    参考 ADR: docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - types: [{slug, fields: [{field_key, field_type}]}] 云端动态表类型定义列表
    """
    types = sync_repository.get_custom_record_types_full_definitions()
    logger.info("查询云端动态表定义: types=%d", len(types))
    return {
        "types": types,
    }


@router.post("/rebuild-dynamic-tables", summary="根据本地定义重建云端动态表")
def sync_rebuild_dynamic_tables(
    request: RebuildDynamicTablesRequest,
    _: None = Depends(verify_sync_api_key),
):
    """根据本地发送的自定义记录类型定义，在云端创建/更新动态表

    在 pull 之前，由 _sync_dynamic_tables_definitions 检测到本地有云端没有的 slug 时调用。
    云端根据最新的 type + fields 定义：
    - 新增 type → CREATE TABLE
    - 已有 type 缺字段 → ALTER TABLE ADD COLUMN（只增不删）
    - 已有 type 且字段齐全 → skipped

    注意：不删除任何表——删除同步需要独立的 tombstone 机制。

    幂等操作：重复调用不会产生副作用。

    **请求参数**:
    - types: 自定义记录类型定义列表

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - rebuilt: [{slug, action}] 每个类型的处理结果（created/altered/skipped）
    - sync_time: 本次同步时间
    """
    logger.info("重建动态表请求开始: types=%d", len(request.types))
    start_time = time.perf_counter()

    # 将 Pydantic 模型转为普通 dict 供 Repository 层处理
    types_data = [
        {
            "slug": t.slug,
            "fields": [{"field_key": f.field_key, "field_type": f.field_type} for f in t.fields],
        }
        for t in request.types
    ]

    rebuilt = sync_repository.rebuild_dynamic_tables(types_data)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("重建动态表完成: results=%s, 耗时=%.2fms", rebuilt, elapsed_ms)

    return {
        "rebuilt": rebuilt,
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/heartbeat", summary="接收本地心跳/生命周期事件")
async def sync_heartbeat(
    request: HeartbeatRequest,
    _: None = Depends(verify_sync_api_key),
):
    """接收本地心跳/生命周期事件

    事件类型:
    - online: 本地启动（set_event）
    - offline: 本地关闭（set_event）
    - ping: 心跳（update_heartbeat）

    **请求参数**:
    - event: 事件类型（online/offline/ping）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - status: 状态（"ok"）
    - server_time: 服务器时间
    """
    from lifeprism.sync.heartbeat_manager import heartbeat_manager

    if request.event in ("online", "offline"):
        heartbeat_manager.set_event(request.event)
        logger.info("收到生命周期事件: event=%s", request.event)
    elif request.event == "ping":
        heartbeat_manager.update_heartbeat()
        logger.debug("收到心跳 ping")
    else:
        raise ValidationError(
            message=f"无效的事件类型: {request.event}",
            code="INVALID_HEARTBEAT_EVENT",
        )

    return {
        "status": "ok",
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# ==================== 文件同步端点 ====================


def _is_path_safe(path: Path, base: Path) -> bool:
    """检查路径是否在 base 目录内（防止路径遍历攻击）

    Args:
        path: 待检查的路径（已 resolve）
        base: 基准目录（已 resolve）

    Returns:
        bool: 路径在 base 目录内返回 True
    """
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _encode_file(file_path: Path, data_path: Path) -> dict[str, str]:
    """将单个文件编码为同步响应项（gzip 压缩 + base64 编码）

    Args:
        file_path: 文件绝对路径
        data_path: 数据根目录（用于计算相对路径）

    Returns:
        dict: 包含 path、content、mtime 三个字段的字典
    """
    content_bytes = file_path.read_bytes()
    compressed = gzip.compress(content_bytes)
    encoded = base64.b64encode(compressed).decode("ascii")
    rel_path = str(file_path.relative_to(data_path)).replace("\\", "/")
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
    return {
        "path": rel_path,
        "content": encoded,
        "mtime": mtime.isoformat(),
    }


def _build_file_hash_state(file_path: Path, data_path: Path) -> dict[str, Any]:
    """构建文件的 hash 状态项（path + parent_hash + current_hash）

    实时计算 current_hash（调用 compute_file_hash），从 file_sync_state 表读 parent_hash。

    Args:
        file_path: 文件绝对路径
        data_path: 数据根目录（用于计算相对路径）

    Returns:
        dict: 包含 path、parent_hash、current_hash 三个字段的字典
    """
    rel_path = str(file_path.relative_to(data_path)).replace("\\", "/")
    content_bytes = file_path.read_bytes()
    current_hash = compute_file_hash(content_bytes)
    state = file_sync_state_repository.get_state(rel_path)
    parent_hash = state["parent_hash"] if state else None
    return {
        "path": rel_path,
        "parent_hash": parent_hash,
        "current_hash": current_hash,
    }


@router.post("/pull-files", summary="从云端拉取增量文件")
def sync_pull_files(
    request: SyncPullFilesRequest,
    _: None = Depends(verify_sync_api_key),
):
    """从云端拉取增量文件

    遍历请求的目录/文件列表，找到 mtime > last_sync_time 的文件，
    读取内容并 gzip 压缩 + base64 编码后返回。

    支持目录路径（递归遍历）和单文件路径（如 channel/wechat/account.json）。
    路径不存在时自动跳过，不报错。
    首次同步（last_sync_time 为空字符串）时拉取全部文件。

    **请求参数**:
    - last_sync_time: 上次同步时间（ISO 8601 格式，空字符串表示首次同步）
    - directories: 需要拉取的目录/文件列表（相对 lifeprism_data_path）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - files: [{path, content, mtime}] 变更文件列表
    - sync_time: 本次同步时间
    """
    logger.debug(
        "同步 Pull-Files 请求开始: last_sync_time=%s, directories=%s",
        request.last_sync_time,
        request.directories,
    )
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()
    last_sync_dt = parse_iso_to_aware(request.last_sync_time) if request.last_sync_time else None

    files: list[dict[str, str]] = []
    for dir_rel in request.directories:
        dir_path = (data_path / dir_rel).resolve()

        # 路径安全检查：防止路径遍历攻击
        if not _is_path_safe(dir_path, data_path):
            logger.warning("跳过不安全路径: %s", dir_rel)
            continue

        if dir_path.is_file():
            # 单文件处理（如 channel/wechat/account.json）
            file_mtime_dt = datetime.fromtimestamp(dir_path.stat().st_mtime, tz=timezone.utc)
            if last_sync_dt and file_mtime_dt <= last_sync_dt:
                continue
            files.append(_encode_file(dir_path, data_path))
        elif dir_path.is_dir():
            # 目录递归遍历
            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                file_mtime_dt = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if last_sync_dt and file_mtime_dt <= last_sync_dt:
                    continue
                files.append(_encode_file(file_path, data_path))
        else:
            # 不存在的路径跳过
            logger.debug("路径不存在，跳过: %s", dir_rel)
            continue

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if files:
        logger.info(
            "同步 Pull-Files 完成: 文件数=%d, 耗时=%.2fms",
            len(files),
            elapsed_ms,
        )
    else:
        logger.debug(
            "同步 Pull-Files 完成: 无新文件, 耗时=%.2fms",
            elapsed_ms,
        )

    return {
        "files": files,
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }


# ==================== 文件同步三阶段端点 (check / fetch / verify / commit) ====================


@router.post("/pull-files/check", summary="Phase 1: 按 mtime 过滤返回变更文件的 hash 状态")
def sync_pull_files_check(
    request: SyncPullFilesCheckRequest,
    _: None = Depends(verify_sync_api_key),
):
    """Phase 1 快照交换：云端按 mtime 过滤返回变更文件 hash 状态 + 完整文件路径清单

    遍历 directories（排除 EXCLUDED_FILENAMES 黑名单），单次遍历同时收集：
    - files: mtime > last_sync_time 的变更文件（含 path + parent_hash + current_hash）
    - all_paths: 所有非黑名单文件的相对路径列表（仅路径字符串，不做 mtime 过滤）

    all_paths 用于本地区分"云端有但未变更"和"云端不存在"两种情况，
    避免云端缺失文件被错误 SKIP（修复 cloud-missing-files-not-synced bug）。

    **请求参数**:
    - last_sync_time: 上次同步时间（ISO 8601 格式，空字符串表示首次同步）
    - directories: 需要检查的目录/文件列表（相对 lifeprism_data_path）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - files: [{path, parent_hash, current_hash}] 变更文件 hash 状态列表
    - all_paths: [str] 云端所有非黑名单文件的相对路径列表
    - sync_time: 本次同步时间
    """
    logger.debug(
        "同步 Pull-Files-Check 请求开始: last_sync_time=%s, directories=%s",
        request.last_sync_time,
        request.directories,
    )
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()
    last_sync_dt = parse_iso_to_aware(request.last_sync_time) if request.last_sync_time else None

    files: list[dict[str, Any]] = []
    all_paths: list[str] = []
    skipped_blacklist_cloud = []
    for dir_rel in request.directories:
        dir_path = (data_path / dir_rel).resolve()

        # 路径安全检查：防止路径遍历攻击
        if not _is_path_safe(dir_path, data_path):
            logger.warning("跳过不安全路径: %s", dir_rel)
            continue

        if dir_path.is_file():
            # 单文件处理
            if dir_path.name in _EXCLUDED_FILENAMES:
                skipped_blacklist_cloud.append(
                    str(dir_path.relative_to(data_path)).replace("\\", "/")
                )
                continue
            # 收集所有非黑名单文件路径（不做 mtime 过滤，用于存在性判断）
            rel_path = str(dir_path.relative_to(data_path)).replace("\\", "/")
            all_paths.append(rel_path)
            # mtime 过滤，仅变更文件才计算 hash
            file_mtime_dt = datetime.fromtimestamp(dir_path.stat().st_mtime, tz=timezone.utc)
            if last_sync_dt and file_mtime_dt <= last_sync_dt:
                continue
            files.append(_build_file_hash_state(dir_path, data_path))
        elif dir_path.is_dir():
            # 目录递归遍历
            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.name in _EXCLUDED_FILENAMES:
                    skipped_blacklist_cloud.append(
                        str(file_path.relative_to(data_path)).replace("\\", "/")
                    )
                    continue
                # 收集所有非黑名单文件路径（不做 mtime 过滤，用于存在性判断）
                rel_path = str(file_path.relative_to(data_path)).replace("\\", "/")
                all_paths.append(rel_path)
                # mtime 过滤，仅变更文件才计算 hash
                file_mtime_dt = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if last_sync_dt and file_mtime_dt <= last_sync_dt:
                    continue
                files.append(_build_file_hash_state(file_path, data_path))
        else:
            logger.debug("路径不存在，跳过: %s", dir_rel)
            continue

    if skipped_blacklist_cloud:
        logger.info(
            "pull-files/check: 云端黑名单过滤生效，跳过 %d 个文件: %s",
            len(skipped_blacklist_cloud),
            skipped_blacklist_cloud,
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if files:
        logger.info(
            "同步 Pull-Files-Check 完成: 变更文件=%d, 总文件=%d, 耗时=%.2fms",
            len(files),
            len(all_paths),
            elapsed_ms,
        )
    else:
        logger.debug(
            "同步 Pull-Files-Check 完成: 无变更文件, 总文件=%d, 耗时=%.2fms",
            len(all_paths),
            elapsed_ms,
        )

    return {
        "files": files,
        "all_paths": all_paths,
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/pull-files/fetch", summary="Phase 2: 按路径返回文件内容 + hash")
def sync_pull_files_fetch(
    request: SyncPullFilesPathsRequest,
    _: None = Depends(verify_sync_api_key),
):
    """Phase 2 内容拉取：按路径返回文件内容（gzip+base64）+ parent_hash + current_hash

    请求路径不存在时跳过（不报错，不返回该文件）。
    content 为 gzip 压缩 + base64 编码。
    parent_hash 从 file_sync_state 表读取（供客户端初始化本地状态）。
    current_hash 实时计算（供客户端校验传输完整性，客户端写入后应重新计算）。

    **请求参数**:
    - paths: 文件相对路径列表（相对 lifeprism_data_path）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - files: [{path, content, parent_hash, current_hash}] 文件内容列表
    """
    logger.info("同步 Pull-Files-Fetch 请求开始: 路径数=%d", len(request.paths))
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()

    files: list[dict[str, Any]] = []
    for rel_path in request.paths:
        file_path = (data_path / rel_path).resolve()

        if not _is_path_safe(file_path, data_path):
            logger.warning("跳过不安全路径: %s", rel_path)
            continue

        if not file_path.is_file():
            logger.debug("文件不存在，跳过: %s", rel_path)
            continue

        content_bytes = file_path.read_bytes()
        compressed = gzip.compress(content_bytes)
        encoded = base64.b64encode(compressed).decode("ascii")
        current_hash = compute_file_hash(content_bytes)
        state = file_sync_state_repository.get_state(rel_path)
        parent_hash = state["parent_hash"] if state else None

        files.append(
            {
                "path": rel_path,
                "content": encoded,
                "parent_hash": parent_hash,
                "current_hash": current_hash,
            }
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "同步 Pull-Files-Fetch 完成: 文件数=%d, 耗时=%.2fms",
        len(files),
        elapsed_ms,
    )

    return {"files": files}


@router.post("/pull-files/verify", summary="Phase 3: 实时计算 hash（纯只读）")
def sync_pull_files_verify(
    request: SyncPullFilesPathsRequest,
    _: None = Depends(verify_sync_api_key),
):
    """Phase 3 一致性校验：实时计算 hash，纯只读，不修改任何状态

    云端对 paths 中的文件实时计算 current_hash（再次读取文件内容 → 规范化 → SHA-256）。
    请求路径不存在时跳过。

    **请求参数**:
    - paths: 文件相对路径列表（相对 lifeprism_data_path）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - files: [{path, current_hash}] 文件 hash 列表
    """
    logger.info("同步 Pull-Files-Verify 请求开始: 路径数=%d", len(request.paths))
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()

    files: list[dict[str, Any]] = []
    for rel_path in request.paths:
        file_path = (data_path / rel_path).resolve()

        if not _is_path_safe(file_path, data_path):
            logger.warning("跳过不安全路径: %s", rel_path)
            continue

        if not file_path.is_file():
            logger.debug("文件不存在，跳过: %s", rel_path)
            continue

        content_bytes = file_path.read_bytes()
        current_hash = compute_file_hash(content_bytes)

        files.append(
            {
                "path": rel_path,
                "current_hash": current_hash,
            }
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "同步 Pull-Files-Verify 完成: 文件数=%d, 耗时=%.2fms",
        len(files),
        elapsed_ms,
    )

    return {"files": files}


@router.post("/pull-files/commit", summary="Phase 4: 推进云端 parent_hash = current_hash")
def sync_pull_files_commit(
    request: SyncPullFilesPathsRequest,
    _: None = Depends(verify_sync_api_key),
):
    """Phase 4 推进版本：将 file_sync_state 的 parent_hash = current_hash

    本地 verify 校验通过后调用此端点推进云端 parent_hash。
    实时计算 current_hash（不使用缓存值），然后 upsert file_sync_state。
    请求路径不存在时跳过。

    **请求参数**:
    - paths: 文件相对路径列表（相对 lifeprism_data_path）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - committed: [{path, parent_hash}] 已推进的文件列表
    """
    logger.info("同步 Pull-Files-Commit 请求开始: 路径数=%d", len(request.paths))
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()

    committed: list[dict[str, str]] = []
    for rel_path in request.paths:
        file_path = (data_path / rel_path).resolve()

        if not _is_path_safe(file_path, data_path):
            logger.warning("跳过不安全路径: %s", rel_path)
            continue

        if not file_path.is_file():
            logger.debug("文件不存在，跳过: %s", rel_path)
            continue

        content_bytes = file_path.read_bytes()
        current_hash = compute_file_hash(content_bytes)

        # 推进 parent_hash = current_hash（实时计算，不使用缓存值）
        file_sync_state_repository.upsert_state(
            file_path=rel_path,
            parent_hash=current_hash,
            current_hash=current_hash,
        )

        committed.append(
            {
                "path": rel_path,
                "parent_hash": current_hash,
            }
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "同步 Pull-Files-Commit 完成: 推进文件数=%d, 耗时=%.2fms",
        len(committed),
        elapsed_ms,
    )

    return {"committed": committed}


@router.post("/push-files", summary="推送本地文件到云端")
def sync_push_files(
    request: SyncPushFilesRequest,
    _: None = Depends(verify_sync_api_key),
):
    """推送本地文件到云端（Issue 32: hash-based 同步）

    云端逻辑：
    1. base64 解码 + gzip 解压 → 写入文件
    2. 写入后立即计算 current_hash（调用 compute_file_hash）→ 更新 file_sync_state 表
    3. 如果 file_sync_state 中无此文件记录 → 插入新记录（parent_hash = NULL, current_hash = 计算值）
    4. 如果已有记录 → 只更新 current_hash（parent_hash 不修改，保持云端原值）

    push-files 不推进 parent_hash（由 commit 端点负责）。
    原 mtime LWW 逻辑已废弃，冲突检测由 hash 矩阵判定（SyncClient 侧执行）。

    **请求参数**:
    - files: [{path, content, parent_hash, current_hash}] 待推送的文件列表

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - results: [{path, action}] 每个文件的处理结果（action="accepted" 表示已写入）
    - sync_time: 本次同步时间
    """
    logger.info("同步 Push-Files 请求开始: 文件数=%d", len(request.files))
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()
    results: list[dict[str, str]] = []

    for item in request.files:
        file_path = (data_path / item.path).resolve()

        # 路径安全检查：防止路径遍历攻击
        if not _is_path_safe(file_path, data_path):
            logger.warning("跳过不安全路径: %s", item.path)
            continue

        # base64 解码 + gzip 解压（带大小限制）
        compressed = base64.b64decode(item.content)
        content_bytes = safe_gzip_decompress(compressed)

        # 自动创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        file_path.write_bytes(content_bytes)

        # 云端写入后立即计算 current_hash 并更新 file_sync_state
        # （不信任客户端传入的 current_hash，云端自行计算）
        cloud_current_hash = compute_file_hash(content_bytes)
        existing_state = file_sync_state_repository.get_state(item.path)
        # push-files 不推进 parent_hash（由 commit 端点负责）
        # 新文件：parent_hash = NULL；已有记录：保持原 parent_hash 不变
        preserved_parent_hash = existing_state["parent_hash"] if existing_state else None
        file_sync_state_repository.upsert_state(
            file_path=item.path,
            parent_hash=preserved_parent_hash,
            current_hash=cloud_current_hash,
        )

        results.append({"path": item.path, "action": "accepted"})

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "同步 Push-Files 完成: 写入文件数=%d, 耗时=%.2fms",
        len(results),
        elapsed_ms,
    )

    return {
        "results": results,
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }


# ==================== 首次同步初始化端点 ====================


@router.get("/initialization-status", summary="检查云端是否已完成首次同步初始化")
def sync_get_initialization_status(_: None = Depends(verify_sync_api_key)):
    """检查云端是否已完成首次同步初始化

    通过标志文件 `<config_base_path>/config/cloud_initialized` 是否存在判断。
    标志文件由 /mark-initialized 端点创建。

    **响应**:
    - initialized: True 已初始化，False 未初始化
    - checked_at: 检查时间（ISO 8601 UTC）
    """
    marker_path = settings.config_base_path / "config" / "cloud_initialized"
    return {
        "initialized": marker_path.exists(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/full-clear", summary="清空云端所有同步数据（首次同步前调用）")
def sync_full_clear(_: None = Depends(verify_sync_api_key)):
    """清空云端所有同步数据（数据库 + 文件），保留 schema_version 和 custom_* 表结构

    清空范围：
    - SYNC_TABLES 中的所有表（30 张静态表，包括 custom_record_types/custom_record_fields）
    - file_sync_state 表（文件同步状态归零）
    - SYNC_DIRECTORIES 下的所有文件（包括黑名单文件 chat_history.json/bootstrap.md）

    未清空范围：
    - schema_version 表（保留迁移版本，不在 SYNC_TABLES 中）
    - custom_<slug> 数据表（不在 SYNC_TABLES 中，孤儿表不影响功能，决策点 3）

    非原子性说明：跨表 DELETE 非原子，单表失败不阻塞整体清空。
    依赖首次同步的幂等重试（不设标志位，下次重试）。
    此端点使用 try/except 是 ADR 2026-07-17 前提 7 的明确要求
    （跨表 DELETE 非原子，单表失败不阻塞整体清空），不作为其他端点的先例。

    **响应**:
    - status: "ok"
    - cleared_tables: 已清空的表名列表
    - cleared_files: 已删除的文件数
    - cleared_at: 清空时间（ISO 8601 UTC）
    """
    # 1. 清空 SYNC_TABLES 中的所有表
    # 例外说明：本端点使用 try/except 是 ADR 2026-07-17 前提 7 的明确要求
    # （跨表 DELETE 非原子，单表失败不阻塞整体清空），不作为其他端点的先例
    cleared_tables = []
    for table in SYNC_TABLES:
        try:
            sync_repository.delete_all_rows(table)
            cleared_tables.append(table)
        except DataAccessError as e:
            logger.warning("清空表 %s 失败: %s", table, e)

    # 2. 清空 file_sync_state（让云端文件同步状态归零）
    try:
        sync_repository.delete_all_rows("file_sync_state")
    except DataAccessError as e:
        logger.warning("清空 file_sync_state 失败: %s", e)

    # 3. 显式清空 deletion_log（墓碑表已从 SYNC_TABLES 移除，走专用通道）
    # 复用 try/except 模式，单表失败不阻塞整体清空（与 SYNC_TABLES 遍历一致）
    try:
        sync_repository.delete_all_rows("deletion_log")
        cleared_tables.append("deletion_log")
    except DataAccessError as e:
        logger.warning("清空 deletion_log 失败: %s", e)

    # 4. 删除 SYNC_DIRECTORIES 下所有文件（包括黑名单文件，首次同步特殊行为）
    # 路径安全检查：确保 dir_path 在 lifeprism_data_path 下（参照 /push-files 的 _is_path_safe）
    cleared_files = 0
    data_path_resolved = settings.lifeprism_data_path.resolve()
    for dir_name in SYNC_DIRECTORIES:
        dir_path = (settings.lifeprism_data_path / dir_name.rstrip("/")).resolve()
        # 安全检查：dir_path 必须在 lifeprism_data_path 下
        try:
            dir_path.relative_to(data_path_resolved)
        except ValueError:
            logger.warning("跳过非数据目录下的文件删除: %s", dir_path)
            continue
        if dir_path.exists():
            # 删除所有文件
            for item in dir_path.rglob("*"):
                if item.is_file():
                    try:
                        item.unlink()
                        cleared_files += 1
                    except OSError as e:
                        logger.warning("删除文件失败 %s: %s", item, e)
            # 清理空目录（自底向上，避免多次首次同步重试后累积空目录结构）
            for root, dirs, _ in os.walk(dir_path, topdown=False):
                for d in dirs:
                    full = Path(root) / d
                    with contextlib.suppress(OSError):
                        full.rmdir()  # 仅在目录为空时成功

    logger.info(
        "full-clear 完成: 表=%d, 文件=%d",
        len(cleared_tables),
        cleared_files,
    )

    return {
        "status": "ok",
        "cleared_tables": cleared_tables,
        "cleared_files": cleared_files,
        "cleared_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/mark-initialized", summary="标记云端已完成首次同步初始化")
def sync_mark_initialized(_: None = Depends(verify_sync_api_key)):
    """标记云端已完成首次同步初始化

    创建标志文件 `<config_base_path>/config/cloud_initialized`，
    文件内容为当前时间戳（ISO 8601 UTC）。

    标志文件存在时，下次 sync_once 走增量同步分支；
    标志文件不存在时，触发首次同步（full-clear + 全量推送）。

    **响应**:
    - status: "ok"
    - marked_at: 标记时间（ISO 8601 UTC）
    """
    config_dir = settings.config_base_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    marker_path = config_dir / "cloud_initialized"
    marker_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")

    logger.info("云端已标记为已初始化: %s", marker_path)

    return {
        "status": "ok",
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }
