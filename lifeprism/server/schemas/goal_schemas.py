"""
goal 页面的schemas定义
"""

from pydantic import BaseModel, Field

# ============================================================================
# Goal Schemas
# ============================================================================


class MilestoneItem(BaseModel):
    """里程碑项"""

    id: str = Field(..., description="唯一标识符")
    content: str = Field(..., description="里程碑内容")
    state: int = Field(default=0, description="状态 0: 未达成, 1: 已达成")
    finish_time: str | None = Field(default=None, description="完成时间 YYYY-MM-DD")
    order_index: int = Field(default=0, description="排序索引")


class JournalEntry(BaseModel):
    """日志条目"""

    id: str = Field(..., description="唯一标识符")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    time: str | None = Field(default=None, description="时间 HH:MM")
    content: str = Field(..., description="日志内容")
    mood: str = Field(default="neutral", description="心情（joy/calm/frustrated/neutral）")
    duration: int = Field(default=0, description="持续时间（分钟）")
    tags: list[str] = Field(default=[], description="标签列表")


class GoalItem(BaseModel):
    """目标项"""

    id: str = Field(..., description="唯一标识符 id（格式：goal-xxx）")
    name: str = Field(..., description="目标名称")
    content: str = Field(default="", description="目标内容（Markdown）")
    color: str = Field(default="#5B8FF9", description="目标颜色（十六进制）")
    created_at: str = Field(..., description="创建时间")
    # 关联内容（返回名称，非 ID）
    link_to_category: str | None = Field(default=None, description="关联的分类名称")
    link_to_sub_category: str | None = Field(default=None, description="关联的子分类名称")
    # 新增字段
    start_date: str | None = Field(default=None, description="开始日期 YYYY-MM-DD")
    expected_finished_at: str | None = Field(default=None, description="预计完成时间 YYYY-MM-DD")
    value: str | None = Field(default=None, description="价值观/意义描述")
    commitment: str | None = Field(default=None, description="承诺/行动计划")
    time_invested: str = Field(default="0h 0m", description="投入时间（格式化字符串，如 '2h 30m'）")
    track_time_automatically: bool = Field(default=True, description="是否自动追踪时间")
    milestones: list[MilestoneItem] = Field(default=[], description="里程碑列表")
    journal: list[JournalEntry] = Field(default=[], description="日志列表")
    status: str = Field(default="active", description="目标状态: active, completed, archived")
    order_index: int = Field(default=0, description="排序索引")
    days_started: int | None = Field(default=None, description="已开始天数（计算字段）")


class GoalListResponse(BaseModel):
    """目标列表响应"""

    items: list[GoalItem] = Field(default=[], description="目标列表")
    total: int = Field(default=0, description="总数")


# ============================================================================
# Goal Request Schemas
# ============================================================================


class CreateGoalRequest(BaseModel):
    """创建目标请求"""

    name: str = Field(..., description="目标名称")
    content: str = Field(default="", description="目标内容（Markdown）")
    color: str = Field(default="#5B8FF9", description="目标颜色")
    link_to_category_id: str | None = Field(default=None, description="关联的分类 id")
    link_to_sub_category_id: str | None = Field(default=None, description="关联的子分类 id")
    start_date: str | None = Field(default=None, description="开始日期 YYYY-MM-DD")
    expected_finished_at: str | None = Field(default=None, description="预计完成时间 YYYY-MM-DD")
    value: str | None = Field(default=None, description="价值观/意义描述")
    commitment: str | None = Field(default=None, description="承诺/行动计划")
    track_time_automatically: bool = Field(default=True, description="是否自动追踪时间")


