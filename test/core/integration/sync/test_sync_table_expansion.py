"""
同步表范围扩展测试（Issue #13）

测试 seam:
- Seam 1: SYNC_TABLES 常量 - 验证 31 张静态表完整性

注：get_all_sync_tables() 已删除（见 ADR 2026-07-16-dynamic-tables-sync-definition-comparison.md），
动态表列表由 _sync_dynamic_tables_definitions 产出，相关测试在 test_sync_client.py 中。

参考: test/core/integration/sync/test_sync_client.py
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 31 张静态表期望清单 ====================

EXPECTED_STATIC_TABLES = [
    # 用户输入数据（15张）
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
    "habit_chains",
    "habit_chain_nodes",
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
    # 微信账户状态（1张）- 替代 channel/wechat/account.json 文件存储（Issue 35）
    "wechat_account_state",
]


# ==================== Seam 1: SYNC_TABLES 常量 ====================


class TestSyncTablesStatic:
    """Seam 1: SYNC_TABLES 常量 - 验证 31 张静态表完整性"""

    def test_sync_tables_contains_all_31_static_tables(self):
        """验证 SYNC_TABLES 包含所有 31 张静态表"""
        # Arrange: 从模块导入 SYNC_TABLES
        from lifeprism.sync.sync_client import SYNC_TABLES

        # Act: 检查每张期望表是否在 SYNC_TABLES 中

        # Assert: 所有 31 张期望表都在 SYNC_TABLES 中
        for table in EXPECTED_STATIC_TABLES:
            assert table in SYNC_TABLES, f"静态表 {table} 不在 SYNC_TABLES 中"

        # Assert: SYNC_TABLES 恰好包含 31 张表
        assert len(SYNC_TABLES) == 31, f"SYNC_TABLES 应包含 31 张表，实际 {len(SYNC_TABLES)} 张"
