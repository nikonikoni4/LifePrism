"""
通用响应模型 - 最简化版本
"""

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class StandardResponse(BaseModel):
    """标准API响应格式"""
    success: bool = True
    data: Optional[Any] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = None


class PaginatedResponse(BaseModel):
    """分页响应格式"""
    total: int 
    page: int
    page_size: int
    data: List[Any]


