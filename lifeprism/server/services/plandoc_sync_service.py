"""
PlanDoc 同步服务 - 计划书 MD 文件与数据库的双向同步

核心功能：
1. MD 文件读写与解析（todoblock、锚点、任务行）
2. MD ↔ DB 双向同步（sync_plan_doc）
3. MD 回写操作（插入、更新、删除、状态回写）
4. 系统展示区管理

MD 解析规则：
- 任务块：<!-- lp:todoblock --> 和 <!-- /lp:todoblock --> 之间
- 支持多个 todoblock，每个 block 独立解析
- 锚点格式：<!-- lp:t-xxx -->
- 缩进规则：Tab 缩进判断父子关系（仅在同一 block 内有效）
"""
import re
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from lifeprism.server.schemas.plan_doc_schemas import (
    SyncPlanDocResponse, TodoDeletePreview,
)
from lifeprism.server.providers.todo_provider import todo_provider
from lifeprism.server.providers.plan_doc_provider import plan_doc_provider
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# 文件 I/O
# ============================================================================

def _get_plan_doc_dir() -> Path:
    """获取计划书目录路径"""
    from lifeprism.config.settings_manager import settings
    return Path(settings.lifeprism_data_path) / "plan"


def _get_plan_doc_path(doc_id: str) -> Path:
    """获取计划书 MD 文件路径"""
    return _get_plan_doc_dir() / f"{doc_id}.md"


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
        _get_plan_doc_dir().mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        logger.error(f"写入计划书文件失败 {doc_id}: {e}")
        return False


def _generate_anchor_id() -> str:
    """生成锚点 ID（格式：t-{uuid[:8]}）"""
    return f"t-{uuid.uuid4().hex[:8]}"


# ============================================================================
# 正则常量
# ============================================================================

TODOBLOCK_PATTERN = re.compile(
    r'<!--\s*lp:todoblock\s*-->(.*?)<!--\s*/lp:todoblock\s*-->',
    re.DOTALL
)
TASK_LINE_PATTERN = re.compile(
    r'^(\t*)-\s*\[([ xX])\]\s*(.+?)(?:\s*<!--\s*lp:(t-[a-f0-9]+)\s*-->)?$'
)
ANCHOR_PATTERN = re.compile(r'<!--\s*lp:(t-[a-f0-9]+)\s*-->')
SYSTEM_SECTION_START = '<!-- lp:system-section -->'


# ============================================================================
# MD 解析
# ============================================================================

def _ensure_todoblock_exists(content: str) -> str:
    """
    确保 MD 内容中存在 todoblock 标记

    如果不存在，在文档末尾（系统展示区之前）添加 todoblock。
    """
    if TODOBLOCK_PATTERN.search(content):
        return content

    todoblock = "\n\n## 任务列表\n<!-- lp:todoblock -->\n\n<!-- /lp:todoblock -->\n"

    system_start = content.find(SYSTEM_SECTION_START)
    if system_start != -1:
        separator_pos = content.rfind('---', 0, system_start)
        if separator_pos != -1:
            content = content[:separator_pos].rstrip() + todoblock + content[separator_pos:]
        else:
            content = content[:system_start].rstrip() + todoblock + content[system_start:]
    else:
        content = content.rstrip() + todoblock

    return content


def _get_all_todoblocks(content: str) -> List[Dict[str, Any]]:
    """
    获取所有 todoblock 的信息

    Returns:
        List[Dict]: 每个 block 包含:
            - block_content: block 内容
            - start: block 内容在原文中的起始位置
            - end: block 内容在原文中的结束位置
            - block_index: block 索引（从 0 开始）
    """
    blocks = []
    for i, match in enumerate(TODOBLOCK_PATTERN.finditer(content)):
        blocks.append({
            'block_content': match.group(1),
            'start': match.start(1),
            'end': match.end(1),
            'block_index': i,
        })
    return blocks


def _find_anchor_in_blocks(content: str, anchor_id: str) -> Optional[int]:
    """
    查找锚点所在的 todoblock 索引

    Returns:
        Optional[int]: block 索引，未找到返回 None
    """
    blocks = _get_all_todoblocks(content)
    for block in blocks:
        if f"lp:{anchor_id}" in block['block_content']:
            return block['block_index']
    return None


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
        - indent_level, is_checked, content, anchor_id, line_index, original_line
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
# 数据完整性校验
# ============================================================================

