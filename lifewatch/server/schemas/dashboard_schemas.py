"""
Dashboard Schema 定义
用于 Dashboard 相关 API 的请求和响应模型
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChartSegment(BaseModel):
    """饼图数据项"""
    key: str = Field(..., description="分类唯一标识符（用于逻辑处理）")
    name: str = Field(..., description="显示名称")
    value: int = Field(..., description="时长（分钟）")
    color: str = Field(..., description="颜色（十六进制格式）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "work",
                "name": "Work/Study",
                "value": 480,
                "color": "#5B8FF9"
            }
        }


class BarConfig(BaseModel):
    """柱状图配置项（用于 Legend 和堆叠顺序）"""
    key: str = Field(..., description="数据键（与 barData 中的键对应）")
    label: str = Field(..., description="图例标签")
    color: str = Field(..., description="颜色（十六进制格式）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "work",
                "label": "Work",
                "color": "#5B8FF9"
            }
        }




class TimeOverviewResponse(BaseModel):
    """Time Overview 完整响应"""
    title: str = Field(..., description="标题")
    sub_title: str = Field(..., alias="subTitle", description="副标题")
    total_tracked_minutes: int = Field(..., alias="totalTrackedMinutes", description="总追踪时长（分钟）")
    pie_data: List[ChartSegment] = Field(..., alias="pieData", description="饼图数据")
    bar_keys: List[BarConfig] = Field(..., alias="barKeys", description="柱状图配置")
    bar_data: List[Dict[str, Any]] = Field(..., alias="barData", description="24小时分布数据")
    details: Optional[Dict[str, 'TimeOverviewResponse']] = Field(None, description="子分类详情（递归结构）")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "title": "Time Overview",
                "subTitle": "Activity breakdown & timeline",
                "totalTrackedMinutes": 780,
                "pieData": [
                    {"key": "work", "name": "Work/Study", "value": 480, "color": "#5B8FF9"}
                ],
                "barKeys": [
                    {"key": "work", "label": "Work", "color": "#5B8FF9"}
                ],
                "barData": [
                    {"timeRange": "0-2", "work": 0, "entertainment": 30, "other": 90}
                ],
                "details": {
                    "Work/Study": {
                        "title": "Work/Study Details",
                        "subTitle": "Detailed breakdown",
                        "totalTrackedMinutes": 480,
                        "pieData": [],
                        "barKeys": [],
                        "barData": []
                    }
                }
            }
        }
