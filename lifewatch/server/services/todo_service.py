"""
Goal 服务层 -TodoList 业务逻辑

提供 TodoList 和 SubTodoList 的纯函数接口
"""
from datetime import datetime, timedelta
from typing import Optional, List

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
    DailyPlanItem,
    WeeklyPlanResponse,
    WeeklyPlanItem,
    MonthlyPlanItem,
    UpsertDailyFocusRequest,
    UpsertWeeklyFocusRequest,
    # Folder Schemas
    TaskPoolFolderItem,
    TaskPoolFolderListResponse,
    CreateFolderRequest,
    UpdateFolderRequest,
    ReorderFoldersRequest,
    MoveTodoToFolderRequest,
)
from lifewatch.server.providers.todo_provider import todo_provider
from lifewatch.server.providers.folder_provider import folder_provider


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
    # 获取日计划重点
    daily_focus = todo_provider.get_daily_focus(date)
    daily_focus_content = daily_focus['content'] if daily_focus else None
    
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
            pool_order_index=todo.get('pool_order_index'),
            content=todo['content'],
            color=todo['color'] or '#FFFFFF',
            state=todo.get('state', 'active'),
            link_to_goal_id=todo['link_to_goal_id'],
            date=todo.get('date'),
            expected_finished_at=todo['expected_finished_at'],
            actual_finished_at=todo['actual_finished_at'],
            cross_day=bool(todo['cross_day']),
            folder_id=todo.get('folder_id'),
            sub_items=sub_items if sub_items else None
        ))
    
    return TodoListResponse(daily_focus_content=daily_focus_content, items=items)


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
        pool_order_index=todo.get('pool_order_index'),
        content=todo['content'],
        color=todo['color'] or '#FFFFFF',
        state=todo.get('state', 'active'),
        link_to_goal_id=todo['link_to_goal_id'],
        date=todo.get('date'),
        expected_finished_at=todo['expected_finished_at'],
        actual_finished_at=todo['actual_finished_at'],
        cross_day=bool(todo['cross_day']),
        folder_id=todo.get('folder_id'),
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
        'state': request.state,
        'link_to_goal_id': request.link_to_goal_id,
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
    # Use exclude_unset=True so we can distinguish between "unset" and "set to None"
    update_data = request.model_dump(exclude_unset=True)
    data = update_data.copy()

    # Handle side effects
    
    # 1. State changes -> actual_finished_at
    if 'state' in update_data:
        if update_data['state'] == 'completed':
            data['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
        elif update_data['state'] in ['active', 'inactive']:
            data['actual_finished_at'] = None

    # 2. expected_finished_at -> cross_day
    if update_data.get('expected_finished_at'):
        data['cross_day'] = True

    # 3. Explicit cross_day overwrites implicit one
    if 'cross_day' in update_data:
        data['cross_day'] = update_data['cross_day']
        # If manually turning off cross_day, clear expected_finished_at
        if not update_data['cross_day']:
            data['expected_finished_at'] = None
    
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
# Task Pool 服务
# ============================================================================

def get_pool_todos() -> TodoListResponse:
    """
    获取任务池中的所有任务（state='inactive'）
    
    Returns:
        TodoListResponse: 任务列表响应
    """
    todos_data = todo_provider.get_todos_by_state('inactive')
    
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
            pool_order_index=todo.get('pool_order_index'),
            content=todo['content'],
            color=todo['color'] or '#FFFFFF',
            state=todo.get('state', 'inactive'),
            link_to_goal_id=todo['link_to_goal_id'],
            date=todo.get('date'),
            expected_finished_at=todo['expected_finished_at'],
            actual_finished_at=todo['actual_finished_at'],
            cross_day=bool(todo['cross_day']),
            folder_id=todo.get('folder_id'),
            sub_items=sub_items if sub_items else None
        ))
    
    return TodoListResponse(daily_focus_content=None, items=items)


