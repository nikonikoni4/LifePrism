"""
Business logic services

V2 架构：
- Service 类通过单例导出，在 API 层复用（适用于有状态或需要缓存的服务）
- Builder/Helper 模块作为纯函数模块导入
"""


# V2 Service 单例（有状态或需要缓存的服务）
from .activity_service import ActivityService
from .category_service import CategoryService

# V2 纯函数服务模块
from . import timeline_service
from . import usage_service

# 创建单例实例（仅用于有状态或需要缓存的服务）
activity_service = ActivityService()
category_service = CategoryService()

__all__ = [
    # V2 单例（有状态服务）
    "activity_service",
    "category_service",
    # V2 纯函数模块
    "timeline_service",
    "usage_service",
]

