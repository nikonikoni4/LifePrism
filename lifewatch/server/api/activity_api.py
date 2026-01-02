"""
Activity V2 API 路由

新版 Activity API，采用统一入口设计：
- /activity/stats - 统计数据（支持 include 参数按需获取）
- /activity/logs - 日志数据
- /activity/manage - 管理操作
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List

from lifewatch.server.schemas.activity_schemas import (
    ActivityStatsIncludeOptions,
    ActivityStatsResponse,
    ActivityLogsResponse,
)
from lifewatch.server.schemas.common_schemas import StandardResponse
from lifewatch.server.services import activity_service
from lifewatch.utils import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/activity", tags=["Activity V2"])


# ============================================================================
# Stats API - 统计数据（只读）
# ============================================================================

@router.get("/stats", summary="获取活动统计数据", response_model=ActivityStatsResponse)
async def get_activity_stats(
    date: str = Query(
        ..., 
        description="中心日期 (YYYY-MM-DD 格式)", 
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    include: str = Query(
        "activity_summary,time_overview,top_title,top_app,todolist",
        description="需要包含的数据模块，多个用逗号分隔。可选值: activity_summary, time_overview, top_title, top_app, todolist"
    ),
    history_number: int = Query(
        15, 
        description="历史数据天数", 
        ge=0, 
        le=15
    ),
    future_number: int = Query(
        14, 
        description="未来数据天数", 
        ge=0, 
        le=15
    ),
    category_id: Optional[str] = Query(
        None, 
        description="主分类ID筛选（可选）"
    ),
    sub_category_id: Optional[str] = Query(
        None, 
        description="子分类ID筛选（可选）"
    )
) -> ActivityStatsResponse:
    """
    获取活动统计数据（统一入口）
    
    **功能：**
    - 根据 `include` 参数按需返回不同的数据模块
    - 支持日期范围和分类筛选
    
    **可包含的模块：**
    - `activity_summary`: 活动摘要条形图数据
    - `time_overview`: 时间概览（饼图+柱状图）
    - `top_title`: 热门窗口标题
    - `top_app`: 热门应用统计
    - `todolist`: 待办事项列表
    
    **示例：**
    - `/api/v2/activity/stats?date=2025-12-19&include=activity_summary,time_overview`
    - `/api/v2/activity/stats?date=2025-12-19&include=todolist&category_id=work`
    """
    try:
        # API 层职责：解析 include 字符串为结构化选项
        include_options = ActivityStatsIncludeOptions.from_include_string(include)
        
        return activity_service.get_activity_stats(
            date=date,
            include_options=include_options,
            history_number=history_number,
            future_number=future_number,
            category_id=category_id,
            sub_category_id=sub_category_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取活动统计失败: {str(e)}")


# ============================================================================
# Logs API - 日志数据
# ============================================================================

@router.get("/logs", summary="获取活动日志列表", response_model=ActivityLogsResponse)
async def get_activity_logs(
    start_time: str = Query(
        ..., 
        description="开始时间 (YYYY-MM-DD HH:MM:SS 格式)", 
        regex=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
    ),
    end_time: str = Query(
        ..., 
        description="结束时间 (YYYY-MM-DD HH:MM:SS 格式)", 
        regex=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
    ),
    device_filter: str = Query(
        "all", 
        description="设备过滤：all/pc/mobile"
    ),
    category_id: Optional[str] = Query(
        None, 
        description="主分类ID筛选（可选）"
    ),
    sub_category_id: Optional[str] = Query(
        None, 
        description="子分类ID筛选（可选）"
    ),
    sort_by: str = Query(
        None,
        description="排序字段：duration/start_time/app"
    ),
    sort_order: str = Query(
        None,
        description="排序方向：asc/desc"
    ),
    page: int = Query(
        1, 
        description="页码", 
        ge=1
    ),
    page_size: int = Query(
        50, 
        description="每页数量", 
        ge=1, 
        le=3000
    )
) -> ActivityLogsResponse:
    """
    获取活动日志列表
    
    **功能：**
    - 获取指定时间范围的活动日志
    - 支持设备和分类过滤
    - 支持排序（默认按时长降序）
    - 支持分页
    
    **返回数据：**
    - 活动事件列表（包含时间、应用、标题、分类ID等）
    
    **颜色说明：**
    - 本接口只返回 category_id，不返回颜色值
    - Timeline 非缩略图模式的分类颜色由前端自行计算
    - 前端使用 /category/tree 获取分类颜色，并通过 softenColor 函数转换为柔和色
    - @see frontend/page/timeline/Timeline.tsx 中的 TAILWIND_500_TO_300 映射表
    
    **示例：**
    - `/api/v2/activity/logs?start_time=2025-12-19 00:00:00&end_time=2025-12-19 23:59:59`
    - `/api/v2/activity/logs?start_time=2025-12-18 00:00:00&end_time=2025-12-20 23:59:59&sort_by=start_time&sort_order=asc`
    """
    try:
        return activity_service.get_activity_logs(
            date=None,
            start_time=start_time,
            end_time=end_time,
            device_filter=device_filter,
            category_id=category_id,
            sub_category_id=sub_category_id,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
    except ValueError as e:
        logger.error(f"获取活动日志失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取活动日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取活动日志失败: {str(e)}")


@router.get("/logs/{log_id}", summary="获取单条活动日志详情")
async def get_activity_log_detail(log_id: str):
    """
    获取单条活动日志的详细信息
    
    **参数：**
    - log_id: 日志ID（路径参数）
    """
    try:
        result = activity_service.get_activity_log_detail(log_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"日志 '{log_id}' 不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取日志详情失败: {str(e)}")


# ============================================================================
# Manage API - 管理操作
# ============================================================================

@router.patch("/manage/logs/{log_id}/category", summary="更新日志分类", response_model=StandardResponse)
async def update_log_category(
    log_id: str,
    category_id: str = Query(
        ..., 
        description="主分类ID"
    ),
    sub_category_id: Optional[str] = Query(
        None, 
        description="子分类ID"
    )
) -> StandardResponse:
    """
    更新指定日志的分类信息
    
    **功能：**
    - 更新日志的 category_id 和 sub_category_id
    
    **参数：**
    - log_id: 日志ID（路径参数）
    - category_id: 主分类ID（查询参数）
    - sub_category_id: 子分类ID（查询参数，可选）
    
    **返回：**
    - success: 是否成功
    - message: 操作消息
    """
    try:
        success = activity_service.update_log_category(
            log_id=log_id,
            category_id=category_id,
            sub_category_id=sub_category_id
        )
        return StandardResponse(
            success=success,
            message=f"日志 '{log_id}' 分类更新{'成功' if success else '失败'}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新分类失败: {str(e)}")


@router.post("/manage/logs/batch-category", summary="批量更新日志分类", response_model=StandardResponse)
async def batch_update_log_category(
    log_ids: List[str] = Query(
        ..., 
        description="日志ID列表"
    ),
    category_id: str = Query(
        ..., 
        description="主分类ID"
    ),
    sub_category_id: Optional[str] = Query(
        None, 
        description="子分类ID"
    )
) -> StandardResponse:
    """
    批量更新多条日志的分类信息
    
    **功能：**
    - 批量更新多条日志的分类
    
    **返回：**
    - success: 是否成功
    - updated_count: 成功更新的数量
    """
    try:
        updated_count = activity_service.batch_update_log_category(
            log_ids=log_ids,
            category_id=category_id,
            sub_category_id=sub_category_id
        )
        return StandardResponse(
            success=True,
            data={"updated_count": updated_count},
            message=f"成功更新 {updated_count} 条日志"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新分类失败: {str(e)}")


@router.delete("/manage/logs/batch", summary="批量删除日志", response_model=StandardResponse)
async def batch_delete_logs(
    log_ids: List[str] = Query(
        ..., 
        description="日志ID列表"
    )
) -> StandardResponse:
    """
    批量删除多条日志
    
    **参数：**
    - log_ids: 日志ID列表（查询参数）
    
    **返回：**
    - success: 是否成功
    - deleted_count: 成功删除的数量
    """
    try:
        deleted_count = activity_service.batch_delete_logs(log_ids)
        return StandardResponse(
            success=True,
            data={"deleted_count": deleted_count},
            message=f"成功删除 {deleted_count} 条日志"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


@router.delete("/manage/logs/{log_id}", summary="删除日志", response_model=StandardResponse)
async def delete_log(log_id: str) -> StandardResponse:
    """
    删除指定的日志记录
    
    **参数：**
    - log_id: 日志ID（路径参数）
    
    **返回：**
    - success: 是否成功
    - message: 操作消息
    """
    try:
        success = activity_service.delete_log(log_id)
        return StandardResponse(
            success=success,
            message=f"日志 '{log_id}' 删除{'成功' if success else '失败'}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除日志失败: {str(e)}")


@router.post("/manage/logs/update-by-cache", summary="根据缓存更新日志分类", response_model=StandardResponse)
async def update_logs_by_cache(
    app: str = Query(..., description="应用名称"),
    title: Optional[str] = Query(None, description="窗口标题（多用途应用时必填）"),
    is_multipurpose_app: bool = Query(..., description="是否为多用途应用"),
    category_id: str = Query(..., description="主分类ID"),
    sub_category_id: Optional[str] = Query(None, description="子分类ID"),
    goal_id: Optional[str] = Query(None, description="目标ID（None=不修改, ''=清除, 'goal-xxx'=设置）"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD（可选）"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（可选）")
) -> StandardResponse:
    """
    根据缓存匹配条件批量更新日志分类
    
    **匹配逻辑：**
    - 单用途应用 (is_multipurpose_app=false): 仅按 app 匹配
    - 多用途应用 (is_multipurpose_app=true): 按 app + title 匹配
    
    **参数：**
    - app: 应用名称（必填）
    - title: 窗口标题（多用途应用时必填）
    - is_multipurpose_app: 是否为多用途应用
    - category_id: 主分类ID
    - sub_category_id: 子分类ID（可选）
    - goal_id: 目标ID（None=不修改, ''=清除, 'goal-xxx'=设置）
    - start_date: 开始日期 YYYY-MM-DD（可选，用于限制更新范围）
    - end_date: 结束日期 YYYY-MM-DD（可选，用于限制更新范围）
    
    **返回：**
    - success: 是否成功
    - data.updated_count: 更新的日志数量
    """
    try:
        # 验证：多用途应用必须提供 title
        if is_multipurpose_app and not title:
            raise HTTPException(
                status_code=400, 
                detail="多用途应用必须提供 title 参数"
            )
        
        updated_count = activity_service.update_logs_by_app_title(
            app=app,
            title=title,
            is_multipurpose_app=is_multipurpose_app,
            category_id=category_id,
            sub_category_id=sub_category_id,
            goal_id=goal_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return StandardResponse(
            success=True,
            data={"updated_count": updated_count},
            message=f"成功更新 {updated_count} 条日志"
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"根据缓存更新日志分类失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新日志分类失败: {str(e)}")



