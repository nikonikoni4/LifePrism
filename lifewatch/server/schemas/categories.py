"""
应用分类管理相关数据模型 - Pydantic V2 兼容版本
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AppCategory(BaseModel):
    """应用分类信息"""
    app: str
    title: Optional[str] = None
    is_multipurpose_app: int = 0
    app_description: Optional[str] = None
    title_description: Optional[str] = None
    class_by_default: Optional[str] = None
    class_by_goals: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AppCategoryList(BaseModel):
    """应用分类列表响应"""
    total: int
    data: List[AppCategory]


class UpdateCategoryRequest(BaseModel):
    """更新应用分类请求"""
    class_by_default: Optional[str] = None
    class_by_goals: Optional[str] = None
    app_description: Optional[str] = None
    title_description: Optional[str] = None
