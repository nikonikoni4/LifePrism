"""
LifeWatch Server - FastAPI 主应用程序
"""

# ==================== 启动时间追踪 ====================
import time

_startup_timer = time.perf_counter()


def _log_startup_time(step_name: str, start_time: float) -> float:
    """记录启动步骤耗时并返回当前时间，调试用"""
    current = time.perf_counter()
    # 关闭打印
    # print(f"[STARTUP] {step_name}: {elapsed:.2f}ms (累计: {total:.2f}ms)")
    return current


_step_start = _startup_timer
print(f"\n{'=' * 60}")
print("[STARTUP] 开始追踪服务器启动时间...")
print(f"{'=' * 60}")

# ==================== 核心库导入 ====================
import asyncio
import sys
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_step_start = _log_startup_time("[OK] Core imports (contextlib, fastapi, logging)", _step_start)

# ==================== 配置初始化（必须在所有 lifeprism 模块之前） ====================
print("[STARTUP] 正在初始化配置管理器...")
_config_start = time.perf_counter()
from lifeprism.config.settings_manager import (
    settings,  # noqa: E402 - 必须最先导入，初始化路径和日志
)

_log_startup_time("[OK] settings_manager initialized (paths + file logging)", _config_start)

# ==================== SQLite 环境前置检查 ====================
# Settings manager 已初始化，logger 的 FileHandler 已挂载，错误可同时写入控制台和日志文件。
# SQLite 3.35.0+ 是硬性要求（ALTER TABLE DROP COLUMN 等关键特性）。
# 注意：sqlite3 是 CPython 内置 C 扩展，不能通过 pip/pyproject.toml 声明依赖，
# 只能在此处做运行时前置校验。
import logging as _logging_check
import sqlite3 as _sqlite3_check

_SQLITE_MIN_VERSION = (3, 35, 0)
_SQLITE_MIN_VERSION_STR = "3.35.0"
_CHECK_LOGGER = _logging_check.getLogger(__name__)

# 检查 1：sqlite3 模块是否可用（极小概率，精简版 Python 可能未编译 _sqlite3）
try:
    _sqlite_actual_version = _sqlite3_check.sqlite_version_info
    _sqlite_actual_version_str = _sqlite3_check.sqlite_version
except Exception as _e:
    _FATAL_MSG = (
        "\n" + "=" * 70 + "\n"
        "[FATAL] SQLite 环境检查失败\n"
        "=" * 70 + "\n"
        f"  错误详情: 无法获取 SQLite 版本信息 — {_e}\n"
        "\n"
        "  原因: 当前 Python 解释器未编译 _sqlite3 C 扩展模块。\n"
        "  这通常发生在以下场景：\n"
        "    1. 使用了极度精简的 Python 发行版（如嵌入式 Python）\n"
        "    2. 自行编译 CPython 时未包含 sqlite3 支持\n"
        "\n"
        "  解决方法：\n"
        "    - Linux/macOS: 安装 libsqlite3-dev 后重新编译 Python\n"
        "    - Windows: 从 python.org 下载官方完整安装包\n"
        "    - 打包环境: 检查 PyInstaller/nuitka 是否正确打包了 _sqlite3.pyd\n"
        "=" * 70
    )
    print(_FATAL_MSG)
    _CHECK_LOGGER.critical(_FATAL_MSG)
    sys.exit(1)

# 检查 2：SQLite 版本是否满足最低要求
if _sqlite_actual_version < _SQLITE_MIN_VERSION:
    _FATAL_MSG = (
        "\n" + "=" * 70 + "\n"
        "[FATAL] SQLite 版本过低，无法启动 LifeWatch\n"
        "=" * 70 + "\n"
        f"  当前版本: {_sqlite_actual_version_str}\n"
        f"  最低要求: {_SQLITE_MIN_VERSION_STR}\n"
        f"  版本元组: {_sqlite_actual_version} < {_SQLITE_MIN_VERSION}\n"
        "\n"
        "  影响范围：\n"
        "    1. ALTER TABLE DROP COLUMN 不可用（迁移 m014 依赖）\n"
        "    2. 其他依赖 SQLite 3.35+ 特性的功能可能异常\n"
        "\n"
        "  解决方法（按推荐顺序）：\n"
        "    1. 升级 Python 版本：Python 3.10+ 通常捆绑 SQLite 3.35+\n"
        "       - Windows: 从 python.org 下载 Python 3.10+ 安装包\n"
        "       - macOS: brew install python@3.12\n"
        "       - Linux: 使用 deadsnakes PPA 或编译安装新版 Python\n"
        "    2. 替换 sqlite3.dll（仅 Windows，高级操作）：\n"
        "       - 从 https://www.sqlite.org/download.html 下载预编译 sqlite3.dll\n"
        "       - 替换 Python 安装目录下的 DLLs/sqlite3.dll\n"
        "    3. 使用 pysqlite3-binary（Python 包，内置新版 SQLite）：\n"
        "       pip install pysqlite3-binary\n"
        "       然后在代码中将 import sqlite3 替换为 import pysqlite3 as sqlite3\n"
        "=" * 70
    )
    print(_FATAL_MSG)
    _CHECK_LOGGER.critical(_FATAL_MSG)
    sys.exit(1)

