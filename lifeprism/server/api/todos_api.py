"""
Todos API - 统一任务接口

提供统一的 /api/v2/todos RESTful API：
- GET /todos?date={date} - 获取指定日期的任务
- GET /todos - 获取任务池任务（无 date 参数时）
- POST /todos - 创建任务
- GET /todos/{id} - 获取单个任务
- PUT /todos/{id} - 更新任务
- DELETE /todos/{id} - 删除任务
"""
from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional

from lifeprism.server.schemas.taskpool_schemas import (
    TaskPoolItem,
    TaskPoolResponse,
    CreateTodoV2Request,
    CreateTodoV2Response,
    UpdateTodoV2Request,
    UpdateTodoV2Response,
)
from lifeprism.server.services import taskpool_service

router = APIRouter(prefix="/todos", tags=["Todos"])


# ============================================================================
# 任务查询接口
# ============================================================================

@router.get("", response_model=TaskPoolResponse)
async def get_todos(
    date: Optional[str] = Query(default=None, description="日期（YYYY-MM-DD 格式）"),
    goal_id: Optional[str] = Query(default=None, description="按目标筛选"),
    plan_doc_id: Optional[str] = Query(default=None, description="按计划书筛选"),
    state: Optional[str] = Query(default=None, description="按状态筛选（pool/scheduled/completed/shelved/all）")
):
    """
    获取任务列表

    - 当提供 **date** 参数时：返回该日期的 scheduled/completed 任务
    - 当不提供 **date** 参数时：返回任务池任务（可通过其他参数筛选）

    筛选参数：
    - **date**: 日期筛选（YYYY-MM-DD 格式）
    - **goal_id**: 按目标筛选
    - **plan_doc_id**: 按计划书筛选
    - **state**: 按状态筛选
        - pool: 任务池中（未分配日期）
        - scheduled: 已安排（已分配日期）
        - completed: 已完成
        - shelved: 已搁置
        - all: 所有状态
    """
    if date:
        # 按日期查询
        return taskpool_service.get_todos_by_date(date)
    else:
        # 任务池查询
        return taskpool_service.get_taskpool(
            goal_id=goal_id,
            plan_doc_id=plan_doc_id,
            state=state or "all"
        )


# ============================================================================
# 任务创建接口
# ============================================================================

@router.post("", response_model=CreateTodoV2Response)
async def create_todo(request: CreateTodoV2Request):
    """
    创建新任务

    请求体:
    - **content**: 任务内容（必需）
    - **state**: 任务状态（可选，默认 pool）
    - **date**: 安排日期（可选，设置后状态自动变为 scheduled）
    - **color**: 任务颜色（可选，默认 #FFFFFF）
    - **link_to_goal_id**: 关联的目标 ID（可选）
    - **plan_doc_id**: 关联的计划书 ID（可选）
    - **parent_id**: 父任务 ID（可选）
    - **expected_finished_at**: 预计完成日期（可选）
    - **pool_order_index**: 任务池排序（可选）
    """
    data = request.model_dump(exclude_unset=True)

    result = taskpool_service.create_todo_v2(data)
    if not result:
        raise HTTPException(status_code=500, detail="创建任务失败")

    return CreateTodoV2Response(item=result)


# ============================================================================
# 单个任务操作接口
# ============================================================================

@router.get("/{todo_id}", response_model=TaskPoolItem)
async def get_todo(
    todo_id: int = Path(..., description="任务 ID")
):
    """
    获取单个任务详情
    """
    result = taskpool_service.get_todo_by_id(todo_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在")
    return result


@router.put("/{todo_id}", response_model=UpdateTodoV2Response)
async def update_todo(
    todo_id: int = Path(..., description="任务 ID"),
    request: UpdateTodoV2Request = ...
):
    """
    更新任务

    支持 MD 文件回写：当 state 变为 completed 时，
    如果任务关联了计划书且有锚点，会同步将 MD 中的 [ ] 改为 [x]。

    可更新字段：
    - **content**: 任务内容
    - **color**: 任务颜色
    - **state**: 任务状态（pool/scheduled/completed/shelved）
    - **date**: 安排日期（设置后状态自动变为 scheduled）
    - **expected_finished_at**: 预计完成日期
    - **parent_id**: 父任务 ID
    - **delay_days**: 延期天数
    - **delay_reason**: 延期/未完成原因说明

    返回：
    - **item**: 更新后的任务
    - **md_synced**: 是否同步了 MD 文件
    """
    # 如果设置了 date，自动将状态改为 scheduled
    updates = request.model_dump(exclude_unset=True)
    if 'date' in updates and updates['date'] and updates.get('state') not in ('completed', 'shelved'):
        updates['state'] = 'scheduled'

    result = taskpool_service.update_todo_with_writeback(todo_id, updates)

    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return result


@router.delete("/{todo_id}")
async def delete_todo(
    todo_id: int = Path(..., description="任务 ID")
):
    """
    删除任务（会级联删除子任务）
    """
    success = taskpool_service.delete_todo(todo_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}
