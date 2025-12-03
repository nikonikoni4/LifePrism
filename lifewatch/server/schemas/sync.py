"""
数据同步相关数据模型 - Pydantic V2 兼容版本
"""

from pydantic import BaseModel
from typing import Optional


class SyncRequest(BaseModel):
    """同步请求参数"""
    hours: Optional[int] = 24
    auto_classify: bool = True
    use_incremental_sync: bool = False


class SyncResponse(BaseModel):
    """同步响应结果"""
    status: str
    synced_events: int
    new_apps_classified: int
    duration: float
    message: Optional[str] = None
