"""
goal 页面的schemas定义
"""

from tomlkit.api import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


# ============================================================================
# TodoList Schemas
# ============================================================================

class SubTodoListItem(BaseModel):
    """子任务项"""
    id: int = Field(..., description="唯一标识符 id")
    order_index: int = Field(..., description="排序索引")
    parent_id: int = Field(..., description="父任务 ID")
    content: str = Field(..., description="子任务内容")
    completed: bool = Field(default=False, description="是否完成")


class SubTodoListResponse(BaseModel):
    """子任务列表响应"""
    items: List[SubTodoListItem] = Field(default=[], description="子任务列表")


class TodoListItem(BaseModel):
    """
    主任务项
    
    当开启跨天追踪(cross_day=True)后，在未完成之前都会显示
    """
    id: int = Field(..., description="唯一标识符 id")
    order_index: int = Field(..., description="每天todolist的排序索引")
    pool_order_index: Optional[int] = Field(default=None, description="任务池排序索引")
    content: str = Field(..., description="任务内容")
    color: str = Field(default="#FFFFFF", description="任务颜色（十六进制格式）")
    state: str = Field(default="active", description="任务状态（active/completed/inactive）")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    date: Optional[str] = Field(default=None, description="任务日期 YYYY-MM-DD（inactive状态可为空）")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期 YYYY-MM-DD")
    actual_finished_at: Optional[str] = Field(default=None, description="实际完成日期 YYYY-MM-DD")
    cross_day: bool = Field(default=False, description="是否开启跨天追踪")
    # 嵌套子任务（可选，用于响应时包含子任务）
    sub_items: Optional[List[SubTodoListItem]] = Field(default=None, description="子任务列表")


class TodoListResponse(BaseModel):
    """任务列表响应"""
    daily_focus_content: Optional[str] = Field(default=None, description="日计划重点")
    items: List[TodoListItem] = Field(default=[], description="任务列表")


# ============================================================================
# TodoList Request Schemas
# ============================================================================

class TodoListQueryRequest(BaseModel):
    """查询任务列表请求"""
    date: str = Field(..., description="请求日期 YYYY-MM-DD")
    include_cross_day: bool = Field(default=True, description="是否包含跨天未完成任务")


class CreateTodoRequest(BaseModel):
    """创建任务请求"""
    content: str = Field(..., description="任务内容")
    date: Optional[str] = Field(default=None, description="任务日期 YYYY-MM-DD（inactive状态可为空）")
    color: str = Field(default="#FFFFFF", description="任务颜色")
    state: str = Field(default="active", description="任务状态（active/inactive）")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期 YYYY-MM-DD")
    cross_day: bool = Field(default=False, description="是否开启跨天追踪")


class UpdateTodoRequest(BaseModel):
    """更新任务请求（部分更新）"""
    content: Optional[str] = Field(default=None, description="任务内容")
    color: Optional[str] = Field(default=None, description="任务颜色")
    state: Optional[str] = Field(default=None, description="任务状态（active/completed/inactive）")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    date: Optional[str] = Field(default=None, description="任务日期 YYYY-MM-DD")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期")
    cross_day: Optional[bool] = Field(default=None, description="是否开启跨天追踪")


class ReorderTodoRequest(BaseModel):
    """任务重排序请求"""
    todo_ids: List[int] = Field(..., description="任务 ID 列表（按新顺序排列）")


class CreateSubTodoRequest(BaseModel):
    """创建子任务请求"""
    parent_id: int = Field(..., description="父任务 ID")
    content: str = Field(..., description="子任务内容")


class UpdateSubTodoRequest(BaseModel):
    """更新子任务请求（部分更新）"""
    content: Optional[str] = Field(default=None, description="子任务内容")
    completed: Optional[bool] = Field(default=None, description="是否完成")


class ReorderSubTodoRequest(BaseModel):
    """子任务重排序请求"""
    parent_id: int = Field(..., description="父任务 ID")
    sub_todo_ids: List[int] = Field(..., description="子任务 ID 列表（按新顺序排列）")


class ReorderPoolTodoRequest(BaseModel):
    """任务池重排序请求"""
    todo_ids: List[int] = Field(..., description="任务 ID 列表（按新顺序排列）")


# ============================================================================
# Plan Schemas (预留)
# ============================================================================

# 周计划项
class DailyPlanItem(BaseModel):
    """日计划项"""
    id: int = Field(..., description="唯一标识符 id")
    date : str = Field(..., description="日期 YYYY-MM-DD")
    daily_focus_content: str = Field(..., description="日计划重点")
    completion_rate: float = Field(..., description="完成度")
    todo_list: List[TodoListItem] = Field(default=[], description="任务列表（无子任务）")

