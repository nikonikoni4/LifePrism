"""
承诺模块 Schema 定义
"""

from pydantic import BaseModel, Field, model_validator


class CommitmentBriefItem(BaseModel):
    """承诺简要信息（用于 ValueDetailItem 内嵌）"""

    id: str = Field(..., description="承诺 ID (格式: cmt-xxx)")
    content: str = Field(..., description="承诺行动描述")
    status: str = Field(..., description="状态: active / completed / archived")
    created_at: str = Field(default="", description="创建时间")


class CommitmentItem(BaseModel):
    """承诺完整信息"""

    id: str = Field(..., description="承诺 ID (格式: cmt-xxx)")
    content: str = Field(..., description="承诺行动描述")
    value_id: str | None = Field(default=None, description="关联价值 ID")
    value_keyword: str | None = Field(default=None, description="关联价值短标签（JOIN 冗余）")
    status: str = Field(..., description="状态: active / completed / archived")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str | None = Field(default=None, description="更新时间")


class CommitmentListResponse(BaseModel):
    """承诺列表响应"""

    items: list[CommitmentItem] = Field(default=[], description="承诺列表")
    total: int = Field(default=0, description="总数")


class CreateCommitmentRequest(BaseModel):
    """创建承诺"""

    content: str = Field(..., description="承诺行动描述")
    value_id: str = Field(..., description="关联价值 ID")


class UpdateCommitmentRequest(BaseModel):
    """更新承诺（部分更新）"""

    content: str | None = Field(default=None, description="承诺行动描述")
    value_id: str | None = Field(default=None, description="关联价值 ID")
    status: str | None = Field(default=None, description="状态: active / completed / archived")

    @model_validator(mode="after")
    def check_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个要更新的字段")
        return self
