"""
Task Pool V2 API - 任务池接口

提供任务池的 RESTful API：
- GET /api/v2/taskpool - 获取任务池任务
- POST /api/v2/taskpool/sync - 同步计划书任务
- POST /api/v2/taskpool/regenerate-summary - 重新生成系统展示区
- PUT /api/v2/todos/{id} - 更新任务（含 MD 回写）
"""
from fastapi import APIRouter, Query, HTTPException, Path
from typing import Optional

from lifeprism.server.schemas.taskpool_schemas import (
    TaskPoolResponse,
    SyncPlanDocRequest,
    SyncPlanDocResponse,
    RegenerateSummaryRequest,
    RegenerateSummaryResponse,
    UpdateTodoV2Request,
    UpdateTodoV2Response,
)
from lifeprism.server.services import taskpool_service

router = APIRouter(prefix="/v2", tags=["Task Pool V2"])


# ============================================================================
# 任务池接口
# ============================================================================

@router.get("/taskpool", response_model=TaskPoolResponse)
async def get_taskpool(
    goal_id: Optional[str] = Query(default=None, description="按目标筛选"),
    plan_doc_id: Optional[str] = Query(default=None, description="按计划书筛选"),
    state: Optional[str] = Query(default="all", description="按状态筛选（pool/scheduled/completed/all）")
):
    """
    获取任务池任务列表
    
    返回扁平结构的任务列表，前端通过 parent_id 构建树形结构。
    
    - **goal_id**: 按目标筛选
    - **plan_doc_id**: 按计划书筛选
    - **state**: 按状态筛选
        - pool: 任务池中（未分配日期）
        - scheduled: 已安排（已分配日期）
        - completed: 已完成
        - all: 所有状态（默认）
    """
    return taskpool_service.get_taskpool(
        goal_id=goal_id,
        plan_doc_id=plan_doc_id,
        state=state
    )


@router.post("/taskpool/sync", response_model=SyncPlanDocResponse)
async def sync_plan_doc(request: SyncPlanDocRequest):
    """
    同步计划书任务
    
    从指定计划书的 MD 文件中解析任务，同步到数据库。
    
    处理流程：
    1. 读取 MD 文件，查找 todoblock
    2. 解析任务（支持嵌套层级）
    3. 为无锚点的任务生成锚点并写回 MD
    4. 创建/更新数据库记录
    5. 更新系统展示区
    
    返回同步统计：
    - **created**: 新创建的任务数
    - **updated**: 更新的任务数
    - **cleaned**: 清理的锚点数
    - **total**: 该计划书关联的总任务数
    """
    return taskpool_service.sync_plan_doc(request.plan_doc_id)


@router.post("/taskpool/regenerate-summary", response_model=RegenerateSummaryResponse)
async def regenerate_summary(request: RegenerateSummaryRequest):
    """
    重新生成系统展示区
    
    根据数据库中的任务数据，重新生成计划书 MD 文件中的系统展示区。
    
    系统展示区位于 MD 文件末尾，以 `<!-- lp:system-section -->` 标记。
    用户对此区域的手动修改会在下次同步时被覆盖。
    """
    success = taskpool_service.regenerate_summary(request.plan_doc_id)
    
    if success:
        return RegenerateSummaryResponse(
            success=True,
            message="系统展示区已更新"
        )
    else:
        return RegenerateSummaryResponse(
            success=False,
            message="更新失败，请检查计划书是否存在"
        )


# ============================================================================
# 任务更新接口（V2，支持 MD 回写）
# ============================================================================

@router.put("/todos/{todo_id}", response_model=UpdateTodoV2Response)
async def update_todo_v2(
    todo_id: int = Path(..., description="任务 ID"),
    request: UpdateTodoV2Request = ...
):
    """
    更新任务（V2）
    
    支持 MD 文件回写：当 state 变为 completed 时，
    如果任务关联了计划书且有锚点，会同步将 MD 中的 [ ] 改为 [x]。
    
    可更新字段：
    - **content**: 任务内容
    - **color**: 任务颜色
    - **state**: 任务状态（pool/scheduled/completed）
    - **date**: 安排日期（设置后状态自动变为 scheduled）
    - **expected_finished_at**: 预计完成日期
    - **parent_id**: 父任务 ID
    
    返回：
    - **item**: 更新后的任务
    - **md_synced**: 是否同步了 MD 文件
    """
    # 如果设置了 date，自动将状态改为 scheduled
    updates = request.model_dump(exclude_unset=True)
    if 'date' in updates and updates['date'] and updates.get('state') != 'completed':
        updates['state'] = 'scheduled'
    
    result = taskpool_service.update_todo_with_writeback(todo_id, updates)
    
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return result