# ============================================================================
# MD 回写操作
# ============================================================================

def insert_todo_to_md(
    plan_doc_id: str,
    content: str,
    parent_anchor_id: Optional[str] = None
) -> Optional[str]:
    """
    插入新任务到 MD 文件（支持多个 todoblock）

    插入策略：
    - 如果有 parent_anchor_id，插入到父任务所在的 block
    - 如果没有 parent_anchor_id，插入到第一个 todoblock

    Returns:
        Optional[str]: 新生成的锚点 ID，失败返回 None
    """
    md_content = _read_plan_doc_content(plan_doc_id)
    if md_content is None:
        logger.warning(f"插入失败：MD 文件不存在 {plan_doc_id}")
        return None

    blocks = _get_all_todoblocks(md_content)
    if not blocks:
        logger.warning(f"插入失败：无 todoblock {plan_doc_id}")
        return None

    # 确定目标 block
    target_block_index = 0
    if parent_anchor_id:
        found_index = _find_anchor_in_blocks(md_content, parent_anchor_id)
        if found_index is not None:
            target_block_index = found_index

    target_block = blocks[target_block_index]
    block_content = target_block['block_content']
    block_start = target_block['start']
    block_end = target_block['end']

    new_anchor = _generate_anchor_id()

    # 确定缩进级别和插入位置
    indent_level = 0
    insert_position = len(block_content)

    if parent_anchor_id:
        lines = block_content.split('\n')
        for i, line in enumerate(lines):
            if f"lp:{parent_anchor_id}" in line:
                parent_indent = len(line) - len(line.lstrip('\t'))
                indent_level = parent_indent + 1

                insert_line_index = i + 1
                while insert_line_index < len(lines):
                    next_line = lines[insert_line_index]
                    if next_line.strip() and next_line.startswith('\t' * (parent_indent + 1)):
                        insert_line_index += 1
                    else:
                        break

                insert_position = sum(len(lines[j]) + 1 for j in range(insert_line_index))
                break

    tabs = '\t' * indent_level
    new_line = f"{tabs}- [ ] {content} <!-- lp:{new_anchor} -->\n"

    new_block_content = block_content[:insert_position] + new_line + block_content[insert_position:]
    new_md_content = md_content[:block_start] + new_block_content + md_content[block_end:]

    new_md_content = _update_system_section(new_md_content, plan_doc_id)
    if _write_plan_doc_content(plan_doc_id, new_md_content):
        logger.info(f"插入任务到 MD 成功: {plan_doc_id}/{new_anchor} (block {target_block_index})")
        return new_anchor

    return None


def update_todo_in_md(plan_doc_id: str, anchor_id: str, new_content: str) -> bool:
    """
    更新 MD 中的任务内容

    Returns:
        bool: 是否成功
    """
    md_content = _read_plan_doc_content(plan_doc_id)
    if md_content is None:
        logger.warning(f"更新失败：MD 文件不存在 {plan_doc_id}")
        return False

    pattern = re.compile(
        rf'^(\t*)-\s*\[([ xX])\]\s*.+?\s*<!--\s*lp:{re.escape(anchor_id)}\s*-->',
        re.MULTILINE
    )

    match = pattern.search(md_content)
    if not match:
        logger.warning(f"更新失败：未找到锚点 {anchor_id}")
        return False

    tabs = match.group(1)
    checkbox_state = match.group(2)
    old_line = match.group(0)
    new_line = f"{tabs}- [{checkbox_state}] {new_content} <!-- lp:{anchor_id} -->"

    new_md_content = md_content.replace(old_line, new_line, 1)

    new_md_content = _update_system_section(new_md_content, plan_doc_id)
    if _write_plan_doc_content(plan_doc_id, new_md_content):
        logger.info(f"更新任务内容成功: {plan_doc_id}/{anchor_id}")
        return True

    return False


