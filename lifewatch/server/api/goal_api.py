"""
Goal API - TodoList 接口

提供 TodoList 和 SubTodoList 的 RESTful API
"""
from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional

from lifewatch.server.schemas.goal_schemas import (
    TodoListItem,
    TodoListResponse,
    SubTodoListItem,
    SubTodoListResponse,
    CreateTodoRequest,
    UpdateTodoRequest,
    ReorderTodoRequest,
    CreateSubTodoRequest,
    UpdateSubTodoRequest,
    ReorderSubTodoRequest,
    # Plan Schemas
    WeeklyPlanResponse,
    MonthlyPlanItem,
    UpsertDailyFocusRequest,
    UpsertWeeklyFocusRequest,
)
from lifewatch.server.services import todo_service

router = APIRouter(prefix="/goal", tags=["Goal - TodoList"])


# ============================================================================
# TodoList 接口
# ============================================================================

@router.get("/todos", response_model=TodoListResponse)
async def get_todos(
    date: str = Query(..., description="日期（YYYY-MM-DD 格式）"),
    include_cross_day: bool = Query(default=True, description="是否包含跨天未完成任务")
):
    """
    获取指定日期的任务列表
    
    - **date**: 请求日期
    - **include_cross_day**: 是否包含历史跨天未完成的任务
    """
    return todo_service.get_todos(date, include_cross_day)


@router.post("/todos", response_model=TodoListItem)
async def create_todo(request: CreateTodoRequest):
    """
    创建新任务
    
    请求体:
    - **content**: 任务内容（必需）
    - **date**: 任务日期（必需）
    - **color**: 任务颜色（可选，默认 #FFFFFF）
    - **link_to_goal**: 关联目标 ID（可选）
    - **expected_finished_at**: 预计完成日期（可选）
    - **cross_day**: 是否开启跨天追踪（可选，默认 false）
    """
    result = todo_service.create_todo(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建任务失败")
    return result


# 注意：静态路由必须放在动态路由之前
@router.post("/todos/reorder")
async def reorder_todos(request: ReorderTodoRequest):
    """
    重排序任务
    
    请求体:
    - **todo_ids**: 任务 ID 列表（按新顺序排列）
    """
    success = todo_service.reorder_todos(request)
    if not success:
        raise HTTPException(status_code=500, detail="重排序任务失败")
    return {"success": True}


@router.get("/todos/{todo_id}", response_model=TodoListItem)
async def get_todo_detail(
    todo_id: int = Path(..., description="任务 ID")
):
    """
    获取任务详情（含子任务）
    """
    result = todo_service.get_todo_detail(todo_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在")
    return result


@router.patch("/todos/{todo_id}", response_model=TodoListItem)
async def update_todo(
    todo_id: int = Path(..., description="任务 ID"),
    request: UpdateTodoRequest = ...
):
    """
    更新任务（部分更新）
    
    请求体（所有字段可选）:
    - **content**: 任务内容
    - **color**: 任务颜色
    - **completed**: 是否完成（完成时自动填充 actual_finished_at）
    - **link_to_goal**: 关联目标 ID
    - **expected_finished_at**: 预计完成日期
    - **cross_day**: 是否开启跨天追踪
    """
    result = todo_service.update_todo(todo_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在或更新失败")
    return result


@router.delete("/todos/{todo_id}")
async def delete_todo(
    todo_id: int = Path(..., description="任务 ID")
):
    """
    删除任务（会级联删除子任务）
    """
    success = todo_service.delete_todo(todo_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}


@router.get("/todos/{todo_id}/subtodos", response_model=SubTodoListResponse)
async def get_sub_todos(
    todo_id: int = Path(..., description="父任务 ID")
):
    """
    获取任务的子任务列表
    """
    return todo_service.get_sub_todos(todo_id)


# ============================================================================
# SubTodoList 接口
# ============================================================================

@router.post("/subtodos", response_model=SubTodoListItem)
async def create_sub_todo(request: CreateSubTodoRequest):
    """
    创建子任务
    
    请求体:
    - **parent_id**: 父任务 ID（必需）
    - **content**: 子任务内容（必需）
    """
    result = todo_service.create_sub_todo(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建子任务失败")
    return result


@router.post("/subtodos/reorder")
async def reorder_sub_todos(request: ReorderSubTodoRequest):
    """
    重排序子任务
    
    请求体:
    - **parent_id**: 父任务 ID
    - **sub_todo_ids**: 子任务 ID 列表（按新顺序排列）
    """
    success = todo_service.reorder_sub_todos(request)
    if not success:
        raise HTTPException(status_code=500, detail="重排序子任务失败")
    return {"success": True}


@router.patch("/subtodos/{sub_id}", response_model=SubTodoListItem)
async def update_sub_todo(
    sub_id: int = Path(..., description="子任务 ID"),
    request: UpdateSubTodoRequest = ...
):
    """
    更新子任务（部分更新）
    
    请求体（所有字段可选）:
    - **content**: 子任务内容
    - **completed**: 是否完成
    """
    result = todo_service.update_sub_todo(sub_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="子任务不存在或更新失败")
    return result


@router.delete("/subtodos/{sub_id}")
async def delete_sub_todo(
    sub_id: int = Path(..., description="子任务 ID")
):
    """
    删除子任务
    """
    success = todo_service.delete_sub_todo(sub_id)
    if not success:
        raise HTTPException(status_code=404, detail="子任务不存在")
    return {"success": True}


# ============================================================================
# Plan 接口
# ============================================================================

@router.get("/plan/weekly", response_model=WeeklyPlanResponse)
async def get_weekly_plan(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份 (1-12)"),
    week_num: int = Query(..., description="周序号 (1-4)")
):
    """
    获取周计划
    
    - **year**: 年份
    - **month**: 月份 (1-12)
    - **week_num**: 周序号 (1-4)
    """
    return todo_service.get_weekly_plan(year, month, week_num)


@router.get("/plan/monthly", response_model=MonthlyPlanItem)
async def get_monthly_plan(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份 (1-12)")
):
    """
    获取月计划
    
    - **year**: 年份
    - **month**: 月份 (1-12)
    """
    return todo_service.get_monthly_plan(year, month)


@router.post("/plan/daily-focus")
async def upsert_daily_focus(request: UpsertDailyFocusRequest):
    """
    创建或更新日焦点
    
    请求体:
    - **date**: 日期 (YYYY-MM-DD)
    - **content**: 焦点内容
    """
    success = todo_service.upsert_daily_focus(request)
    if not success:
        raise HTTPException(status_code=500, detail="更新日焦点失败")
    return {"success": True}


@router.post("/plan/weekly-focus")
async def upsert_weekly_focus(request: UpsertWeeklyFocusRequest):
    """
    创建或更新周焦点
    
    请求体:
    - **year**: 年份
    - **month**: 月份 (1-12)
    - **week_num**: 周序号 (1-4)
    - **content**: 焦点内容
    """
    success = todo_service.upsert_weekly_focus(request)
    if not success:
        raise HTTPException(status_code=500, detail="更新周焦点失败")
    return {"success": True}
