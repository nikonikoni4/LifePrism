"""
同步表范围扩展测试（Issue #13）

测试 seam:
- Seam 1: SYNC_TABLES 常量 - 验证静态表完整性
  （原 31 张；Issue 06 移除 habit_chains/habit_chain_nodes -2；Issue 05 新增 deletion_log +1；当前 30 张）
- Seam 2: habit 链条表从 SYNC_TABLES 移除（Issue 06）

注：get_all_sync_tables() 已删除（见 ADR 2026-07-16-dynamic-tables-sync-definition-comparison.md），
动态表列表由 _sync_dynamic_tables_definitions 产出，相关测试在 test_sync_client.py 中。

参考: test/core/integration/sync/test_sync_client.py
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 静态表期望清单 ====================
# 注：habit_chains 和 habit_chain_nodes 已从 SYNC_TABLES 移除（Issue 06），
# 因 chain_id 引用自增 id 同步后断裂。详见 docs/known-limitations/habit-chain-tables-not-synced.md
# 注：deletion_log 由 Issue 05 加入 SYNC_TABLES（删除同步墓碑表）

EXPECTED_STATIC_TABLES = [
    # 用户输入数据（13张）
    "mood_entries",
    "diary",
    "todo_list",
    "goal",
    "goal_journal",
    "plan_doc",
    "daily_focus",
    "weekly_focus",
    "habits",
    "habit_challenges",
    "habit_checkins",
    "timeline_custom_block",
    "time_paradoxes",
    # 元数据（8张）
    "category",
    "sub_category",
    "mood_types",
    "mood_impacts",
    "user_values",
    "commitments",
    "custom_record_types",
    "custom_record_fields",
    # Monitor 数据（3张）
    "user_app_behavior_log",
    "behavior_analysis",
    "raw_behavior_analysis",
    # 缓存表（3张）
    "multi_purpose_map_cache",
    "single_purpose_map_cache",
    "category_map_cache",
    # 统计数据（1张）
    "tokens_usage_log",
    # 微信账户状态（1张）- 替代原 channel/wechat/account.json 文件存储（Issue 35）
    "wechat_account_state",
    # 墓碑表（1张）- 删除同步用，记录删除意图跨端传播（Issue 05）
    "deletion_log",
]


# ==================== Seam 1: SYNC_TABLES 常量 ====================


class TestSyncTablesStatic:
    """Seam 1: SYNC_TABLES 常量 - 验证静态表完整性

    注：原 31 张，Issue 06 移除 habit_chains 和 habit_chain_nodes（-2），
    Issue 05 新增 deletion_log（+1），当前 30 张。
    期望清单见 EXPECTED_STATIC_TABLES，count 由清单长度自动派生（抗并行修改）。
    """

    def test_sync_tables_contains_all_expected_static_tables(self):
        """验证 SYNC_TABLES 包含 EXPECTED_STATIC_TABLES 中所有表，且数量一致"""
        # Arrange: 从模块导入 SYNC_TABLES
        from lifeprism.sync.sync_client import SYNC_TABLES

        # Act: 检查每张期望表是否在 SYNC_TABLES 中

        # Assert: 所有期望表都在 SYNC_TABLES 中
        for table in EXPECTED_STATIC_TABLES:
            assert table in SYNC_TABLES, f"静态表 {table} 不在 SYNC_TABLES 中"

        # Assert: SYNC_TABLES 数量与期望清单一致（避免额外表混入）
        assert len(SYNC_TABLES) == len(EXPECTED_STATIC_TABLES), (
            f"SYNC_TABLES 应包含 {len(EXPECTED_STATIC_TABLES)} 张表，"
            f"实际 {len(SYNC_TABLES)} 张"
        )


# ==================== Seam 2: habit 链条表从 SYNC_TABLES 移除（Issue 06） ====================


class TestHabitChainTablesExcludedFromSync:
    """Seam 2: habit_chains 和 habit_chain_nodes 从 SYNC_TABLES 移除

    原因: habit_chain_nodes.chain_id 引用 habit_chains.id（自增 id），
    同步后两端 id 不一致导致外键断裂。临时移除，待 PRD 2 解决 chain_id 改引用 hash_id 后恢复。

    参考:
    - Issue: .scratch/deletion-sync-01-schema/issues/06-habit-tables-sync-removal.md
    - ADR: docs/adr/2026-07-22-habit-chain-tables-not-synced.md
    - 已知限制: docs/known-limitations/habit-chain-tables-not-synced.md
    """

    def test_habit_chains_not_in_sync_tables(self):
        """habit_chains 不在 SYNC_TABLES 中（chain_id 外键引用自增 id，同步后断裂）"""
        from lifeprism.sync.constants import SYNC_TABLES

        assert "habit_chains" not in SYNC_TABLES, (
            "habit_chains 不应在 SYNC_TABLES 中：chain_id 引用自增 id，"
            "同步后两端 id 不一致导致外键断裂。详见 "
            "docs/known-limitations/habit-chain-tables-not-synced.md"
        )

    def test_habit_chain_nodes_not_in_sync_tables(self):
        """habit_chain_nodes 不在 SYNC_TABLES 中（chain_id 外键引用自增 id，同步后断裂）"""
        from lifeprism.sync.constants import SYNC_TABLES

        assert "habit_chain_nodes" not in SYNC_TABLES, (
            "habit_chain_nodes 不应在 SYNC_TABLES 中：chain_id 引用自增 id，"
            "同步后两端 id 不一致导致外键断裂。详见 "
            "docs/known-limitations/habit-chain-tables-not-synced.md"
        )

    def test_habit_chains_still_in_hash_id_prefixes(self):
        """habit_chains 仍在 HASH_ID_PREFIXES 中（hash_id 字段照加，为未来恢复同步做准备）"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        assert "habit_chains" in HASH_ID_PREFIXES, (
            "habit_chains 应仍在 HASH_ID_PREFIXES 中：hash_id 字段照加，"
            "迁移脚本仍回填，为未来恢复同步做准备"
        )

    def test_habit_chain_nodes_still_in_hash_id_prefixes(self):
        """habit_chain_nodes 仍在 HASH_ID_PREFIXES 中（hash_id 字段照加，为未来恢复同步做准备）"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        assert "habit_chain_nodes" in HASH_ID_PREFIXES, (
            "habit_chain_nodes 应仍在 HASH_ID_PREFIXES 中：hash_id 字段照加，"
            "迁移脚本仍回填，为未来恢复同步做准备"
        )
