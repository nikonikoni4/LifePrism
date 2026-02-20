"""
Task Pool API - 任务池接口

提供任务池的 RESTful API：
- GET /taskpool - 获取任务池任务
- POST /taskpool/sync - 同步计划书任务
- POST /taskpool/regenerate-summary - 重新生成系统展示区
"""
from fastapi import APIRouter, Query
from typing import Optional

from lifeprism.server.schemas.todo_schemas import (
    TodoListResponse,
)
from lifeprism.server.schemas.plan_doc_schemas import (
    SyncPlanDocRequest, SyncPlanDocResponse,
    RegenerateSummaryRequest, RegenerateSummaryResponse,
)
from lifeprism.server.services import taskpool_service
from lifeprism.server.services import plandoc_sync_service

router = APIRouter(prefix="/taskpool", tags=["Task Pool"])


# ============================================================================
# 任务池接口
# ============================================================================

@router.get("", response_model=TodoListResponse)
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


@router.post("/sync", response_model=SyncPlanDocResponse)
async def sync_plan_doc(request: SyncPlanDocRequest):
    """
    同步计划书任务

    从指定计划书的 MD 文件中解析任务，同步到数据库。

    处理流程：
    1. 读取 MD 文件，查找 todoblock
    2. 解析任务（支持嵌套层级）
    3. 为无锚点的任务生成锚点并写回 MD
    4. 创建/更新数据库记录
    5. 检测并处理删除的任务
    6. 更新系统展示区

    参数说明：
    - **plan_doc_id**: 计划书 ID
    - **dry_run**: 预检模式，只返回差异不执行操作
    - **confirm_delete**: 确认删除，True=删除全部待删除任务，False=保留全部

    返回同步统计：
    - **created**: 新创建的任务数
    - **updated**: 更新的任务数
    - **deleted**: 删除的任务数
    - **cleaned**: 清理的锚点数
    - **total**: 该计划书关联的总任务数
    - **to_delete**: 待删除任务列表（dry_run 模式返回）
    """
    return plandoc_sync_service.sync_plan_doc(
        request.plan_doc_id,
        dry_run=request.dry_run,
        confirm_delete=request.confirm_delete
    )


@router.post("/regenerate-summary", response_model=RegenerateSummaryResponse)
async def regenerate_summary(request: RegenerateSummaryRequest):
    """
    重新生成系统展示区
    
    根据数据库中的任务数据，重新生成计划书 MD 文件中的系统展示区。
    
    系统展示区位于 MD 文件末尾，以 `<!-- lp:system-section -->` 标记。
    用户对此区域的手动修改会在下次同步时被覆盖。
    """
    success = plandoc_sync_service.regenerate_summary(request.plan_doc_id)
    
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
