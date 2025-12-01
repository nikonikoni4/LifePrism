"""
统计分析相关数据模型 - Pydantic V2 兼容版本
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import date


class DailyStatistics(BaseModel):
    """每日统计数据"""
    date: date
    total_duration: int
    work_duration: int
    entertainment_duration: int
    other_duration: int
    top_app: Optional[str] = None
    top_category_default: Optional[str] = None
    top_category_goals: Optional[str] = None


class AnalyticsSummary(BaseModel):
    """统计汇总信息"""
    period: dict
    group_by: str
    statistics: List[DailyStatistics]


class AnalyticsResponse(BaseModel):
    """统计分析API响应"""
    summary: AnalyticsSummary
