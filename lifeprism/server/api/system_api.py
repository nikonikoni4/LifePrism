import asyncio
import os
import signal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lifeprism.server.schemas.system_schemas import SystemWarningsResponse
from lifeprism.server.services import system_service
from lifeprism.utils import get_logger

router = APIRouter(prefix="/system", tags=["System - 系统信息"])

logger = get_logger(__name__)


@router.get("/warnings", response_model=SystemWarningsResponse, summary="获取系统警告列表")
async def get_warnings():
    """获取系统警告列表"""
    return SystemWarningsResponse(warnings=system_service.get_warnings())


@router.post("/shutdown", summary="优雅关闭后端服务（含关闭前同步）")
async def shutdown_backend(request: Request):
    """触发后端优雅关闭流程（用户主动退出场景）

    收到请求后立即返回 202 Accepted，然后在后台异步触发 SIGINT 信号，
    让 uvicorn 执行完整的 lifespan shutdown 流程：
    1. 清理监控进程
    2. 关闭微信渠道
    3. 取消 AgentLoop
    4. 停止定时任务
    5. 清理 ChatBot 资源
    6. 执行关闭前同步 sync_once（1-3 分钟）
    7. 发送 offline 心跳到云端

    设计参考：思源笔记的 Close(force=false) 流程（同步阻塞等待 syncData 完成）。
    与思源差异：LifePrism 后端是独立进程，通过 HTTP 触发 + 监听进程退出实现。

    适用场景：用户主动退出（托盘菜单/窗口关闭），有充足时间等待同步完成。

    重复调用安全（通过 app.state.shutdown_triggered 标志位防止）。
    """
    app = request.app

    # 防止重复触发
    if getattr(app.state, "shutdown_triggered", False):
        logger.info("[SHUTDOWN] 关闭流程已在进行中，跳过重复触发")
        return JSONResponse(
            status_code=202,
            content={
                "status": "already_shutting_down",
                "message": "关闭流程已在进行中",
            },
        )

    app.state.shutdown_triggered = True
    # 标记是否跳过关闭前同步（关机场景设置为 True）
    app.state.skip_sync_on_shutdown = False
    logger.info("[SHUTDOWN] 收到关闭请求，准备触发优雅关闭流程（含关闭前同步）")

    # 异步触发 SIGINT，让 uvicorn 进入 shutdown 流程
    # 延迟 0.5s 是为了让当前 HTTP 响应先返回给 Electron
    async def _trigger_shutdown():
        await asyncio.sleep(0.5)
        logger.info(
            "[SHUTDOWN] 触发 SIGINT，开始执行 lifespan shutdown（含关闭前同步和 offline 心跳）"
        )
        # 向当前进程发送 SIGINT，uvicorn 会捕获并触发 lifespan shutdown
        os.kill(os.getpid(), signal.SIGINT)

    asyncio.create_task(_trigger_shutdown())

    return JSONResponse(
        status_code=202,
        content={
            "status": "shutting_down",
            "message": "后端正在执行优雅关闭流程（含关闭前同步和 offline 心跳）",
        },
    )


@router.post("/quick-shutdown", summary="快速关闭后端服务（跳过同步，关机专用）")
async def quick_shutdown_backend(request: Request):
    """触发后端快速关闭流程（Windows 关机/重启场景）

    与 /shutdown 的区别：**跳过关闭前 sync_once**，只执行：
    1. 发送 offline 心跳到云端（~1 秒，让云端立即接管）
    2. 清理资源（监控进程/微信渠道/AgentLoop 等）
    3. 触发 SIGINT 退出

    设计原因：
    - Windows 关机只给应用 5 秒响应时间（WM_QUERYENDSESSION）
    - sync_once 需要 1-3 分钟，无法在 5 秒内完成
    - 如果启动 sync_once 但被强杀 → parent_hash 不一致 → 下次启动走 AI 合并（600s 超时）
    - 因此关机时不启动 sync_once，依赖：
      a. 每 10 分钟定时同步保证数据延迟 ≤10 分钟
      b. 下次启动时的启动同步补齐数据

    重复调用安全（通过 app.state.shutdown_triggered 标志位防止）。
    """
    app = request.app

    # 防止重复触发
    if getattr(app.state, "shutdown_triggered", False):
        logger.info("[SHUTDOWN] 关闭流程已在进行中，跳过重复触发")
        return JSONResponse(
            status_code=202,
            content={
                "status": "already_shutting_down",
                "message": "关闭流程已在进行中",
            },
        )

    app.state.shutdown_triggered = True
    # 关键：标记跳过关闭前同步
    app.state.skip_sync_on_shutdown = True
    logger.info("[SHUTDOWN] 收到快速关闭请求（关机场景），跳过关闭前同步")

    # 异步触发 SIGINT，让 uvicorn 进入 shutdown 流程
    async def _trigger_quick_shutdown():
        await asyncio.sleep(0.3)  # 关机场景缩短延迟，尽快进入 shutdown
        logger.info("[SHUTDOWN] 触发 SIGINT（快速模式），跳过 sync_once，只发 offline 心跳")
        os.kill(os.getpid(), signal.SIGINT)

    asyncio.create_task(_trigger_quick_shutdown())

    return JSONResponse(
        status_code=202,
        content={
            "status": "quick_shutting_down",
            "message": "后端正在执行快速关闭流程（跳过同步，只发 offline 心跳）",
        },
    )
