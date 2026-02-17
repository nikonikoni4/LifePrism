"""
价值模块 Schema 定义
"""
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List

from lifeprism.server.schemas.commitment_schemas import CommitmentBriefItem


class ValueItem(BaseModel):
    """价值信息"""
    id: str = Field(..., description="价值 ID (格式: val-xxx)")
    keyword: str = Field(..., description="短标签（2-4字）")
    content: Optional[str] = Field(default=None, description="详细描述")
    sort_order: int = Field(default=0, description="排序权重")
    created_at: str = Field(default="", description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class ValueDetailItem(ValueItem):
    """价值详情（含关联承诺列表）"""
    commitments: List[CommitmentBriefItem] = Field(default=[], description="关联承诺列表")


class ValueListResponse(BaseModel):
    """价值列表响应"""
    items: List[ValueItem] = Field(default=[], description="价值列表")


class CreateValueRequest(BaseModel):
    """创建价值"""
    keyword: str = Field(..., description="短标签（2-4字）")
    content: Optional[str] = Field(default=None, description="详细描述")


class UpdateValueRequest(BaseModel):
    """更新价值（部分更新）"""
    keyword: Optional[str] = Field(default=None, description="短标签")
    content: Optional[str] = Field(default=None, description="详细描述")
    sort_order: Optional[int] = Field(default=None, description="排序权重")

    @model_validator(mode='after')
    def check_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个要更新的字段")
        return self