class WeeklyPlanResponse(BaseModel):
    """周计划响应：包含日计划项列表"""
    weekly_focus_content: str = Field(..., description="本周重点")
    items: List[DailyPlanItem] = Field(default=[], description="周计划列表")

class WeeklyPlanItem(BaseModel):
    """周计划项:展示在月plan界面"""
    id: int = Field(..., description="唯一标识符 id")
    start_date : str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date : str = Field(..., description="结束日期 YYYY-MM-DD")
    weekly_focus_content: str = Field(..., description="本周重点")
    completion_rate: float = Field(..., description="完成度")


class MonthlyPlanItem(BaseModel):
    """月计划项"""
    monthly_focus_content: str = Field(..., description="月计划重点")
    items: List[WeeklyPlanItem] = Field(default=[], description="周计划列表")


# ============================================================================
# Plan Request Schemas
# ============================================================================

class UpsertDailyFocusRequest(BaseModel):
    """更新日焦点请求"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    content: str = Field(..., description="焦点内容")


class UpsertWeeklyFocusRequest(BaseModel):
    """更新周焦点请求"""
    year: int = Field(..., description="年份")
    month: int = Field(..., description="月份 1-12")
    week_num: int = Field(..., description="周序号 1-4")
    content: str = Field(..., description="焦点内容")


# ============================================================================
# Goal Schemas
# ============================================================================

class MilestoneItem(BaseModel):
    """里程碑项"""
    id: str = Field(..., description="唯一标识符")
    content: str = Field(..., description="里程碑内容")
    state: int = Field(default=0, description="状态 0: 未达成, 1: 已达成")
    finish_time: Optional[str] = Field(default=None, description="完成时间 YYYY-MM-DD")
    order_index: int = Field(default=0, description="排序索引")


class JournalEntry(BaseModel):
    """日志条目"""
    id: str = Field(..., description="唯一标识符")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    time: Optional[str] = Field(default=None, description="时间 HH:MM")
    content: str = Field(..., description="日志内容")
    mood: str = Field(default="neutral", description="心情（joy/calm/frustrated/neutral）")
    duration: int = Field(default=0, description="持续时间（分钟）")
    tags: List[str] = Field(default=[], description="标签列表")


class GoalItem(BaseModel):
    """目标项"""
    id: str = Field(..., description="唯一标识符 id（格式：goal-xxx）")
    name: str = Field(..., description="目标名称")
    content: str = Field(default="", description="目标内容（Markdown）")
    color: str = Field(default="#5B8FF9", description="目标颜色（十六进制）")
    created_at: str = Field(..., description="创建时间")
    # 关联内容（返回名称，非 ID）
    link_to_category: Optional[str] = Field(default=None, description="关联的分类名称")
    link_to_sub_category: Optional[str] = Field(default=None, description="关联的子分类名称")
    # 新增字段
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成时间 YYYY-MM-DD")
    value: Optional[str] = Field(default=None, description="价值观/意义描述")
    commitment: Optional[str] = Field(default=None, description="承诺/行动计划")
    time_unit: str = Field(default="HRS", description="时间单位 HRS/MINS")
    time_invested: str = Field(default="0h 0m", description="投入时间（格式化字符串）")
    track_time_automatically: bool = Field(default=True, description="是否自动追踪时间")
    milestones: List[MilestoneItem] = Field(default=[], description="里程碑列表")
    journal: List[JournalEntry] = Field(default=[], description="日志列表")
    status: str = Field(default="active", description="目标状态: active, completed, archived")
    order_index: int = Field(default=0, description="排序索引")
    days_started: Optional[int] = Field(default=None, description="已开始天数（计算字段）")


class GoalListResponse(BaseModel):
    """目标列表响应"""
    items: List[GoalItem] = Field(default=[], description="目标列表")
    total: int = Field(default=0, description="总数")


# ============================================================================
# Goal Request Schemas
# ============================================================================


class CreateGoalRequest(BaseModel):
    """创建目标请求"""
    name: str = Field(..., description="目标名称")
    content: str = Field(default="", description="目标内容（Markdown）")
    color: str = Field(default="#5B8FF9", description="目标颜色")
    link_to_category_id: Optional[str] = Field(default=None, description="关联的分类 id")
    link_to_sub_category_id: Optional[str] = Field(default=None, description="关联的子分类 id")
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成时间 YYYY-MM-DD")
    value: Optional[str] = Field(default=None, description="价值观/意义描述")
    commitment: Optional[str] = Field(default=None, description="承诺/行动计划")
    track_time_automatically: bool = Field(default=True, description="是否自动追踪时间")


class UpdateGoalRequest(BaseModel):
    """更新目标请求（部分更新）"""
    name: Optional[str] = Field(default=None, description="目标名称")
    content: Optional[str] = Field(default=None, description="目标内容（Markdown）")
    color: Optional[str] = Field(default=None, description="目标颜色")
    link_to_category_id: Optional[str] = Field(default=None, description="关联的分类 id")
    link_to_sub_category_id: Optional[str] = Field(default=None, description="关联的子分类 id")
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成时间")
    value: Optional[str] = Field(default=None, description="价值观/意义描述")
    commitment: Optional[str] = Field(default=None, description="承诺/行动计划")
    time_invested: Optional[int] = Field(default=None, description="投入时间（分钟）")
    time_unit: Optional[str] = Field(default=None, description="时间单位 HRS/MINS")
    track_time_automatically: Optional[bool] = Field(default=None, description="是否自动追踪时间")
    milestones: Optional[str] = Field(default=None, description="里程碑 JSON 字符串")
    status: Optional[str] = Field(default=None, description="目标状态")


class ReorderGoalRequest(BaseModel):
    """目标重排序请求"""
    goal_ids: List[str] = Field(..., description="目标 ID 列表（按新顺序排列）")


class ActiveGoalItem(BaseModel):
    """活跃目标项（用于下拉选择）"""
    id: str = Field(..., description="目标 ID")
    name: str = Field(..., description="目标名称")


class ActiveGoalNamesResponse(BaseModel):
    """活跃目标名称列表响应"""
    items: List[ActiveGoalItem] = Field(default=[], description="活跃目标列表")


class GoalWithCategoryItem(BaseModel):
    """绑定了分类的目标项（用于 Map Cache 编辑）"""
    id: str = Field(..., description="目标 ID")
    name: str = Field(..., description="目标名称")
    link_to_category_id: str = Field(..., description="关联的分类 ID")
    link_to_sub_category_id: Optional[str] = Field(default=None, description="关联的子分类 ID")


class GoalsWithCategoryResponse(BaseModel):
    """绑定了分类的目标列表响应"""
    items: List[GoalWithCategoryItem] = Field(default=[], description="目标列表")


class UpdateMilestoneStateRequest(BaseModel):
    """更新里程碑状态请求"""
    state: int = Field(..., description="状态 0: 未达成, 1: 已达成")


# ============================================================================
# Journal Schemas
# ============================================================================


class CreateJournalRequest(BaseModel):
    """创建日志请求"""
    goal_id: str = Field(..., description="关联的目标 ID")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    time: Optional[str] = Field(default=None, description="时间 HH:MM")
    content: str = Field(..., description="日志内容")
    mood: str = Field(default="neutral", description="心情（joy/calm/frustrated/neutral）")
    duration: int = Field(default=0, description="持续时间（分钟）")
    tags: Optional[str] = Field(default=None, description="标签 JSON 字符串")


class UpdateJournalRequest(BaseModel):
    """更新日志请求（部分更新）"""
    date: Optional[str] = Field(default=None, description="日期 YYYY-MM-DD")
    time: Optional[str] = Field(default=None, description="时间 HH:MM")
    content: Optional[str] = Field(default=None, description="日志内容")
    mood: Optional[str] = Field(default=None, description="心情")
    duration: Optional[int] = Field(default=None, description="持续时间（分钟）")
    tags: Optional[str] = Field(default=None, description="标签 JSON 字符串")


class JournalListResponse(BaseModel):
    """日志列表响应"""
    items: List[JournalEntry] = Field(default=[], description="日志列表")


# ============================================================================
# PlanDoc Schemas
# ============================================================================


class PlanDocItem(BaseModel):
    """计划书项"""
    id: str = Field(..., description="唯一标识符（格式：plandoc-xxx）")
    goal_id: str = Field(..., description="关联的目标 ID")
    title: str = Field(..., description="计划书标题")
    content: str = Field(default="", description="计划书内容（Markdown）")
    status: str = Field(default="active", description="状态: active, completed, archived")
    order_index: int = Field(default=0, description="排序索引")
    created_at: str = Field(..., description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class PlanDocListResponse(BaseModel):
    """计划书列表响应"""
    items: List[PlanDocItem] = Field(default=[], description="计划书列表")


class CreatePlanDocRequest(BaseModel):
    """创建计划书请求"""
    goal_id: Optional[str] = Field(default=None, description="关联的目标 ID（可为空，表示临时文档）")
    title: str = Field(..., description="计划书标题（同时作为 ID 和文件名）")
    content: str = Field(default="", description="计划书内容（Markdown）")


class UpdatePlanDocRequest(BaseModel):
    """更新计划书请求（部分更新）"""
    title: Optional[str] = Field(default=None, description="计划书标题")
    content: Optional[str] = Field(default=None, description="计划书内容（Markdown）")
    status: Optional[str] = Field(default=None, description="状态")
