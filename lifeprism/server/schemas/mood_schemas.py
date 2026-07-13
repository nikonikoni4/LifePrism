"""
心情模块 Schema 定义

心情类型、心情记录、影响因素的请求/响应模型
"""

from pydantic import BaseModel, Field

# ==================== 心情类型 ====================


class MoodTypeItem(BaseModel):
    """心情类型"""

    id: str = Field(..., description="心情类型 ID")
    name: str = Field(..., description="心情名称")
    icon: str = Field(..., description="Lucide 图标名")
    color: str = Field(..., description="十六进制颜色值")
    score: int = Field(..., description="心情评分权重 0-100")
    is_dark: int = Field(default=0, description="是否深色主题")
    sort_order: int = Field(default=0, description="排序权重")
    created_at: str = Field(default="", description="创建时间")


class MoodTypeListResponse(BaseModel):
    """心情类型列表响应"""

    items: list[MoodTypeItem] = Field(default=[], description="心情类型列表")


class CreateMoodTypeRequest(BaseModel):
    """创建心情类型"""

    name: str = Field(..., min_length=1, max_length=4, description="心情名称，最长 4 字符")
    icon: str = Field(..., description="Lucide 图标名")
    color: str = Field(..., description="十六进制颜色值")
    score: int = Field(..., ge=0, le=100, description="心情评分权重 0-100")
    is_dark: int = Field(default=0, description="是否深色主题")
    sort_order: int = Field(default=0, description="排序权重")


class UpdateMoodTypeRequest(BaseModel):
    """更新心情类型（部分更新）"""

    name: str | None = Field(default=None, description="心情名称")
    icon: str | None = Field(default=None, description="Lucide 图标名")
    color: str | None = Field(default=None, description="十六进制颜色值")
    score: int | None = Field(default=None, ge=0, le=100, description="心情评分权重 0-100")
    is_dark: int | None = Field(default=None, description="是否深色主题")
    sort_order: int | None = Field(default=None, description="排序权重")


# ==================== 心情记录 ====================


class MoodEntryItem(BaseModel):
    """心情记录"""

    id: str = Field(..., description="心情记录 ID")
    mood_type_id: str = Field(..., description="关联心情类型 ID")
    score: int = Field(..., description="心情评分")
    content: str | None = Field(default=None, description="用户输入的文字内容")
    factors: list[str] = Field(default=[], description="影响因素列表")
    created_at: str = Field(default="", description="创建时间")
    event_time: str = Field(default="", description="事件时间（UTC ISO 8601）")


class MoodEntryListResponse(BaseModel):
    """心情记录列表响应"""

    items: list[MoodEntryItem] = Field(default=[], description="心情记录列表")


class CreateMoodEntryRequest(BaseModel):
    """创建心情记录（score 由 Service 层从 mood_type 自动获取）"""

    mood_type_id: str = Field(..., description="关联心情类型 ID")
    content: str | None = Field(default=None, description="用户输入的文字内容")
    factors: list[str] | None = Field(default=None, description="影响因素列表")
    event_time: str | None = Field(
        default=None, description="事件时间（UTC ISO 8601），不传则使用当前时间"
    )


class UpdateMoodEntryRequest(BaseModel):
    """更新心情记录（部分更新）"""

    mood_type_id: str | None = Field(default=None, description="关联心情类型 ID")
    content: str | None = Field(default=None, description="用户输入的文字内容")
    factors: list[str] | None = Field(default=None, description="影响因素列表")


# ==================== 影响因素 ====================


class MoodImpactItem(BaseModel):
    """影响因素"""

    id: int = Field(..., description="影响因素 ID")
    name: str = Field(..., description="因素名称")
    sort_order: int = Field(default=0, description="排序权重")
    created_at: str = Field(default="", description="创建时间")


class MoodImpactListResponse(BaseModel):
    """影响因素列表响应"""

    items: list[MoodImpactItem] = Field(default=[], description="影响因素列表")


class CreateMoodImpactRequest(BaseModel):
    """创建影响因素"""

    name: str = Field(..., description="因素名称")
    sort_order: int = Field(default=0, description="排序权重")
