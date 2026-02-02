"""
任务池服务层 - Task Pool V2 业务逻辑

核心功能：
1. 获取任务池任务（支持筛选）
2. 同步计划书任务（MD 解析 + 数据库同步）
3. 更新任务（含 MD 回写）
4. 重新生成系统展示区

MD 解析规则：
- 任务块：<!-- lp:todoblock --> 和 <!-- /lp:todoblock --> 之间
- 锚点格式：<!-- lp:t-xxx -->
- 缩进规则：Tab 缩进判断父子关系
"""
import re
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from lifeprism.server.schemas.taskpool_schemas import (
    TaskPoolItem,
    TaskPoolResponse,
    SyncPlanDocResponse,
    UpdateTodoV2Response,
)
from lifeprism.server.providers.todo_provider import todo_provider
from lifeprism.server.providers.plan_doc_provider import plan_doc_provider
from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 计划书文件存储目录（与 plan_doc_service.py 保持一致）
PLAN_DOC_DIR = Path("frontend/customData/plan")


# ============================================================================
# 数据转换
# ============================================================================

def _db_to_taskpool_item(db_item: Dict[str, Any]) -> TaskPoolItem:
    """将数据库记录转换为 TaskPoolItem"""
    return TaskPoolItem(
        id=db_item['id'],
        content=db_item['content'],
        parent_id=db_item.get('parent_id'),
        link_to_goal_id=db_item.get('link_to_goal_id'),
        plan_doc_id=db_item.get('plan_doc_id'),
        source_anchor_id=db_item.get('source_anchor_id'),
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
    )


# ============================================================================
# 任务池查询
# ============================================================================

def get_taskpool(
    goal_id: Optional[str] = None,
    plan_doc_id: Optional[str] = None,
    state: Optional[str] = "all"
) -> TaskPoolResponse:
    """
    获取任务池任务列表
    
    Args:
        goal_id: 按目标筛选
        plan_doc_id: 按计划书筛选
        state: 按状态筛选（pool/scheduled/completed/all）
    
    Returns:
        TaskPoolResponse: 任务列表（扁平结构）
    """
    db_items = todo_provider.get_todos_for_taskpool(
        goal_id=goal_id,
        plan_doc_id=plan_doc_id,
        state=state
    )
    
    items = [_db_to_taskpool_item(item) for item in db_items]
    return TaskPoolResponse(items=items)


# ============================================================================
# MD 文件操作
# ============================================================================

def _get_plan_doc_path(doc_id: str) -> Path:
    """获取计划书 MD 文件路径"""
    return PLAN_DOC_DIR / f"{doc_id}.md"


def _read_plan_doc_content(doc_id: str) -> Optional[str]:
    """读取计划书 MD 内容"""
    file_path = _get_plan_doc_path(doc_id)
    try:
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        return None
    except Exception as e:
        logger.error(f"读取计划书文件失败 {doc_id}: {e}")
        return None


def _write_plan_doc_content(doc_id: str, content: str) -> bool:
    """写入计划书 MD 内容"""
    file_path = _get_plan_doc_path(doc_id)
    try:
        PLAN_DOC_DIR.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        logger.error(f"写入计划书文件失败 {doc_id}: {e}")
        return False


def _generate_anchor_id() -> str:
    """生成锚点 ID（格式：t-{uuid[:8]}）"""
    return f"t-{uuid.uuid4().hex[:8]}"


# ============================================================================
# MD 解析
# ============================================================================

# 正则表达式
TODOBLOCK_PATTERN = re.compile(
    r'<!--\s*lp:todoblock\s*-->(.*?)<!--\s*/lp:todoblock\s*-->',
    re.DOTALL
)
TASK_LINE_PATTERN = re.compile(
    r'^(\t*)-\s*\[([ xX])\]\s*(.+?)(?:\s*<!--\s*lp:(t-[a-f0-9]+)\s*-->)?$'
)
ANCHOR_PATTERN = re.compile(r'<!--\s*lp:(t-[a-f0-9]+)\s*-->')
SYSTEM_SECTION_START = '<!-- lp:system-section -->'


