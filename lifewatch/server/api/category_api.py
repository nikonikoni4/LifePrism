"""
Category API v2 - 分类数据接口

包含两个主要端点：
- /tree: 获取分类树形结构
- /state: 获取分类统计数据
"""

from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional, List
from datetime import datetime

from lifewatch.server.schemas.category_schemas import (
    CategoryTreeResponse,
    CategoryTreeItem,
    SubCategoryTreeItem,
    CategoryStatsResponse,
    CategoryStatsIncludeOptions,
    CreateCategoryRequest,
    UpdateCategoryRequest,
    DeleteCategoryRequest,
    CreateSubCategoryRequest,
    UpdateSubCategoryRequest,
    ToggleCategoryStateRequest,
    # AppPurposeCategory 相关
    AppPurposeCategoryItem,
    AppPurposeCategoryResponse,
    UpdateAppPurposeCategoryRequest,
    BatchUpdateAppPurposeCategoryRequest,
    DeleteAppPurposeCategoryRequest,
    BatchDeleteAppPurposeCategoryRequest
)
from lifewatch.server.schemas.common_schemas import StandardResponse
from lifewatch.server.services import category_service
from lifewatch.utils import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/category", tags=["Category V2"])


# ============================================================================
# /tree - 分类结构接口
# ============================================================================

@router.get("/tree", summary="获取分类树形结构")
async def get_category_tree(
    depth: int = Query(
        default=2,
        ge=1,
        le=2,
        description="返回层级深度。1=仅主分类，2=主分类+子分类"
    )
)->CategoryTreeResponse:
    try:
        return category_service.get_category_tree(depth)
    except Exception as e:
        logger.error(f"获取分类结构失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取分类结构失败: {str(e)}")


# ============================================================================
# /stats - 分类统计接口
# ============================================================================

@router.get("/stats", summary="获取分类统计数据")
async def get_category_stats(
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
)->CategoryStatsResponse:
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
        # API 层职责：解析 include 字符串为结构化选项
        include_options = CategoryStatsIncludeOptions.from_include_string(include)
        
        return category_service.get_category_stats(
            start_time=start_time,
            end_time=end_time,
            include_options=include_options,
            top_title=top_title,
            category=category,
            sub_category=sub_category
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分类统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取分类统计失败: {str(e)}")


# ============================================================================
# /manage - 分类管理接口（CRUD）
# ============================================================================

@router.post("/manage", response_model=CategoryTreeItem, summary="创建主分类")
async def create_category(request: CreateCategoryRequest):
    """
    创建新的主分类
    
    请求体:
    - name: 分类名称
    - color: 分类颜色（十六进制格式，如 #5B8FF9）
    
    返回创建的分类对象
    """
    try:
        category = category_service.create_category(
            name=request.name,
            color=request.color
        )
        return category
    except Exception as e:
        logger.error(f"创建分类失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建分类失败: {str(e)}")


@router.put("/manage/{category_id}", response_model=CategoryTreeItem, summary="更新主分类")
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
        category = category_service.update_category(
            category_id=category_id,
            name=request.name or "",
            color=request.color or ""
        )
        return category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新分类失败: {str(e)}")
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
        logger.error(f"删除分类失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除分类失败: {str(e)}")


@router.post("/manage/{parent_id}/sub", response_model=SubCategoryTreeItem, summary="添加子分类")
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
        sub_category = category_service.create_sub_category(
            category_id=parent_id,
            name=request.name
        )
        return sub_category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"创建子分类失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建子分类失败: {str(e)}")


@router.put("/manage/{parent_id}/sub/{sub_id}", response_model=SubCategoryTreeItem, summary="更新子分类")
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
        sub_category = category_service.update_sub_category(
            category_id=parent_id,
            sub_id=sub_id,
            name=request.name
        )
        return sub_category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新子分类失败: {str(e)}")
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
        logger.error(f"删除子分类失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除子分类失败: {str(e)}")


# ============================================================================
# /state - 分类状态切换接口
# ============================================================================

@router.patch("/manage/{category_id}/state", response_model=CategoryTreeItem, summary="切换主分类状态")
async def toggle_category_state(
    category_id: str = Path(..., description="分类ID"),
    request: ToggleCategoryStateRequest = ...
):
    """
    切换主分类的启用/禁用状态
    
    - state=1: 启用
    - state=0: 禁用（该分类将不再参与自动分类，已分类数据不受影响）
    """
    try:
        category = category_service.toggle_category_state(
            category_id=category_id,
            state=request.state
        )
        return category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"切换分类状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"切换分类状态失败: {str(e)}")


