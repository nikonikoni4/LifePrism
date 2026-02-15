"""
承诺与价值模块 Schema 定义

Value 和 Commitment 放同一文件，因为 ValueDetailItem 依赖 CommitmentBriefItem。
"""
from pydantic import BaseModel, Field
from typing import Optional, List


# ==================== Commitment Schema ====================

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
    value_id: Optional[str] = Field(default=None, description="关联价值 ID")
    value_keyword: Optional[str] = Field(default=None, description="关联价值短标签（JOIN 冗余）")
    status: str = Field(..., description="状态: active / completed / archived")
    created_at: str = Field(default="", description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class CommitmentListResponse(BaseModel):
    """承诺列表响应"""
    items: List[CommitmentItem] = Field(default=[], description="承诺列表")
    total: int = Field(default=0, description="总数")


class CreateCommitmentRequest(BaseModel):
    """创建承诺"""
    content: str = Field(..., description="承诺行动描述")
    value_id: str = Field(..., description="关联价值 ID")


class UpdateCommitmentRequest(BaseModel):
    """更新承诺（部分更新）"""
    content: Optional[str] = Field(default=None, description="承诺行动描述")
    value_id: Optional[str] = Field(default=None, description="关联价值 ID")
    status: Optional[str] = Field(default=None, description="状态: active / completed / archived")


# ==================== Value Schema ====================

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
