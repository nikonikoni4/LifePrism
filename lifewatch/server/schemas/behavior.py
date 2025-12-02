"""
行为日志相关数据模型 - Pydantic V2 兼容版本
"""

from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime, date


class BehaviorLogItem(BaseModel):
    """单条行为日志"""
    id: str
    timestamp: datetime
    duration: int
    app: str
    title: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    is_multipurpose_app: int = 0


class BehaviorLogsResponse(BaseModel):
    """行为日志列表响应（分页）"""
    total: int
    page: int
    page_size: int
    data: List[BehaviorLogItem]


class TimelineEvent(BaseModel):
    """时间线单个事件"""
    app: str
    title: Optional[str] = None
    duration: int
    category: Optional[str] = None
    sub_category: Optional[str] = None


class TimelineSlot(BaseModel):
    """时间线时间槽"""
    timestamp: datetime
    duration: int
    events: List[TimelineEvent]


class TimelineResponse(BaseModel):
    """时间线API响应"""
    date: date
    interval: str
    timeline: List[TimelineSlot]
