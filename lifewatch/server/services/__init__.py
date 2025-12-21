"""
Business logic services

V2 架构：
- Service 类通过单例导出，在 API 层复用
- Builder/Helper 模块作为纯函数模块导入
"""

# 旧的 Service 类导出（逐步废弃）
from .activity_service import ActivityService
from .category_service import CategoryService

# V2 Service 单例
from .activity_service import ActivityService
from .category_service import CategoryService

# V2 纯函数服务模块
from . import timeline_service

# 创建单例实例
activity_service = ActivityService()
category_service = CategoryService()

__all__ = [
    # 旧类（逐步废弃）
    "ActivityService",
    "CategoryService", 
    # V2 单例
    "activity_service",
    "category_service",
    # V2 纯函数模块
    "timeline_service",
]

