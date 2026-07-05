"""
LifeWatch Server - FastAPI 主应用程序
"""

# ==================== 启动时间追踪 ====================
import time
_startup_timer = time.perf_counter()

def _log_startup_time(step_name: str, start_time: float) -> float:
    """记录启动步骤耗时并返回当前时间"""
    current = time.perf_counter()
    elapsed = (current - start_time) * 1000  # 转换为毫秒
    total = (current - _startup_timer) * 1000
    # 关闭打印
    # print(f"[STARTUP] {step_name}: {elapsed:.2f}ms (累计: {total:.2f}ms)")
    return current

_step_start = _startup_timer
print(f"\n{'='*60}")
print("[STARTUP] 开始追踪服务器启动时间...")
print(f"{'='*60}")

# ==================== 核心库导入 ====================
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
_step_start = _log_startup_time("[OK] Core imports (contextlib, fastapi, logging)", _step_start)

# ==================== 配置初始化（必须在所有 lifeprism 模块之前） ====================
print("[STARTUP] 正在初始化配置管理器...")
_config_start = time.perf_counter()
from lifeprism.config.settings_manager import settings  # noqa: E402 - 必须最先导入，初始化路径和日志
_log_startup_time("[OK] settings_manager initialized (paths + file logging)", _config_start)

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
from lifeprism.server.api import value_router, commitment_router
_log_startup_time("  - value_router + commitment_router", _import_start)

_import_start = time.perf_counter()
from lifeprism.server.api import habit_router
_log_startup_time("  - habit_router", _import_start)

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
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    在应用启动时初始化数据库
    注：数据库连接池清理由 DatabaseManager 的 atexit 处理
    """
    print(f"\n{'='*60}")
    print("[STARTUP] 进入 lifespan - 应用初始化阶段")
    print(f"{'='*60}")
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

        # 集成内置监控进程
        if settings._config.get("monitor_type") == "lifeprism":
            logger.info("检测到 monitor_type 为 'lifeprism'，正在启动内置监控进程...")
            try:
                from lifeprism.monitor.windows_monitor.main import start_monitor_process
                app.state.monitor_process = start_monitor_process()
                logger.info("内置监控进程启动成功")
            except Exception as e:
                logger.error("启动内置监控进程失败: error=%s", e)
                app.state.monitor_process = None
        else:
            app.state.monitor_process = None

        # 启动channel
        from lifeprism.llm.channel import wechat_channel
        try:
            await wechat_channel.start()
            logger.info("微信渠道启动成功")
        except Exception as e:
            logger.error("启动微信渠道失败: error=%s", e)

        _total_lifespan = (time.perf_counter() - _startup_timer) * 1000
        print(f"\n{'='*60}")
        print(f"[STARTUP] [DONE] App init complete! Total: {_total_lifespan:.2f}ms")
        print(f"{'='*60}\n")
        
        logger.info("[DONE] Database initialized successfully")
    except Exception as e:
        logger.error("[ERROR] Database init failed: error=%s", e)
        raise
    
    



    # 启动定时任务调度器
    from lifeprism.server.services.schedule_service import schedule_service
    try:
        schedule_service.start()
        logger.info("[STARTUP] ScheduleService started")
    except Exception as e:
        logger.error("启动定时任务服务失败: error=%s", e)

    # 初始化 ChatBot 服务和 AgentLoop
    from lifeprism.llm.agent.loop import agent_loop
    import asyncio
    loop_task = asyncio.create_task(agent_loop.loop())
    logger.info("[STARTUP] AgentLoop started")

    yield  # 应用运行期间

    # 初始化 ChatBot 服务（可选，延迟初始化也可以）
    # 关闭时：清理监控进程
    if hasattr(app.state, "monitor_process") and app.state.monitor_process:
        proc = app.state.monitor_process
        if proc.is_alive():
            logger.info("正在终止监控进程 (PID: %s)...", proc.pid)
            proc.terminate()
            proc.join(timeout=5)
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

# ==================== 全局异常处理器 ====================
print("[STARTUP] 正在注册全局异常处理器...")
_exception_start = time.perf_counter()

from lifeprism.utils.exceptions import LWBaseError
from lifeprism.server.errors import to_http_exception


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
            "%s: %s (code=%s, path=%s)",
            type(exc).__name__, exc.message, exc.code, request.url.path
        )
    else:
        logger.error(
            "%s: %s (code=%s, path=%s)",
            type(exc).__name__, exc.message, exc.code, request.url.path,
            exc_info=True
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
        type(exc).__name__, str(exc), request.url.path,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "details": {},
        }
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
app.include_router(add_on_router)

_log_startup_time("[OK] API routers registered (20 routers)", _router_start)

# 模块加载阶段总结
_module_load_total = (time.perf_counter() - _startup_timer) * 1000
print(f"\n{'='*60}")
print(f"[STARTUP] 模块加载阶段完成！总耗时: {_module_load_total:.2f}ms")
print(f"[STARTUP] (数据库初始化将在 uvicorn 启动后的 lifespan 阶段执行)")
print(f"{'='*60}\n")



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
            "openapi_spec": "/openapi.json"
        },
        "endpoints": {
            "sync": "/api/v2/sync/activitywatch",
            "categories": "/api/v2/categories/apps",
            "timeline": "/api/v2/timeline",
            "activity": "/api/v2/activity",
            "usage": "/api/v2/usage"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    健康检查端点
    
    用于监控服务运行状态
    """
    return {
        "status": "healthy",
        "service": "lifeprism-api",
        "version": "0.2.0"
    }


