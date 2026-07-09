"""
云端数据同步 API 路由

提供 Pull + Push 双向同步的 REST API 端点：
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
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from lifeprism.config.settings_manager import settings
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
    mtime: str = Field(..., description="文件修改时间（ISO 8601 格式）")


class SyncPushFilesRequest(BaseModel):
    """文件推送请求"""

    files: list[FilePushItem] = Field(..., description="待推送的文件列表")


class HeartbeatRequest(BaseModel):
    """心跳请求"""

    event: str = Field(..., description="事件类型（online/offline/ping）")


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
    last_sync_dt = (
        datetime.fromisoformat(request.last_sync_time) if request.last_sync_time else None
    )

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


@router.post("/push-files", summary="推送本地文件到云端")
def sync_push_files(
    request: SyncPushFilesRequest,
    _: None = Depends(verify_sync_api_key),
):
    """推送本地文件到云端

    对每个文件执行 Last-Write-Wins 冲突解决：
    比较本地文件 mtime 与推送的 mtime，谁更晚保留谁。
    如果本地文件 mtime 更新则跳过，否则写入并设置 mtime。

    文件内容为 gzip 压缩 + base64 编码，写入时自动解码解压。
    自动创建父目录。

    **请求参数**:
    - files: [{path, content, mtime}] 待推送的文件列表

    **认证**:
    - Authorization: Bearer {api_key} HTTP Header

    **响应**:
    - status: 同步状态（"ok"）
    - written: 写入的文件数
    - skipped: 跳过的文件数
    - sync_time: 本次同步时间
    """
    logger.info("同步 Push-Files 请求开始: 文件数=%d", len(request.files))
    start_time = time.perf_counter()

    data_path = settings.lifeprism_data_path.resolve()
    written = 0
    skipped = 0

    for item in request.files:
        file_path = (data_path / item.path).resolve()

        # 路径安全检查：防止路径遍历攻击
        if not _is_path_safe(file_path, data_path):
            logger.warning("跳过不安全路径: %s", item.path)
            skipped += 1
            continue

        remote_mtime_dt = datetime.fromisoformat(item.mtime)
        remote_mtime_ts = remote_mtime_dt.timestamp()

        # LWW 冲突解决：本地文件 mtime 更新时跳过
        if file_path.exists():
            local_mtime_ts = file_path.stat().st_mtime
            if local_mtime_ts > remote_mtime_ts:
                logger.debug("LWW 跳过（本地更新）: %s", item.path)
                skipped += 1
                continue

        # base64 解码 + gzip 解压
        compressed = base64.b64decode(item.content)
        content_bytes = gzip.decompress(compressed)

        # 自动创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        file_path.write_bytes(content_bytes)

        # 设置 mtime
        os.utime(file_path, (remote_mtime_ts, remote_mtime_ts))

        written += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "同步 Push-Files 完成: written=%d, skipped=%d, 耗时=%.2fms",
        written,
        skipped,
        elapsed_ms,
    )

    return {
        "status": "ok",
        "written": written,
        "skipped": skipped,
        "sync_time": datetime.now(timezone.utc).isoformat(),
    }