def _parse_task_line(line: str) -> Optional[Dict[str, Any]]:
    """
    解析单行任务
    
    Returns:
        Dict with keys: indent_level, is_checked, content, anchor_id (可能为 None)
        如果不是任务行，返回 None
    """
    match = TASK_LINE_PATTERN.match(line)
    if not match:
        return None
    
    tabs, checkbox, content, anchor_id = match.groups()
    
    # 清理 content 中可能残留的锚点注释
    content = ANCHOR_PATTERN.sub('', content).strip()
    
    if not content:
        return None
    
    return {
        'indent_level': len(tabs),
        'is_checked': checkbox.lower() == 'x',
        'content': content,
        'anchor_id': anchor_id,
    }


def _parse_todoblock(block_content: str) -> List[Dict[str, Any]]:
    """
    解析 todoblock 中的所有任务
    
    Returns:
        任务列表，每项包含：
        - indent_level: 缩进级别
        - is_checked: 是否勾选
        - content: 任务内容
        - anchor_id: 锚点 ID（可能为 None）
        - line_index: 在 block 中的行索引
    """
    tasks = []
    lines = block_content.split('\n')
    
    for line_index, line in enumerate(lines):
        parsed = _parse_task_line(line)
        if parsed:
            parsed['line_index'] = line_index
            parsed['original_line'] = line
            tasks.append(parsed)
    
    return tasks


def _build_parent_map(tasks: List[Dict[str, Any]]) -> Dict[int, Optional[str]]:
    """
    根据缩进级别构建父任务映射
    
    Returns:
        Dict[line_index -> parent_anchor_id]
    """
    parent_map = {}
    level_stack = []  # 栈：(level, anchor_id)
    
    for task in tasks:
        level = task['indent_level']
        anchor_id = task['anchor_id']
        line_index = task['line_index']
        
        # 弹出栈中所有 level >= 当前 level 的项
        while level_stack and level_stack[-1][0] >= level:
            level_stack.pop()
        
        # 确定父任务
        if level_stack:
            parent_map[line_index] = level_stack[-1][1]
        else:
            parent_map[line_index] = None
        
        # 当前任务入栈
        if anchor_id:
            level_stack.append((level, anchor_id))
    
    return parent_map


# ============================================================================
# 同步逻辑
# ============================================================================

