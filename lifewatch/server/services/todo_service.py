"""
Goal 服务层 -TodoList 业务逻辑

提供 TodoList 和 SubTodoList 的纯函数接口
"""
from datetime import datetime
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
    ReorderSubTodoRequest
)
from lifewatch.server.providers.todo_provider import todo_provider


# ============================================================================
# TodoList 服务
# ============================================================================

def get_todos(date: str, include_cross_day: bool = True) -> TodoListResponse:
    """
    获取指定日期的任务列表
    
    Args:
        date: 日期（YYYY-MM-DD 格式）
        include_cross_day: 是否包含跨天未完成任务
    
    Returns:
        TodoListResponse: 任务列表响应
    """
    todos_data = todo_provider.get_todos_by_date(date, include_cross_day)
    
    items = []
    for todo in todos_data:
        # 获取子任务
        sub_todos_data = todo_provider.get_sub_todos_by_parent(todo['id'])
        sub_items = [
            SubTodoListItem(
                id=sub['id'],
                order_index=sub['order_index'],
                parent_id=sub['parent_id'],
                content=sub['content'],
                completed=bool(sub['completed'])
            )
            for sub in sub_todos_data
        ]
        
        items.append(TodoListItem(
            id=todo['id'],
            order_index=todo['order_index'],
            content=todo['content'],
            color=todo['color'] or '#FFFFFF',
            completed=bool(todo['completed']),
            link_to_goal=todo['link_to_goal'],
            date=todo['date'],
            expected_finished_at=todo['expected_finished_at'],
            actual_finished_at=todo['actual_finished_at'],
            cross_day=bool(todo['cross_day']),
            sub_items=sub_items if sub_items else None
        ))
    
    return TodoListResponse(items=items)


def get_todo_detail(todo_id: int) -> Optional[TodoListItem]:
    """
    获取任务详情（含子任务）
    
    Args:
        todo_id: 任务 ID
    
    Returns:
        Optional[TodoListItem]: 任务详情，不存在返回 None
    """
    todo = todo_provider.get_todo_by_id(todo_id)
    if not todo:
        return None
    
    # 获取子任务
    sub_todos_data = todo_provider.get_sub_todos_by_parent(todo_id)
    sub_items = [
        SubTodoListItem(
            id=sub['id'],
            order_index=sub['order_index'],
            parent_id=sub['parent_id'],
            content=sub['content'],
            completed=bool(sub['completed'])
        )
        for sub in sub_todos_data
    ]
    
    return TodoListItem(
        id=todo['id'],
        order_index=todo['order_index'],
        content=todo['content'],
        color=todo['color'] or '#FFFFFF',
        completed=bool(todo['completed']),
        link_to_goal=todo['link_to_goal'],
        date=todo['date'],
        expected_finished_at=todo['expected_finished_at'],
        actual_finished_at=todo['actual_finished_at'],
        cross_day=bool(todo['cross_day']),
        sub_items=sub_items if sub_items else None
    )


def create_todo(request: CreateTodoRequest) -> Optional[TodoListItem]:
    """
    创建任务
    
    Args:
        request: 创建任务请求
    
    Returns:
        Optional[TodoListItem]: 新创建的任务，失败返回 None
    """
    data = {
        'content': request.content,
        'date': request.date,
        'color': request.color,
        'link_to_goal': request.link_to_goal,
        'expected_finished_at': request.expected_finished_at,
        'cross_day': request.cross_day
    }
    
    new_id = todo_provider.create_todo(data)
    if new_id:
        return get_todo_detail(new_id)
    return None


def update_todo(todo_id: int, request: UpdateTodoRequest) -> Optional[TodoListItem]:
    """
    更新任务
    
    Args:
        todo_id: 任务 ID
        request: 更新任务请求
    
    Returns:
        Optional[TodoListItem]: 更新后的任务，失败返回 None
    """
    # 构建更新数据（只包含非 None 字段）
    data = {}
    if request.content is not None:
        data['content'] = request.content
    if request.color is not None:
        data['color'] = request.color
    if request.completed is not None:
        data['completed'] = request.completed
        # 完成时自动填充 actual_finished_at
        if request.completed:
            data['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
        else:
            data['actual_finished_at'] = None
    if request.link_to_goal is not None:
        data['link_to_goal'] = request.link_to_goal
    if request.expected_finished_at is not None:
        data['expected_finished_at'] = request.expected_finished_at
    if request.cross_day is not None:
        data['cross_day'] = request.cross_day
    
    success = todo_provider.update_todo(todo_id, data)
    if success:
        return get_todo_detail(todo_id)
    return None


def delete_todo(todo_id: int) -> bool:
    """
    删除任务
    
    Args:
        todo_id: 任务 ID
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.delete_todo(todo_id)


def reorder_todos(request: ReorderTodoRequest) -> bool:
    """
    重排序任务
    
    Args:
        request: 重排序请求
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.reorder_todos(request.todo_ids)


# ============================================================================
# SubTodoList 服务
# ============================================================================

def get_sub_todos(parent_id: int) -> SubTodoListResponse:
    """
    获取子任务列表
    
    Args:
        parent_id: 父任务 ID
    
    Returns:
        SubTodoListResponse: 子任务列表响应
    """
    sub_todos_data = todo_provider.get_sub_todos_by_parent(parent_id)
    
    items = [
        SubTodoListItem(
            id=sub['id'],
            order_index=sub['order_index'],
            parent_id=sub['parent_id'],
            content=sub['content'],
            completed=bool(sub['completed'])
        )
        for sub in sub_todos_data
    ]
    
    return SubTodoListResponse(items=items)


def create_sub_todo(request: CreateSubTodoRequest) -> Optional[SubTodoListItem]:
    """
    创建子任务
    
    Args:
        request: 创建子任务请求
    
    Returns:
        Optional[SubTodoListItem]: 新创建的子任务，失败返回 None
    """
    new_id = todo_provider.create_sub_todo(request.parent_id, request.content)
    if new_id:
        sub = todo_provider.get_sub_todo_by_id(new_id)
        if sub:
            return SubTodoListItem(
                id=sub['id'],
                order_index=sub['order_index'],
                parent_id=sub['parent_id'],
                content=sub['content'],
                completed=bool(sub['completed'])
            )
    return None


def update_sub_todo(sub_id: int, request: UpdateSubTodoRequest) -> Optional[SubTodoListItem]:
    """
    更新子任务
    
    Args:
        sub_id: 子任务 ID
        request: 更新子任务请求
    
    Returns:
        Optional[SubTodoListItem]: 更新后的子任务，失败返回 None
    """
    data = {}
    if request.content is not None:
        data['content'] = request.content
    if request.completed is not None:
        data['completed'] = request.completed
    
    success = todo_provider.update_sub_todo(sub_id, data)
    if success:
        sub = todo_provider.get_sub_todo_by_id(sub_id)
        if sub:
            return SubTodoListItem(
                id=sub['id'],
                order_index=sub['order_index'],
                parent_id=sub['parent_id'],
                content=sub['content'],
                completed=bool(sub['completed'])
            )
    return None


def delete_sub_todo(sub_id: int) -> bool:
    """
    删除子任务
    
    Args:
        sub_id: 子任务 ID
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.delete_sub_todo(sub_id)


def reorder_sub_todos(request: ReorderSubTodoRequest) -> bool:
    """
    重排序子任务
    
    Args:
        request: 重排序请求
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.reorder_sub_todos(request.parent_id, request.sub_todo_ids)
