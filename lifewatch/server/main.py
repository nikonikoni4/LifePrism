"""
LifeWatch Server - FastAPI 主应用程序
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from lifewatch.server.api import (
    dashboard_router,
    behavior_router,
    categories_router,
    sync_router,
    activity_summary_router
)

# 创建 FastAPI 应用实例
app = FastAPI(
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
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(behavior_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(activity_summary_router, prefix="/api/v1")



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
            "homepage": "/api/v1/dashboard/homepage",
            "dashboard": "/api/v1/dashboard",
            "behavior_logs": "/api/v1/behavior/logs",
            "timeline": "/api/v1/behavior/timeline",
            "categories": "/api/v1/categories/apps",
            "activity_summary": "/api/v1/activity-summary",
            "sync": "/api/v1/sync/activitywatch"
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
        "version": "0.1.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "lifewatch.server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式：代码变更自动重启
        log_level="info"
    )
