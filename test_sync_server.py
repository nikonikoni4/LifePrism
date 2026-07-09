"""云端同步 API 测试服务器

启动一个仅包含 sync_cloud_router 的 FastAPI 服务，用于端到端同步测试。
模拟 main_agent_only.py 的启动流程（cloud_init 初始化 + 数据库初始化 + FastAPI），
但不启动 Agent Loop 和 WeChat Channel，确保同步 API 稳定运行。

使用 importlib 直接加载 sync_cloud_api 模块，绕过 server.api.__init__.py 的重导入链。
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

# 确保使用 explore\LifePrism 目录下的 lifeprism 模块
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from lifeprism.config.cloud_initializer import CloudInitializer
from lifeprism.config.settings_manager import settings
from lifeprism.server.bootstrap import init_database_full
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import LWBaseError

logger = get_logger(__name__)


async def _lw_base_error_handler(request: Request, exc: LWBaseError):
    from lifeprism.server.errors import to_http_exception
    http_exc = to_http_exception(exc)
    logger.warning("LWBaseError: %s (code=%s, path=%s)", exc.message, exc.code, request.url.path)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


async def _global_exception_handler(request: Request, exc: Exception):
    logger.error("未处理异常: %s, path=%s", str(exc), request.url.path, exc_info=True)
    return JSONResponse(status_code=500, content={"error_code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": {}})


def _load_sync_cloud_router():
    """使用 importlib 直接加载 sync_cloud_api 模块，绕过 __init__.py 导入链"""
    module_path = Path(__file__).parent / "lifeprism" / "server" / "api" / "sync_cloud_api.py"
    spec = importlib.util.spec_from_file_location("lifeprism.server.api.sync_cloud_api", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lifeprism.server.api.sync_cloud_api"] = module
    spec.loader.exec_module(module)
    return module.router


async def main():
    """启动云端同步 API 测试服务器"""
    print("=" * 60)
    print("[TEST SERVER] 云端同步 API 测试服务器启动")
    print(f"[TEST SERVER] 数据路径: {settings.lifeprism_data_path}")
    print("=" * 60)

    # 1. CloudInitializer 处理 cloud_init.yaml
    initializer = CloudInitializer(settings.lifeprism_data_path)
    if initializer.should_initialize():
        logger.info("检测到 cloud_init.yaml，开始云端配置初始化...")
        initializer.initialize()
    initializer.validate_monitor_type()
    # 重新加载配置（CloudInitializer 写入了 config.yaml，但 settings 单例在之前已初始化）
    settings.reload()
    logger.info("[TEST SERVER] CloudInitializer 完成，配置已重新加载")

    # 2. 数据库初始化
    logger.info("[TEST SERVER] 正在初始化数据库...")
    init_database_full()
    logger.info("[TEST SERVER] 数据库初始化完成")

    # 3. 直接加载 sync_cloud_router（绕过 __init__.py）
    sync_cloud_router = _load_sync_cloud_router()
    logger.info("[TEST SERVER] sync_cloud_router 加载完成")

    # 4. 创建 FastAPI 实例（仅同步 API）
    app = FastAPI(
        title="LifePrism Sync API Test Server",
        description="云端同步 API 测试服务（仅数据同步）",
        version="1.0.0",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(sync_cloud_router)
    app.add_exception_handler(LWBaseError, _lw_base_error_handler)
    app.add_exception_handler(Exception, _global_exception_handler)
    logger.info("[TEST SERVER] FastAPI 实例创建完成（仅同步 API）")

    # 5. 启动 uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8102,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("[TEST SERVER] FastAPI 启动: host=0.0.0.0, port=8102")

    print("\n[TEST SERVER] 服务已启动，等待测试请求...")
    print("[TEST SERVER] 按 Ctrl+C 停止\n")

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
