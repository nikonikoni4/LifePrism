"""
Business logic services

V2 架构：
- Service 类通过单例导出，在 API 层复用
- Builder/Helper 模块作为纯函数模块导入
"""

# 旧的 Service 类导出（逐步废弃）
from .dashboard_service import DashboardService
from .behavior_service import BehaviorService
from .sync_service import SyncService
from .data_processing_service import DataProcessingService

# V2 纯函数模块
from . import activity_stats_builder

# V2 Service 单例
from .activity_v2_service import ActivityService
from .category_v2_service import CategoryService

# 创建单例实例
activity_service = ActivityService()
category_service = CategoryService()

__all__ = [
    # 旧类（逐步废弃）
    "DashboardService",
    "BehaviorService", 
    "SyncService",
    "DataProcessingService",
    # V2 纯函数模块
    "activity_stats_builder",
    # V2 单例
    "activity_service",
    "category_service",
]
