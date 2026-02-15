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
from .report_api import router as report_router
from .being_api import router as being_router
from .taskpool_api import router as taskpool_router
from .todos_api import router as todos_router
from .system_api import router as system_router
from .diary_api import router as diary_router
from .mood_api import router as mood_router
from .value_commitment_api import value_router, commitment_router

__all__ = [
    "sync_router",
    "category_v2_router",
    "activity_v2_router",
    "timeline_v2_router",
    "usage_router",
    "goal_router",
    "chatbot_router",
    "setting_router",
    "report_router",
    "being_router",
    "taskpool_router",
    "todos_router",
    "system_router",
    "diary_router",
    "mood_router",
    "value_router",
    "commitment_router",
]

