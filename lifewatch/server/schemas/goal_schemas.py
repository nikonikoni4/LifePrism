"""
goal 页面的schemas定义
"""

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