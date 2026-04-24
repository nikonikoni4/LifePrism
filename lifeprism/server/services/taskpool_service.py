"""
任务池服务层 - Todo 业务逻辑

核心功能：
1. 获取任务池任务（支持筛选）
2. 按日期查询任务
3. 创建/更新/删除任务（含 MD 回写）

PlanDoc MD 同步逻辑已拆分至 plandoc_sync_service.py
"""
from typing import Optional, Dict, Any
from datetime import datetime

from lifeprism.server.schemas.todo_schemas import (
    TodoItem, TodoListResponse, UpdateTodoResponse,
)
from lifeprism.repository import todo_repository
from lifeprism.server.services.plandoc_sync_service import (
    insert_todo_to_md,
    update_todo_in_md,
    delete_todo_from_md,
    writeback_completion_to_md,
    writeback_uncomplete_to_md,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# 数据转换
# ============================================================================

def db_to_todo_item(db_item: Dict[str, Any]) -> TodoItem:
    """将数据库记录转换为 TodoItem"""
    return TodoItem(
        id=db_item['id'],
        content=db_item['content'],
        parent_id=db_item.get('parent_id'),
        link_to_goal_id=db_item.get('link_to_goal_id'),
        plan_doc_id=db_item.get('plan_doc_id'),
        state=db_item.get('state', 'pool'),
        date=db_item.get('date'),
        expected_finished_at=db_item.get('expected_finished_at'),
        actual_finished_at=db_item.get('actual_finished_at'),
        color=db_item.get('color', '#FFFFFF'),
        order_index=db_item.get('order_index', 0),
        pool_order_index=db_item.get('pool_order_index'),
        created_at=db_item.get('created_at'),
        delay_days=db_item.get('delay_days'),
        delay_reason=db_item.get('delay_reason'),
        waid_order=db_item.get('waid_order'),
    )


# ============================================================================
# 任务池查询
# ============================================================================

def get_taskpool(
    goal_id: Optional[str] = None,
    plan_doc_id: Optional[str] = None,
    state: Optional[str] = None
) -> TodoListResponse:
    """
    获取任务池任务列表

    Args:
        goal_id: 按目标筛选
        plan_doc_id: 按计划书筛选
        state: 按状态筛选（pool/scheduled/completed/all）

    Returns:
        TodoListResponse: 任务列表（扁平结构）
    """
    db_items = todo_repository.get_todos_for_taskpool(
        goal_id=goal_id,
        plan_doc_id=plan_doc_id,
        state=state or "all"
    )

    items = [db_to_todo_item(item) for item in db_items]
    return TodoListResponse(items=items)


# ============================================================================
# 统一 Todos API 服务函数
# ============================================================================

def get_todos_by_date(date: str) -> TodoListResponse:
    """
    获取指定日期的任务列表

    包含：
    1. 当天 scheduled 状态的任务
    2. 当天 completed 状态的任务
    """
    db_items = todo_repository.get_todos_by_date(date, include_cross_day=False)

    filtered_items = [
        item for item in db_items
        if item.get('state') in ('scheduled', 'completed')
    ]

    items = [db_to_todo_item(item) for item in filtered_items]
    return TodoListResponse(items=items)


def create_todo_v2(data: Dict[str, Any]) -> Optional[TodoItem]:
    """
    创建新任务 (V2)

    支持子任务继承：当创建子任务时，自动继承父任务的 plan_doc_id 和 goal_id，
    并同步插入到 MD 文件，生成的锚点即为任务 ID。
    """
    # 如果设置了 date 且状态为 pool，自动改为 scheduled
    if data.get('date') and data.get('state', 'pool') == 'pool':
        data['state'] = 'scheduled'

    # 子任务继承逻辑
    parent_id = data.get('parent_id')
    if parent_id:
        parent = todo_repository.get_todo_by_id(parent_id)
        if parent:
            if not data.get('plan_doc_id') and parent.get('plan_doc_id'):
                data['plan_doc_id'] = parent['plan_doc_id']
            if not data.get('link_to_goal_id') and parent.get('link_to_goal_id'):
                data['link_to_goal_id'] = parent['link_to_goal_id']

    # 如果有 plan_doc_id，插入到 MD 并用锚点作为任务 ID
    plan_doc_id = data.get('plan_doc_id')
    if plan_doc_id and not data.get('id'):
        parent_anchor_id = parent_id if parent_id else None

        new_anchor = insert_todo_to_md(plan_doc_id, data['content'], parent_anchor_id)
        if new_anchor:
            data['id'] = new_anchor

    new_id = todo_repository.create_todo(data)
    if not new_id:
        return None

    db_item = todo_repository.get_todo_by_id(new_id)
    if not db_item:
        return None

    return db_to_todo_item(db_item)


def get_todo_by_id(todo_id: str) -> Optional[TodoItem]:
    """获取单个任务"""
    db_item = todo_repository.get_todo_by_id(todo_id)
    if not db_item:
        return None
    return db_to_todo_item(db_item)


# ============================================================================
# 更新任务（含 MD 回写）
# ============================================================================

def update_todo_with_writeback(
    todo_id: str,
    updates: Dict[str, Any]
) -> Optional[UpdateTodoResponse]:
    """
    更新任务，并在必要时回写 MD 文件

    回写场景：
    1. state 变为 completed 时，将 MD 中的 [ ] 改为 [x]
    2. content 变更时，更新 MD 中的任务内容
    """
    # 1. 获取现有任务
    existing = todo_repository.get_todo_by_id(todo_id)
    if not existing:
        logger.warning(f"任务不存在: {todo_id}")
        return None

    # 2. 处理状态变更副作用
    if updates.get('state') == 'completed' and existing.get('state') != 'completed':
        updates['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
    elif updates.get('state') in ['pool', 'scheduled'] and existing.get('state') == 'completed':
        updates['actual_finished_at'] = None

    # 3. 更新数据库
    success = todo_repository.update_todo(todo_id, updates)
    if not success:
        return None

    # 4. 检查是否需要回写 MD（id 就是锚点）
    md_synced = False
    plan_doc_id = existing.get('plan_doc_id')
    anchor_id = existing['id']

    if plan_doc_id:
        new_state = updates.get('state')
        new_content = updates.get('content')

        if new_state == 'completed' and existing.get('state') != 'completed':
            md_synced = writeback_completion_to_md(plan_doc_id, anchor_id)

        if new_state in ['pool', 'scheduled'] and existing.get('state') == 'completed':
            md_synced = writeback_uncomplete_to_md(plan_doc_id, anchor_id)

        if new_content and new_content != existing.get('content'):
            content_synced = update_todo_in_md(plan_doc_id, anchor_id, new_content)
            md_synced = md_synced or content_synced

    # 5. 获取更新后的任务
    updated = todo_repository.get_todo_by_id(todo_id)
    if not updated:
        return None

    return UpdateTodoResponse(
        item=db_to_todo_item(updated),
        md_synced=md_synced
    )


def delete_todo(todo_id: str) -> bool:
    """
    删除任务（含 MD 回写和级联删除）

    如果任务关联了计划书，会同步从 MD 文件中删除（id 即锚点）。
    同时级联删除所有子任务。
    """
    todo = todo_repository.get_todo_by_id(todo_id)
    if not todo:
        return False

    plan_doc_id = todo.get('plan_doc_id')
    anchor_id = todo['id']

    if plan_doc_id:
        delete_todo_from_md(plan_doc_id, anchor_id)

    deleted_count = todo_repository.delete_todo_cascade(todo_id)
    return deleted_count > 0
