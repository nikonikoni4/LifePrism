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
    ReorderPoolTodoRequest,
    # Plan Schemas
    WeeklyPlanResponse,
    MonthlyPlanItem,
    UpsertDailyFocusRequest,
    UpsertWeeklyFocusRequest,
    # Goal Schemas
    GoalItem,
    GoalListResponse,
    CreateGoalRequest,
    UpdateGoalRequest,
    ReorderGoalRequest,
    ActiveGoalNamesResponse,
    # Folder Schemas
    TaskPoolFolderItem,
    TaskPoolFolderListResponse,
    CreateFolderRequest,
    UpdateFolderRequest,
    ReorderFoldersRequest,
    MoveTodoToFolderRequest,
)
from lifewatch.server.services import todo_service
from lifewatch.server.services.goal_service import goal_service

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


# ============================================================================
# Task Pool 接口
# ============================================================================

@router.get("/todos/pool", response_model=TodoListResponse)
async def get_pool_todos():
    """
    获取任务池任务列表
    
    返回所有状态为 inactive 的任务，按 pool_order_index 排序
    """
    return todo_service.get_pool_todos()


@router.post("/todos/pool/reorder")
async def reorder_pool_todos(request: ReorderPoolTodoRequest):
    """
    重排序任务池任务
    
    请求体:
    - **todo_ids**: 任务 ID 列表（按新顺序排列）
    """
    success = todo_service.reorder_pool_todos(request.todo_ids)
    if not success:
        raise HTTPException(status_code=500, detail="重排序任务池失败")
    return {"success": True}


# ============================================================================
# Task Pool Folder 接口
# ============================================================================

@router.get("/pool/folders", response_model=TaskPoolFolderListResponse)
async def get_folders():
    """
    获取所有任务池文件夹
    """
    return todo_service.get_folders()


@router.post("/pool/folders", response_model=TaskPoolFolderItem)
async def create_folder(request: CreateFolderRequest):
    """
    创建文件夹
    
    请求体:
    - **name**: 文件夹名称（必需）
    """
    result = todo_service.create_folder(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建文件夹失败")
    return result


@router.post("/pool/folders/reorder")
async def reorder_folders(request: ReorderFoldersRequest):
    """
    重排序文件夹
    
    请求体:
    - **folder_ids**: 文件夹 ID 列表（按新顺序排列）
    """
    success = todo_service.reorder_folders(request)
    if not success:
        raise HTTPException(status_code=500, detail="重排序文件夹失败")
    return {"success": True}


@router.patch("/pool/folders/{folder_id}", response_model=TaskPoolFolderItem)
async def update_folder(
    folder_id: int = Path(..., description="文件夹 ID"),
    request: UpdateFolderRequest = ...
):
    """
    更新文件夹
    
    请求体（所有字段可选）:
    - **name**: 文件夹名称
    - **is_expanded**: 是否展开
    """
    result = todo_service.update_folder(folder_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="文件夹不存在或更新失败")
    return result


@router.delete("/pool/folders/{folder_id}")
async def delete_folder(
    folder_id: int = Path(..., description="文件夹 ID")
):
    """
    删除文件夹（文件夹内任务会移动到根级别）
    """
    success = todo_service.delete_folder(folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    return {"success": True}


@router.patch("/todos/{todo_id}/move")
async def move_todo_to_folder(
    todo_id: int = Path(..., description="任务 ID"),
    request: MoveTodoToFolderRequest = ...
):
    """
    移动任务到文件夹
    
    请求体:
    - **folder_id**: 目标文件夹 ID（null 表示移出到根级别）
    """
    success = todo_service.move_todo_to_folder(todo_id, request)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或移动失败")
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


# ============================================================================
# Goal 接口
# ============================================================================

@router.get("/goals", response_model=GoalListResponse)
async def get_goals(
    status: Optional[str] = Query(default=None, description="按状态筛选 (active, completed, archived)"),
    category_id: Optional[str] = Query(default=None, description="按分类筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量")
):
    """
    获取目标列表
    
    - **status**: 按状态筛选（可选）
    - **category_id**: 按分类筛选（可选）
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    """
    return goal_service.get_goals(status, category_id, page, page_size)


@router.post("/goals", response_model=GoalItem)
async def create_goal(request: CreateGoalRequest):
    """
    创建新目标
    
    请求体:
    - **name**: 目标名称（必需）
    - **abstract**: 目标摘要/别名（可选）
    - **content**: 目标详细内容（可选）
    - **color**: 目标颜色（可选，默认 #5B8FF9）
    - **link_to_category**: 关联分类 ID（可选）
    - **link_to_sub_category**: 关联子分类 ID（可选）
    - **expected_finished_at**: 预计完成时间（可选）
    - **expected_hours**: 预计耗时小时数（可选）
    """
    result = goal_service.create_goal(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建目标失败")
    return result


@router.post("/goals/reorder")
async def reorder_goals(request: ReorderGoalRequest):
    """
    重排序目标
    
    请求体:
    - **goal_ids**: 目标 ID 列表（按新顺序排列）
    """
    success = goal_service.reorder_goals(request)
    if not success:
        raise HTTPException(status_code=500, detail="重排序目标失败")
    return {"success": True}


@router.get("/goals/active-names", response_model=ActiveGoalNamesResponse)
async def get_active_goal_names():
    """
    获取所有进行中的目标名称（用于前端下拉选择绑定）
    
    返回 status='active' 的目标的 id 和 name
    """
    return goal_service.get_active_goal_names()


@router.get("/goals/{goal_id}", response_model=GoalItem)
async def get_goal_detail(
    goal_id: str = Path(..., description="目标 ID (格式: goal-xxx)")
):
    """
    获取目标详情
    """
    result = goal_service.get_goal_detail(goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="目标不存在")
    return result


@router.patch("/goals/{goal_id}", response_model=GoalItem)
async def update_goal(
    goal_id: str = Path(..., description="目标 ID (格式: goal-xxx)"),
    request: UpdateGoalRequest = ...
):
    """
    更新目标（部分更新）
    
    请求体（所有字段可选）:
    - **name**: 目标名称
    - **abstract**: 目标摘要/别名
    - **content**: 目标详细内容
    - **color**: 目标颜色
    - **link_to_category**: 关联分类 ID
    - **link_to_sub_category**: 关联子分类 ID
    - **expected_finished_at**: 预计完成时间
    - **expected_hours**: 预计耗时
    - **actual_finished_at**: 实际完成时间
    - **actual_hours**: 实际耗时
    - **completion_rate**: 完成度 (0-1)
    - **status**: 目标状态
    """
    result = goal_service.update_goal(goal_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="目标不存在或更新失败")
    return result


@router.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: str = Path(..., description="目标 ID (格式: goal-xxx)")
):
    """
    删除目标
    """
    success = goal_service.delete_goal(goal_id)
    if not success:
        raise HTTPException(status_code=404, detail="目标不存在")
    return {"success": True}

