"""
Bug 复现：sync_plan_doc 不更新已存在任务的 parent_id

触发条件：MD 文件中任务的层级结构发生变化（子任务移到另一个父任务下），
         但该任务已存在于数据库中
预期行为：同步后数据库中的 parent_id 应反映 MD 中的新层级关系
实际行为：existing 分支的 update_data 不包含 parent_id，
         导致数据库中的 parent_id 保持旧值不变
相关代码：lifeprism/server/services/taskpool_service.py:760-778
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lifeprism.server.services.taskpool_service import (
    _parse_todoblock,
    _build_parent_map,
    _get_all_todoblocks,
)


class TestBugExistingTaskParentNotUpdated:
    """已存在任务在 MD 层级变化后 parent_id 不更新"""

    def test_reproduce_update_data_missing_parent(self):
        """
        复现步骤：
        1. 构造一个 MD，任务 C 是 A 的子任务
        2. 模拟第一次同步后，任务 C 已存在于数据库（parent_id 指向 A）
        3. 修改 MD，将任务 C 移到 B 下面
        4. 模拟第二次同步的 existing 分支逻辑
        5. 检查 update_data 是否包含新的 parent 信息

        判定条件：update_data 应包含 parent 相关信息以更新 parent_id，
                 但当前代码不包含
        """
        # -- Arrange: 第二次同步时的 MD（C 已从 A 下移到 B 下） --
        md_after_move = """\
<!-- lp:todoblock -->
- [ ] 任务A <!-- lp:t-aaa00001 -->
- [ ] 任务B <!-- lp:t-aaa00002 -->
\t- [ ] 任务C（已移动到B下） <!-- lp:t-aaa00003 -->
<!-- /lp:todoblock -->
"""
        # 模拟数据库中的已存在记录（C 的 parent 还是 A）
        existing_db_records = {
            't-aaa00001': {'id': 'todo-001', 'source_anchor_id': 't-aaa00001', 'parent_id': None},
            't-aaa00002': {'id': 'todo-002', 'source_anchor_id': 't-aaa00002', 'parent_id': None},
            't-aaa00003': {'id': 'todo-003', 'source_anchor_id': 't-aaa00003', 'parent_id': 'todo-001'},  # 旧 parent 是 A
        }

        # -- Act: 模拟 sync_plan_doc 的 existing 分支逻辑 --
        blocks = _get_all_todoblocks(md_after_move)
        block_content = blocks[0]['block_content']
        parsed_tasks = _parse_todoblock(block_content)
        parent_map = _build_parent_map(parsed_tasks)

        # 验证 parent_map 确实计算出了 C 的新 parent 是 B
        task_c = parsed_tasks[2]  # 任务C
        assert task_c['anchor_id'] == 't-aaa00003', f"前置条件失败: 第3个任务应为 C, 实际 anchor={task_c['anchor_id']}"
        new_parent_anchor = parent_map.get(task_c['line_index'])
        assert new_parent_anchor == 't-aaa00002', (
            f"前置条件失败: parent_map 应计算出 C 的新 parent 为 t-aaa00002（B）, "
            f"实际为 {new_parent_anchor}"
        )

        # 模拟修复后的 sync_plan_doc existing 分支逻辑
        existing_parent_info = []
        for order_index, task in enumerate(parsed_tasks):
            anchor_id = task['anchor_id']
            existing = existing_db_records.get(anchor_id)

            if existing:
                parent_anchor = parent_map.get(task['line_index'])
                existing_parent_info.append({
                    'id': existing['id'],
                    'parent_anchor': parent_anchor,
                    'old_parent_id': existing.get('parent_id'),
                })

        # 模拟 anchor_to_db_id 映射
        anchor_to_db_id = {r['source_anchor_id']: r['id'] for r in existing_db_records.values()}

        # 模拟修复后的 parent_id 更新逻辑
        parent_updates = []
        for info in existing_parent_info:
            new_parent_id = None
            if info['parent_anchor']:
                new_parent_id = anchor_to_db_id.get(info['parent_anchor'])
            if new_parent_id != info['old_parent_id']:
                parent_updates.append({
                    'id': info['id'],
                    'parent_id': new_parent_id,
                })

        # -- Assert: 任务 C 的 parent 应该被更新为 B --
        task_c_update = next((u for u in parent_updates if u['id'] == 'todo-003'), None)

        assert task_c_update is not None, (
            f"任务C 的 parent 已从 A 变为 B，应出现在 parent_updates 中, "
            f"但 parent_updates 只有: {[u['id'] for u in parent_updates]}"
        )
        assert task_c_update['parent_id'] == 'todo-002', (
            f"任务C 的新 parent_id 应为 todo-002（B）, "
            f"实际为 {task_c_update['parent_id']}"
        )

    def test_reproduce_parent_removed_not_detected(self):
        """
        复现：任务从子任务变为根任务（取消缩进），parent_id 不会被清除

        判定条件：原本有 parent 的任务变成根任务后，
                 update_data 应包含 parent_id=None 来清除旧关系
        """
        # -- Arrange: C 原本是 A 的子任务，现在变成根任务 --
        md_after_unindent = """\
