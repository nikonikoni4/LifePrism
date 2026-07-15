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
import gzip
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from lifeprism.config.settings_manager import settings
from lifeprism.repository import SyncRepository, file_sync_state_repository
from lifeprism.sync.constants import EXCLUDED_FILENAMES as _EXCLUDED_FILENAMES
from lifeprism.sync.constants import safe_gzip_decompress
from lifeprism.sync.hash_utils import compute_file_hash
from lifeprism.sync.sync_config import get_sync_api_key
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ValidationError
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

    logger.info(
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
    logger.info(
        "同步 Pull 完成: 记录数=%s, 耗时=%.2fms",
        record_counts,
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


@router.post("/rebuild-dynamic-tables", summary="根据本地定义重建云端动态表")
def sync_rebuild_dynamic_tables(
    request: RebuildDynamicTablesRequest,
    _: None = Depends(verify_sync_api_key),
):
    """根据本地发送的自定义记录类型定义，重建/同步云端动态表

    本地 pull 完成后检测到 custom_record_types meta 表有变更时调用此端点，
    云端根据最新的 type + fields 定义：
    - 新增 type → CREATE TABLE
    - 已有 type 缺字段 → ALTER TABLE ADD COLUMN（只增不删）
    - 云端有但本地已删除的 type → DROP TABLE

    幂等操作：重复调用不会产生副作用。

    **请求参数**:
    - types: 自定义记录类型定义列表

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - rebuilt: [{slug, action}] 每个类型的处理结果（created/altered/skipped/dropped）
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
    logger.info(
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
    logger.info(
        "同步 Pull-Files 完成: 文件数=%d, 耗时=%.2fms",
        len(files),
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
    """Phase 1 快照交换：云端按 mtime 过滤，返回变更文件的 hash 状态（轻量，不传内容）

    遍历 directories（排除 chat_history.json），找到 mtime > last_sync_time 的文件，
    实时计算 current_hash（调用 compute_file_hash），从 file_sync_state 表读 parent_hash。

    **请求参数**:
    - last_sync_time: 上次同步时间（ISO 8601 格式，空字符串表示首次同步）
    - directories: 需要检查的目录/文件列表（相对 lifeprism_data_path）

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - files: [{path, parent_hash, current_hash}] 变更文件 hash 状态列表
    - sync_time: 本次同步时间
    """
    logger.info(
        "同步 Pull-Files-Check 请求开始: last_sync_time=%s, directories=%s",
        request.last_sync_time,
        request.directories,
    )
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()
    last_sync_dt = parse_iso_to_aware(request.last_sync_time) if request.last_sync_time else None

    files: list[dict[str, Any]] = []
    for dir_rel in request.directories:
        dir_path = (data_path / dir_rel).resolve()

        # 路径安全检查：防止路径遍历攻击
        if not _is_path_safe(dir_path, data_path):
            logger.warning("跳过不安全路径: %s", dir_rel)
            continue

        if dir_path.is_file():
            # 单文件处理
            if dir_path.name in _EXCLUDED_FILENAMES:
                continue
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
                    continue
                file_mtime_dt = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if last_sync_dt and file_mtime_dt <= last_sync_dt:
                    continue
                files.append(_build_file_hash_state(file_path, data_path))
        else:
            logger.debug("路径不存在，跳过: %s", dir_rel)
            continue

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "同步 Pull-Files-Check 完成: 文件数=%d, 耗时=%.2fms",
        len(files),
        elapsed_ms,
    )

    return {
        "files": files,
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
