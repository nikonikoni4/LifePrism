"""
Goal API - 目标管理接口

提供 Goal、Journal、PlanDoc 的 RESTful API
"""
from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional

from lifeprism.server.schemas.goal_schemas import (
    # Goal Schemas
    GoalItem,
    GoalListResponse,
    CreateGoalRequest,
    UpdateGoalRequest,
    ReorderGoalRequest,
    ActiveGoalNamesResponse,
    GoalsWithCategoryResponse,
    UpdateMilestoneStateRequest,
    # Journal Schemas
    JournalEntry,
    JournalListResponse,
    CreateJournalRequest,
    UpdateJournalRequest,
    # PlanDoc Schemas
    PlanDocItem,
    PlanDocListResponse,
    CreatePlanDocRequest,
    UpdatePlanDocRequest,
)
from lifeprism.server.services import journal_service
from lifeprism.server.services import plan_doc_service
from lifeprism.server.services.goal_service import goal_service

router = APIRouter(prefix="/goal", tags=["Goal"])


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
    - **content**: 目标详细内容（可选）
    - **color**: 目标颜色（可选，默认 #5B8FF9）
    - **link_to_category_id**: 关联分类 ID（可选）
    - **link_to_sub_category_id**: 关联子分类 ID（可选）
    - **start_date**: 开始日期（可选）
    - **expected_finished_at**: 预计完成时间（可选）
    - **value**: 价值观/意义描述（可选）
    - **commitment**: 承诺/行动计划（可选）
    - **track_time_automatically**: 是否自动追踪时间（可选，默认 true）
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


@router.get("/goals/with-category", response_model=GoalsWithCategoryResponse)
async def get_goals_with_category():
    """
    获取所有绑定了分类的进行中目标（用于 Map Cache 编辑界面）

    仅返回 link_to_category_id 不为空的目标
    包含 id, name, link_to_category_id, link_to_sub_category_id
    """
    return goal_service.get_goals_with_category()



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
    - **content**: 目标详细内容
    - **color**: 目标颜色
    - **link_to_category_id**: 关联分类 ID
    - **link_to_sub_category_id**: 关联子分类 ID
    - **start_date**: 开始日期
    - **expected_finished_at**: 预计完成时间
    - **actual_finished_at**: 实际完成时间
    - **value**: 价值观/意义描述
    - **commitment**: 承诺/行动计划
    - **track_time_automatically**: 是否自动追踪时间
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


# ============================================================================
# Milestone 接口
# ============================================================================

@router.patch("/goals/{goal_id}/milestones/{milestone_id}")
async def update_milestone_state(
    goal_id: str = Path(..., description="目标 ID (格式: goal-xxx)"),
    milestone_id: str = Path(..., description="里程碑 ID"),
    request: UpdateMilestoneStateRequest = ...
):
    """
    更新里程碑状态

    请求体:
    - **state**: 状态 (0: 未达成, 1: 已达成)
    """
    result = goal_service.update_milestone(goal_id, milestone_id, request.state)
    if not result:
        raise HTTPException(status_code=404, detail="目标或里程碑不存在")
    return {"success": True}


# ============================================================================
# Journal 接口
# ============================================================================

