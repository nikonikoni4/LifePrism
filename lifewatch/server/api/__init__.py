"""
API路由模块
"""

from .dashboard import router as dashboard_router
from .behavior import router as behavior_router
from .categories import router as categories_router
from .analytics import router as analytics_router
from .sync import router as sync_router

__all__ = [
    "dashboard_router",
    "behavior_router",
    "categories_router",
    "analytics_router",
    "sync_router"
]
