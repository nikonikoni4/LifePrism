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
# Tree 端点专用模型（精简版，无统计数据）
# ============================================================================

class SubCategoryTreeItem(BaseModel):
    """子分类树节点（精简）"""
    id: str = Field(..., description="子分类唯一标识符")
    name: str = Field(..., description="子分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式）")
    state: int = Field(default=1, description="分类状态（1: 启用, 0: 禁用）")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "coding",
                "name": "编程",
                "color": "#5B8FF9",
                "state": 1
            }
        }


class CategoryTreeItem(BaseModel):
    """主分类树节点（精简）"""
    id: str = Field(..., description="分类唯一标识符")
    name: str = Field(..., description="分类名称")
    color: str = Field(..., description="分类颜色（十六进制格式）")
    state: int = Field(default=1, description="分类状态（1: 启用, 0: 禁用）")
    subcategories: list[SubCategoryTreeItem] | None = Field(default=None, description="子分类列表，depth=1时为None")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "work",
                "name": "工作/学习",
                "color": "#5B8FF9",
                "state": 1,
                "subcategories": [
                    {
                        "id": "coding",
                        "name": "编程",
                        "color": "#7C9AE6",
                        "state": 1
                    }
                ]
            }
        }


# ============================================================================
# Stats 端点专用模型（完整版，含统计数据）
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
    data: list[CategoryTreeItem]


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


class ToggleCategoryStateRequest(BaseModel):
    """切换分类状态请求"""
    state: int = Field(..., ge=0, le=1, description="新状态（1: 启用, 0: 禁用）")


# ============================================================================
# CategoryMapCache 数据展示模型
# ============================================================================

class CategoryMapCacheItem(BaseModel):
    """
    category_map_cache 表单条记录展示
    
    用于在分类管理页面的新选项卡中展示 AI 分类元数据
    注意：category 和 sub_category 是通过 ID 映射得到的名称，而非直接从表中读取
    """
    # 主键
    id: str = Field(..., description="记录唯一标识（格式：m-xxx 或 s-xxx）")
    # 核心展示字段
    app: str = Field(..., description="应用程序名称（如 chrome.exe）")
    app_description: str | None = Field(default=None, description="应用程序描述（AI 生成）")
    title: str = Field(..., description="窗口标题")
    title_analysis: str | None = Field(default=None, description="标题分析结果（AI 生成）")
    # 分类信息（映射后的名称）
    category: str | None = Field(default=None, description="主分类名称（通过 category_id 映射）")
    sub_category: str | None = Field(default=None, description="子分类名称（通过 sub_category_id 映射）")
    # 分类 ID（原始值）
    category_id: str | None = Field(default=None, description="主分类ID（原始值）")
    sub_category_id: str | None = Field(default=None, description="子分类ID（原始值）")
    # Goal 关联
    link_to_goal_id: str | None = Field(default=None, description="关联的目标ID")
    link_to_goal: str | None = Field(default=None, description="关联的目标名称（通过 ID 映射）")
    # 其他字段
    is_multipurpose_app: bool = Field(default=False, description="是否为多用途应用")
    state: int = Field(default=1, description="记录状态（1: 有效, 0: 无效）")
    created_at: str | None = Field(default=None, description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "m-a1b2c3d4",
                "app": "msedge.exe",
                "app_description": "Microsoft Edge 浏览器，用于网页浏览",
                "title": "YouTube - 首页",
                "title_analysis": "用户正在观看 YouTube 视频",
                "category": "娱乐",
                "sub_category": "视频",
                "category_id": "entertainment",
                "sub_category_id": "video",
                "link_to_goal_id": "goal-123",
                "link_to_goal": "学习 Python",
                "is_multipurpose_app": True,
                "state": 1,
                "created_at": "2025-12-22T10:30:00"
            }
        }

class CategoryMapCacheResponse(BaseModel):
    """GET /category/app-purpose 响应"""
    data: List[CategoryMapCacheItem] = Field(..., description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页记录数")
    total_pages: int = Field(..., description="总页数")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "app": "msedge.exe",
                        "app_description": "Microsoft Edge 浏览器",
                        "title": "YouTube",
                        "title_analysis": "视频观看",
                        "category": "娱乐",
                        "sub_category": "视频"
                    }
                ],
                "total": 100,
                "page": 1,
                "page_size": 50,
                "total_pages": 2
            }
        }


# ============================================================================
# CategoryMapCache 更新/删除请求模型
# ============================================================================

class UpdateCategoryMapCacheRequest(BaseModel):
    """更新 category_map_cache 记录请求"""
    id: str = Field(..., description="记录ID（格式：m-xxx 或 s-xxx）")
    category_id: str | None = Field(default=None, description="新的主分类ID，为空时不修改")
    sub_category_id: str | None = Field(default=None, description="新的子分类ID")
    app_description: str | None = Field(default=None, description="应用程序描述，为空时不修改")
    title_analysis: str | None = Field(default=None, description="标题分析结果，为空时不修改")
    link_to_goal_id: str | None = Field(default=None, description="新的关联目标ID，为空时不修改")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "m-a1b2c3d4",
                "category_id": "cat-124",
                "sub_category_id": "subcat-124",
                "app_description": "Microsoft Edge 浏览器",
                "title_analysis": "用户正在浏览视频网站",
                "link_to_goal_id": "goal-123"
            }
        }


class BatchUpdateCategoryMapCacheRequest(BaseModel):
    """批量更新 category_map_cache 记录请求"""
    ids: List[str] = Field(..., description="记录ID列表", min_length=1)
    category_id: str | None = Field(default=None, description="新的主分类ID，为空时不修改")
    sub_category_id: str | None = Field(default=None, description="新的子分类ID")
    app_description: str | None = Field(default=None, description="应用程序描述，为空时不修改")
    link_to_goal_id: str | None = Field(default=None, description="新的关联目标ID，为空时不修改")
    class Config:
        json_schema_extra = {
            "example": {
                "ids": ["m-a1b2c3d4", "s-e5f6g7h8"],
                "category_id": "cat-124",
                "sub_category_id": "subcat-124",
                "app_description": "Microsoft Edge 浏览器"
            }
        }


class DeleteCategoryMapCacheRequest(BaseModel):
    """删除 category_map_cache 记录请求"""
    id: str = Field(..., description="记录ID（格式：m-xxx 或 s-xxx）")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "m-a1b2c3d4"
            }
        }


class BatchDeleteCategoryMapCacheRequest(BaseModel):
    """批量删除 category_map_cache 记录请求"""
    ids: List[str] = Field(..., description="记录ID列表", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "ids": ["m-a1b2c3d4", "s-e5f6g7h8"]
            }
        }
