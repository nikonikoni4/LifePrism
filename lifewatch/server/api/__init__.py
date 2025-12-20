"""
API路由模块
"""


from .sync import router as sync_router
from .category_v2_api import router as category_v2_router
from .activity_v2_api import router as activity_v2_router
from .timeline_v2_api import router as timeline_v2_router

__all__ = [
    "dashboard_router",
    "behavior_router",
    "categories_router",
    "sync_router",
    "activity_summary_router",
    "category_v2_router",
    "activity_v2_router",
    "timeline_v2_router",
]

