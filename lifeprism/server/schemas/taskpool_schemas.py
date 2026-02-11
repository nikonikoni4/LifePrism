"""
任务池 V2 API Schemas 定义

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

class TaskPoolItem(BaseModel):
    """任务池任务项"""
    id: int = Field(..., description="任务 ID")
    content: str = Field(..., description="任务内容")
    parent_id: Optional[int] = Field(default=None, description="父任务 ID（NULL 表示根任务）")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    plan_doc_id: Optional[str] = Field(default=None, description="关联的计划书 ID")
    source_anchor_id: Optional[str] = Field(default=None, description="MD 锚点标识")
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


class TaskPoolResponse(BaseModel):
    """任务池响应"""
    items: List[TaskPoolItem] = Field(default=[], description="任务列表（扁平结构）")


# ============================================================================
# Request Models
# ============================================================================

class TaskPoolQueryParams(BaseModel):
    """任务池查询参数"""
    goal_id: Optional[str] = Field(default=None, description="按目标筛选")
    plan_doc_id: Optional[str] = Field(default=None, description="按计划书筛选")
    state: Optional[str] = Field(default="all", description="按状态筛选（pool/scheduled/completed/all）")


class SyncPlanDocRequest(BaseModel):
    """同步计划书任务请求"""
    plan_doc_id: str = Field(..., description="计划书 ID")
    dry_run: bool = Field(default=False, description="预检模式：只返回差异，不执行操作")
    confirm_delete: bool = Field(default=False, description="确认删除：True=删除全部待删除任务，False=保留全部")


class TodoDeletePreview(BaseModel):
    """待删除任务预览"""
    id: int = Field(..., description="任务 ID")
    content: str = Field(..., description="任务内容")
    state: str = Field(..., description="任务状态")
    source_anchor_id: Optional[str] = Field(default=None, description="锚点 ID")


class SyncPlanDocResponse(BaseModel):
    """同步计划书任务响应"""
    created: int = Field(default=0, description="新创建的任务数")
    updated: int = Field(default=0, description="更新的任务数")
    deleted: int = Field(default=0, description="删除的任务数")
    cleaned: int = Field(default=0, description="清理的锚点数")
    total: int = Field(default=0, description="该计划书关联的总任务数")
    to_delete: Optional[List[TodoDeletePreview]] = Field(default=None, description="待删除任务列表（dry_run 模式返回）")


class RegenerateSummaryRequest(BaseModel):
    """重新生成系统展示区请求"""
    plan_doc_id: str = Field(..., description="计划书 ID")


class RegenerateSummaryResponse(BaseModel):
    """重新生成系统展示区响应"""
    success: bool = Field(..., description="是否成功")
    message: Optional[str] = Field(default=None, description="提示信息")


class UpdateTodoV2Request(BaseModel):
    """
    更新任务请求 (V2)

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
    parent_id: Optional[int] = Field(default=None, description="父任务 ID")
    delay_days: Optional[int] = Field(default=None, description="延期天数")
    delay_reason: Optional[str] = Field(default=None, description="延期/未完成原因说明")
    waid_order: Optional[int] = Field(default=None, description="WAID 浮窗排序")


class UpdateTodoV2Response(BaseModel):
    """更新任务响应 (V2)"""
    item: TaskPoolItem = Field(..., description="更新后的任务")
    md_synced: bool = Field(default=False, description="是否同步了 MD 文件")


class CreateTodoV2Request(BaseModel):
    """
    创建任务请求 (V2)

    用于统一的 /api/v2/todos 接口
    """
    content: str = Field(..., description="任务内容")
    state: Optional[Literal["pool", "scheduled", "completed", "shelved"]] = Field(
        default="pool",
        description="任务状态"
    )
    date: Optional[str] = Field(default=None, description="安排日期 YYYY-MM-DD")
    color: Optional[str] = Field(default="#FFFFFF", description="任务颜色")
    link_to_goal_id: Optional[str] = Field(default=None, description="关联的目标 ID")
    plan_doc_id: Optional[str] = Field(default=None, description="关联的计划书 ID")
    parent_id: Optional[int] = Field(default=None, description="父任务 ID")
    expected_finished_at: Optional[str] = Field(default=None, description="预计完成日期")
    pool_order_index: Optional[int] = Field(default=None, description="任务池排序")
    waid_order: Optional[int] = Field(default=None, description="WAID 浮窗排序")


class CreateTodoV2Response(BaseModel):
    """创建任务响应 (V2)"""
    item: TaskPoolItem = Field(..., description="创建的任务")


class WaidReorderRequest(BaseModel):
    """WAID 浮窗重排序请求"""
    todo_ids: List[int] = Field(..., description="按新顺序排列的 todo ID 列表")


class WaidAddRequest(BaseModel):
    """添加 todo 到 WAID 浮窗请求"""
    waid_order: Optional[int] = Field(default=None, description="排序位置（可选，默认追加到末尾）")


class BatchDurationRequest(BaseModel):
    """批量查询累计时长请求"""
    todo_ids: List[int] = Field(..., description="待办事项 ID 列表")
    date: str = Field(..., description="查询日期（YYYY-MM-DD）")


class BatchDurationResponse(BaseModel):
    """批量查询累计时长响应"""
    data: Dict[str, int] = Field(default={}, description="todo_id -> 累计分钟数")
