"""
任务池服务层 - Task Pool V2 业务逻辑

核心功能：
1. 获取任务池任务（支持筛选）
2. 同步计划书任务（MD 解析 + 数据库同步）
3. 更新任务（含 MD 回写）
4. 重新生成系统展示区

MD 解析规则：
- 任务块：<!-- lp:todoblock --> 和 <!-- /lp:todoblock --> 之间
- 支持多个 todoblock，每个 block 独立解析
- 锚点格式：<!-- lp:t-xxx -->
- 缩进规则：Tab 缩进判断父子关系（仅在同一 block 内有效）
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
    TodoDeletePreview,
)
from lifeprism.server.providers.todo_provider import todo_provider
from lifeprism.server.providers.plan_doc_provider import plan_doc_provider
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def _get_plan_doc_dir() -> Path:
    """获取计划书目录路径（与 plan_doc_service.py 保持一致）"""
    from lifeprism.config.settings_manager import settings
    return Path(settings.lifeprism_data_path) / "plan"


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
        waid_order=db_item.get('waid_order'),
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


def _ensure_todoblock_exists(content: str) -> str:
    """
    确保 MD 内容中存在 todoblock 标记

    如果不存在，在文档末尾（系统展示区之前）添加 todoblock。

    Args:
        content: MD 文件内容

    Returns:
        str: 更新后的内容
    """
    # 检查是否已存在 todoblock
    if TODOBLOCK_PATTERN.search(content):
        return content

    # 构建 todoblock
    todoblock = "\n\n## 任务列表\n<!-- lp:todoblock -->\n\n<!-- /lp:todoblock -->\n"

    # 查找系统展示区位置
    system_start = content.find(SYSTEM_SECTION_START)
    if system_start != -1:
        # 在系统展示区之前插入
        separator_pos = content.rfind('---', 0, system_start)
        if separator_pos != -1:
            content = content[:separator_pos].rstrip() + todoblock + content[separator_pos:]
        else:
            content = content[:system_start].rstrip() + todoblock + content[system_start:]
    else:
        # 在文档末尾添加
        content = content.rstrip() + todoblock

    return content

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

    Args:
        content: MD 文件内容
        anchor_id: 锚点 ID

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
# 数据完整性校验
# ============================================================================

def validate_todo_integrity(todo: Dict[str, Any]) -> List[str]:
    """
    校验 todo 数据完整性，返回问题列表

    Args:
        todo: 任务数据

    Returns:
        List[str]: 问题描述列表，空列表表示无问题
    """
    issues = []

    plan_doc_id = todo.get('plan_doc_id')
    anchor_id = todo.get('source_anchor_id')
    parent_id = todo.get('parent_id')

    # 检查 plan_doc_id 存在性
    if plan_doc_id:
        plan_doc = plan_doc_provider.get_plan_doc_by_id(plan_doc_id)
        if not plan_doc:
            issues.append(f"关联的计划书不存在: {plan_doc_id}")

        # 检查 anchor_id 存在性（仅当有 plan_doc_id 时）
        if anchor_id:
            content = _read_plan_doc_content(plan_doc_id)
            if content and f"lp:{anchor_id}" not in content:
                issues.append(f"锚点在 MD 文件中不存在: {anchor_id}")

    # 检查 parent_id 存在性
    if parent_id:
        parent = todo_provider.get_todo_by_id(parent_id)
        if not parent:
            issues.append(f"父任务不存在: {parent_id}")

    return issues


def safe_update_todo_to_md(todo: Dict[str, Any], updates: Dict[str, Any]) -> bool:
    """
    安全地更新 todo 到 MD，处理各种边界情况

    Args:
        todo: 原任务数据
        updates: 更新数据

    Returns:
        bool: 是否成功更新 MD（跳过也返回 True）
    """
    plan_doc_id = todo.get('plan_doc_id')
    anchor_id = todo.get('source_anchor_id')

    # 无计划书关联，跳过
    if not plan_doc_id:
        return True

    # 无锚点，跳过
    if not anchor_id:
        logger.warning(f"任务 {todo.get('id')} 无锚点，跳过 MD 更新")
        return True

    # 检查计划书是否存在
    plan_doc = plan_doc_provider.get_plan_doc_by_id(plan_doc_id)
    if not plan_doc:
        logger.warning(f"计划书 {plan_doc_id} 不存在，清除任务关联")
        # 清除关联
        todo_provider.update_todo(todo['id'], {
            'plan_doc_id': None,
            'source_anchor_id': None
        })
        return True

    # 检查 MD 文件是否存在
    content = _read_plan_doc_content(plan_doc_id)
    if content is None:
        logger.warning(f"MD 文件不存在: {plan_doc_id}，跳过 MD 更新")
        return True

    # 检查锚点是否存在
    if f"lp:{anchor_id}" not in content:
        logger.warning(f"锚点 {anchor_id} 在 MD 中不存在，跳过 MD 更新")
        return True

    # 执行更新
    try:
        if 'content' in updates:
            _update_todo_in_md(plan_doc_id, anchor_id, updates['content'])
        return True
    except Exception as e:
        logger.error(f"更新 MD 失败: {e}")
        return False


# ============================================================================
# MD 回写操作
# ============================================================================

def _insert_todo_to_md(
    plan_doc_id: str,
    content: str,
    parent_anchor_id: Optional[str] = None
) -> Optional[str]:
    """
    插入新任务到 MD 文件（支持多个 todoblock）

    插入策略：
    - 如果有 parent_anchor_id，插入到父任务所在的 block
    - 如果没有 parent_anchor_id，插入到第一个 todoblock

    Args:
        plan_doc_id: 计划书 ID
        content: 任务内容
        parent_anchor_id: 父任务锚点 ID（可选，用于确定插入位置）

    Returns:
        Optional[str]: 新生成的锚点 ID，失败返回 None
    """
    md_content = _read_plan_doc_content(plan_doc_id)
    if md_content is None:
        logger.warning(f"插入失败：MD 文件不存在 {plan_doc_id}")
        return None

    # 获取所有 todoblock
    blocks = _get_all_todoblocks(md_content)
    if not blocks:
        logger.warning(f"插入失败：无 todoblock {plan_doc_id}")
        return None

    # 确定目标 block
    target_block_index = 0  # 默认第一个 block
    if parent_anchor_id:
        found_index = _find_anchor_in_blocks(md_content, parent_anchor_id)
        if found_index is not None:
            target_block_index = found_index

    target_block = blocks[target_block_index]
    block_content = target_block['block_content']
    block_start = target_block['start']
    block_end = target_block['end']

    # 生成新锚点
    new_anchor = _generate_anchor_id()

    # 确定缩进级别和插入位置
    indent_level = 0
    insert_position = len(block_content)  # 默认插入到末尾

    if parent_anchor_id:
        # 查找父任务行，确定缩进级别
        lines = block_content.split('\n')
        for i, line in enumerate(lines):
            if f"lp:{parent_anchor_id}" in line:
                # 计算父任务的缩进级别
                parent_indent = len(line) - len(line.lstrip('\t'))
                indent_level = parent_indent + 1

                # 找到父任务的最后一个子任务位置
                insert_line_index = i + 1
                while insert_line_index < len(lines):
                    next_line = lines[insert_line_index]
                    if next_line.strip() and next_line.startswith('\t' * (parent_indent + 1)):
                        insert_line_index += 1
                    else:
                        break

                # 计算字符位置
                insert_position = sum(len(lines[j]) + 1 for j in range(insert_line_index))
                break

    # 构建新行
    tabs = '\t' * indent_level
    new_line = f"{tabs}- [ ] {content} <!-- lp:{new_anchor} -->\n"

    # 插入新行
    new_block_content = block_content[:insert_position] + new_line + block_content[insert_position:]
    new_md_content = md_content[:block_start] + new_block_content + md_content[block_end:]

    # 更新系统展示区并保存
    new_md_content = _update_system_section(new_md_content, plan_doc_id)
    if _write_plan_doc_content(plan_doc_id, new_md_content):
        logger.info(f"插入任务到 MD 成功: {plan_doc_id}/{new_anchor} (block {target_block_index})")
        return new_anchor

    return None


def _update_todo_in_md(plan_doc_id: str, anchor_id: str, new_content: str) -> bool:
    """
    更新 MD 中的任务内容

    Args:
        plan_doc_id: 计划书 ID
        anchor_id: 锚点 ID
        new_content: 新任务内容

    Returns:
        bool: 是否成功
    """
    md_content = _read_plan_doc_content(plan_doc_id)
    if md_content is None:
        logger.warning(f"更新失败：MD 文件不存在 {plan_doc_id}")
        return False

    # 查找锚点所在行并替换内容
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

    # 更新系统展示区并保存
    new_md_content = _update_system_section(new_md_content, plan_doc_id)
    if _write_plan_doc_content(plan_doc_id, new_md_content):
        logger.info(f"更新任务内容成功: {plan_doc_id}/{anchor_id}")
        return True

    return False


def _delete_todo_from_md(plan_doc_id: str, anchor_id: str) -> bool:
    """
    从 MD 删除任务（含子任务，支持多个 todoblock）

    Args:
        plan_doc_id: 计划书 ID
        anchor_id: 锚点 ID

    Returns:
        bool: 是否成功
    """
    md_content = _read_plan_doc_content(plan_doc_id)
    if md_content is None:
        logger.warning(f"删除失败：MD 文件不存在 {plan_doc_id}")
        return False

    # 获取所有 todoblock
    blocks = _get_all_todoblocks(md_content)
    if not blocks:
        logger.warning(f"删除失败：无 todoblock {plan_doc_id}")
        return False

    # 查找锚点所在的 block
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
    skip_until_indent = -1  # 跳过子任务的缩进级别阈值

    for line in lines:
        # 检查是否是目标锚点行
        if f"lp:{anchor_id}" in line:
            # 计算当前行的缩进级别
            current_indent = len(line) - len(line.lstrip('\t'))
            skip_until_indent = current_indent
            continue  # 跳过此行

        # 检查是否需要跳过子任务
        if skip_until_indent >= 0:
            if line.strip():  # 非空行
                current_indent = len(line) - len(line.lstrip('\t'))
                if current_indent > skip_until_indent:
                    continue  # 跳过子任务
                else:
                    skip_until_indent = -1  # 结束跳过
            else:
                # 空行：在删除模式下也跳过，避免留下孤立空行
                continue

        new_lines.append(line)

    # 清理连续的多余空行（保留最多一个空行）
    cleaned_lines = []
    prev_empty = False
    for line in new_lines:
        is_empty = not line.strip()
        if is_empty and prev_empty:
            continue  # 跳过连续空行
        cleaned_lines.append(line)
        prev_empty = is_empty

    new_block_content = '\n'.join(cleaned_lines)
    new_md_content = md_content[:block_start] + new_block_content + md_content[block_end:]

    # 更新系统展示区并保存
    new_md_content = _update_system_section(new_md_content, plan_doc_id)
    if _write_plan_doc_content(plan_doc_id, new_md_content):
        logger.info(f"从 MD 删除任务成功: {plan_doc_id}/{anchor_id} (block {target_block_index})")
        return True

    return False


# ============================================================================
# 同步逻辑
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

    Args:
        plan_doc_id: 计划书 ID
        dry_run: 预检模式，只返回差异不执行操作
        confirm_delete: 确认删除，True=删除全部待删除任务

    Returns:
        SyncPlanDocResponse: 同步结果统计
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
        # 自动创建 todoblock
        content = _ensure_todoblock_exists(content)
        _write_plan_doc_content(plan_doc_id, content)
        # 重新获取 todoblock
        blocks = _get_all_todoblocks(content)
        if not blocks:
            logger.error(f"创建 todoblock 失败: {plan_doc_id}")
            return result

    # 4. 解析所有 block 中的任务，并记录需要修改的内容
    all_parsed_tasks = []  # 所有任务（带 block_index）
    block_modifications = {}  # block_index -> {line_index -> new_line}

    for block in blocks:
        block_content = block['block_content']
        block_index = block['block_index']

        parsed_tasks = _parse_todoblock(block_content)

        # 为无锚点的任务生成锚点
        modifications = {}
        for task in parsed_tasks:
            # 添加 block_index 标记
            task['block_index'] = block_index

            if not task['anchor_id']:
                new_anchor = _generate_anchor_id()
                task['anchor_id'] = new_anchor

                # 构建新行（在内容后添加锚点）
                tabs = '\t' * task['indent_level']
                checkbox = '[x]' if task['is_checked'] else '[ ]'
                new_line = f"{tabs}- {checkbox} {task['content']} <!-- lp:{new_anchor} -->"
                modifications[task['line_index']] = new_line

        if modifications:
            block_modifications[block_index] = modifications

        all_parsed_tasks.extend(parsed_tasks)

    # 5. 如果有修改，更新 MD 内容（从后往前更新，避免位置偏移）
    if block_modifications:
        # 按 block_index 倒序处理
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

        # 重新获取 blocks（位置已变化）
        blocks = _get_all_todoblocks(content)

    # 6. 构建父任务映射（每个 block 独立构建，然后合并）
    # 注意：父子关系只在同一个 block 内有效
    parent_map = {}
    for block in blocks:
        block_tasks = [t for t in all_parsed_tasks if t.get('block_index') == block['block_index']]
        block_parent_map = _build_parent_map(block_tasks)
        parent_map.update(block_parent_map)

    # 7. 获取现有任务（用于匹配和删除检测）
    existing_todos = todo_provider.get_todos_by_plan_doc(plan_doc_id)
    existing_by_anchor = {t['source_anchor_id']: t for t in existing_todos if t.get('source_anchor_id')}

    # 收集所有 block 中存在的锚点
    md_anchor_ids = {task['anchor_id'] for task in all_parsed_tasks if task['anchor_id']}

    # 8. 检测待删除的任务（数据库中有但 MD 中没有的）
    todos_to_delete = []
    for todo in existing_todos:
        anchor_id = todo.get('source_anchor_id')
        if anchor_id and anchor_id not in md_anchor_ids:
            todos_to_delete.append(todo)

    # 9. 处理每个解析出的任务（使用全局 order_index）
    anchor_to_db_id = {}  # anchor_id -> db_id 映射（用于设置 parent_id）
    todos_to_create = []
    todos_to_update = []

    for order_index, task in enumerate(all_parsed_tasks):
        anchor_id = task['anchor_id']
        existing = existing_by_anchor.get(anchor_id)

        if existing:
            # 更新现有任务
            update_data = {
                'id': existing['id'],
                'content': task['content'],
                'pool_order_index': order_index,
            }

            # 状态同步：[x] -> completed，[ ] + completed -> pool
            if task['is_checked'] and existing.get('state') != 'completed':
                update_data['state'] = 'completed'
                update_data['actual_finished_at'] = datetime.now().strftime('%Y-%m-%d')
            elif not task['is_checked'] and existing.get('state') == 'completed':
                update_data['state'] = 'pool'
                update_data['actual_finished_at'] = None

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

    # 10. dry_run 模式：只返回差异，不执行操作
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
    # 先批量更新
    if todos_to_update:
        todo_provider.batch_update_todos(todos_to_update)

    # 再批量创建（需要先创建父任务才能设置 parent_id）
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

    # 12. 处理删除
    if confirm_delete and todos_to_delete:
        delete_ids = [todo['id'] for todo in todos_to_delete]
        # 使用级联删除，确保子任务也被删除
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
# 更新任务（含 MD 回写）
# ============================================================================

def update_todo_with_writeback(
    todo_id: int,
    updates: Dict[str, Any]
) -> Optional[UpdateTodoV2Response]:
    """
    更新任务，并在必要时回写 MD 文件

    回写场景：
    1. state 变为 completed 时，将 MD 中的 [ ] 改为 [x]
    2. content 变更时，更新 MD 中的任务内容

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
        # 允许取消完成，清除实际完成时间
        updates['actual_finished_at'] = None

    # 3. 更新数据库
    success = todo_provider.update_todo(todo_id, updates)
    if not success:
        return None

    # 4. 检查是否需要回写 MD
    md_synced = False
    plan_doc_id = existing.get('plan_doc_id')
    anchor_id = existing.get('source_anchor_id')

    if plan_doc_id and anchor_id:
        new_state = updates.get('state')
        new_content = updates.get('content')

        # 4.1 完成状态回写
        if new_state == 'completed' and existing.get('state') != 'completed':
            md_synced = _writeback_completion_to_md(plan_doc_id, anchor_id)

        # 4.2 取消完成状态回写
        if new_state in ['pool', 'scheduled'] and existing.get('state') == 'completed':
            md_synced = _writeback_uncomplete_to_md(plan_doc_id, anchor_id)

        # 4.2 内容变更回写
        if new_content and new_content != existing.get('content'):
            content_synced = _update_todo_in_md(plan_doc_id, anchor_id, new_content)
            md_synced = md_synced or content_synced

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