def sync_plan_doc(plan_doc_id: str) -> SyncPlanDocResponse:
    """
    同步计划书任务
    
    处理流程：
    1. 读取 MD 文件
    2. 解析 todoblock 中的任务
    3. 为无锚点的任务生成锚点并写回 MD
    4. 创建/更新数据库记录
    5. 更新系统展示区
    
    Args:
        plan_doc_id: 计划书 ID
    
    Returns:
        SyncPlanDocResponse: 同步结果统计
    """
    result = SyncPlanDocResponse(created=0, updated=0, cleaned=0, total=0)
    
    # 1. 验证计划书存在
    plan_doc = plan_doc_provider.get_plan_doc_by_id(plan_doc_id)
    if not plan_doc:
        logger.warning(f"计划书不存在: {plan_doc_id}")
        return result
    
    goal_id = plan_doc.get('goal_id')
    
    # 2. 读取 MD 内容
    content = _read_plan_doc_content(plan_doc_id)
    if content is None:
        logger.warning(f"计划书 MD 文件不存在: {plan_doc_id}")
        return result
    
    # 3. 查找并解析 todoblock
    todoblock_match = TODOBLOCK_PATTERN.search(content)
    if not todoblock_match:
        logger.info(f"计划书无 todoblock: {plan_doc_id}")
        return result
    
    block_content = todoblock_match.group(1)
    block_start = todoblock_match.start(1)
    block_end = todoblock_match.end(1)
    
    # 4. 解析任务
    parsed_tasks = _parse_todoblock(block_content)
    if not parsed_tasks:
        logger.info(f"todoblock 无有效任务: {plan_doc_id}")
        return result
    
    # 5. 为无锚点的任务生成锚点
    modified_lines = {}  # line_index -> new_line
    for task in parsed_tasks:
        if not task['anchor_id']:
            new_anchor = _generate_anchor_id()
            task['anchor_id'] = new_anchor
            
            # 构建新行（在内容后添加锚点）
            tabs = '\t' * task['indent_level']
            checkbox = '[x]' if task['is_checked'] else '[ ]'
            new_line = f"{tabs}- {checkbox} {task['content']} <!-- lp:{new_anchor} -->"
            modified_lines[task['line_index']] = new_line
    
    # 6. 如果有修改，更新 MD 内容
    if modified_lines:
        lines = block_content.split('\n')
        for line_index, new_line in modified_lines.items():
            lines[line_index] = new_line
        new_block_content = '\n'.join(lines)
        content = content[:block_start] + new_block_content + content[block_end:]
    
    # 7. 构建父任务映射
    parent_map = _build_parent_map(parsed_tasks)
    
    # 8. 获取现有任务（用于匹配）
    existing_todos = todo_provider.get_todos_by_plan_doc(plan_doc_id)
    existing_by_anchor = {t['source_anchor_id']: t for t in existing_todos if t.get('source_anchor_id')}
    
    # 9. 处理每个解析出的任务
    anchor_to_db_id = {}  # anchor_id -> db_id 映射（用于设置 parent_id）
    todos_to_create = []
    todos_to_update = []
    
    for order_index, task in enumerate(parsed_tasks):
        anchor_id = task['anchor_id']
        existing = existing_by_anchor.get(anchor_id)
        
        if existing:
            # 更新现有任务
            update_data = {
                'id': existing['id'],
                'content': task['content'],
                'pool_order_index': order_index,
            }
            
            # 状态同步：只有 [x] -> completed，不能 [ ] 取消完成
            if task['is_checked'] and existing.get('state') != 'completed':
                update_data['state'] = 'completed'
                update_data['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
            
            todos_to_update.append(update_data)
            anchor_to_db_id[anchor_id] = existing['id']
            result.updated += 1
        else:
            # 创建新任务
            create_data = {
                'content': task['content'],
                'state': 'completed' if task['is_checked'] else 'pool',
                'plan_doc_id': plan_doc_id,
                'source_anchor_id': anchor_id,
                'link_to_goal_id': goal_id,
                'pool_order_index': order_index,
                'order_index': 0,
                'color': '#FFFFFF',
            }
            
            if task['is_checked']:
                create_data['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
            
            todos_to_create.append({
                'data': create_data,
                'anchor_id': anchor_id,
                'parent_anchor': parent_map.get(task['line_index']),
            })
            result.created += 1
    
    # 10. 执行数据库操作
    # 先批量更新
    if todos_to_update:
        todo_provider.batch_update_todos(todos_to_update)
    
    # 再批量创建（需要先创建父任务才能设置 parent_id）
    # 按缩进级别排序，确保父任务先创建
    if todos_to_create:
        # 第一轮：创建所有任务（暂不设置 parent_id）
        create_data_list = [item['data'] for item in todos_to_create]
        new_ids = todo_provider.batch_create_todos(create_data_list)
        
        # 记录 anchor -> id 映射
        for i, item in enumerate(todos_to_create):
            if i < len(new_ids):
                anchor_to_db_id[item['anchor_id']] = new_ids[i]
        
        # 第二轮：更新 parent_id
        parent_updates = []
        for i, item in enumerate(todos_to_create):
            if i < len(new_ids) and item['parent_anchor']:
                parent_db_id = anchor_to_db_id.get(item['parent_anchor'])
                if parent_db_id:
                    parent_updates.append({
                        'id': new_ids[i],
                        'parent_id': parent_db_id,
                    })
        
        if parent_updates:
            todo_provider.batch_update_todos(parent_updates)
    
    # 11. 更新系统展示区并保存 MD
    content = _update_system_section(content, plan_doc_id)
    _write_plan_doc_content(plan_doc_id, content)
    
    # 12. 统计总数
    result.total = len(todo_provider.get_todos_by_plan_doc(plan_doc_id))
    
    logger.info(f"同步计划书 {plan_doc_id} 完成: created={result.created}, updated={result.updated}")
    return result


# ============================================================================
# 更新任务（含 MD 回写）
# ============================================================================

def update_todo_with_writeback(
    todo_id: int,
    updates: Dict[str, Any]
) -> Optional[UpdateTodoV2Response]:
    """
    更新任务，并在必要时回写 MD 文件
    
    当 state 变为 completed 时，如果任务关联了计划书且有锚点，
    会将 MD 中的 [ ] 改为 [x]
    
    Args:
        todo_id: 任务 ID
        updates: 更新数据
    
    Returns:
        UpdateTodoV2Response: 更新结果
    """
    # 1. 获取现有任务
    existing = todo_provider.get_todo_by_id(todo_id)
    if not existing:
        logger.warning(f"任务不存在: {todo_id}")
        return None
    
    # 2. 处理状态变更副作用
    if updates.get('state') == 'completed' and existing.get('state') != 'completed':
        updates['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
    elif updates.get('state') in ['pool', 'scheduled'] and existing.get('state') == 'completed':
        # 不允许取消完成（根据需求文档）
        pass  # 保持 completed 状态
    
    # 3. 更新数据库
    success = todo_provider.update_todo(todo_id, updates)
    if not success:
        return None
    
    # 4. 检查是否需要回写 MD
    md_synced = False
    new_state = updates.get('state')
    plan_doc_id = existing.get('plan_doc_id')
    anchor_id = existing.get('source_anchor_id')
    
    if new_state == 'completed' and plan_doc_id and anchor_id:
        md_synced = _writeback_completion_to_md(plan_doc_id, anchor_id)
    
    # 5. 获取更新后的任务
    updated = todo_provider.get_todo_by_id(todo_id)
    if not updated:
        return None
    
    return UpdateTodoV2Response(
        item=_db_to_taskpool_item(updated),
        md_synced=md_synced
    )


def _writeback_completion_to_md(plan_doc_id: str, anchor_id: str) -> bool:
    """
    将完成状态回写到 MD 文件
    
    将 - [ ] xxx <!-- lp:t-xxx --> 改为 - [x] xxx <!-- lp:t-xxx -->
    """
    content = _read_plan_doc_content(plan_doc_id)
    if not content:
        logger.warning(f"回写失败：MD 文件不存在 {plan_doc_id}")
        return False
    
    # 查找锚点所在行
    anchor_pattern = re.compile(
        rf'^(\t*)-\s*\[\s*\]\s*(.+?)\s*<!--\s*lp:{re.escape(anchor_id)}\s*-->',
        re.MULTILINE
    )
    
    match = anchor_pattern.search(content)
    if not match:
        logger.warning(f"回写失败：未找到锚点 {anchor_id}")
        return False
    
    # 替换 [ ] 为 [x]
    tabs = match.group(1)
    task_content = match.group(2)
    old_line = match.group(0)
    new_line = f"{tabs}- [x] {task_content} <!-- lp:{anchor_id} -->"
    
    content = content.replace(old_line, new_line, 1)
    
    # 更新系统展示区
    content = _update_system_section(content, plan_doc_id)
    
    # 保存
    if _write_plan_doc_content(plan_doc_id, content):
        logger.info(f"回写完成状态成功: {plan_doc_id}/{anchor_id}")
        return True
    
    return False


# ============================================================================
# 系统展示区
# ============================================================================

def _update_system_section(content: str, plan_doc_id: str) -> str:
    """
    更新或添加系统展示区
    
    系统展示区格式：
    ---
    
    ## 任务总览
    <!-- lp:system-section -->
    > 此区域由系统自动生成，手动修改将在下次同步时被覆盖
    
    - [ ] 任务 1
        - [x] 子任务 1.1
    - [x] 任务 2
    """
    # 获取该计划书的所有任务
    todos = todo_provider.get_todos_by_plan_doc(plan_doc_id)
    
    if not todos:
        # 无任务，移除系统展示区
        system_start = content.find(SYSTEM_SECTION_START)
        if system_start != -1:
            # 查找 --- 分隔线
            separator_pos = content.rfind('---', 0, system_start)
            if separator_pos != -1:
                content = content[:separator_pos].rstrip()
        return content
    
    # 构建任务树
    task_tree = _build_task_tree_for_summary(todos)
    
    # 生成 MD 内容
    summary_lines = [
        '',
        '---',
        '',
        '## 任务总览',
        SYSTEM_SECTION_START,
        '> 此区域由系统自动生成，手动修改将在下次同步时被覆盖',
        '',
    ]
    summary_lines.extend(_render_task_tree(task_tree, 0))
    summary_content = '\n'.join(summary_lines)
    
    # 查找并替换现有系统展示区
    system_start = content.find(SYSTEM_SECTION_START)
    if system_start != -1:
        # 找到 --- 分隔线位置
        separator_pos = content.rfind('---', 0, system_start)
        if separator_pos != -1:
            content = content[:separator_pos].rstrip() + summary_content
        else:
            content = content[:system_start].rstrip() + summary_content
    else:
        # 添加新的系统展示区
        content = content.rstrip() + summary_content
    
    return content


def _build_task_tree_for_summary(todos: List[Dict]) -> List[Dict]:
    """构建任务树用于系统展示区"""
    # 按 ID 索引
    todo_map = {t['id']: {**t, 'children': []} for t in todos}
    roots = []
    
    for todo in todos:
        todo_with_children = todo_map[todo['id']]
        parent_id = todo.get('parent_id')
        
        if parent_id and parent_id in todo_map:
            todo_map[parent_id]['children'].append(todo_with_children)
        else:
            roots.append(todo_with_children)
    
    # 按 pool_order_index 排序
    def sort_key(t):
        return t.get('pool_order_index') or 0
    
    roots.sort(key=sort_key)
    for todo in todo_map.values():
        todo['children'].sort(key=sort_key)
    
    return roots


def _render_task_tree(tasks: List[Dict], indent: int) -> List[str]:
    """渲染任务树为 MD 格式（不含锚点）"""
    lines = []
    tabs = '\t' * indent
    
    for task in tasks:
        checkbox = '[x]' if task.get('state') == 'completed' else '[ ]'
        lines.append(f"{tabs}- {checkbox} {task['content']}")
        
        if task.get('children'):
            lines.extend(_render_task_tree(task['children'], indent + 1))
    
    return lines


def regenerate_summary(plan_doc_id: str) -> bool:
    """
    重新生成系统展示区

    Args:
        plan_doc_id: 计划书 ID

    Returns:
        bool: 是否成功
    """
    content = _read_plan_doc_content(plan_doc_id)
    if content is None:
        logger.warning(f"重新生成失败：MD 文件不存在 {plan_doc_id}")
        return False

    content = _update_system_section(content, plan_doc_id)
    return _write_plan_doc_content(plan_doc_id, content)


# ============================================================================
# 统一 Todos API 服务函数
# ============================================================================

def get_todos_by_date(date: str) -> TaskPoolResponse:
    """
    获取指定日期的任务列表

    包含：
    1. 当天 scheduled 状态的任务
    2. 当天 completed 状态的任务

    Args:
        date: 日期（YYYY-MM-DD 格式）

    Returns:
        TaskPoolResponse: 任务列表
    """
    db_items = todo_provider.get_todos_by_date(date, include_cross_day=False)

    # 过滤出 scheduled 和 completed 状态的任务
    filtered_items = [
        item for item in db_items
        if item.get('state') in ('scheduled', 'completed')
    ]

    items = [_db_to_taskpool_item(item) for item in filtered_items]
    return TaskPoolResponse(items=items)


def create_todo_v2(data: Dict[str, Any]) -> Optional[TaskPoolItem]:
    """
    创建新任务 (V2)

    Args:
        data: 任务数据

    Returns:
        Optional[TaskPoolItem]: 创建的任务，失败返回 None
    """
    # 如果设置了 date 且状态为 pool，自动改为 scheduled
    if data.get('date') and data.get('state', 'pool') == 'pool':
        data['state'] = 'scheduled'

    new_id = todo_provider.create_todo(data)
    if not new_id:
        return None

    db_item = todo_provider.get_todo_by_id(new_id)
    if not db_item:
        return None

    return _db_to_taskpool_item(db_item)


def get_todo_by_id(todo_id: int) -> Optional[TaskPoolItem]:
    """
    获取单个任务

    Args:
        todo_id: 任务 ID

    Returns:
        Optional[TaskPoolItem]: 任务数据，不存在返回 None
    """
    db_item = todo_provider.get_todo_by_id(todo_id)
    if not db_item:
        return None

    return _db_to_taskpool_item(db_item)


def delete_todo(todo_id: int) -> bool:
    """
    删除任务

    Args:
        todo_id: 任务 ID

    Returns:
        bool: 是否成功
    """
    return todo_provider.delete_todo(todo_id)