@router.patch("/manage/{parent_id}/sub/{sub_id}/state", response_model=SubCategoryTreeItem, summary="切换子分类状态")
async def toggle_sub_category_state(
    parent_id: str = Path(..., description="主分类ID"),
    sub_id: str = Path(..., description="子分类ID"),
    request: ToggleCategoryStateRequest = ...
):
    """
    切换子分类的启用/禁用状态
    
    - state=1: 启用
    - state=0: 禁用（该子分类将不再参与自动分类，已分类数据不受影响）
    """
    try:
        sub_category = category_service.toggle_sub_category_state(
            category_id=parent_id,
            sub_id=sub_id,
            state=request.state
        )
        return sub_category
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"切换子分类状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"切换子分类状态失败: {str(e)}")


# ============================================================================
# /app_purpose_category - 分类缓存表接口
# ============================================================================

@router.get("/app_purpose", response_model=AppPurposeCategoryResponse, summary="获取分类缓存列表")
async def get_app_purpose_category_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页数量"),
    search: Optional[str] = Query(default=None, description="搜索关键词（匹配 app 或 title）"),
    state: Optional[int] = Query(default=None, ge=0, le=1, description="按状态筛选"),
):
    """
    获取 app_purpose_category 分类缓存列表
    
    支持分页、搜索和状态筛选
    """
    try:
        # 调用 Service 层获取数据
        result = category_service.get_app_purpose_category_list(
            page=page,
            page_size=page_size,
            search=search,
            state=state
        )
        return result
    except Exception as e:
        logger.error(f"获取分类缓存列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取分类缓存列表失败: {str(e)}")


# 注意：静态路径路由必须放在动态路径路由之前，否则 "batch" 会被错误解析为 record_id
@router.put("/app_purpose/batch", response_model=StandardResponse, summary="批量更新分类缓存记录")
async def batch_update_app_purpose_category(
    request: BatchUpdateAppPurposeCategoryRequest
):
    """
    批量更新 app_purpose_category 记录的分类
    
    - 更新时会自动同步目标分类的 state 状态
    """
    try:
        count = category_service.batch_update_app_purpose_category(
            record_ids=request.ids,
            category_id=request.category_id,
            sub_category_id=request.sub_category_id
        )
        return StandardResponse(
            success=True,
            data={"updated_count": count},
            message=f"成功更新 {count} 条记录"
        )
    except Exception as e:
        logger.error(f"批量更新分类缓存记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量更新分类缓存记录失败: {str(e)}")


@router.put("/app_purpose/{record_id}", response_model=StandardResponse, summary="更新分类缓存记录")
async def update_app_purpose_category(
    record_id: int = Path(..., description="记录ID"),
    request: UpdateAppPurposeCategoryRequest = ...
):
    """
    更新单条 app_purpose_category 记录的分类
    
    - 更新时会自动同步目标分类的 state 状态
    """
    try:
        success = category_service.update_app_purpose_category(
            record_id=record_id,
            category_id=request.category_id,
            sub_category_id=request.sub_category_id
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"记录 ID={record_id} 不存在")
        return StandardResponse(
            success=True,
            data={"updated": True},
            message=f"记录 ID={record_id} 更新成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新分类缓存记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新分类缓存记录失败: {str(e)}")


# 同样，DELETE 的 batch 路由也需要放在动态路径之前
@router.delete("/app_purpose/batch", response_model=StandardResponse, summary="批量删除分类缓存记录")
async def batch_delete_app_purpose_category(
    request: BatchDeleteAppPurposeCategoryRequest
):
    """
    批量删除 app_purpose_category 记录
    """
    try:
        count = category_service.batch_delete_app_purpose_category(record_ids=request.ids)
        return StandardResponse(
            success=True,
            data={"deleted_count": count},
            message=f"成功删除 {count} 条记录"
        )
    except Exception as e:
        logger.error(f"批量删除分类缓存记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量删除分类缓存记录失败: {str(e)}")


@router.delete("/app_purpose/{record_id}", response_model=StandardResponse, summary="删除分类缓存记录")
async def delete_app_purpose_category(
    record_id: int = Path(..., description="记录ID")
):
    """
    删除单条 app_purpose_category 记录
    """
    try:
        success = category_service.delete_app_purpose_category(record_id=record_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"记录 ID={record_id} 不存在")
        return StandardResponse(
            success=True,
            data={"deleted": True},
            message=f"记录 ID={record_id} 删除成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除分类缓存记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除分类缓存记录失败: {str(e)}")