def delete_todo_from_md(plan_doc_id: str, anchor_id: str) -> bool:
    """
    从 MD 删除任务（含子任务，支持多个 todoblock）

    Returns:
        bool: 是否成功
    """
    md_content = _read_plan_doc_content(plan_doc_id)
    if md_content is None:
        logger.warning(f"删除失败：MD 文件不存在 {plan_doc_id}")
        return False

    blocks = _get_all_todoblocks(md_content)
    if not blocks:
        logger.warning(f"删除失败：无 todoblock {plan_doc_id}")
        return False

    target_block_index = _find_anchor_in_blocks(md_content, anchor_id)
    if target_block_index is None:
        logger.warning(f"删除失败：未找到锚点 {anchor_id}")
        return False

    target_block = blocks[target_block_index]
    block_content = target_block['block_content']
    block_start = target_block['start']
    block_end = target_block['end']

    lines = block_content.split('\n')
    new_lines = []
    skip_until_indent = -1

    for line in lines:
        if f"lp:{anchor_id}" in line:
            current_indent = len(line) - len(line.lstrip('\t'))
            skip_until_indent = current_indent
            continue

        if skip_until_indent >= 0:
            if line.strip():
                current_indent = len(line) - len(line.lstrip('\t'))
                if current_indent > skip_until_indent:
                    continue
                else:
                    skip_until_indent = -1
            else:
                continue

        new_lines.append(line)

    # 清理连续的多余空行
    cleaned_lines = []
    prev_empty = False
    for line in new_lines:
        is_empty = not line.strip()
        if is_empty and prev_empty:
            continue
        cleaned_lines.append(line)
        prev_empty = is_empty

    new_block_content = '\n'.join(cleaned_lines)
    new_md_content = md_content[:block_start] + new_block_content + md_content[block_end:]

    new_md_content = _update_system_section(new_md_content, plan_doc_id)
    if _write_plan_doc_content(plan_doc_id, new_md_content):
        logger.info(f"从 MD 删除任务成功: {plan_doc_id}/{anchor_id} (block {target_block_index})")
        return True

    return False


# ============================================================================
# 同步核心
# ============================================================================

