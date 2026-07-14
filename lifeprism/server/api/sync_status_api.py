"""
同步状态查询和手动触发同步 API 路由

提供同步状态查询和手动触发同步的 REST API 端点：
- GET /api/sync/status: 获取同步状态信息（上次同步时间、状态、远程 URL、各表记录数）
- POST /api/sync/trigger: 手动触发一次同步（后台线程执行，立即返回 202）
- POST /api/sync/reset-sync-progress: 重置同步进度（清空 last_sync_time，下次同步变为全量同步）

API 层不直接编写 SQL，所有数据库操作通过 SyncRepository。
API 层不使用 try/except，异常自然冒泡到全局异常处理器。

SyncClient 实例通过 app.state.sync_client 获取，在 main.py 的 lifespan 中创建。
SyncRepository 复用 SyncClient 中已注入的实例，不单独创建。
若 SyncClient 不存在，返回 503 Service Unavailable。
"""

import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lifeprism.config.settings_manager import get_setting, set_setting
from lifeprism.sync.sync_client import SYNC_TABLES
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ExternalServiceError

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sync", tags=["Sync Status"])


# ==================== API 端点 ====================


@router.get("/status", summary="获取同步状态信息")
def get_sync_status(request: Request):
    """获取同步状态信息

    返回上次同步时间、同步状态、远程 URL 和各表记录数。

    注意：本端点使用同步 def（非 async def），FastAPI 会自动将其放入
    线程池执行，避免同步 sqlite3 阻塞调用阻塞事件循环。

    **响应**:
    - last_sync_time: 上次同步时间（ISO 8601 格式）
    - status: 同步状态（"idle" | "syncing"）
    - remote_url: 远程服务器 URL
    - tables: 各表记录数 {table_name: count}
    """
    sync_client = getattr(request.app.state, "sync_client", None)
    if sync_client is None:
        raise ExternalServiceError(message="同步服务不可用")

    # 判断同步状态（通过只读 property，不直接访问私有属性）
    status = "syncing" if sync_client.is_syncing else "idle"

    # 读取配置
    last_sync_time = get_setting("sync.last_sync_time", "")
    remote_url = get_setting("sync.remote_url", "")

    # 批量查询各表记录数（复用 SyncClient 中已注入的 SyncRepository 实例，
    # 使用单一连接执行多次 COUNT(*)，避免 N+1 式连接获取）
    sync_repository = sync_client.sync_repository
    tables = sync_repository.count_rows_batch(list(SYNC_TABLES))

    return {
        "last_sync_time": last_sync_time,
        "status": status,
        "remote_url": remote_url,
        "tables": tables,
    }


@router.post("/trigger", summary="手动触发同步")
async def trigger_sync(request: Request):
    """手动触发一次同步

    在后台线程中执行同步，立即返回 202 Accepted。
    如果同步正在进行中，返回 409 Conflict。

    并发控制通过 SyncClient.try_start_sync() 原子方法实现，
    避免 check-then-set 竞态条件。

    **响应**:
    - 202: {"message": "同步已触发", "status": "syncing"}
    - 409: {"message": "同步正在进行中", "status": "syncing"}
    """
    sync_client = getattr(request.app.state, "sync_client", None)
    if sync_client is None:
        raise ExternalServiceError(message="同步服务不可用")

    # 并发控制：原子地尝试获取同步锁，失败则返回 409
    if not sync_client.try_start_sync():
        return JSONResponse(
            status_code=409,
            content={
                "message": "同步正在进行中",
                "status": "syncing",
            },
        )

    # 启动后台线程执行同步（try_start_sync 已将 _is_syncing 置为 True）
    thread = threading.Thread(
        target=_run_sync_background,
        args=(sync_client,),
        daemon=True,
    )
    thread.start()

    return JSONResponse(
        status_code=202,
        content={
            "message": "同步已触发",
            "status": "syncing",
        },
    )


@router.post("/reset-sync-progress", summary="重置同步进度")
def reset_sync_progress(request: Request):
    """重置同步进度（清空 last_sync_time）

    清空本地的 last_sync_time，使下次同步变为全量同步。
    适用场景：换服务器、云端数据库重置、本地数据库重置后需要全量同步。

    安全约束：
    - 同步进行中时拒绝执行（返回 409），避免状态不一致

    **响应**:
    - 200: {"message": "同步进度已重置，下次同步将为全量同步"}
    - 409: 同步进行中，拒绝执行
    """
    sync_client = getattr(request.app.state, "sync_client", None)
    if sync_client is None:
        raise ExternalServiceError(message="同步服务不可用")

    # 同步进行中时拒绝执行（避免状态不一致）
    if sync_client.is_syncing:
        return JSONResponse(
            status_code=409,
            content={
                "message": "同步正在进行中，无法重置进度",
                "status": "syncing",
            },
        )

    # 清空 last_sync_time，下次同步将变为全量同步
    # （WHERE updated_at > '' 返回所有记录）
    set_setting("sync.last_sync_time", "")
    logger.info("同步进度已重置，last_sync_time 已清空，下次同步将为全量同步")

    return {
        "message": "同步进度已重置，下次同步将为全量同步",
    }


# ==================== 内部辅助函数 ====================


def _run_sync_background(sync_client) -> None:
    """在后台线程中执行同步

    使用 try...finally 确保 finish_sync() 在异常时也能被调用。
    该函数在独立线程中运行，不在 HTTP 请求生命周期内，
    因此需要自行捕获异常（不影响 API 层异常冒泡规范）。

    Args:
        sync_client: SyncClient 实例
    """
    try:
        sync_client.sync_once()
    except Exception as e:
        logger.error("手动触发同步失败: %s", e)
    finally:
        sync_client.finish_sync()
