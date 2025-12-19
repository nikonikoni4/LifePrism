"""
Category API v2 - 分类数据接口

包含两个主要端点：
- /tree: 获取分类树形结构
- /state: 获取分类统计数据
"""

from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional, List
from datetime import datetime

from lifewatch.server.schemas.category_v2_schemas import (
    CategoryTreeResponse,
    CategoryStateResponse,
    CategoryDef,
    SubCategoryDef,
    CreateCategoryRequest,
    UpdateCategoryRequest,
    DeleteCategoryRequest,
    CreateSubCategoryRequest,
    UpdateSubCategoryRequest,
    StandardResponse
)
from lifewatch.server.services.category_v2_service import CategoryService
router = APIRouter(prefix="/category", tags=["Category V2"])


# ============================================================================
# /tree - 分类结构接口
# ============================================================================

@router.get("/tree", summary="获取分类树形结构")
async def get_category_tree(
    depth: int = Query(
        default=1,
        ge=1,
        le=2,
        description="返回层级深度。1=仅主分类，2=主分类+子分类"
    )
)->CategoryTreeResponse:
    try:
        category_service = CategoryService()
        return category_service.get_category_tree(depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类结构失败: {str(e)}")


# ============================================================================
# /state - 分类统计接口
# ============================================================================

@router.get("/state", summary="获取分类统计数据")
async def get_category_state(
    # 包含的数据类型（可多选，逗号分隔）
    include: str = Query(
        default="app,duration,title",
        description="包含的数据类型，可多选逗号分隔。可选值：app, duration, title"
    ),
    # 时间范围
    start_time: datetime = Query(
        description="开始时间，ISO 8601 格式，如 2024-12-18T00:00:00"
    ),
    end_time: datetime = Query(
        description="结束时间，ISO 8601 格式"
    ),
    # 数量限制
    top_title: int = Query(
        default=3,
        ge=1,
        le=20,
        description="返回的 Top 标题数量"
    ),
    # 筛选条件
    category: Optional[str] = Query(
        default=None,
        description="按主分类ID筛选"
    ),
    sub_category: Optional[str] = Query(
        default=None,
        description="按子分类ID筛选"
    )
)->CategoryStateResponse:
    """
    获取分类相关的统计数据
    
    **参数：**
    - `include`: 包含的数据类型
        - `duration`: 时长统计
        - `app`: 应用列表
        - `title`: 标题列表
        - 可组合使用，如 `include=duration,app`
    - `start_time`, `end_time`: 统计的时间范围
    - `top_title`: 返回的 Top 标题数量
    - `category`, `sub_category`: 按分类筛选
    
    **响应示例：**
    ```json
    {
        "data": [
            {
                "id": "work",
                "name": "工作/学习",
                "duration": 14400,
                "apps": [
                    {"name": "Code.exe", "duration": 7200},
                    {"name": "PyCharm", "duration": 3600}
                ],
                "titles": [
                    {"title": "main.py - VS Code", "duration": 3600},
                    {"title": "api.py - VS Code", "duration": 2400}
                ]
            }
        ]
    }
    ```
    """
    try:
        category_service = CategoryService()
        return category_service.get_category_state(start_time, end_time, include, top_title, category, sub_category)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类统计失败: {str(e)}")


# ============================================================================
# /manage - 分类管理接口（CRUD）
# ============================================================================

@router.post("/manage", response_model=CategoryDef, summary="创建主分类")
async def create_category(request: CreateCategoryRequest):
    """
    创建新的主分类
    
    请求体:
    - name: 分类名称
    - color: 分类颜色（十六进制格式，如 #5B8FF9）
    
    返回创建的分类对象
    """
    try:
        category_service = CategoryService()
        category = category_service.create_category(
            name=request.name,
            color=request.color
        )
        return category
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建分类失败: {str(e)}")


@router.put("/manage/{category_id}", response_model=CategoryDef, summary="更新主分类")
async def update_category(
    category_id: str = Path(..., description="分类ID"),
    request: UpdateCategoryRequest = ...
):
    """
    更新主分类的名称或颜色
    
    路径参数:
    - category_id: 分类ID
    
    请求体:
    - name: 新的分类名称（可选）
    - color: 新的分类颜色（可选）
    """
    try:
        category_service = CategoryService()
        category = category_service.update_category(
            category_id=category_id,
            name=request.name or "",
            color=request.color or ""
        )
        return category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新分类失败: {str(e)}")


@router.delete("/manage/{category_id}", response_model=StandardResponse, summary="删除主分类")
async def delete_category(
    category_id: str = Path(..., description="分类ID"),
    request: DeleteCategoryRequest = DeleteCategoryRequest()
):
    """
    删除主分类
    
    注意：
    - 会自动删除该分类下的所有子分类（CASCADE）
    - 关联的活动记录会被重新分配到指定分类（默认 'other'）
    """
    try:
        category_service = CategoryService()
        success = category_service.delete_category(
            category_id=category_id,
            reassign_to=request.reassign_to
        )
        return StandardResponse(
            success=True,
            data={"deleted": success},
            message=f"分类 '{category_id}' 删除成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除分类失败: {str(e)}")


@router.post("/manage/{parent_id}/sub", response_model=SubCategoryDef, summary="添加子分类")
async def create_sub_category(
    parent_id: str = Path(..., description="主分类ID"),
    request: CreateSubCategoryRequest = ...
):
    """
    为指定主分类添加子分类
    
    路径参数:
    - parent_id: 主分类ID
    
    请求体:
    - name: 子分类名称
    """
    try:
        category_service = CategoryService()
        sub_category = category_service.create_sub_category(
            category_id=parent_id,
            name=request.name
        )
        return sub_category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建子分类失败: {str(e)}")


@router.put("/manage/{parent_id}/sub/{sub_id}", response_model=SubCategoryDef, summary="更新子分类")
async def update_sub_category(
    parent_id: str = Path(..., description="主分类ID"),
    sub_id: str = Path(..., description="子分类ID"),
    request: UpdateSubCategoryRequest = ...
):
    """
    更新子分类名称
    
    路径参数:
    - parent_id: 主分类ID
    - sub_id: 子分类ID
    
    请求体:
    - name: 新的子分类名称
    """
    try:
        category_service = CategoryService()
        sub_category = category_service.update_sub_category(
            category_id=parent_id,
            sub_id=sub_id,
            name=request.name
        )
        return sub_category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新子分类失败: {str(e)}")


@router.delete("/manage/{parent_id}/sub/{sub_id}", response_model=StandardResponse, summary="删除子分类")
async def delete_sub_category(
    parent_id: str = Path(..., description="主分类ID"),
    sub_id: str = Path(..., description="子分类ID")
):
    """
    删除子分类
    
    注意：关联的活动记录会被重新分配到 'untracked' 子分类
    """
    try:
        category_service = CategoryService()
        success = category_service.delete_sub_category(
            category_id=parent_id,
            sub_id=sub_id
        )
        return StandardResponse(
            success=True,
            data={"deleted": success},
            message=f"子分类 '{sub_id}' 删除成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除子分类失败: {str(e)}")


