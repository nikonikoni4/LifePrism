"""
数据同步相关数据模型 - Pydantic V2 兼容版本
"""

from pydantic import BaseModel
from typing import Optional


class SyncRequest(BaseModel):
    """增量同步请求参数（从数据库最新时间开始同步到现在）"""
    auto_classify: bool = True


class SyncTimeRangeRequest(BaseModel):
    """时间范围同步请求参数"""
    start_time: str  # Format: YYYY-MM-DD HH:MM:SS
    end_time: str    # Format: YYYY-MM-DD HH:MM:SS
    auto_classify: bool = True


class SyncResponse(BaseModel):
    """同步响应结果"""
    status: str
    synced_events: int
    new_apps_classified: int
    duration: float
    message: Optional[str] = None
