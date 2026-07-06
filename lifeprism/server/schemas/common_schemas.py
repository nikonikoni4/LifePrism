"""
通用 Schema 定义

存放跨模块共享的通用数据模型
"""

from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# 通用响应模型
# ============================================================================


class StandardResponse(BaseModel):
    """通用响应模型"""

    success: bool = Field(..., description="操作是否成功")
    data: dict[str, Any] | None = Field(default=None, description="响应数据")
    message: str | None = Field(default=None, description="响应消息")


class PaginatedResponse(BaseModel):
    """通用分页响应模型"""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    has_more: bool = Field(default=False, description="是否有更多数据")
