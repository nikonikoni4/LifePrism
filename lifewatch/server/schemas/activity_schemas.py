"""
Activity V2 API Schema 定义

用于 Activity 统计、日志等接口的请求和响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ============================================================================
# Include 选项模型
# ============================================================================

class ActivityStatsIncludeOptions(BaseModel):
    """
    活动统计 include 选项
    
    用于在 API 层解析 include 字符串后，以类型安全的方式传递给 Service 层
    """
    include_activity_summary: bool = Field(default=True, description="是否包含活动摘要条形图")
    include_time_overview: bool = Field(default=True, description="是否包含时间概览")
    include_top_title: bool = Field(default=True, description="是否包含热门标题")
    include_top_app: bool = Field(default=True, description="是否包含热门应用")
    include_todolist: bool = Field(default=False, description="是否包含待办事项")
    
    @classmethod
    def from_include_string(cls, include_str: str) -> "ActivityStatsIncludeOptions":
        """
        从逗号分隔的字符串解析选项
        
        Args:
            include_str: 如 "activity_summary,time_overview,top_title"
            
        Returns:
            ActivityStatsIncludeOptions 实例
        """
        include_set = {item.strip().lower() for item in include_str.split(',')}
        return cls(
            include_activity_summary='activity_summary' in include_set,
            include_time_overview='time_overview' in include_set,
            include_top_title='top_title' in include_set,
            include_top_app='top_app' in include_set,
            include_todolist='todolist' in include_set
        )


# ============================================================================
# 响应数据模型（基础结构，具体字段待业务实现时补充）
# ============================================================================

# -------------------------------ActivitySummaryData-------------------------

class DailyActivitiesData(BaseModel):
    """每日活动数据项"""
    date: str = Field(..., description="日期（YYYY-MM-DD 格式）", alias="date")
    duration: int = Field(..., description="活动时长（秒）", alias="duration")
    percentage: int = Field(..., description="活动时长占比（%）", alias="activeTimePercentage")
    color: str = Field(..., description="分类颜色（十六进制格式）", alias="color")
    class Config:
        populate_by_name = True
from lifewatch.server.schemas.category_schemas import CategoryTreeItem
class ActivitySummaryData(BaseModel):
    """活动摘要条形图数据（框架）"""
    daily_activities: List[DailyActivitiesData] = Field(..., description="每日活动数据", alias="dailyActivities")
    category_tree: Optional[List[CategoryTreeItem]] = Field(default=None, description="分类树", alias="categoryTree")
    
    class Config:
        populate_by_name = True    

# -------------------------------TimeOverviewData-------------------------

class ChartSegment(BaseModel):
    """饼图数据项"""
    key: str = Field(..., description="分类唯一标识符（用于逻辑处理）")
    name: str = Field(..., description="显示名称")
    value: int = Field(..., description="时长（分钟）")
    color: str = Field(..., description="颜色（十六进制格式）")
    title: str = Field(default="", description="app层的标题显示,显示该应用最长的3个title")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "work",
                "name": "Work/Study",
                "value": 480,
                "color": "#5B8FF9",
                "title": ""
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


class TimeOverviewData(BaseModel):
    """Time Overview 完整响应"""
    title: str = Field(..., description="旭日图标题") 
    sub_title: str = Field(..., alias="subTitle", description="旭日图副标题")
    total_tracked_minutes: int = Field(..., alias="totalTrackedMinutes", description="总追踪时长（分钟）")
    total_range_minutes: Optional[int] = Field(default=None, alias="totalRangeMinutes", description="时间范围总分钟数（用于计算百分比的分母）")
    pie_data: List[ChartSegment] = Field(..., alias="pieData", description="旭日图数据")
    bar_keys: List[BarConfig] = Field(..., alias="barKeys", description="柱状图配置")
    bar_data: List[Dict[str, Any]] = Field(..., alias="barData", description="时间分布数据")
    details: Optional[Dict[str, 'TimeOverviewData']] = Field(None, description="子分类详情（递归结构）")
    
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
class TopTitleData(BaseModel):
    """热门标题数据（框架）"""
    name: str = Field(..., description="窗口标题")
    duration: int = Field(..., description="活跃时长（秒）")
    percentage: int = Field(..., description="占比（%）")
class TopAppData(BaseModel):
    """热门应用数据（框架）"""
    name: str = Field(..., description="应用名称")
    duration: int = Field(..., description="活跃时长（秒）")
    percentage: int = Field(..., description="占比（%）")

class TodoListData(BaseModel):
    """待办事项数据（框架）"""
    id: int = Field(..., description="待办事项ID")
    name: str = Field(..., description="待办事项名称")
    is_completed: bool = Field(..., description="是否完成",alias="isCompleted")
    link_to_goal: int = Field(..., description="关联目标ID",alias="linkToGoal")
    class Config:
        populate_by_name = True

# ============================================================================
# API 响应模型
# ============================================================================
from lifewatch.server.schemas.category_schemas import CategoryDef
class ActivityStatsResponse(BaseModel):
    """GET /activity/stats 响应"""
    activity_summary: Optional[ActivitySummaryData] = Field(default=None, description="活动摘要条形图数据")
    time_overview: Optional[TimeOverviewData] = Field(default=None, description="时间概览数据")
    top_title: Optional[List[TopTitleData]] = Field(default=None, description="热门标题数据")
    top_app: Optional[List[TopAppData]] = Field(default=None, description="热门应用数据")
    todolist: Optional[List[TodoListData]] = Field(default=None, description="待办事项数据")
    category_tree : Optional[List[CategoryDef]] = Field(default=None, description="分类树")
    query: Optional[Dict[str, Any]] = Field(default=None, description="查询参数回显（调试用）")
    

class ActivityLogItem(BaseModel):
    """活动日志条目（框架）"""
    # TODO: 根据业务需求补充具体字段
    id: str = Field(..., description="日志ID")
    start_time: str = Field(..., description="开始时间")
    end_time: str = Field(..., description="结束时间")
    app: str = Field(..., description="应用名称")
    title: str = Field(..., description="窗口标题")
    duration: int = Field(..., description="持续时长（秒）")
    category_id: Optional[str] = Field(default=None, description="主分类ID")
    sub_category_id: Optional[str] = Field(default=None, description="子分类ID")
    category: Optional[str] = Field(default=None, description="主分类")
    sub_category: Optional[str] = Field(default=None, description="子分类")
    app_description: Optional[str] = Field(None, alias="appDescription", description="应用描述")
    title_analysis: Optional[str] = Field(None, alias="titleDescription", description="标题描述")
class ActivityLogsResponse(BaseModel):
    """GET /activity/logs 响应"""
    data: List[ActivityLogItem] = Field(default=[], description="日志列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")

class ActivityLogDetailResponse(BaseModel):
    """GET /activity/logs/{log_id} 响应"""
    data: ActivityLogItem = Field(..., description="日志详情")

