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
    order_index: int = Field(..., description="排序索引")
    content: str = Field(..., description="任务内容")
    color: str = Field(default="#FFFFFF", description="任务颜色（十六进制格式）")
    completed: bool = Field(default=False, description="是否完成")
    link_to_goal: Optional[int] = Field(default=None, description="关联的目标 ID")
    date: str = Field(..., description="任务日期 YYYY-MM-DD")
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
    date: str = Field(..., description="任务日期 YYYY-MM-DD")
    color: str = Field(default="#FFFFFF", description="任务颜色")
    link_to_goal: Optional[int] = Field(default=None, description="关联的目标 ID")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期 YYYY-MM-DD")
    cross_day: bool = Field(default=False, description="是否开启跨天追踪")


class UpdateTodoRequest(BaseModel):
    """更新任务请求（部分更新）"""
    content: Optional[str] = Field(default=None, description="任务内容")
    color: Optional[str] = Field(default=None, description="任务颜色")
    completed: Optional[bool] = Field(default=None, description="是否完成")
    link_to_goal: Optional[int] = Field(default=None, description="关联的目标 ID")
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


class GoalItem(BaseModel):
    """目标项"""
    id: int = Field(..., description="唯一标识符 id")
    name: str = Field(..., description="目标名称")
    abstract: Optional[str] = Field(default=None, description="目标摘要/别名")
    content: str = Field(default="", description="目标内容")
    color: str = Field(default="#5B8FF9", description="目标颜色")
    created_at: str = Field(..., description="创建时间")
    # 关联内容（返回名称，非 ID）
    link_to_category: Optional[str] = Field(default=None, description="关联的分类名称")
    link_to_sub_category: Optional[str] = Field(default=None, description="关联的子分类名称")
    link_to_reward_id: Optional[int] = Field(default=None, description="关联的奖励 id")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成时间 YYYY-MM-DD")
    expected_hours: Optional[int] = Field(default=None, description="预计耗时（小时）")
    actual_finished_at: Optional[str] = Field(default=None, description="实际完成时间 YYYY-MM-DD")
    actual_hours: Optional[int] = Field(default=None, description="实际耗时（小时）")
    completion_rate: float = Field(default=0.0, description="完成度 0-1")
    status: str = Field(default="active", description="目标状态: active, completed, archived")
    order_index: int = Field(default=0, description="排序索引")


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
    abstract: Optional[str] = Field(default=None, description="目标摘要/别名")
    content: str = Field(default="", description="目标内容")
    color: str = Field(default="#5B8FF9", description="目标颜色")
    link_to_category_id: Optional[str] = Field(default=None, description="关联的分类 id")
    link_to_sub_category_id: Optional[str] = Field(default=None, description="关联的子分类 id")
    link_to_reward_id: Optional[int] = Field(default=None, description="关联的奖励 id")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成时间 YYYY-MM-DD")
    expected_hours: Optional[int] = Field(default=None, description="预计耗时（小时）")


class UpdateGoalRequest(BaseModel):
    """更新目标请求（部分更新）"""
    name: Optional[str] = Field(default=None, description="目标名称")
    abstract: Optional[str] = Field(default=None, description="目标摘要/别名")
    content: Optional[str] = Field(default=None, description="目标内容")
    color: Optional[str] = Field(default=None, description="目标颜色")
    link_to_category_id: Optional[str] = Field(default=None, description="关联的分类 id")
    link_to_sub_category_id: Optional[str] = Field(default=None, description="关联的子分类 id")
    link_to_reward_id: Optional[int] = Field(default=None, description="关联的奖励 id")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成时间")
    expected_hours: Optional[int] = Field(default=None, description="预计耗时（小时）")
    actual_finished_at: Optional[str] = Field(default=None, description="实际完成时间")
    actual_hours: Optional[int] = Field(default=None, description="实际耗时（小时）")
    completion_rate: Optional[float] = Field(default=None, description="完成度 0-1")
    status: Optional[str] = Field(default=None, description="目标状态")


class ReorderGoalRequest(BaseModel):
    """目标重排序请求"""
    goal_ids: List[int] = Field(..., description="目标 ID 列表（按新顺序排列）")




# ============================================================================
# reward Schemas (预留)
# ============================================================================



# ============================================================================
# reward Request Schemas (预留)
# ============================================================================