def reorder_pool_todos(todo_ids: List[int]) -> bool:
    """
    重排序任务池任务
    
    Args:
        todo_ids: 任务 ID 列表（按新顺序排列）
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.reorder_pool_todos(todo_ids)


# ============================================================================
# Task Pool Folder 服务
# ============================================================================

def get_folders() -> TaskPoolFolderListResponse:
    """
    获取所有任务池文件夹
    
    Returns:
        TaskPoolFolderListResponse: 文件夹列表响应
    """
    folders_data = folder_provider.get_all_folders()
    
    items = [
        TaskPoolFolderItem(
            id=f['id'],
            name=f['name'],
            order_index=f['order_index'],
            is_expanded=f['is_expanded']
        )
        for f in folders_data
    ]
    
    return TaskPoolFolderListResponse(items=items)


def create_folder(request: CreateFolderRequest) -> TaskPoolFolderItem:
    """
    创建文件夹
    
    Args:
        request: 创建文件夹请求
    
    Returns:
        TaskPoolFolderItem: 新创建的文件夹，失败返回 None
    """
    new_id = folder_provider.create_folder(request.name)
    if new_id:
        folder = folder_provider.get_folder_by_id(new_id)
        if folder:
            return TaskPoolFolderItem(
                id=folder['id'],
                name=folder['name'],
                order_index=folder['order_index'],
                is_expanded=folder['is_expanded']
            )
    return None


def update_folder(folder_id: int, request: UpdateFolderRequest) -> TaskPoolFolderItem:
    """
    更新文件夹
    
    Args:
        folder_id: 文件夹 ID
        request: 更新请求
    
    Returns:
        TaskPoolFolderItem: 更新后的文件夹，失败返回 None
    """
    data = {}
    if request.name is not None:
        data['name'] = request.name
    if request.is_expanded is not None:
        data['is_expanded'] = request.is_expanded
    
    success = folder_provider.update_folder(folder_id, data)
    if success:
        folder = folder_provider.get_folder_by_id(folder_id)
        if folder:
            return TaskPoolFolderItem(
                id=folder['id'],
                name=folder['name'],
                order_index=folder['order_index'],
                is_expanded=folder['is_expanded']
            )
    return None


def delete_folder(folder_id: int) -> bool:
    """
    删除文件夹
    
    Args:
        folder_id: 文件夹 ID
    
    Returns:
        bool: 是否成功
    """
    return folder_provider.delete_folder(folder_id)


def reorder_folders(request: ReorderFoldersRequest) -> bool:
    """
    重排序文件夹
    
    Args:
        request: 重排序请求
    
    Returns:
        bool: 是否成功
    """
    return folder_provider.reorder_folders(request.folder_ids)


def move_todo_to_folder(todo_id: int, request: MoveTodoToFolderRequest) -> bool:
    """
    移动任务到文件夹
    
    Args:
        todo_id: 任务 ID
        request: 移动请求
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.move_todo_to_folder(todo_id, request.folder_id)


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


# ============================================================================
# Plan 服务
# ============================================================================

def _get_week_dates(year: int, month: int, week_num: int) -> tuple:
    """
    计算指定周的日期范围
    
    Args:
        year: 年份
        month: 月份 (1-12)
        week_num: 周序号 (1-4)
    
    Returns:
        tuple: (start_date, end_date) YYYY-MM-DD 格式
    """
    # 获取月份第一天
    first_day = datetime(year, month, 1)
    
    # 调整到该周的周一
    day_of_week = first_day.weekday()  # 0=Monday, 6=Sunday
    first_monday = first_day - timedelta(days=day_of_week)
    
    # 计算目标周的开始日期
    week_start = first_monday + timedelta(weeks=week_num - 1)
    week_end = week_start + timedelta(days=6)
    
    return week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')


