"""
Todo Schemas 定义

状态说明：
- pool: 任务池中（未分配日期）
- scheduled: 已安排（已分配日期）
- completed: 已完成
- shelved: 已搁置
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal


# ============================================================================
# Response Models
# ============================================================================

class TodoItem(BaseModel):
    """任务项"""
    id: str = Field(..., description="任务 ID（格式：t-{uuid[:8]}）")
    content: str = Field(..., description="任务内容")
    parent_id: Optional[str] = Field(default=None, description="父任务 ID（NULL 表示根任务）")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    plan_doc_id: Optional[str] = Field(default=None, description="关联的计划书 ID")
    state: str = Field(..., description="任务状态（pool/scheduled/completed/shelved）")
    date: Optional[str] = Field(default=None, description="安排日期 YYYY-MM-DD")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期")
    actual_finished_at: Optional[str] = Field(default=None, description="实际完成日期")
    color: str = Field(default="#FFFFFF", description="任务颜色")
    order_index: int = Field(default=0, description="日历视图排序")
    pool_order_index: Optional[int] = Field(default=None, description="任务池排序")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    delay_days: Optional[int] = Field(default=None, description="延期天数")
    delay_reason: Optional[str] = Field(default=None, description="延期/未完成原因说明")
    waid_order: Optional[int] = Field(default=None, description="WAID 浮窗排序")


class TodoListResponse(BaseModel):
    """任务列表响应"""
    items: List[TodoItem] = Field(default=[], description="任务列表（扁平结构）")


# ============================================================================
# Query Models
# ============================================================================

class TodoQueryParams(BaseModel):
    """任务查询参数"""
    goal_id: Optional[str] = Field(default=None, description="按目标筛选")
    plan_doc_id: Optional[str] = Field(default=None, description="按计划书筛选")
    state: Optional[str] = Field(default="all", description="按状态筛选（pool/scheduled/completed/all）")


# ============================================================================
# Request Models
# ============================================================================

class UpdateTodoRequest(BaseModel):
    """
    更新任务请求

    支持 MD 文件回写：当 state 变为 completed 时，
    如果任务关联了计划书且有锚点，会同步更新 MD 文件
    """
    content: Optional[str] = Field(default=None, description="任务内容")
    color: Optional[str] = Field(default=None, description="任务颜色")
    state: Optional[Literal["pool", "scheduled", "completed", "shelved"]] = Field(
        default=None,
        description="任务状态"
    )
    date: Optional[str] = Field(default=None, description="安排日期 YYYY-MM-DD")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期")
    parent_id: Optional[str] = Field(default=None, description="父任务 ID")
    delay_days: Optional[int] = Field(default=None, description="延期天数")
    delay_reason: Optional[str] = Field(default=None, description="延期/未完成原因说明")
    waid_order: Optional[int] = Field(default=None, description="WAID 浮窗排序")


class UpdateTodoResponse(BaseModel):
    """更新任务响应"""
    item: TodoItem = Field(..., description="更新后的任务")
    md_synced: bool = Field(default=False, description="是否同步了 MD 文件")


class CreateTodoRequest(BaseModel):
    """创建任务请求"""
    content: str = Field(..., description="任务内容")
    state: Optional[Literal["pool", "scheduled", "completed", "shelved"]] = Field(
        default="pool",
        description="任务状态"
    )
    date: Optional[str] = Field(default=None, description="安排日期 YYYY-MM-DD")
    color: Optional[str] = Field(default="#FFFFFF", description="任务颜色")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    plan_doc_id: Optional[str] = Field(default=None, description="关联的计划书 ID")
    parent_id: Optional[str] = Field(default=None, description="父任务 ID")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期")
    pool_order_index: Optional[int] = Field(default=None, description="任务池排序")
    waid_order: Optional[int] = Field(default=None, description="WAID 浮窗排序")


class CreateTodoResponse(BaseModel):
    """创建任务响应"""
    item: TodoItem = Field(..., description="创建的任务")


class WaidReorderRequest(BaseModel):
    """WAID 浮窗重排序请求"""
    todo_ids: List[str] = Field(..., description="按新顺序排列的 todo ID 列表")


class WaidAddRequest(BaseModel):
    """添加 todo 到 WAID 浮窗请求"""
    waid_order: Optional[int] = Field(default=None, description="排序位置（可选，默认追加到末尾）")


class BatchDurationRequest(BaseModel):
    """批量查询累计时长请求"""
    todo_ids: List[str] = Field(..., description="待办事项 ID 列表")
    date: str = Field(..., description="查询日期（YYYY-MM-DD）")


class BatchDurationResponse(BaseModel):
    """批量查询累计时长响应"""
    data: Dict[str, int] = Field(default={}, description="todo_id -> 累计分钟数")
