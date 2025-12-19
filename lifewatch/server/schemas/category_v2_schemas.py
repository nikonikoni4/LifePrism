"""
Category V2 API Schema 定义

层级结构：
- CategoryDef (主分类)
  └── SubCategoryDef (子分类)
      └── AppUseInfo (应用使用情况)
          └── TitleDuration (标题及时长)
"""

from pydantic import BaseModel, Field
from typing import List


# ============================================================================
# 基础数据模型（从底层往上定义）
# ============================================================================

class TitleDuration(BaseModel):
    """标题及使用时长"""
    title: str = Field(..., description="窗口标题")
    duration: int = Field(..., description="使用时长（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Youtube - 首页",
                "duration": 300
            }
        }


class AppUseInfo(BaseModel):
    """应用使用情况"""
    name: str = Field(..., description="应用名称")
    duration: int | None = Field(default=None, description="该应用总使用时长（秒）")
    top_titles: list[TitleDuration] | None = Field(default=None, description="该应用下使用时长最长的标题列表")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "msedge.exe",
                "duration": 3600,
                "top_titles": [
                    {"title": "Youtube - 首页", "duration": 1200},
                    {"title": "GitHub - Issues", "duration": 800}
                ]
            }
        }


class SubCategoryDef(BaseModel):
    """子分类定义"""
    id: str = Field(..., description="子分类唯一标识符")
    name: str = Field(..., description="子分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式）")
    duration: int | None = Field(default=None, description="该子分类总时长（秒）")
    duration_percent: int | None = Field(default=None, description="该子分类占主分类的时长百分比")
    app_use_info: list[AppUseInfo] | None = Field(default=None, description="该子分类下的应用使用情况")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "coding",
                "name": "编程",
                "duration": 7200,
                "duration_percent": 60,
                "app_use_info": [
                    {
                        "name": "Code.exe",
                        "duration": 5400,
                        "top_titles": [
                            {"title": "main.py - VS Code", "duration": 3000}
                        ]
                    }
                ]
            }
        }


class CategoryDef(BaseModel):
    """主分类定义"""
    id: str = Field(..., description="分类唯一标识符")
    name: str = Field(..., description="分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式）")
    duration: int | None = Field(default=None, description="该分类总时长（秒）")
    duration_percent: int | None = Field(default=None, description="该分类占总时长的百分比")
    subcategories: list[SubCategoryDef] | None = Field(default=None, description="子分类列表，depth=1时为None")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "work",
                "name": "工作/学习",
                "color": "#5B8FF9",
                "duration": 14400,
                "duration_percent": 50,
                "subcategories": [
                    {
                        "id": "coding",
                        "name": "编程",
                        "duration": 7200,
                        "duration_percent": 50
                    }
                ]
            }
        }


# ============================================================================
# API 响应模型
# ============================================================================

class CategoryTreeResponse(BaseModel):
    """GET /category/tree 响应"""
    data: list[CategoryDef]


class CategoryStatsResponse(BaseModel):
    """GET /category/state 响应"""
    data: list[CategoryDef]
    query: dict | None = Field(default=None, description="查询参数回显（调试用）")


class CategoryStatsIncludeOptions(BaseModel):
    """
    分类统计 include 选项
    
    用于在 API 层解析 include 字符串后，以类型安全的方式传递给 Service 层
    """
    include_duration: bool = Field(default=True, description="是否包含时长统计")
    include_app: bool = Field(default=True, description="是否包含应用列表")
    include_title: bool = Field(default=True, description="是否包含标题列表")
    
    @classmethod
    def from_include_string(cls, include_str: str) -> "CategoryStatsIncludeOptions":
        """
        从逗号分隔的字符串解析选项
        
        Args:
            include_str: 如 "app,duration,title"
            
        Returns:
            CategoryStatsIncludeOptions 实例
        """
        include_set = {item.strip().lower() for item in include_str.split(',')}
        return cls(
            include_duration='duration' in include_set,
            include_app='app' in include_set,
            include_title='title' in include_set
        )


# ============================================================================
# CRUD 请求/响应模型
# ============================================================================

class CreateCategoryRequest(BaseModel):
    """创建主分类请求"""
    name: str = Field(..., description="分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式，如 #5B8FF9）")


class UpdateCategoryRequest(BaseModel):
    """更新主分类请求"""
    name: str | None = Field(default=None, description="新的分类名称")
    color: str | None = Field(default=None, description="新的分类颜色")


class DeleteCategoryRequest(BaseModel):
    """删除主分类请求"""
    reassign_to: str = Field(default="other", description="重新分配关联记录到的分类ID")


class CreateSubCategoryRequest(BaseModel):
    """创建子分类请求"""
    name: str = Field(..., description="子分类名称")


class UpdateSubCategoryRequest(BaseModel):
    """更新子分类请求"""
    name: str = Field(..., description="新的子分类名称")


