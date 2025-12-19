"""
Pydantic schemas for request/response models
"""

from .response import StandardResponse, PaginatedResponse
from .dashboard import (
    DashboardResponse,
    TopItem,
    CategorySummary,
    DashboardSummary
)
from .behavior import (
    BehaviorLogItem,
    BehaviorLogsResponse,
    TimelineResponse,
    TimelineEvent,
    TimelineSlot
)
from .categories import (
    AppCategory,
    AppCategoryList,
    UpdateCategoryRequest
)
from .homepage import HomepageResponse
from .sync import (
    SyncRequest,
    SyncResponse
)


__all__ = [
    "StandardResponse",
    "PaginatedResponse",
    "DashboardResponse",
    "TopItem",
    "CategorySummary",
    "DashboardSummary",
    "BehaviorLogItem",
    "BehaviorLogsResponse",
    "TimelineResponse",
    "TimelineEvent",
    "TimelineSlot",
    "AppCategory",
    "AppCategoryList",
    "UpdateCategoryRequest",
    "HomepageResponse",
    "SyncRequest",
    "SyncResponse"
]
