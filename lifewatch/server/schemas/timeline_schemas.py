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
    sub_category_id: Optional[str] = Field(None, alias="subCategoryId", description="子分类ID")
    sub_category_name: Optional[str] = Field(None, alias="subCategoryName", description="子分类名称")
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