# 通过：记录版本信息到日志
_CHECK_LOGGER.info("SQLite 环境检查通过: version=%s", _sqlite_actual_version_str)

# 清理：移除临时的引用，避免污染模块命名空间
# 注意：_FATAL_MSG 仅在检查失败分支中定义，通过时不存在，需单独处理
del _sqlite3_check, _sqlite_actual_version, _sqlite_actual_version_str
del _SQLITE_MIN_VERSION, _SQLITE_MIN_VERSION_STR
del _logging_check, _CHECK_LOGGER
with suppress(NameError):
    del _FATAL_MSG

_log_startup_time("[OK] SQLite environment check passed", _step_start)

# ==================== API 路由导入 ====================
print("[STARTUP] 正在导入 API 路由模块...")
_import_start = time.perf_counter()

from lifeprism.server.api import sync_router

_log_startup_time("  - sync_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import category_v2_router

_log_startup_time("  - category_v2_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import activity_v2_router

_log_startup_time("  - activity_v2_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import timeline_v2_router

_log_startup_time("  - timeline_v2_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import usage_router

_log_startup_time("  - usage_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import goal_router

_log_startup_time("  - goal_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import chatbot_router

_log_startup_time("  - chatbot_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import setting_router

_log_startup_time("  - setting_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import report_router

_log_startup_time("  - report_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import being_router

_log_startup_time("  - being_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import taskpool_router

_log_startup_time("  - taskpool_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import todos_router

_log_startup_time("  - todos_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import system_router

_log_startup_time("  - system_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import diary_router

_log_startup_time("  - diary_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import mood_router

_log_startup_time("  - mood_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import commitment_router, value_router

_log_startup_time("  - value_router + commitment_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import habit_router

_log_startup_time("  - habit_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import custom_records_router

_log_startup_time("  - custom_records_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import sync_status_router

_log_startup_time("  - sync_status_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import cloud_config_router

_log_startup_time("  - cloud_config_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api.add_on_api import router as add_on_router

_log_startup_time("  - add_on_router", _import_start)

_step_start = _log_startup_time("[OK] API routers imported", _step_start)

# ==================== 数据库模块导入 ====================
print("[STARTUP] 正在导入数据库模块...")
_import_start = time.perf_counter()
from lifeprism.repository.lw_table_manager import init_database

_log_startup_time("  - lw_table_manager.init_database", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.providers.category_color_provider import initialize_category_colors

_log_startup_time("  - category_color_provider.initialize_category_colors", _import_start)

_import_start = time.perf_counter()
from lifeprism.repository.data_initializer import initialize_default_data

_log_startup_time("  - data_initializer.initialize_default_data", _import_start)

_import_start = time.perf_counter()
from lifeprism.repository.migrations.migration_runner import run_migrations

_log_startup_time("  - migration_runner.run_migrations", _import_start)

_import_start = time.perf_counter()
from lifeprism.repository.resource_initializer import initialize_resources

_log_startup_time("  - resource_initializer.initialize_resources", _import_start)

_step_start = _log_startup_time("[OK] Database modules imported", _step_start)

from lifeprism.utils import get_logger

settings.set_runtime_config("run_mode", "full")

logger = get_logger(__name__)


async def send_heartbeat(event: str, timeout: float = 10.0):
    """发送心跳事件到云端

    在本地生命周期启动/关闭时调用，让云端立即知道本地状态变化。
    心跳发送失败不会影响启动/关闭流程（仅记录 WARNING）。

    Args:
        event: 心跳事件类型，'online' | 'offline'
        timeout: HTTP 超时秒数。关机场景（quick-shutdown）传入较短超时（如 2.0），
            避免 10s 网络超时被 Electron 4s 强杀打断。
    """
    from lifeprism.config.settings_manager import get_setting
    from lifeprism.sync.sync_config import get_sync_api_key

    remote_url = get_setting("sync.remote_url")
    api_key = get_sync_api_key()

    if not remote_url or not api_key:
        logger.debug("未配置同步，跳过心跳发送")
        return

    try:
        # 使用 AsyncClient 避免同步 httpx.post 阻塞事件循环
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{remote_url}/api/sync/heartbeat",
                json={"event": event},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
            response.raise_for_status()
            logger.info("心跳事件已发送: event=%s", event)
    except Exception as e:
        logger.warning("心跳事件发送失败: event=%s, error=%s", event, e)


async def _start_sync_on_startup(app: FastAPI):
    """应用启动时启动同步（启动时立即同步 + 定时同步）

    执行流程：
    1. 仅在 run_mode == "full"（本地）时启动——云端不需要拉取自己
    2. 启动时立即调用 sync_once()（通过 try_start_sync() 原子锁判断是否可启动）
       - 使用 asyncio.to_thread 在独立线程中执行，不阻塞 lifespan
       - 启动同步失败不阻塞应用启动（日志记录 ERROR，应用继续运行）
    3. 启动定时同步循环 start_scheduled_sync(interval=600)（10 分钟间隔）

    并发控制:
    - 通过 try_start_sync() 原子锁判断是否可启动（防止 sync_once 自身并发）
    - 全局任务状态互斥: try_acquire(CLOUD_SYNC, timeout=0)
      若 LOCAL_TASK 正在执行，放弃本次启动同步，调 send_ping 报告本地在线
      参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 4
    - sync_once() 完成后调用 finish_sync() + global_task_state.release() 释放双重锁

    Args:
        app: FastAPI 应用实例
    """
    sync_client = getattr(app.state, "sync_client", None)
    if sync_client is None:
        logger.info("[STARTUP] SyncClient 未创建，跳过启动同步")
        return

    # 仅在 run_mode == "full"（本地）时启动同步——云端不需要拉取自己
    if settings.run_mode != "full":
        logger.info(
            "[STARTUP] 跳过启动同步：run_mode=%s（仅 full 模式启用）",
            settings.run_mode,
        )
        return

    # 1. 启动时立即同步一次（通过 try_start_sync() 原子锁判断是否可启动）
    if sync_client.try_start_sync():
        try:
            # 全局任务状态互斥：尝试获取 CLOUD_SYNC（不等待）
            # 若 LOCAL_TASK 在执行，放弃本次启动同步，调 ping 心跳报告在线
            # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 4
            from lifeprism.server.services.global_task_state import (
                TaskState,
                global_task_state,
            )

            if not global_task_state.try_acquire(TaskState.CLOUD_SYNC, 0):
                logger.info("[STARTUP] 跳过启动同步：LOCAL_TASK 正在执行，发送 ping 心跳")
                await asyncio.to_thread(sync_client.send_ping)
            else:
                try:
                    logger.info("[STARTUP] 启动同步开始")
                    await asyncio.to_thread(sync_client.sync_once)
                    logger.info("[STARTUP] 启动同步完成")
                except Exception as e:
                    # 启动同步失败不阻塞应用启动，日志记录 ERROR
                    logger.error("[STARTUP] 启动同步失败: error=%s", e, exc_info=True)
                finally:
                    global_task_state.release()
        finally:
            sync_client.finish_sync()
    else:
        logger.warning("[STARTUP] 启动同步跳过：上一次同步未完成")

    # 2. 启动定时同步循环（10 分钟间隔）
    sync_client.start_scheduled_sync(600)
    logger.info("[STARTUP] 定时同步已启动（间隔 600s）")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    在应用启动时初始化数据库
    注：数据库连接池清理由 DatabaseManager 的 atexit 处理
    """
    print(f"\n{'=' * 60}")
    print("[STARTUP] 进入 lifespan - 应用初始化阶段")
    print(f"{'=' * 60}")

    # 发送 online 心跳事件（让云端尽早知道本地上线）
    await send_heartbeat("online")

    from lifeprism.utils.logger import enable_uvicorn_file_logging

    enable_uvicorn_file_logging()

    # 启动时：初始化资源文件（打包环境：从 exe 内嵌资源复制缺失文件）
    logger.info("正在初始化资源文件...")
    try:
        _resource_start = time.perf_counter()
        initialize_resources()
        _log_startup_time("[OK] Resource files init (initialize_resources)", _resource_start)
    except Exception as e:
        logger.warning("资源文件初始化失败（非致命）: error=%s", e)

    # 启动时：初始化数据库表结构
    logger.info("正在初始化 LifeWatch 数据库...")
    try:
        _init_start = time.perf_counter()
        init_database()
        _log_startup_time("[OK] Database tables init (init_database)", _init_start)

        _migration_start = time.perf_counter()
        run_migrations(str(settings.lw_db_path))
        _log_startup_time("[OK] Database migrations (run_migrations)", _migration_start)

        _default_data_start = time.perf_counter()
        initialize_default_data()
        _log_startup_time("[OK] Default data init (initialize_default_data)", _default_data_start)

        _color_start = time.perf_counter()
        initialize_category_colors()
        _log_startup_time("[OK] Category colors init (initialize_category_colors)", _color_start)

        # 集成内置监控进程（仅当 monitor_type='lifeprism' 且 Windows 平台时启动）
        app.state.monitor_process = None
        if settings._config.get("monitor_type") == "lifeprism":
            if sys.platform != "win32":
                logger.warning(
                    "monitor_type 为 'lifeprism'，但当前平台非 Windows (platform=%s)，"
                    "跳过 Monitor 启动",
                    sys.platform,
                )
            else:
                logger.info("检测到 monitor_type 为 'lifeprism'，正在启动内置监控进程...")
                try:
                    from lifeprism.monitor.windows_monitor.main import start_monitor_process

                    app.state.monitor_process = start_monitor_process()
                    logger.info("内置监控进程启动成功")
                except ImportError as e:
                    logger.warning(
                        "Monitor 依赖缺失，跳过启动 (error=%s)。"
                        "请确认 pywin32 等 Windows 依赖已安装",
                        e,
                    )
                except Exception as e:
                    logger.warning("启动内置监控进程失败: error=%s", e)

        # 启动channel
        from lifeprism.llm.channel import wechat_channel

        try:
            await wechat_channel.start()
            logger.info("微信渠道启动成功")
        except Exception as e:
            logger.warning("启动微信渠道失败: error=%s", e)

        _total_lifespan = (time.perf_counter() - _startup_timer) * 1000
        print(f"\n{'=' * 60}")
        print(f"[STARTUP] [DONE] App init complete! Total: {_total_lifespan:.2f}ms")
        print(f"{'=' * 60}\n")

        logger.info("[DONE] Database initialized successfully")
    except Exception:
        logger.error("[ERROR] Database init failed", exc_info=True)
        raise

    # 启动定时任务调度器
    from lifeprism.server.services.schedule_service import schedule_service

    try:
        schedule_service.start()
        logger.info("[STARTUP] ScheduleService started")
    except Exception as e:
        logger.warning("启动定时任务服务失败: error=%s", e)

    # 创建 SyncClient 实例（用于同步状态查询和手动触发同步）
    # 传入主线程事件循环引用，用于 CONFLICT_RESOLVE 时通过 run_coroutine_threadsafe 桥接 bus.send（Issue 34）
    try:
        import asyncio

        from lifeprism.repository import lw_db_manager
        from lifeprism.repository.sync_repository import SyncRepository
        from lifeprism.sync.sync_client import SyncClient

        sync_repo = SyncRepository()
        app.state.sync_client = SyncClient(
            db_manager=lw_db_manager,
            sync_repository=sync_repo,
            main_event_loop=asyncio.get_running_loop(),
        )
        logger.info("[STARTUP] SyncClient created")
    except Exception as e:
        logger.warning("创建 SyncClient 失败: error=%s", e)
        app.state.sync_client = None

    # 先启动 AgentLoop，再执行启动同步
    # 原因：sync_once 在遇到 CONFLICT 时会通过 bus.send 发送 AI 合并请求，
    # 若 AgentLoop 未启动，请求会在队列中积压直到 timeout 超时降级。
    # 必须先启动 AgentLoop 作为消费者，sync_once 的冲突合并请求才能被及时处理。
    import asyncio

    from lifeprism.llm.agent.loop import agent_loop

    loop_task = asyncio.create_task(agent_loop.loop())
    logger.info("[STARTUP] AgentLoop started")

    # 启动时立即同步一次 + 定时同步（仅在 run_mode == "full" 时启用）
    await _start_sync_on_startup(app)

    yield  # 应用运行期间

    # 初始化 ChatBot 服务（可选，延迟初始化也可以）
    # 关闭时：清理监控进程
    if hasattr(app.state, "monitor_process") and app.state.monitor_process:
        proc = app.state.monitor_process
        if proc.is_alive():
            logger.info("正在终止监控进程 (PID: %s)...", proc.pid)
            proc.terminate()
            # 不阻塞事件循环：proc.join 是同步调用，包到 to_thread
            await asyncio.to_thread(proc.join, 5)
            if proc.is_alive():
                logger.warning("监控进程未能在 5 秒内退出，正在强制杀死...")
                proc.kill()
            logger.info("监控进程已清理")

    # 关闭wechatchannel
    if wechat_channel._running:
        await wechat_channel.stop()

    # 关闭时：取消 AgentLoop 任务
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        logger.info("[SHUTDOWN] AgentLoop stopped")

    # 关闭时：停止定时任务调度器
    try:
        schedule_service.shutdown()
        logger.info("[SHUTDOWN] ScheduleService stopped")
    except Exception as e:
        logger.warning("定时任务服务关闭时出现警告: error=%s", e)

    # 关闭时：清理 ChatBot 资源
    try:
        from lifeprism.server.services.chatbot_service import chatbot_service

        await chatbot_service.shutdown()
    except Exception as e:
        logger.warning("ChatBot 服务关闭时出现警告: error=%s", e)

    # 关闭时：推送最终数据到云端（sync → offline 顺序，先同步再告知离线）
    # 关机场景（quick-shutdown）会跳过 sync_once，因为：
    # 1. Windows 关机只给 5 秒，sync_once 需要 1-3 分钟
    # 2. 中途被强杀会导致 parent_hash 不一致
    # 3. 依赖定时同步（≤10 分钟延迟）和下次启动同步补齐
    skip_sync = getattr(app.state, "skip_sync_on_shutdown", False)
    if skip_sync:
        logger.info("[SHUTDOWN] 跳过关闭前同步（关机场景，只发 offline 心跳）")
    elif hasattr(app.state, "sync_client") and app.state.sync_client:
        try:
            await asyncio.to_thread(app.state.sync_client.sync_once)
            logger.info("[SHUTDOWN] 关闭前同步完成")
        except Exception as e:
            logger.warning("[SHUTDOWN] 关闭前同步失败: error=%s", e)

    # 发送 offline 心跳事件（同步完成后通知云端接管）
    # 关机场景也必须发送，让云端立即接管
    # 关机场景（skip_sync=True）使用 2s 超时，避免 10s 网络超时被 Electron 4s 强杀打断
    heartbeat_timeout = 2.0 if skip_sync else 10.0
    try:
        await send_heartbeat("offline", timeout=heartbeat_timeout)
    except Exception as e:
        logger.warning("[SHUTDOWN] 发送 offline 心跳失败: error=%s", e)


# ==================== 创建 FastAPI 应用实例 ====================
print("[STARTUP] 正在创建 FastAPI 应用实例...")
_app_start = time.perf_counter()

app = FastAPI(
    lifespan=lifespan,  # 添加生命周期管理
    title="LifeWatch API",
    description="""
    ## LifePrism 后端 API 服务

    基于 ActivityWatch 数据的个人时间管理和分析平台后端服务。

    ### 功能模块

    - **Dashboard**: 仪表盘数据，包括 Top Apps、Top Titles、分类统计、首页统一数据
    - **Behavior Logs**: 行为日志查询和时间线数据
    - **Categories**: 应用分类管理
    - **Activity Summary**: 活动总结数据
    - **Sync**: 从 ActivityWatch 同步数据

    ### 数据来源

    - **ActivityWatch**: 用户行为数据采集
    - **LLM 分类**: 基于 AI 的应用用途分类
    - **SQLite**: 本地数据持久化存储

    ### 开发状态

    当前大部分 API 返回 **Mock 数据** 用于前端开发和测试。

    真实数据实现将在第二阶段完成。
    """,
)
_log_startup_time("[OK] FastAPI app created", _app_start)

# 配置 CORS 中间件（允许前端跨域访问）
_cors_start = time.perf_counter()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Vue/React 开发服务器
        "http://localhost:3001",  # Vite 端口 (当3000被占用时)
        "http://localhost:5173",  # Vite 默认端口
        "http://localhost:8080",  # 其他可能的前端端口
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)
_log_startup_time("[OK] CORS middleware configured", _cors_start)


# ==================== Shutdown 端点 localhost 限制中间件 ====================
# /shutdown 和 /quick-shutdown 仅允许本机访问，防止局域网内其他设备触发后端关闭
@app.middleware("http")
async def restrict_shutdown_endpoints(request: Request, call_next):
    path = request.url.path
    if path.endswith("/shutdown") or path.endswith("/quick-shutdown"):
        client_host = request.client.host if request.client else ""
        if client_host not in ("127.0.0.1", "::1"):
            logger.warning(
                "[SHUTDOWN] 拒绝非本机的关闭请求: client=%s path=%s",
                client_host,
                path,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Shutdown endpoints only accessible from localhost"},
            )
    return await call_next(request)


# ==================== 全局异常处理器 ====================
print("[STARTUP] 正在注册全局异常处理器...")
_exception_start = time.perf_counter()

from lifeprism.server.errors import to_http_exception
from lifeprism.utils.exceptions import LWBaseError


@app.exception_handler(LWBaseError)
async def lw_base_error_handler(request: Request, exc: LWBaseError):
    """统一处理所有 LWBaseError 子类异常。

    映射关系（由 _fallback_code + ERROR_CODE_TO_STATUS 决定）：
    - NotFoundError       → 404
    - ConflictError       → 409
    - ValidationError     → 422
    - DataAccessError     → 500
    - ExternalServiceError → 503
    """
    http_exc = to_http_exception(exc)
    if http_exc.status_code < 500:
        logger.warning(
            "%s: %s (code=%s, path=%s)", type(exc).__name__, exc.message, exc.code, request.url.path
        )
    else:
        logger.error(
            "%s: %s (code=%s, path=%s)",
            type(exc).__name__,
            exc.message,
            exc.code,
            request.url.path,
            exc_info=True,
        )
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局兜底异常处理器 → 500。捕获所有非 LWBaseError 的未知异常。"""
    logger.error(
        "未处理的异常: type=%s, error=%s, path=%s",
        type(exc).__name__,
        str(exc),
        request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "details": {},
        },
    )


_log_startup_time("[OK] Exception handlers registered (LWBaseError + Exception)", _exception_start)

# ==================== 注册 API 路由 ====================
print("[STARTUP] 正在注册 API 路由...")
_router_start = time.perf_counter()

app.include_router(sync_router, prefix="/api/v2")
app.include_router(category_v2_router, prefix="/api/v2")
app.include_router(activity_v2_router, prefix="/api/v2")
app.include_router(timeline_v2_router, prefix="/api/v2")  # 已包含 /api/v2/timeline 前缀
app.include_router(usage_router, prefix="/api/v2")  # Token 使用统计
app.include_router(goal_router, prefix="/api/v2")  # Goal
app.include_router(chatbot_router, prefix="/api/v2")  # Chatbot
app.include_router(setting_router, prefix="/api/v2")  # Settings
app.include_router(report_router, prefix="/api/v2")  # Report 日报告
app.include_router(being_router, prefix="/api/v2")  # Being 时间悖论测试
app.include_router(taskpool_router, prefix="/api/v2")  # Task Pool
app.include_router(todos_router, prefix="/api/v2")  # Todos 统一接口
app.include_router(system_router, prefix="/api/v2")  # System 系统信息
app.include_router(diary_router, prefix="/api/v2")  # Diary 日记
app.include_router(mood_router, prefix="/api/v2")  # Mood 心情
app.include_router(value_router, prefix="/api/v2")  # Value 价值
app.include_router(commitment_router, prefix="/api/v2")  # Commitment 承诺
app.include_router(habit_router, prefix="/api/v2/habit", tags=["habit"])  # Habit 习惯
app.include_router(custom_records_router, prefix="/api/v2")  # Custom Records 自定义记录
app.include_router(sync_status_router)  # 同步状态查询和手动触发
app.include_router(cloud_config_router)  # 云端配置生成
app.include_router(add_on_router)

_log_startup_time("[OK] API routers registered (21 routers)", _router_start)

# 模块加载阶段总结
_module_load_total = (time.perf_counter() - _startup_timer) * 1000
print(f"\n{'=' * 60}")
print(f"[STARTUP] 模块加载阶段完成！总耗时: {_module_load_total:.2f}ms")
print("[STARTUP] (数据库初始化将在 uvicorn 启动后的 lifespan 阶段执行)")
print(f"{'=' * 60}\n")


@app.get("/", tags=["Root"])
async def root():
    """
    API 根路径

    返回服务基本信息和可用端点导航
    """
    return {
        "service": "LifeWatch API",
        "version": "0.1.0",
        "status": "running",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json",
        },
        "endpoints": {
            "sync": "/api/v2/sync/activitywatch",
            "categories": "/api/v2/categories/apps",
            "timeline": "/api/v2/timeline",
            "activity": "/api/v2/activity",
            "usage": "/api/v2/usage",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    健康检查端点

    用于监控服务运行状态
    """
    return {"status": "healthy", "service": "lifeprism-api", "version": "0.2.0"}


def is_port_available(port: int) -> bool:
    """检查端口是否可用"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # 使用 0.0.0.0 与 uvicorn 绑定地址一致
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def find_available_port(config_path: str = None) -> int:
    """从配置文件读取端口，若被占用则自动递增"""
    import json

    default_port = 8000
    fallback_list = [8000, 8001, 8002, 8003, 8004]  # 默认端口列表
    # 尝试读取配置文件
    if config_path:
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
                server_config = config.get("server", {})
                default_port = server_config.get("backendPort", 8000)
                fallback_list = server_config.get("portFallbackList", fallback_list)
                # 确保用户配置的端口在列表最前面
                if default_port not in fallback_list:
                    fallback_list = [default_port] + fallback_list
                else:
                    fallback_list = [default_port] + [p for p in fallback_list if p != default_port]
                print(
                    f"[STARTUP] 从配置文件读取端口配置: 首选端口={default_port}, 备用列表={fallback_list}"
                )
        except Exception as e:
            logger.warning("未找到 lifeprismData/config/config.json!!")
            print(f"[STARTUP] 读取配置文件失败，使用默认端口: {e}")

    # 按顺序尝试端口
    for port in fallback_list:
        if is_port_available(port):
            logger.debug("[STARTUP] 端口 %s 可用", port)
            return port
        else:
            logger.warning("[STARTUP] 端口 %s 被占用，尝试下一个...", port)

    # 所有端口都被占用，返回默认端口（让 uvicorn 报错）
    print(f"[STARTUP] 警告：所有备用端口都被占用，将尝试使用端口 {default_port}")
    return default_port


if __name__ == "__main__":
    import multiprocessing
    import sys

    import uvicorn

    # Windows 下 multiprocessing 必须调用 freeze_support()
    multiprocessing.freeze_support()
    logger.debug(multiprocessing.current_process().name)  # 之前重复运行的问题在打包环境下还存在？
    # 防止子进程重复启动服务器（只需 2 行代码）
    if multiprocessing.current_process().name != "MainProcess":
        print("===============================")
        print("监控子进程")
        sys.exit(0)

    # 判断是否为打包环境
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        logger.info("正在运行打包环境")
        # settings_manager 已初始化，直接从 settings 获取固定配置路径
        config_path = str(settings.config_base_path / "config" / "config.json")
        print(f"[STARTUP] 打包环境，配置文件路径: {config_path}")
        port = find_available_port(config_path)
    else:
        logger.info("正在运行开发环境")
        # 开发环境：固定使用 8101 端口（避免与生产环境 8000 混淆）
        port = 8101
        print(f"[STARTUP] 开发环境，固定使用端口 {port}")

    print(f"[STARTUP] 后端将在端口 {port} 启动")

    if is_frozen:
        # 生产模式：禁用热重载，启动极快
        uvicorn.run(
            app,  # 直接传入 app 对象，不使用字符串
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True,
        )
    else:
        # 开发模式：启用热重载
        uvicorn.run(
            "lifeprism.server.main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            reload_dirs=["lifeprism"],  # 只监控 Python 代码目录
            reload_excludes=["__pycache__", "*.pyc", ".git", "*.db", "lifeprism.egg-info"],
            log_level="info",
            access_log=True,
        )
