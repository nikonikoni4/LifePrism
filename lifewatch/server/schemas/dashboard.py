"""
仪表盘相关数据模型 - Pydantic V2 兼容版本
"""

from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import date


class TopItem(BaseModel):
    """Top 排行项（应用或标题）"""
    model_config = ConfigDict(json_schema_extra={"example": {
        "name": "chrome.exe", "duration": 4500, "percentage": 41.7
    }})
    
    name: str
    duration: int 
    percentage: float


class CategorySummary(BaseModel):
    """分类统计摘要"""
    model_config = ConfigDict(json_schema_extra={"example": {
        "category": "工作/学习", "duration": 7200, "percentage": 66.7
    }})
    
    category: str
    duration: int
    percentage: float


class DashboardSummary(BaseModel):
    """仪表盘数据汇总"""
    top_apps: List[TopItem]
    top_titles: List[TopItem]
    categories_by_default: List[CategorySummary]
    categories_by_goals: List[CategorySummary]


class DashboardResponse(BaseModel):
    """仪表盘API响应"""
    date: date
    total_active_time: int
    summary: DashboardSummary
