"""
分类管理相关数据模型 - Category Settings API
Pydantic V2 兼容版本
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ============ 基础定义模型 ============

class SubCategoryDef(BaseModel):
    """子分类定义"""
    id: str = Field(..., description="子分类唯一标识符")
    name: str = Field(..., description="子分类名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "coding",
                "name": "Coding"
            }
        }


class CategoryDef(BaseModel):
    """主分类定义（含子分类）"""
    id: str = Field(..., description="分类唯一标识符")
    name: str = Field(..., description="分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式）")
    subCategories: List[SubCategoryDef] = Field(default_factory=list, description="子分类列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "work",
                "name": "工作/学习",
                "color": "#5B8FF9",
                "subCategories": [
                    {"id": "coding", "name": "Coding"},
                    {"id": "meeting", "name": "Meetings"}
                ]
            }
        }


# ============ 请求模型 ============

class CreateCategoryRequest(BaseModel):
    """创建主分类请求"""
    name: str = Field(..., min_length=1, max_length=50, description="分类名称")
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$', description="分类颜色（十六进制格式，如 #5B8FF9）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "学习",
                "color": "#34D399"
            }
        }


class UpdateCategoryRequest(BaseModel):
    """更新主分类请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="分类名称")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="分类颜色")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "工作",
                "color": "#5B8FF9"
            }
        }


class CreateSubCategoryRequest(BaseModel):
    """创建子分类请求"""
    name: str = Field(..., min_length=1, max_length=50, description="子分类名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "编程"
            }
        }


class UpdateSubCategoryRequest(BaseModel):
    """更新子分类请求"""
    name: str = Field(..., min_length=1, max_length=50, description="子分类名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "代码审查"
            }
        }


# ============ 响应模型 ============

class CategoryListResponse(BaseModel):
    """分类列表响应"""
    categories: List[CategoryDef] = Field(..., description="分类列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "categories": [
                    {
                        "id": "work",
                        "name": "工作/学习",
                        "color": "#5B8FF9",
                        "subCategories": [
                            {"id": "coding", "name": "Coding"}
                        ]
                    }
                ]
            }
        }


class CategoryResponse(BaseModel):
    """单个分类响应"""
    id: str
    name: str
    color: str
    subCategories: List[SubCategoryDef] = Field(default_factory=list)


class SubCategoryResponse(BaseModel):
    """子分类响应"""
    id: str
    name: str
