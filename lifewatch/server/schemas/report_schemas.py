"""
Report 页面的 schemas 定义

Daily Report 数据模型，与前端 types.ts 对齐
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ============================================================================
# 基础数据类型 (与前端 types.ts 对齐)
# ============================================================================

class ChartSegment(BaseModel):
    """饼图/旭日图数据项"""
    key: str = Field(..., description="分类 key")
    name: str = Field(..., description="分类名称")
    value: int = Field(..., description="时间值（分钟）")
    color: str = Field(..., description="颜色（十六进制）")
    title: Optional[str] = Field(default=None, description="app层的标题显示")


class TimeOverviewData(BaseModel):
    """旭日图完整数据 (递归结构，无柱状图)"""
    title: str = Field(..., description="标题")
    sub_title: str = Field(..., description="副标题")
    total_tracked_minutes: int = Field(..., description="总追踪分钟数")
    total_range_minutes: Optional[int] = Field(default=None, description="时间范围总分钟数")
    pie_data: List[ChartSegment] = Field(default=[], description="饼图数据")
    details: Optional[Dict[str, "TimeOverviewData"]] = Field(default=None, description="钻取详情")


class TodoStatsData(BaseModel):
    """Todo 统计数据"""
    total: int = Field(..., description="总任务数")
    completed: int = Field(..., description="已完成数")
    pending: int = Field(..., description="待完成数")
    procrastination_rate: float = Field(..., description="拖延率（百分比）")


class GoalTodoItem(BaseModel):
    """Goal 中的 Todo 项"""
    id: int = Field(..., description="任务 ID")
    content: str = Field(..., description="任务内容")
    completed: bool = Field(..., description="是否完成")


class GoalProgressData(BaseModel):
    """Goal 进度数据"""
    goal_id: str = Field(..., description="目标 ID")
    goal_name: str = Field(..., description="目标名称")
    goal_color: str = Field(..., description="目标颜色")
    time_invested: int = Field(..., description="投入时间（分钟）")
    todo_total: int = Field(..., description="总待办数")
    todo_completed: int = Field(..., description="已完成待办数")
    todo_list: List[GoalTodoItem] = Field(default=[], description="待办列表")


# ============================================================================
# Daily Report 请求/响应 Schemas
# ============================================================================

class DailyReportResponse(BaseModel):
    """日报告响应"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    sunburst_data: Optional[TimeOverviewData] = Field(default=None, description="旭日图数据")
    todo_data: Optional[TodoStatsData] = Field(default=None, description="Todo 统计数据")
    goal_data: Optional[List[GoalProgressData]] = Field(default=None, description="Goal 进度数据")
    daily_trend_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="24小时趋势数据")
    state: str = Field(default="0", description="数据状态 (0: 未完成, 1: 已完成)")
    data_version: int = Field(default=1, description="数据格式版本号")


class UpsertDailyReportRequest(BaseModel):
    """创建/更新日报告请求 (部分更新)"""
    sunburst_data: Optional[TimeOverviewData] = Field(default=None, description="旭日图数据")
    todo_data: Optional[TodoStatsData] = Field(default=None, description="Todo 统计数据")
    goal_data: Optional[List[GoalProgressData]] = Field(default=None, description="Goal 进度数据")
    daily_trend_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="24小时趋势数据")
    state: Optional[str] = Field(default=None, description="数据状态")
    

class DailyReportQueryRequest(BaseModel):
    """查询日报告请求"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    force_refresh: bool = Field(default=False, description="是否强制重新计算数据")


class DailyReportRangeQueryRequest(BaseModel):
    """日期范围查询请求"""
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")


class DailyReportListResponse(BaseModel):
    """日报告列表响应"""
    items: List[DailyReportResponse] = Field(default=[], description="报告列表")
    total: int = Field(default=0, description="总数")