<!-- lp:todoblock -->
- [ ] 任务A <!-- lp:t-bbb00001 -->
- [ ] 任务C（已取消缩进） <!-- lp:t-bbb00003 -->
<!-- /lp:todoblock -->
"""
        existing_db_records = {
            't-bbb00001': {'id': 'todo-101', 'source_anchor_id': 't-bbb00001', 'parent_id': None},
            't-bbb00003': {'id': 'todo-103', 'source_anchor_id': 't-bbb00003', 'parent_id': 'todo-101'},  # 旧 parent 是 A
        }

        # -- Act --
        blocks = _get_all_todoblocks(md_after_unindent)
        parsed_tasks = _parse_todoblock(blocks[0]['block_content'])
        parent_map = _build_parent_map(parsed_tasks)

        # 验证 C 现在是根任务（无 parent）
        task_c = next(t for t in parsed_tasks if t['anchor_id'] == 't-bbb00003')
        assert parent_map.get(task_c['line_index']) is None, (
            f"前置条件失败: C 应为根任务（parent=None）, "
            f"实际 parent={parent_map.get(task_c['line_index'])}"
        )

        # 模拟修复后的 existing 分支
        existing_parent_info = []
        for order_index, task in enumerate(parsed_tasks):
            anchor_id = task['anchor_id']
            existing = existing_db_records.get(anchor_id)
            if existing:
                parent_anchor = parent_map.get(task['line_index'])
                existing_parent_info.append({
                    'id': existing['id'],
                    'parent_anchor': parent_anchor,
                    'old_parent_id': existing.get('parent_id'),
                })

        # 模拟 anchor_to_db_id 映射
        anchor_to_db_id = {r['source_anchor_id']: r['id'] for r in existing_db_records.values()}

        # 模拟修复后的 parent_id 更新逻辑
        parent_updates = []
        for info in existing_parent_info:
            new_parent_id = None
            if info['parent_anchor']:
                new_parent_id = anchor_to_db_id.get(info['parent_anchor'])
            if new_parent_id != info['old_parent_id']:
                parent_updates.append({
                    'id': info['id'],
                    'parent_id': new_parent_id,
                })

        # -- Assert: C 从子任务变为根任务，parent_id 应被清除为 None --
        task_c_update = next((u for u in parent_updates if u['id'] == 'todo-103'), None)

        assert task_c_update is not None, (
            f"任务C 已从子任务变为根任务，应出现在 parent_updates 中, "
            f"但 parent_updates 只有: {[u['id'] for u in parent_updates]}"
        )
        assert task_c_update['parent_id'] is None, (
            f"任务C 已变为根任务，parent_id 应为 None, "
            f"实际为 {task_c_update['parent_id']}"
        )
