"""
LifeWatch Server - FastAPI 主应用程序
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from lifewatch.server.api import (
    sync_router,
    category_v2_router, 
    activity_v2_router, 
    timeline_v2_router,
    usage_router
)
from lifewatch.storage.lw_table_manager import init_database
from lifewatch.server.providers.category_color_provider import initialize_category_colors
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    在应用启动时初始化数据库
    注：数据库连接池清理由 DatabaseManager 的 atexit 处理
    """
    # 启动时：初始化数据库表结构
    logger.info("正在初始化 LifeWatch 数据库...")
    try:
        init_database()
        initialize_category_colors()
        logger.info("✅ 数据库初始化成功")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        raise
    
    yield  # 应用运行期间
    
    # 关闭时：无需额外清理（全局单例通过 atexit 自动清理）


# 创建 FastAPI 应用实例
app = FastAPI(
    lifespan=lifespan,  # 添加生命周期管理
    title="LifeWatch API",
    description="""
    ## LifeWatch-AI 后端 API 服务
    
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

# 配置 CORS 中间件（允许前端跨域访问）
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

# 注册 API 路由
app.include_router(sync_router, prefix="/api/v2")
# V2 API 路由
app.include_router(category_v2_router, prefix="/api/v2")
app.include_router(activity_v2_router, prefix="/api/v2")
app.include_router(timeline_v2_router, prefix="/api/v2")  # 已包含 /api/v2/timeline 前缀
app.include_router(usage_router, prefix="/api/v2")  # Token 使用统计



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
        "service": "lifewatch-api",
        "version": "0.2.0"
    }


if __name__ == "__main__":
    import uvicorn
    import os
    
    # 通过环境变量判断是否为开发模式
    # 开发时设置 LIFEWATCH_DEV=1，打包后默认为生产模式
    is_dev_mode = os.environ.get("LIFEWATCH_DEV", "0") == "1"
    is_dev_mode = True
    if is_dev_mode:
        # 开发模式：启用热重载
        uvicorn.run(
            "lifewatch.server.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["lifewatch"],  # 只监控 Python 代码目录
            reload_excludes=["__pycache__", "*.pyc", ".git","lifewatch_ai.db"],
            log_level="info"
        )
    else:
        # 生产模式：禁用热重载，启动极快
        uvicorn.run(
            app,  # 直接传入 app 对象，不使用字符串
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
