"""
应用分类管理API路由
(已弃用)
"""

from fastapi import APIRouter, HTTPException, Path
from lifewatch.server.schemas.categories import AppCategoryList, AppCategory, UpdateCategoryRequest
from lifewatch.server.schemas.response import StandardResponse
from lifewatch.server.providers.statistical_data_providers import server_lw_data_provider

router = APIRouter(prefix="/categories", tags=["Categories Management"])


@router.get("/apps", response_model=AppCategoryList, summary="获取所有应用分类")
async def get_all_app_categories():
    """
    获取所有已分类的应用列表
    
    返回数据库中所有应用的分类信息，包括：
    - 应用名称
    - 分类信息（默认分类和目标分类）
    - 应用描述
    - 是否为多用途应用
    
    **使用真实数据库查询**
    """
    try:
        df = server_lw_data_provider.load_app_purpose_category()
        if df is None or df.empty:
            return {"total": 0, "data": []}
        
        data = df.to_dict('records')
        return {"total": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/apps/{app_name}", response_model=AppCategory, summary="获取指定应用分类")
async def get_app_category(
    app_name: str = Path(..., description="应用程序名称（例如：chrome.exe）")
):
    """
    获取指定应用的分类信息
    
    **使用真实数据库查询**
    """
    try:
        df = server_lw_data_provider.db.query('app_purpose_category', where={'app': app_name})
        if df.empty:
            raise HTTPException(status_code=404, detail=f"应用 '{app_name}' 未找到")
        
        return df.iloc[0].to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.put("/apps/{app_name}", response_model=StandardResponse, summary="更新应用分类")
async def update_app_category(
    app_name: str = Path(..., description="应用程序名称"),
    update_data: UpdateCategoryRequest = ...
):
    """
    更新指定应用的分类信息
    
    可更新字段：
    - category: 默认分类
    - sub_category: 目标分类
    - app_description: 应用描述
    - title_analysis: 标题描述
    
    **使用真实数据库更新**
    """
    try:
        # 检查应用是否存在
        df = server_lw_data_provider.db.query('app_purpose_category', where={'app': app_name})
        if df.empty:
            raise HTTPException(status_code=404, detail=f"应用 '{app_name}' 未找到")
        
        # 构建更新数据
        update_dict = update_data.model_dump(exclude_none=True)
        update_dict['app'] = app_name
        
        # 执行更新
        affected = server_lw_data_provider.db.upsert_many(
            'app_purpose_category',
            [update_dict],
            conflict_columns=['app']
        )
        
        return StandardResponse(
            success=True,
            data={"affected_rows": affected},
            message=f"应用 '{app_name}' 分类更新成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


# ============================================================================
# Category Settings API - 分类设置管理
# ============================================================================

from lifewatch.server.schemas.category_schemas import (
    CategoryListResponse, CategoryResponse, SubCategoryResponse,
    CreateCategoryRequest, UpdateCategoryRequest as UpdateCategoryReq,
    CreateSubCategoryRequest, UpdateSubCategoryRequest
)
from lifewatch.server.services.category_service import CategoryService

category_service = CategoryService()


@router.get("", response_model=CategoryListResponse, summary="获取所有分类")
async def get_categories():
    """
    获取完整的分类层级结构
    
    返回所有主分类及其对应的子分类列表
    
    对应前端需求: GET /api/categories
    """
    try:
        categories = category_service.get_all_categories()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类失败: {str(e)}")


@router.post("", response_model=CategoryResponse, summary="创建主分类")
async def create_category(request: CreateCategoryRequest):
    """
    创建新的主分类
    
    请求体:
    - name: 分类名称
    - color: 分类颜色（十六进制格式，如 #5B8FF9）
    
    返回创建的分类对象
    
    对应前端需求: POST /api/categories
    """
    try:
        category = category_service.create_category(
            name=request.name,
            color=request.color
        )
        return category
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建分类失败: {str(e)}")


@router.put("/{category_id}", response_model=CategoryResponse, summary="更新主分类")
async def update_category(
    category_id: str = Path(..., description="分类ID"),
    request: UpdateCategoryReq = ...
):
    """
    更新主分类的名称或颜色
    
    路径参数:
    - category_id: 分类ID
    
    请求体:
    - name: 新的分类名称（可选）
    - color: 新的分类颜色（可选）
    
    对应前端需求: PUT /api/categories/:id
    """
    try:
        category = category_service.update_category(
            category_id=category_id,
            name=request.name,
            color=request.color
        )
        return category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新分类失败: {str(e)}")


@router.delete("/{category_id}", response_model=StandardResponse, summary="删除主分类")
async def delete_category(
    category_id: str = Path(..., description="分类ID")
):
    """
    删除主分类
    
    注意：
    - 会自动删除该分类下的所有子分类（CASCADE）
    - 关联的活动记录会被重新分配到 'other' 分类
    
    对应前端需求: DELETE /api/categories/:id
    """
    try:
        success = category_service.delete_category(category_id)
        return StandardResponse(
            success=True,
            data={"deleted": success},
            message=f"分类 '{category_id}' 删除成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除分类失败: {str(e)}")


@router.post("/{parent_id}/sub", response_model=SubCategoryResponse, summary="添加子分类")
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
    
    对应前端需求: POST /api/categories/:parentId/sub
    """
    try:
        sub_category = category_service.create_sub_category(
            category_id=parent_id,
            name=request.name
        )
        return sub_category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建子分类失败: {str(e)}")


@router.put("/{parent_id}/sub/{sub_id}", response_model=SubCategoryResponse, summary="更新子分类")
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
    
    对应前端需求: PUT /api/categories/:parentId/sub/:subId
    """
    try:
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


@router.delete("/{parent_id}/sub/{sub_id}", response_model=StandardResponse, summary="删除子分类")
async def delete_sub_category(
    parent_id: str = Path(..., description="主分类ID"),
    sub_id: str = Path(..., description="子分类ID")
):
    """
    删除子分类
    
    注意：关联的活动记录会被重新分配到 'untracked' 子分类
    
    对应前端需求: DELETE /api/categories/:parentId/sub/:subId
    """
    try:
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

