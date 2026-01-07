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
    title: Optional[str] = Field(default="", description="app层的标题显示")


class BarConfig(BaseModel):
    """柱状图配置项"""
    key: str = Field(..., description="数据键")
    label: str = Field(..., description="图例标签")
    color: str = Field(..., description="颜色（十六进制格式）")


class TimeOverviewData(BaseModel):
    """旭日图完整数据 (递归结构，支持三层钻取)"""
    title: str = Field(..., description="标题")
    sub_title: str = Field(..., description="副标题")
    total_tracked_minutes: int = Field(..., description="总追踪分钟数")
    total_range_minutes: Optional[int] = Field(default=None, description="时间范围总分钟数")
    pie_data: List[ChartSegment] = Field(default=[], description="饼图数据")
    bar_keys: Optional[List[BarConfig]] = Field(default=None, description="柱状图配置")
    bar_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="时间分布数据")
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
    comparison_data: Optional["ComparisonData"] = Field(default=None, description="与前一天的环比对比数据")
    ai_summary: Optional[str] = Field(default=None, description="AI 总结内容")
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


# ============================================================================
# Weekly Report 请求/响应 Schemas
# ============================================================================

class WeeklyReportResponse(BaseModel):
    """周报告响应"""
    week_start_date: str = Field(..., description="周开始日期 YYYY-MM-DD（周一）")
    week_end_date: str = Field(..., description="周结束日期 YYYY-MM-DD（周日）")
    sunburst_data: Optional[TimeOverviewData] = Field(default=None, description="旭日图数据")
    todo_data: Optional[TodoStatsData] = Field(default=None, description="Todo 统计数据")
    goal_data: Optional[List[GoalProgressData]] = Field(default=None, description="Goal 进度数据")
    daily_trend_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="每日趋势数据（7天）")
    comparison_data: Optional["ComparisonData"] = Field(default=None, description="与上一周的环比对比数据")
    ai_summary: Optional[str] = Field(default=None, description="AI 总结内容")
    state: str = Field(default="0", description="数据状态 (0: 未完成, 1: 已完成)")
    data_version: int = Field(default=1, description="数据格式版本号")


class UpsertWeeklyReportRequest(BaseModel):
    """创建/更新周报告请求 (部分更新)"""
    sunburst_data: Optional[TimeOverviewData] = Field(default=None, description="旭日图数据")
    todo_data: Optional[TodoStatsData] = Field(default=None, description="Todo 统计数据")
    goal_data: Optional[List[GoalProgressData]] = Field(default=None, description="Goal 进度数据")
    daily_trend_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="每日趋势数据")
    state: Optional[str] = Field(default=None, description="数据状态")


class WeeklyReportQueryRequest(BaseModel):
    """查询周报告请求"""
    week_start_date: str = Field(..., description="周开始日期 YYYY-MM-DD（周一）")
    force_refresh: bool = Field(default=False, description="是否强制重新计算数据")


# ============================================================================
# Monthly Report 请求/响应 Schemas
# ============================================================================