@router.get("/journals", response_model=JournalListResponse)
async def get_journals(
    goal_id: Optional[str] = Query(default=None, description="按目标筛选"),
    start_date: Optional[str] = Query(default=None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量")
):
    """
    获取日志列表

    - **goal_id**: 按目标筛选（可选）
    - **start_date**: 开始日期（可选）
    - **end_date**: 结束日期（可选）
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    """
    return journal_service.get_journals(goal_id, start_date, end_date, page, page_size)


@router.post("/journals", response_model=JournalEntry)
async def create_journal(request: CreateJournalRequest):
    """
    创建新日志

    请求体:
    - **goal_id**: 关联目标 ID（必需）
    - **title**: 日志标题（必需）
    - **content**: 日志内容（可选）
    - **journal_date**: 日志日期（可选，默认今天）
    - **mood**: 心情（可选）
    - **tags**: 标签列表（可选）
    """
    result = journal_service.create_journal(request)
    if not result:
        raise HTTPException(status_code=500, detail="创建日志失败")
    return result


@router.get("/journals/{journal_id}", response_model=JournalEntry)
async def get_journal_detail(
    journal_id: str = Path(..., description="日志 ID (格式: journal-xxx)")
):
    """
    获取日志详情
    """
    result = journal_service.get_journal_detail(journal_id)
    if not result:
        raise HTTPException(status_code=404, detail="日志不存在")
    return result


@router.patch("/journals/{journal_id}", response_model=JournalEntry)
async def update_journal(
    journal_id: str = Path(..., description="日志 ID (格式: journal-xxx)"),
    request: UpdateJournalRequest = ...
):
    """
    更新日志（部分更新）

    请求体（所有字段可选）:
    - **title**: 日志标题
    - **content**: 日志内容
    - **journal_date**: 日志日期
    - **mood**: 心情
    - **tags**: 标签列表
    """
    result = journal_service.update_journal(journal_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="日志不存在或更新失败")
    return result


@router.delete("/journals/{journal_id}")
async def delete_journal(
    journal_id: str = Path(..., description="日志 ID (格式: journal-xxx)")
):
    """
    删除日志
    """
    success = journal_service.delete_journal(journal_id)
    if not success:
        raise HTTPException(status_code=404, detail="日志不存在")
    return {"success": True}


# ============================================================================
# PlanDoc 接口
# ============================================================================

@router.get("/plan-docs", response_model=PlanDocListResponse)
async def get_plan_docs(
    goal_id: Optional[str] = Query(default=None, description="按目标筛选"),
    doc_type: Optional[str] = Query(default=None, description="按类型筛选 (weekly, monthly, quarterly, yearly, custom)"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量")
):
    """
    获取计划文档列表

    - **goal_id**: 按目标筛选（可选）
    - **doc_type**: 按类型筛选（可选）
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    """
    return plan_doc_service.get_plan_docs(goal_id, doc_type, page, page_size)


@router.post("/plan-docs", response_model=PlanDocItem)
async def create_plan_doc(request: CreatePlanDocRequest):
    """
    创建新计划文档

    请求体:
    - **goal_id**: 关联目标 ID（必需）
    - **title**: 文档标题（必需）
    - **doc_type**: 文档类型（必需）: weekly, monthly, quarterly, yearly, custom
    - **content**: 文档内容（可选）
    - **period_start**: 周期开始日期（可选）
    - **period_end**: 周期结束日期（可选）
    """
    try:
        result = plan_doc_service.create_plan_doc(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建计划文档失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/plan-docs/{doc_id}", response_model=PlanDocItem)
async def get_plan_doc_detail(
    doc_id: str = Path(..., description="计划文档 ID (格式: plandoc-xxx)")
):
    """
    获取计划文档详情
    """
    result = plan_doc_service.get_plan_doc_detail(doc_id)
    if not result:
        raise HTTPException(status_code=404, detail="计划文档不存在")
    return result


@router.patch("/plan-docs/{doc_id}", response_model=PlanDocItem)
async def update_plan_doc(
    doc_id: str = Path(..., description="计划文档 ID (格式: plandoc-xxx)"),
    request: UpdatePlanDocRequest = ...
):
    """
    更新计划文档（部分更新）

    请求体（所有字段可选）:
    - **title**: 文档标题
    - **doc_type**: 文档类型
    - **content**: 文档内容
    - **period_start**: 周期开始日期
    - **period_end**: 周期结束日期
    """
    try:
        result = plan_doc_service.update_plan_doc(doc_id, request)
        if not result:
            raise HTTPException(status_code=404, detail="计划文档不存在或更新失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/plan-docs/{doc_id}")
async def delete_plan_doc(
    doc_id: str = Path(..., description="计划文档 ID (格式: plandoc-xxx)")
):
    """
    删除计划文档
    """
    success = plan_doc_service.delete_plan_doc(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="计划文档不存在")
    return {"success": True}