def sync_plan_doc(
    plan_doc_id: str,
    dry_run: bool = False,
    confirm_delete: bool = False
) -> SyncPlanDocResponse:
    """
    同步计划书任务（支持多个 todoblock）

    处理流程：
    1. 读取 MD 文件
    2. 解析所有 todoblock 中的任务
    3. 为无锚点的任务生成锚点并写回 MD
    4. 创建/更新数据库记录
    5. 检测并处理删除的任务
    6. 更新系统展示区
    """
    result = SyncPlanDocResponse(created=0, updated=0, deleted=0, cleaned=0, total=0)

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

    # 3. 获取所有 todoblock
    blocks = _get_all_todoblocks(content)
    if not blocks:
        logger.info(f"计划书无 todoblock，自动创建: {plan_doc_id}")
        content = _ensure_todoblock_exists(content)
        _write_plan_doc_content(plan_doc_id, content)
        blocks = _get_all_todoblocks(content)
        if not blocks:
            logger.error(f"创建 todoblock 失败: {plan_doc_id}")
            return result

    # 4. 解析所有 block 中的任务
    all_parsed_tasks = []
    block_modifications = {}

    for block in blocks:
        block_content = block['block_content']
        block_index = block['block_index']

        parsed_tasks = _parse_todoblock(block_content)

        modifications = {}
        for task in parsed_tasks:
            task['block_index'] = block_index

            if not task['anchor_id']:
                new_anchor = _generate_anchor_id()
                task['anchor_id'] = new_anchor

                tabs = '\t' * task['indent_level']
                checkbox = '[x]' if task['is_checked'] else '[ ]'
                new_line = f"{tabs}- {checkbox} {task['content']} <!-- lp:{new_anchor} -->"
                modifications[task['line_index']] = new_line

        if modifications:
            block_modifications[block_index] = modifications

        all_parsed_tasks.extend(parsed_tasks)

    # 5. 如果有修改，更新 MD 内容（从后往前更新，避免位置偏移）
    if block_modifications:
        for block_index in sorted(block_modifications.keys(), reverse=True):
            block = blocks[block_index]
            block_content = block['block_content']
            block_start = block['start']
            block_end = block['end']

            lines = block_content.split('\n')
            for line_index, new_line in block_modifications[block_index].items():
                lines[line_index] = new_line
            new_block_content = '\n'.join(lines)

            content = content[:block_start] + new_block_content + content[block_end:]

        blocks = _get_all_todoblocks(content)

    # 6. 构建父任务映射（每个 block 独立构建）
    parent_map = {}
    for block in blocks:
        block_tasks = [t for t in all_parsed_tasks if t.get('block_index') == block['block_index']]
        block_parent_map = _build_parent_map(block_tasks)
        for line_index, parent_anchor in block_parent_map.items():
            parent_map[(block['block_index'], line_index)] = parent_anchor

    # 7. 获取现有任务
    existing_todos = todo_provider.get_todos_by_plan_doc(plan_doc_id)
    existing_by_anchor = {t['source_anchor_id']: t for t in existing_todos if t.get('source_anchor_id')}

    md_anchor_ids = {task['anchor_id'] for task in all_parsed_tasks if task['anchor_id']}

    # 8. 检测待删除的任务
    todos_to_delete = []
    for todo in existing_todos:
        anchor_id = todo.get('source_anchor_id')
        if anchor_id and anchor_id not in md_anchor_ids:
            todos_to_delete.append(todo)

    # 9. 处理每个解析出的任务
    anchor_to_db_id = {}
    todos_to_create = []
    todos_to_update = []
    existing_parent_info = []

    for order_index, task in enumerate(all_parsed_tasks):
        anchor_id = task['anchor_id']
        existing = existing_by_anchor.get(anchor_id)
        parent_key = (task.get('block_index'), task['line_index'])

        if existing:
            update_data = {
                'id': existing['id'],
                'content': task['content'],
                'pool_order_index': order_index,
            }

            if task['is_checked'] and existing.get('state') != 'completed':
                update_data['state'] = 'completed'
                update_data['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
            elif not task['is_checked'] and existing.get('state') == 'completed':
                update_data['state'] = 'pool'
                update_data['actual_finished_at'] = None

            todos_to_update.append(update_data)
            anchor_to_db_id[anchor_id] = existing['id']

            existing_parent_info.append({
                'id': existing['id'],
                'parent_anchor': parent_map.get(parent_key),
                'old_parent_id': existing.get('parent_id'),
            })

            result.updated += 1
        else:
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
                'parent_anchor': parent_map.get(parent_key),
            })
            result.created += 1

    # 10. dry_run 模式
    if dry_run:
        result.to_delete = [
            TodoDeletePreview(
                id=todo['id'],
                content=todo['content'],
                state=todo.get('state', 'pool'),
                source_anchor_id=todo.get('source_anchor_id')
            )
            for todo in todos_to_delete
        ]
        result.total = len(existing_todos)
        logger.info(f"同步预检 {plan_doc_id}: to_create={result.created}, to_update={result.updated}, to_delete={len(todos_to_delete)}")
        return result

    # 11. 执行数据库操作
    if todos_to_update:
        todo_provider.batch_update_todos(todos_to_update)

    if todos_to_create:
        create_data_list = [item['data'] for item in todos_to_create]
        new_ids = todo_provider.batch_create_todos(create_data_list)

        for i, item in enumerate(todos_to_create):
            if i < len(new_ids):
                anchor_to_db_id[item['anchor_id']] = new_ids[i]

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

    # 11.5 更新已存在任务的 parent_id
    if existing_parent_info:
        parent_updates_existing = []
        for info in existing_parent_info:
            new_parent_id = None
            if info['parent_anchor']:
                new_parent_id = anchor_to_db_id.get(info['parent_anchor'])
            if new_parent_id != info['old_parent_id']:
                parent_updates_existing.append({
                    'id': info['id'],
                    'parent_id': new_parent_id,
                })
        if parent_updates_existing:
            todo_provider.batch_update_todos(parent_updates_existing)
            logger.info(f"更新 {len(parent_updates_existing)} 个任务的 parent_id")

    # 12. 处理删除
    if confirm_delete and todos_to_delete:
        delete_ids = [todo['id'] for todo in todos_to_delete]
        for todo_id in delete_ids:
            deleted_count = todo_provider.delete_todo_cascade(todo_id)
            result.deleted += deleted_count if deleted_count > 0 else 1
        logger.info(f"删除 {result.deleted} 个任务")

    # 13. 更新系统展示区并保存 MD
    content = _update_system_section(content, plan_doc_id)
    _write_plan_doc_content(plan_doc_id, content)

    # 14. 统计总数
    result.total = len(todo_provider.get_todos_by_plan_doc(plan_doc_id))

    logger.info(f"同步计划书 {plan_doc_id} 完成: created={result.created}, updated={result.updated}, deleted={result.deleted}")
    return result