def is_port_available(port: int) -> bool:
    """检查端口是否可用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # 使用 0.0.0.0 与 uvicorn 绑定地址一致
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def find_available_port(config_path: str = None) -> int:
    """从配置文件读取端口，若被占用则自动递增"""
    import json
    
    default_port = 8000
    fallback_list = [8000, 8001, 8002, 8003, 8004] # 默认端口列表
    # 尝试读取配置文件
    if config_path:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                server_config = config.get('server', {})
                default_port = server_config.get('backendPort', 8000)
                fallback_list = server_config.get('portFallbackList', fallback_list)
                # 确保用户配置的端口在列表最前面
                if default_port not in fallback_list:
                    fallback_list = [default_port] + fallback_list
                else:
                    fallback_list = [default_port] + [p for p in fallback_list if p != default_port]
                print(f"[STARTUP] 从配置文件读取端口配置: 首选端口={default_port}, 备用列表={fallback_list}")
        except Exception as e:
            logger.warning("未找到 lifeprismData/config/config.json!!")
            print(f"[STARTUP] 读取配置文件失败，使用默认端口: {e}")
    
    # 按顺序尝试端口
    for port in fallback_list:
        if is_port_available(port):
            logger.info("[STARTUP] 端口 %s 可用", port)
            return port
        else:
            logger.warning("[STARTUP] 端口 %s 被占用，尝试下一个...", port)

    # 所有端口都被占用，返回默认端口（让 uvicorn 报错）
    print(f"[STARTUP] 警告：所有备用端口都被占用，将尝试使用端口 {default_port}")
    return default_port


if __name__ == "__main__":
    import uvicorn
    import os
    import sys
    import multiprocessing

    # Windows 下 multiprocessing 必须调用 freeze_support()
    multiprocessing.freeze_support()
    logger.warning(multiprocessing.current_process().name) # 之前重复运行的问题在打包环境下还存在？
    # 防止子进程重复启动服务器（只需 2 行代码）
    if multiprocessing.current_process().name != 'MainProcess':
        print("===============================")
        print("监控子进程")
        sys.exit(0)

    # 判断是否为打包环境
    is_frozen = getattr(sys, 'frozen', False)

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
            access_log=True
        )
    else:
        # 开发模式：启用热重载
        uvicorn.run(
            "lifeprism.server.main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            reload_dirs=["lifeprism"],  # 只监控 Python 代码目录
            reload_excludes=["__pycache__", "*.pyc", ".git","*.db","lifeprism.egg-info"],
            log_level="info",
            access_log=True
        ) 