def _writeback_uncomplete_to_md(plan_doc_id: str, anchor_id: str) -> bool:
    """
    将取消完成状态回写到 MD 文件

    将 - [x] xxx <!-- lp:t-xxx --> 改为 - [ ] xxx <!-- lp:t-xxx -->
    """
    content = _read_plan_doc_content(plan_doc_id)
    if not content:
        logger.warning(f"回写失败：MD 文件不存在 {plan_doc_id}")
        return False

    # 查找锚点所在行（已完成状态）
    anchor_pattern = re.compile(
        rf'^(\t*)-\s*\[x\]\s*(.+?)\s*<!--\s*lp:{re.escape(anchor_id)}\s*-->',
        re.MULTILINE | re.IGNORECASE
    )

    match = anchor_pattern.search(content)
    if not match:
        logger.warning(f"回写失败：未找到已完成的锚点 {anchor_id}")
        return False

    # 替换 [x] 为 [ ]
    tabs = match.group(1)
    task_content = match.group(2)
    old_line = match.group(0)
    new_line = f"{tabs}- [ ] {task_content} <!-- lp:{anchor_id} -->"

    content = content.replace(old_line, new_line, 1)

    # 更新系统展示区
    content = _update_system_section(content, plan_doc_id)

    # 保存
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

    系统展示区格式：
    ---

    ## 任务总览
    <!-- lp:system-section -->
    > 此区域由系统自动生成，手动修改将在下次同步时被覆盖

    - [ ] 任务 1
        - [x] 子任务 1.1
    - [x] 任务 2

    NOTE: 功能暂时禁用，直接返回原内容
    """
    # 暂时禁用任务总览生成功能，直接返回原内容
    return content

    # # 获取该计划书的所有任务
    # todos = todo_provider.get_todos_by_plan_doc(plan_doc_id)
    #
    # if not todos:
    #     # 无任务，移除系统展示区
    #     system_start = content.find(SYSTEM_SECTION_START)
    #     if system_start != -1:
    #         # 查找 --- 分隔线
    #         separator_pos = content.rfind('---', 0, system_start)
    #         if separator_pos != -1:
    #             content = content[:separator_pos].rstrip()
    #     return content
    #
    # # 构建任务树
    # task_tree = _build_task_tree_for_summary(todos)
    #
    # # 生成 MD 内容
    # summary_lines = [
    #     '',
    #     '---',
    #     '',
    #     '## 任务总览',
    #     SYSTEM_SECTION_START,
    #     '> 此区域由系统自动生成，手动修改将在下次同步时被覆盖',
    #     '',
    # ]
    # summary_lines.extend(_render_task_tree(task_tree, 0))
    # summary_content = '\n'.join(summary_lines)
    #
    # # 查找并替换现有系统展示区
    # system_start = content.find(SYSTEM_SECTION_START)
    # if system_start != -1:
    #     # 找到 --- 分隔线位置
    #     separator_pos = content.rfind('---', 0, system_start)
    #     if separator_pos != -1:
    #         content = content[:separator_pos].rstrip() + summary_content
    #     else:
    #         content = content[:system_start].rstrip() + summary_content
    # else:
    #     # 添加新的系统展示区
    #     content = content.rstrip() + summary_content
    #
    # return content


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
    """渲染任务树为 MD 格式（不含锚点）

    使用 4 个空格作为缩进，确保 Markdown 渲染器正确显示层级
    """
    lines = []
    spaces = '    ' * indent  # 使用 4 个空格代替 Tab

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

    支持子任务继承：当创建子任务时，自动继承父任务的 plan_doc_id 和 goal_id，
    并生成 source_anchor_id，同步插入到 MD 文件。

    Args:
        data: 任务数据

    Returns:
        Optional[TaskPoolItem]: 创建的任务，失败返回 None
    """
    # 如果设置了 date 且状态为 pool，自动改为 scheduled
    if data.get('date') and data.get('state', 'pool') == 'pool':
        data['state'] = 'scheduled'

    # 子任务继承逻辑
    parent_id = data.get('parent_id')
    if parent_id:
        parent = todo_provider.get_todo_by_id(parent_id)
        if parent:
            # 继承 plan_doc_id（如果子任务未指定）
            if not data.get('plan_doc_id') and parent.get('plan_doc_id'):
                data['plan_doc_id'] = parent['plan_doc_id']

            # 继承 link_to_goal_id（如果子任务未指定）
            if not data.get('link_to_goal_id') and parent.get('link_to_goal_id'):
                data['link_to_goal_id'] = parent['link_to_goal_id']

    # 如果有 plan_doc_id 但没有 source_anchor_id，需要插入到 MD 并生成锚点
    plan_doc_id = data.get('plan_doc_id')
    if plan_doc_id and not data.get('source_anchor_id'):
        # 获取父任务的锚点（用于确定插入位置）
        parent_anchor_id = None
        if parent_id:
            parent = todo_provider.get_todo_by_id(parent_id)
            if parent:
                parent_anchor_id = parent.get('source_anchor_id')

        # 插入到 MD 并获取新锚点
        new_anchor = _insert_todo_to_md(plan_doc_id, data['content'], parent_anchor_id)
        if new_anchor:
            data['source_anchor_id'] = new_anchor

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
    删除任务（含 MD 回写和级联删除）

    如果任务关联了计划书且有锚点，会同步从 MD 文件中删除。
    同时级联删除所有子任务。

    Args:
        todo_id: 任务 ID

    Returns:
        bool: 是否成功
    """
    # 获取任务信息（用于 MD 回写）
    todo = todo_provider.get_todo_by_id(todo_id)
    if not todo:
        return False

    plan_doc_id = todo.get('plan_doc_id')
    anchor_id = todo.get('source_anchor_id')

    # 从 MD 删除（如果有关联）
    if plan_doc_id and anchor_id:
        _delete_todo_from_md(plan_doc_id, anchor_id)

    # 级联删除数据库记录
    deleted_count = todo_provider.delete_todo_cascade(todo_id)
    return deleted_count > 0