# ============================================================================
# 状态回写
# ============================================================================

def writeback_completion_to_md(plan_doc_id: str, anchor_id: str) -> bool:
    """
    将完成状态回写到 MD 文件

    将 - [ ] xxx <!-- lp:t-xxx --> 改为 - [x] xxx <!-- lp:t-xxx -->
    """
    content = _read_plan_doc_content(plan_doc_id)
    if not content:
        logger.warning(f"回写失败：MD 文件不存在 {plan_doc_id}")
        return False

    anchor_pattern = re.compile(
        rf'^(\t*)-\s*\[\s*\]\s*(.+?)\s*<!--\s*lp:{re.escape(anchor_id)}\s*-->',
        re.MULTILINE
    )

    match = anchor_pattern.search(content)
    if not match:
        logger.warning(f"回写失败：未找到锚点 {anchor_id}")
        return False

    tabs = match.group(1)
    task_content = match.group(2)
    old_line = match.group(0)
    new_line = f"{tabs}- [x] {task_content} <!-- lp:{anchor_id} -->"

    content = content.replace(old_line, new_line, 1)
    content = _update_system_section(content, plan_doc_id)

    if _write_plan_doc_content(plan_doc_id, content):
        logger.info(f"回写完成状态成功: {plan_doc_id}/{anchor_id}")
        return True

    return False


def writeback_uncomplete_to_md(plan_doc_id: str, anchor_id: str) -> bool:
    """
    将取消完成状态回写到 MD 文件

    将 - [x] xxx <!-- lp:t-xxx --> 改为 - [ ] xxx <!-- lp:t-xxx -->
    """
    content = _read_plan_doc_content(plan_doc_id)
    if not content:
        logger.warning(f"回写失败：MD 文件不存在 {plan_doc_id}")
        return False

    anchor_pattern = re.compile(
        rf'^(\t*)-\s*\[x\]\s*(.+?)\s*<!--\s*lp:{re.escape(anchor_id)}\s*-->',
        re.MULTILINE | re.IGNORECASE
    )

    match = anchor_pattern.search(content)
    if not match:
        logger.warning(f"回写失败：未找到已完成的锚点 {anchor_id}")
        return False

    tabs = match.group(1)
    task_content = match.group(2)
    old_line = match.group(0)
    new_line = f"{tabs}- [ ] {task_content} <!-- lp:{anchor_id} -->"

    content = content.replace(old_line, new_line, 1)
    content = _update_system_section(content, plan_doc_id)

    if _write_plan_doc_content(plan_doc_id, content):
        logger.info(f"回写取消完成状态成功: {plan_doc_id}/{anchor_id}")
        return True

    return False


# ============================================================================
# 系统展示区
# ============================================================================

def _update_system_section(content: str, plan_doc_id: str) -> str:
    """
    更新或添加系统展示区

    NOTE: 功能暂时禁用，直接返回原内容
    """
    return content


def _build_task_tree_for_summary(todos: List[Dict]) -> List[Dict]:
    """构建任务树用于系统展示区"""
    todo_map = {t['id']: {**t, 'children': []} for t in todos}
    roots = []

    for todo in todos:
        todo_with_children = todo_map[todo['id']]
        parent_id = todo.get('parent_id')

        if parent_id and parent_id in todo_map:
            todo_map[parent_id]['children'].append(todo_with_children)
        else:
            roots.append(todo_with_children)

    def sort_key(t):
        return t.get('pool_order_index') or 0

    roots.sort(key=sort_key)
    for todo in todo_map.values():
        todo['children'].sort(key=sort_key)

    return roots


def _render_task_tree(tasks: List[Dict], indent: int) -> List[str]:
    """渲染任务树为 MD 格式（不含锚点）

    使用 4 个空格作为缩进，确保 Markdown 渲染器正确显示层级
    """
    lines = []
    spaces = '    ' * indent

    for task in tasks:
        checkbox = '[x]' if task.get('state') == 'completed' else '[ ]'
        lines.append(f"{spaces}- {checkbox} {task['content']}")

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
