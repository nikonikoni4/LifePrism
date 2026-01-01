"""
API路由模块
"""


from .sync import router as sync_router
from .category_api import router as category_v2_router
from .activity_api import router as activity_v2_router
from .timeline_api import router as timeline_v2_router
from .usage import router as usage_router
from .goal_api import router as goal_router
from .chatbot_api import router as chatbot_router
from .setting_api import router as setting_router
from .reward_api import router as reward_router

__all__ = [
    "dashboard_router",
    "behavior_router",
    "categories_router",
    "sync_router",
    "activity_summary_router",
    "category_v2_router",
    "activity_v2_router",
    "timeline_v2_router",
    "usage_router",
    "goal_router",
    "chatbot_router",
    "setting_router",
    "reward_router",
]


