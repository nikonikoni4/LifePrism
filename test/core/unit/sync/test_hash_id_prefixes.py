"""HASH_ID_PREFIXES 字典单元测试

测试 seam: lifeprism.sync.constants.HASH_ID_PREFIXES 字典结构

该字典同时作为"哪些表需要 hash_id"的判断依据（后续 _generic_insert 用
HASH_ID_PREFIXES.get(self._TABLE_NAME) 判断）。

参考:
- Issue: .scratch/deletion-sync-01-schema/issues/01-hash-id-schema-foundation.md
- PRD: .scratch/deletion-sync-01-schema/prd.md
- ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md（hash_id 定位为同步专用标识）
"""

import pytest

pytestmark = pytest.mark.core


# 6 张目标表 + 前缀的独立真值表（来自 Issue 验收标准）
EXPECTED_PREFIXES = {
    "timeline_custom_block": "tcb-",
    "time_paradoxes": "tp-",
    "mood_impacts": "mi-",
    "habit_chains": "hc-",
    "habit_chain_nodes": "hcn-",
    "user_app_behavior_log": "awbl-",
}


class TestHashIdPrefixes:
    """HASH_ID_PREFIXES 字典包含 6 张目标表及其前缀映射"""

    def test_dict_exists_in_constants_module(self):
        """lifeprism.sync.constants 模块导出 HASH_ID_PREFIXES 属性"""
        from lifeprism.sync import constants as constants_module

        assert hasattr(constants_module, "HASH_ID_PREFIXES"), (
            "constants 模块应导出 HASH_ID_PREFIXES"
        )

    def test_dict_is_dict_type(self):
        """HASH_ID_PREFIXES 应为 dict 类型"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        assert isinstance(HASH_ID_PREFIXES, dict), (
            "HASH_ID_PREFIXES 应为 dict，实际为 "
            f"{type(HASH_ID_PREFIXES).__name__}"
        )

    def test_dict_contains_exactly_six_tables(self):
        """HASH_ID_PREFIXES 恰好包含 6 张表"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        assert len(HASH_ID_PREFIXES) == 6, (
            f"HASH_ID_PREFIXES 应有 6 个条目，实际 {len(HASH_ID_PREFIXES)}: "
            f"{sorted(HASH_ID_PREFIXES.keys())}"
        )

    def test_dict_keys_match_expected_six_tables(self):
        """HASH_ID_PREFIXES 的 keys 与预期 6 张表完全一致"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        assert set(HASH_ID_PREFIXES.keys()) == set(EXPECTED_PREFIXES.keys()), (
            f"keys 不匹配: 期望 {sorted(EXPECTED_PREFIXES.keys())}, "
            f"实际 {sorted(HASH_ID_PREFIXES.keys())}"
        )

    @pytest.mark.parametrize(
        "table_name,expected_prefix",
        list(EXPECTED_PREFIXES.items()),
    )
    def test_each_table_has_correct_prefix(self, table_name, expected_prefix):
        """每张表对应的前缀与 Issue 规定一致（参数化覆盖 6 张表）"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        assert table_name in HASH_ID_PREFIXES, f"缺少表 {table_name}"
        assert HASH_ID_PREFIXES[table_name] == expected_prefix, (
            f"{table_name} 的前缀应为 {expected_prefix!r}, "
            f"实际 {HASH_ID_PREFIXES[table_name]!r}"
        )

    def test_all_prefixes_are_non_empty_strings(self):
        """所有前缀均为非空字符串"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        for table, prefix in HASH_ID_PREFIXES.items():
            assert isinstance(prefix, str), (
                f"{table} 前缀应为 str，实际 {type(prefix).__name__}"
            )
            assert len(prefix) > 0, f"{table} 前缀不应为空字符串"

    def test_all_prefixes_end_with_dash(self):
        """所有前缀以 '-' 结尾（与 hash_id 格式 <prefix><hex> 一致）"""
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        for table, prefix in HASH_ID_PREFIXES.items():
            assert prefix.endswith("-"), (
                f"{table} 前缀 {prefix!r} 应以 '-' 结尾"
            )