class HeatmapDataItem(BaseModel):
    """热力图单日数据"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    total_minutes: int = Field(..., description="当日总追踪分钟数")
    category_breakdown: Optional[Dict[str, int]] = Field(default=None, description="分类时间分解（分类名 -> 分钟数）")


class MonthlyReportResponse(BaseModel):
    """月报告响应"""
    month_start_date: str = Field(..., description="月开始日期 YYYY-MM-01")
    month_end_date: str = Field(..., description="月结束日期 YYYY-MM-DD（月末）")
    sunburst_data: Optional[TimeOverviewData] = Field(default=None, description="旭日图数据")
    todo_data: Optional[TodoStatsData] = Field(default=None, description="Todo 统计数据")
    goal_data: Optional[List[GoalProgressData]] = Field(default=None, description="Goal 进度数据")
    daily_trend_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="每日趋势数据（按天）")
    heatmap_data: Optional[List[HeatmapDataItem]] = Field(default=None, description="热力图数据")
    comparison_data: Optional["ComparisonData"] = Field(default=None, description="与上一月的环比对比数据")
    ai_summary: Optional[str] = Field(default=None, description="AI 总结内容")
    state: str = Field(default="0", description="数据状态 (0: 未完成, 1: 已完成)")
    data_version: int = Field(default=1, description="数据格式版本号")


class UpsertMonthlyReportRequest(BaseModel):
    """创建/更新月报告请求 (部分更新)"""
    sunburst_data: Optional[TimeOverviewData] = Field(default=None, description="旭日图数据")
    todo_data: Optional[TodoStatsData] = Field(default=None, description="Todo 统计数据")
    goal_data: Optional[List[GoalProgressData]] = Field(default=None, description="Goal 进度数据")
    daily_trend_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="每日趋势数据")
    heatmap_data: Optional[List[HeatmapDataItem]] = Field(default=None, description="热力图数据")
    state: Optional[str] = Field(default=None, description="数据状态")


class MonthlyReportQueryRequest(BaseModel):
    """查询月报告请求"""
    month: str = Field(..., description="月份 YYYY-MM")
    force_refresh: bool = Field(default=False, description="是否强制重新计算数据")


# ============================================================================
# AI Summary 请求/响应 Schemas
# ============================================================================

class TokenUsage(BaseModel):
    """Token 使用量统计"""
    input_tokens: int = Field(..., description="输入 token 数量")
    output_tokens: int = Field(..., description="输出 token 数量")
    total_tokens: int = Field(..., description="总 token 数量")


class AISummaryResponse(BaseModel):
    """AI 总结响应"""
    content: str = Field(..., description="AI 生成的总结内容")
    tokens_usage: TokenUsage = Field(..., description="Token 使用量统计")


class AISummaryRequest(BaseModel):
    """AI 总结请求 - 日报"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    pattern: Optional[str] = Field(
        default="complex", 
        description="总结模式，如 complex, simple"
    )

 
class WeeklyAISummaryRequest(BaseModel):
    """AI 总结请求 - 周报"""
    week_start_date: str = Field(..., description="周开始日期 YYYY-MM-DD（周一）")
    week_end_date: str = Field(..., description="周结束日期 YYYY-MM-DD（周日）")
    pattern: Optional[str] = Field(
        default="complex", 
        description="总结模式，如 complex, simple"
    )


class MonthlyAISummaryRequest(BaseModel):
    """AI 总结请求 - 月报"""
    month_start_date: str = Field(..., description="月开始日期 YYYY-MM-01")
    month_end_date: str = Field(..., description="月结束日期 YYYY-MM-DD（月末）")
    pattern: Optional[str] = Field(
        default="complex", 
        description="总结模式，如 complex, simple"
    )


# ============================================================================
# 环比对比 请求/响应 Schemas
# ============================================================================

class CategoryComparisonItem(BaseModel):
    """单个分类的环比数据"""
    category_id: str = Field(..., description="分类 ID")
    category_name: str = Field(..., description="分类名称")
    current_duration: int = Field(..., description="当前周期时长（秒）")
    previous_duration: int = Field(..., description="上一周期时长（秒）")
    change_seconds: int = Field(..., description="变化秒数")
    change_percentage: Optional[float] = Field(default=None, description="变化百分比（新增时为 null）")


class GoalComparisonItem(BaseModel):
    """单个目标的环比数据"""
    goal_id: str = Field(..., description="目标 ID")
    goal_name: str = Field(..., description="目标名称")
    current_duration: int = Field(..., description="当前周期时长（秒）")
    previous_duration: int = Field(..., description="上一周期时长（秒）")
    change_seconds: int = Field(..., description="变化秒数")


class ComparisonData(BaseModel):
    """完整的环比对比数据"""
    current_start: str = Field(..., description="当前周期开始时间")
    current_end: str = Field(..., description="当前周期结束时间")
    previous_start: str = Field(..., description="上一周期开始时间")
    previous_end: str = Field(..., description="上一周期结束时间")
    category_comparison: List[CategoryComparisonItem] = Field(default=[], description="分类对比列表")
    goal_comparison: List[GoalComparisonItem] = Field(default=[], description="目标对比列表")


class ComparisonQueryRequest(BaseModel):
    """环比查询请求"""
    current_start: str = Field(..., description="当前周期开始时间 YYYY-MM-DD HH:MM:SS")
    current_end: str = Field(..., description="当前周期结束时间 YYYY-MM-DD HH:MM:SS")
    previous_start: str = Field(..., description="上一周期开始时间 YYYY-MM-DD HH:MM:SS")
    previous_end: str = Field(..., description="上一周期结束时间 YYYY-MM-DD HH:MM:SS")
