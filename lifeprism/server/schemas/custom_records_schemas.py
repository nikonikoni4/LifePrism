"""
自定义记录模块 Schema 定义

类型管理 + 记录 CRUD 的请求/响应模型
"""

from typing import Literal

from pydantic import BaseModel, Field

# ==================== 字段定义 ====================


class FieldDefinition(BaseModel):
    """字段定义"""

    id: str = Field(default="", description="字段 ID（crf-{uuid[:8]}）")
    field_name: str = Field(..., description="字段显示名")
    field_key: str = Field(..., description="字段标识，英文小写+下划线")
    field_type: Literal["text", "integer", "float"] = Field(
        default="text", description="字段类型：text 文本 / integer 整数 / float 浮点数"
    )
    display_role: Literal["auto", "title", "main", "chip", "hidden"] = Field(
        default="auto", description="字段展示角色"
    )


# ==================== 类型管理 ====================


class CustomRecordTypeItem(BaseModel):
    """自定义记录类型"""

    id: str = Field(..., description="类型 ID")
    name: str = Field(..., description="类型显示名")
    slug: str = Field(..., description="语义化标识")
    description: str = Field(default="", description="类型描述")
    fields: list[FieldDefinition] = Field(default=[], description="字段定义列表")
    card_template: Literal["clean", "paper", "minimal", "bold", "metric"] = Field(
        default="clean", description="卡片模板"
    )
    icon: str = Field(default="fileText", description="类型图标名")
    accent_color: str = Field(default="blue", description="强调色")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class CustomRecordTypeListResponse(BaseModel):
    """类型列表响应"""

    items: list[CustomRecordTypeItem] = Field(default=[], description="类型列表")


class CreateCustomRecordTypeRequest(BaseModel):
    """创建自定义记录类型"""

    name: str = Field(..., min_length=1, description="类型显示名")
    slug: str = Field(..., min_length=1, description="语义化标识，英文小写+下划线")
    fields: list[FieldDefinition] = Field(..., min_length=1, description="字段定义列表，至少 1 个")
    description: str | None = Field(default=None, description="类型描述（可选）")


# ==================== 记录管理 ====================


class CustomRecordEntryItem(BaseModel):
    """自定义记录条目"""

    id: str = Field(..., description="记录 ID")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")

    # 允许动态字段（用户自定义的 field_key: value）
    model_config = {"extra": "allow"}


class CustomRecordEntryListResponse(BaseModel):
    """记录列表响应"""

    items: list[CustomRecordEntryItem] = Field(default=[], description="记录列表")
    total: int = Field(default=0, description="满足筛选条件的总记录数")


class CreateCustomRecordEntryRequest(BaseModel):
    """录入自定义记录"""

    data: dict[str, str | int | float] = Field(
        default={}, description="字段值字典 {field_key: value}，value 类型由字段定义决定"
    )


# ==================== 配置更新 ====================


class UpdateTypeConfigRequest(BaseModel):
    """更新类型展示配置"""

    card_template: Literal["clean", "paper", "minimal", "bold", "metric"] | None = Field(
        default=None, description="卡片模板"
    )
    icon: str | None = Field(default=None, description="类型图标名")
    accent_color: str | None = Field(default=None, description="强调色")


class UpdateFieldRoleRequest(BaseModel):
    """更新字段展示角色"""

    display_role: Literal["auto", "title", "main", "chip", "hidden"] = Field(
        ..., description="展示角色"
    )
