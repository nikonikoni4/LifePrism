"""
应用分类管理API路由
"""

from fastapi import APIRouter, HTTPException, Path
from lifewatch.server.schemas.categories import AppCategoryList, AppCategory, UpdateCategoryRequest
from lifewatch.server.schemas.response import StandardResponse
from lifewatch.storage.lifewatch_data_manager import LifeWatchDataManager

router = APIRouter(prefix="/categories", tags=["Categories Management"])
db_manager = LifeWatchDataManager()


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
        df = db_manager.load_app_purpose_category()
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
        df = db_manager.query('app_purpose_category', where={'app': app_name})
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
    - class_by_default: 默认分类
    - class_by_goals: 目标分类
    - app_description: 应用描述
    - title_description: 标题描述
    
    **使用真实数据库更新**
    """
    try:
        # 检查应用是否存在
        df = db_manager.query('app_purpose_category', where={'app': app_name})
        if df.empty:
            raise HTTPException(status_code=404, detail=f"应用 '{app_name}' 未找到")
        
        # 构建更新数据
        update_dict = update_data.model_dump(exclude_none=True)
        update_dict['app'] = app_name
        
        # 执行更新
        affected = db_manager.upsert_many(
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