def _get_weeks_in_month(year: int, month: int) -> List[dict]:
    """
    获取月份中的所有周信息
    
    Returns:
        List[dict]: [{week_num, start_date, end_date}, ...]
    """
    weeks = []
    for week_num in range(1, 5):
        start_date, end_date = _get_week_dates(year, month, week_num)
        weeks.append({
            'week_num': week_num,
            'start_date': start_date,
            'end_date': end_date
        })
    return weeks


def get_weekly_plan(year: int, month: int, week_num: int) -> WeeklyPlanResponse:
    """
    获取周计划数据
    
    Args:
        year: 年份
        month: 月份 (1-12)
        week_num: 周序号 (1-4)
    
    Returns:
        WeeklyPlanResponse: 周计划响应
    """
    # 1. 获取周焦点
    weekly_focus = todo_provider.get_weekly_focus(year, month, week_num)
    weekly_focus_content = weekly_focus['content'] if weekly_focus else ''
    
    # 2. 计算该周的日期范围
    start_date, end_date = _get_week_dates(year, month, week_num)
    
    # 3. 获取该周所有日焦点
    daily_focuses = todo_provider.get_daily_focuses_in_range(start_date, end_date)
    focus_map = {f['date']: f['content'] for f in daily_focuses}
    
    # 4. 遍历7天，组装 DailyPlanItem
    items = []
    current = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    day_id = 1
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        
        # 获取当天任务（复用 get_todos）
        todos_response = get_todos(date_str, include_cross_day=False)
        todo_list = todos_response.items
        
        total = len(todo_list)
        completed = sum(1 for t in todo_list if t.state == 'completed')
        completion_rate = (completed / total) if total > 0 else 0.0
        
        items.append(DailyPlanItem(
            id=day_id,
            date=date_str,
            daily_focus_content=focus_map.get(date_str, ''),
            completion_rate=completion_rate,
            todo_list=todo_list
        ))
        
        current += timedelta(days=1)
        day_id += 1
    
    return WeeklyPlanResponse(
        weekly_focus_content=weekly_focus_content,
        items=items
    )


def get_monthly_plan(year: int, month: int) -> MonthlyPlanItem:
    """
    获取月计划数据
    
    Args:
        year: 年份
        month: 月份 (1-12)
    
    Returns:
        MonthlyPlanItem: 月计划响应
    """
    # 获取该月所有周焦点
    weekly_focuses = todo_provider.get_weekly_focuses_in_month(year, month)
    focus_map = {f['week_num']: f['content'] for f in weekly_focuses}
    
    # 组装周计划项
    weeks = _get_weeks_in_month(year, month)
    items = []
    
    for i, week in enumerate(weeks):
        week_num = week['week_num']
        
        # 获取该周所有任务计算完成率
        start_date = week['start_date']
        end_date = week['end_date']
        
        # 简化完成率计算：获取该周每天的任务
        total_todos = 0
        completed_todos = 0
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            todos = todo_provider.get_todos_by_date(date_str, include_cross_day=False)
            total_todos += len(todos)
            completed_todos += sum(1 for t in todos if t.get('state') == 'completed')
            current += timedelta(days=1)
        
        completion_rate = (completed_todos / total_todos) if total_todos > 0 else 0.0
        
        items.append(WeeklyPlanItem(
            id=i + 1,
            start_date=start_date,
            end_date=end_date,
            weekly_focus_content=focus_map.get(week_num, ''),
            completion_rate=completion_rate
        ))
    
    return MonthlyPlanItem(
        monthly_focus_content='',  # 暂不实现月焦点
        items=items
    )


def upsert_daily_focus(request: UpsertDailyFocusRequest) -> bool:
    """
    创建或更新日焦点
    
    Args:
        request: 更新请求
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.upsert_daily_focus(request.date, request.content)


def upsert_weekly_focus(request: UpsertWeeklyFocusRequest) -> bool:
    """
    创建或更新周焦点
    
    Args:
        request: 更新请求
    
    Returns:
        bool: 是否成功
    """
    return todo_provider.upsert_weekly_focus(
        request.year, 
        request.month, 
        request.week_num, 
        request.content
    )
