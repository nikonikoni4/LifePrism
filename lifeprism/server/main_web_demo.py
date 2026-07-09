"""
LifePrism Linux Web Demo 启动入口

运行形态：FastAPI + 静态前端 + Agent（无 Monitor，无 ScheduleService）

与 Windows 桌面完整版（main.py）的区别：
- 不启动 Monitor 模块（Linux 上不支持 Windows API）
- 不启动 ScheduleService（依赖 Monitor 采集数据）
- 固定监听 0.0.0.0:8101（不读取 config.json 端口配置）
- 不处理 multiprocessing.freeze_support() / is_frozen 打包逻辑

启动命令：
    uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101
"""

# ==================== 核心库导入 ====================
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

# ==================== 配置初始化（必须在所有 lifeprism 模块之前） ====================
from lifeprism.config.settings_manager import settings  # noqa: F401

# ==================== API 路由导入 ====================
from lifeprism.server.api import (
    activity_v2_router,
    being_router,
    category_v2_router,
    chatbot_router,
    commitment_router,
    custom_records_router,
    diary_router,
    goal_router,
    habit_router,
    mood_router,
    report_router,
    setting_router,
    sync_router,
    system_router,
    taskpool_router,
    timeline_v2_router,
    todos_router,
    usage_router,
    value_router,
)
from lifeprism.server.api.add_on_api import router as add_on_router

# ==================== 共享启动模块 ====================
from lifeprism.server.bootstrap import (
    init_database_full,
    start_agent_and_channel,
    stop_agent_and_channel,
)
from lifeprism.server.errors import to_http_exception
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import LWBaseError

settings.set_runtime_config("run_mode", "web_demo")

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Web Demo 应用生命周期管理

    启动：日志 → 数据库初始化 → Agent + Channel
    关闭：Agent + Channel
    不包含 Monitor 和 ScheduleService。
    """
    from lifeprism.utils.logger import enable_uvicorn_file_logging

    enable_uvicorn_file_logging()

    # 数据库初始化
    init_database_full()

    # 生成 Web-Demo 演示数据（每次启动全量重建）
    from scripts.demo import generate_demo_data

    generate_demo_data()

    # 启动 Agent Loop + WeChat Channel
    loop_task, wechat_channel = await start_agent_and_channel()

    yield  # 应用运行期间

    # 关闭 Agent + Channel
    await stop_agent_and_channel(loop_task, wechat_channel)


# ==================== 创建 FastAPI 应用实例 ====================
app = FastAPI(
    lifespan=lifespan,
    title="LifePrism Web Demo API",
    description="""
    ## LifePrism Web Demo 后端 API 服务

    Linux 部署的 Web Demo 模式，提供完整的 API 服务和 Agent 功能。
    不包含 Monitor 数据采集模块。
    """,
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Web Demo 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Demo 只读中间件 ====================
# Web Demo 天然是只读模式，拦截所有写操作（POST/PUT/PATCH/DELETE）


@app.middleware("http")
async def demo_readonly_middleware(request: Request, call_next) -> Response:
    """Web Demo 只读拦截：阻止所有写操作"""
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        # 排除允许的只读操作（如健康检查、系统警告查询）
        allowed_paths = ["/health", "/api/v2/system/warnings"]
        if request.url.path not in allowed_paths:
            logger.info(
                "Demo 只读拦截: method=%s, path=%s, client=%s",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error_code": "DEMO_MODE_READ_ONLY",
                    "message": "Demo 演示网站无法写入数据，请到本地部署或下载安装包",
                    "details": {
                        "github_url": "https://github.com/nikonikoni4/LifePrism",
                        "vote_url": "https://forum.trae.cn/t/topic/70390",
                        "hint": "您可以在 GitHub 下载安装包本地安装,或参与创造力大赛投票",
                    },
                },
            )
    return await call_next(request)


# ==================== 全局异常处理器 ====================
@app.exception_handler(LWBaseError)
async def lw_base_error_handler(request: Request, exc: LWBaseError):
    """统一处理所有 LWBaseError 子类异常。"""
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
    """全局兜底异常处理器 → 500。"""
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


# ==================== 注册 API 路由 ====================
app.include_router(sync_router, prefix="/api/v2")
app.include_router(category_v2_router, prefix="/api/v2")
app.include_router(activity_v2_router, prefix="/api/v2")
app.include_router(timeline_v2_router, prefix="/api/v2")
app.include_router(usage_router, prefix="/api/v2")
app.include_router(goal_router, prefix="/api/v2")
app.include_router(chatbot_router, prefix="/api/v2")
app.include_router(setting_router, prefix="/api/v2")
app.include_router(report_router, prefix="/api/v2")
app.include_router(being_router, prefix="/api/v2")
app.include_router(taskpool_router, prefix="/api/v2")
app.include_router(todos_router, prefix="/api/v2")
app.include_router(system_router, prefix="/api/v2")
app.include_router(diary_router, prefix="/api/v2")
app.include_router(mood_router, prefix="/api/v2")
app.include_router(value_router, prefix="/api/v2")
app.include_router(commitment_router, prefix="/api/v2")
app.include_router(habit_router, prefix="/api/v2/habit", tags=["habit"])
app.include_router(custom_records_router, prefix="/api/v2")
app.include_router(add_on_router)


@app.get("/", tags=["Root"])
async def root():
    """API 根路径"""
    return {
        "service": "LifePrism Web Demo API",
        "version": "0.1.0",
        "status": "running",
        "mode": "web_demo",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "lifeprism-web-demo", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8101,
        log_level="info",
        access_log=True,
    )
