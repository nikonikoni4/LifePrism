"""
Bug 复现：多 todoblock 时 parent_map 的 line_index key 冲突导致父任务错误分配

触发条件：一个 PlanDoc 中有多个 todoblock（如"心情"和"日记"各一个），
         且不同 block 中的任务在 block 内的行号相同
预期行为：每个 block 内的父子关系独立，block A 的子任务不会指向 block B 的父任务
实际行为：后面 block 的 parent_map.update() 覆盖前面 block 的条目，
         导致前面 block 的子任务拿到后面 block 的父任务 anchor
相关代码：lifeprism/server/services/taskpool_service.py:729-735
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


class TestBugParentMapCrossBlock:
    """多 todoblock 场景下 parent_map line_index 冲突导致父任务错误"""

    # 模拟一个包含两个 todoblock 的 MD 文件
    # block 0: "心情" 区域（anchor 用 aa 前缀）
    # block 1: "日记" 区域（anchor 用 bb 前缀）
    # 注意：anchor ID 必须匹配正则 t-[a-f0-9]+
    MD_CONTENT = """\
## 心情

<!-- lp:todoblock -->
- [ ] 心情父任务 <!-- lp:t-aa000001 -->
\t- [ ] 心情子任务A <!-- lp:t-aa000002 -->
\t- [ ] 心情子任务B <!-- lp:t-aa000003 -->
<!-- /lp:todoblock -->

## 日记

<!-- lp:todoblock -->
- [ ] 日记父任务 <!-- lp:t-bb000001 -->
\t- [ ] 日记子任务A <!-- lp:t-bb000002 -->
\t- [ ] 日记子任务B <!-- lp:t-bb000003 -->
<!-- /lp:todoblock -->
"""

    def test_reproduce_parent_map_key_collision(self):
        """
        复现步骤：
        1. 解析两个 todoblock，各自得到 tasks（line_index 从 0 开始）
        2. 对每个 block 调用 _build_parent_map，得到 Dict[line_index -> parent_anchor]
        3. 用 parent_map.update() 合并（当前 sync_plan_doc 的做法）
        4. 检查 block 0 中子任务的 parent_anchor 是否正确

        判定条件：block 0 的子任务 parent 应该是 t-mood-parent，
                 而不是被 block 1 覆盖后的 t-diary-parent
        """
        # -- Arrange: 解析两个 block --
        blocks = _get_all_todoblocks(self.MD_CONTENT)
        assert len(blocks) == 2, f"前置条件失败: 期望 2 个 block, 实际 {len(blocks)}"

        block0_tasks = _parse_todoblock(blocks[0]['block_content'])
        block1_tasks = _parse_todoblock(blocks[1]['block_content'])

        assert len(block0_tasks) == 3, f"前置条件失败: block0 期望 3 个任务, 实际 {len(block0_tasks)}"
        assert len(block1_tasks) == 3, f"前置条件失败: block1 期望 3 个任务, 实际 {len(block1_tasks)}"

        # 验证两个 block 的任务确实有相同的 line_index
        block0_line_indices = {t['line_index'] for t in block0_tasks}
        block1_line_indices = {t['line_index'] for t in block1_tasks}
        assert block0_line_indices & block1_line_indices, (
            f"前置条件失败: 两个 block 的 line_index 应有重叠, "
            f"block0={block0_line_indices}, block1={block1_line_indices}"
        )

        # -- Act: 使用复合键 (block_index, line_index) 构建 parent_map --
        parent_map = {}
        for block_idx, block in enumerate(blocks):
            block_tasks = _parse_todoblock(block['block_content'])
            block_parent_map = _build_parent_map(block_tasks)
            for line_index, parent_anchor in block_parent_map.items():
                parent_map[(block_idx, line_index)] = parent_anchor

        # -- Assert: block 0 的子任务 parent 应该是心情父任务 --
        mood_child_a = block0_tasks[1]  # 心情子任务A
        mood_child_b = block0_tasks[2]  # 心情子任务B

        actual_parent_a = parent_map.get((0, mood_child_a['line_index']))
        actual_parent_b = parent_map.get((0, mood_child_b['line_index']))

        assert actual_parent_a == "t-aa000001", (
            f"心情子任务A 的 parent 应为 t-aa000001（心情父任务）, "
            f"实际为 {actual_parent_a}（被日记 block 覆盖）"
        )
        assert actual_parent_b == "t-aa000001", (
            f"心情子任务B 的 parent 应为 t-aa000001（心情父任务）, "
            f"实际为 {actual_parent_b}（被日记 block 覆盖）"
        )

        # 同时验证 block 1 的子任务 parent 也正确
        diary_child_a = block1_tasks[1]
        actual_diary_parent = parent_map.get((1, diary_child_a['line_index']))
        assert actual_diary_parent == "t-bb000001", (
            f"日记子任务A 的 parent 应为 t-bb000001（日记父任务）, "
            f"实际为 {actual_diary_parent}"
        )

    def test_reproduce_root_task_also_affected(self):
        """
        复现：根任务（level=0）的 parent 也可能被覆盖

        block 0 的根任务 parent 应为 None，
        但如果 block 1 的同 line_index 任务有 parent，就会被覆盖
        """
        # -- Arrange --
        # 两个 block 结构相同（根+子），line_index 会冲突
        md2 = """\
<!-- lp:todoblock -->
- [ ] A根 <!-- lp:t-cc000001 -->
\t- [ ] A子 <!-- lp:t-cc000002 -->
<!-- /lp:todoblock -->

<!-- lp:todoblock -->
- [ ] B根 <!-- lp:t-dd000001 -->
\t- [ ] B子 <!-- lp:t-dd000002 -->
<!-- /lp:todoblock -->
"""
        blocks = _get_all_todoblocks(md2)
        assert len(blocks) == 2, f"前置条件失败: 期望 2 个 block, 实际 {len(blocks)}"

        block0_tasks = _parse_todoblock(blocks[0]['block_content'])
        block1_tasks = _parse_todoblock(blocks[1]['block_content'])

        # -- Act --
        parent_map = {}
        for block_idx, block in enumerate(blocks):
            block_tasks = _parse_todoblock(block['block_content'])
            block_parent_map = _build_parent_map(block_tasks)
            for line_index, parent_anchor in block_parent_map.items():
                parent_map[(block_idx, line_index)] = parent_anchor

        # -- Assert --
        # block 0 的 A子 的 parent 应为 t-cc000001（A根）
        a_child = block0_tasks[1]
        actual_parent = parent_map.get((0, a_child['line_index']))

        assert actual_parent == "t-cc000001", (
            f"A子 的 parent 应为 t-cc000001（A根）, "
            f"实际为 {actual_parent}（被 block 1 覆盖）"
        )