class UpdateGoalRequest(BaseModel):
    """更新目标请求（部分更新）"""

    name: str | None = Field(default=None, description="目标名称")
    content: str | None = Field(default=None, description="目标内容（Markdown）")
    color: str | None = Field(default=None, description="目标颜色")
    link_to_category_id: str | None = Field(default=None, description="关联的分类 id")
    link_to_sub_category_id: str | None = Field(default=None, description="关联的子分类 id")
    start_date: str | None = Field(default=None, description="开始日期 YYYY-MM-DD")
    expected_finished_at: str | None = Field(default=None, description="预计完成时间")
    value: str | None = Field(default=None, description="价值观/意义描述")
    commitment: str | None = Field(default=None, description="承诺/行动计划")
    time_invested: int | None = Field(default=None, description="投入时间（秒），仅手动模式有效")
    track_time_automatically: bool | None = Field(default=None, description="是否自动追踪时间")
    milestones: str | None = Field(default=None, description="里程碑 JSON 字符串")
    status: str | None = Field(default=None, description="目标状态")


class ReorderGoalRequest(BaseModel):
    """目标重排序请求"""

    goal_ids: list[str] = Field(..., description="目标 ID 列表（按新顺序排列）")


class ActiveGoalItem(BaseModel):
    """活跃目标项（用于下拉选择）"""

    id: str = Field(..., description="目标 ID")
    name: str = Field(..., description="目标名称")


class ActiveGoalNamesResponse(BaseModel):
    """活跃目标名称列表响应"""

    items: list[ActiveGoalItem] = Field(default=[], description="活跃目标列表")


class GoalWithCategoryItem(BaseModel):
    """绑定了分类的目标项（用于 Map Cache 编辑）"""

    id: str = Field(..., description="目标 ID")
    name: str = Field(..., description="目标名称")
    link_to_category_id: str = Field(..., description="关联的分类 ID")
    link_to_sub_category_id: str | None = Field(default=None, description="关联的子分类 ID")


class GoalsWithCategoryResponse(BaseModel):
    """绑定了分类的目标列表响应"""

    items: list[GoalWithCategoryItem] = Field(default=[], description="目标列表")


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
    time: str | None = Field(default=None, description="时间 HH:MM")
    content: str = Field(..., description="日志内容")
    mood: str = Field(default="neutral", description="心情（joy/calm/frustrated/neutral）")
    duration: int = Field(default=0, description="持续时间（分钟）")
    tags: str | None = Field(default=None, description="标签 JSON 字符串")


class UpdateJournalRequest(BaseModel):
    """更新日志请求（部分更新）"""

    date: str | None = Field(default=None, description="日期 YYYY-MM-DD")
    time: str | None = Field(default=None, description="时间 HH:MM")
    content: str | None = Field(default=None, description="日志内容")
    mood: str | None = Field(default=None, description="心情")
    duration: int | None = Field(default=None, description="持续时间（分钟）")
    tags: str | None = Field(default=None, description="标签 JSON 字符串")


class JournalListResponse(BaseModel):
    """日志列表响应"""

    items: list[JournalEntry] = Field(default=[], description="日志列表")


# ============================================================================
# PlanDoc Schemas
# ============================================================================


class PlanDocItem(BaseModel):
    """计划书项"""

    id: str = Field(..., description="唯一标识符（格式：plandoc-xxx）")
    goal_id: str = Field(..., description="关联的目标 ID")
    content: str = Field(default="", description="计划书内容（Markdown）")
    status: str = Field(default="active", description="状态: active, completed, archived")
    order_index: int = Field(default=0, description="排序索引")
    created_at: str = Field(..., description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class PlanDocListResponse(BaseModel):
    """计划书列表响应"""

    items: list[PlanDocItem] = Field(default=[], description="计划书列表")


class CreatePlanDocRequest(BaseModel):
    """创建计划书请求"""

    id: str = Field(..., description="计划书 ID（同时作为文件名）")
    goal_id: str | None = Field(default=None, description="关联的目标 ID（可为空，表示临时文档）")
    content: str = Field(default="", description="计划书内容（Markdown）")


class UpdatePlanDocRequest(BaseModel):
    """更新计划书请求（部分更新）"""

    new_id: str | None = Field(default=None, description="新 ID（用于重命名）")
    content: str | None = Field(default=None, description="计划书内容（Markdown）")
    status: str | None = Field(default=None, description="状态")
