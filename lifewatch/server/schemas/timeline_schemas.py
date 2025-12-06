"""
Timeline API 响应模式定义
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TimelineEventSchema(BaseModel):
    """Timeline 单个事件模型"""
    id: str = Field(..., description="事件唯一标识符")
    start_time: float = Field(..., alias="startTime", description="开始时间（小时浮点数，如 9.5 表示 09:30）")
    end_time: float = Field(..., alias="endTime", description="结束时间（小时浮点数）")
    title: str = Field(..., description="窗口标题或应用名称")
    category: str = Field(..., description="主分类ID")
    category_name: str = Field(..., alias="categoryName", description="主分类名称")
    category_color: str = Field(..., alias="categoryColor", description="主分类颜色 (Hex)")
    sub_category_id: Optional[str] = Field(None, alias="subCategoryId", description="子分类ID")
    sub_category_name: Optional[str] = Field(None, alias="subCategoryName", description="子分类名称")
    sub_category_color: Optional[str] = Field(None, alias="subCategoryColor", description="子分类颜色 (Hex)")
    description: str = Field(..., description="事件描述（app_description + title_description 组合）")
    device_type: str = Field(default="pc", alias="deviceType", description="数据来源设备类型")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "evt_123456",
                "startTime": 9.5,
                "endTime": 10.25,
                "title": "Visual Studio Code - main.py",
                "category": "work",
                "categoryName": "工作/学习",
                "subCategoryId": "coding",
                "subCategoryName": "编程",
                "description": "代码编辑器 - 编写 Python 代码",
                "deviceType": "pc"
            }
        }


class TimelineResponse(BaseModel):
    """Timeline 响应模型"""
    date: str = Field(..., description="日期，格式：YYYY-MM-DD")
    events: List[TimelineEventSchema] = Field(..., description="事件列表")
    current_time: Optional[float] = Field(None, alias="currentTime", description="当前时间（小时浮点数）")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "date": "2023-10-25",
                "events": [
                    {
                        "id": "evt_123456",
                        "startTime": 9.5,
                        "endTime": 10.25,
                        "title": "Visual Studio Code - main.py",
                        "category": "work",
                        "categoryName": "工作/学习",
                        "subCategoryId": "coding",
                        "subCategoryName": "编程",
                        "description": "代码编辑器 - 编写 Python 代码",
                        "deviceType": "pc"
                    }
                ],
                "currentTime": 14.05
            }
        }


# 导入共享的图表组件 schema
from lifewatch.server.schemas.dashboard_schemas import ChartSegment, BarConfig


class TimelineOverviewResponse(BaseModel):
    """Timeline Overview 响应（用于缩略图点击详情）"""
    title: str = Field(..., description="标题")
    sub_title: str = Field(..., alias="subTitle", description="副标题")
    total_tracked_minutes: int = Field(..., alias="totalTrackedMinutes", description="总追踪时长（分钟）")
    pie_data: List[ChartSegment] = Field(..., alias="pieData", description="饼图数据")
    bar_keys: List[BarConfig] = Field(..., alias="barKeys", description="柱状图配置")
    bar_data: List[dict] = Field(..., alias="barData", description="柱状图数据（6个固定刻度）")
    details: Optional[dict] = Field(None, description="子分类详情（递归结构）")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "title": "12:00 - 13:00 Overview",
                "subTitle": "Activity breakdown for selected time range",
                "totalTrackedMinutes": 45,
                "pieData": [
                    {"key": "work", "name": "工作/学习", "value": 30, "color": "#5B8FF9"}
                ],
                "barKeys": [
                    {"key": "work", "label": "工作/学习", "color": "#5B8FF9"}
                ],
                "barData": [
                    {"timeRange": "12:00", "work": 5},
                    {"timeRange": "12:10", "work": 8}
                ]
            }
        }

