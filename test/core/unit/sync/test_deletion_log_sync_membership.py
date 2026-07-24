"""deletion_log 在同步常量中的归属关系测试

测试 seam:
- Seam 1: SYNC_TABLES 常量 - 验证 deletion_log 不在 SYNC_TABLES 中（墓碑走专用通道）
- Seam 2: HASH_ID_PREFIXES 字典 - 验证 deletion_log 不在 HASH_ID_PREFIXES 中

PRD 3 验收标准:
- deletion_log 已从 lifeprism/sync/constants.py 的 SYNC_TABLES 移除
- 墓碑仅通过专用通道（_pull_deletion_log / _push_deletion_log / _cleanup_deletion_log）同步
- 避免双重同步和循环引用
- 不将 dl- 前缀加入 HASH_ID_PREFIXES（deletion_log 的 id 是 dl- 前缀的 8 位 hex，
  不是 hash_id；id 生成在 PRD 3 的 DeletionLogProvider 中通过
  _generic_insert(id_prefix='dl-') 实现）

参考:
- PRD: .scratch/deletion-sync-03-tombstone/prd.md
- ADR: docs/adr/2026-07-22-deletion-log-table.md
- 相关 ADR: docs/adr/2026-07-22-deletion-sync-tombstone.md（待写）
- 相关 ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md
"""

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: deletion_log 不在 SYNC_TABLES 中 ====================


class TestDeletionLogNotInSyncTables:
    """Seam 1: SYNC_TABLES 常量不应包含 deletion_log

    deletion_log 已从 SYNC_TABLES 移除，墓碑仅通过专用通道
    （_pull_deletion_log / _push_deletion_log / _cleanup_deletion_log）同步，
    避免双重同步和循环引用。
    """

    def test_deletion_log_not_in_sync_tables_constant(self):
        """lifeprism.sync.constants.SYNC_TABLES 不应包含 'deletion_log'"""
        from lifeprism.sync.constants import SYNC_TABLES

        assert "deletion_log" not in SYNC_TABLES, (
            f"SYNC_TABLES 不应包含 'deletion_log'（墓碑走专用通道），当前列表: {SYNC_TABLES}"
        )

    def test_deletion_log_not_in_sync_tables_via_sync_client_reexport(self):
        """lifeprism.sync.sync_client.SYNC_TABLES（向后兼容重导出）不应包含 'deletion_log'"""
        from lifeprism.sync.sync_client import SYNC_TABLES

        assert "deletion_log" not in SYNC_TABLES, (
            "sync_client 重导出的 SYNC_TABLES 不应包含 'deletion_log'（墓碑走专用通道）"
        )

    def test_deletion_log_not_appears_in_sync_tables(self):
        """SYNC_TABLES 中 'deletion_log' 应不出现（已移除）"""
        from lifeprism.sync.constants import SYNC_TABLES

        count = SYNC_TABLES.count("deletion_log")
        assert count == 0, (
            f"SYNC_TABLES 中 'deletion_log' 应出现 0 次（已移除，走专用通道），实际出现 {count} 次"
        )


# ==================== Seam 2: deletion_log 不在 HASH_ID_PREFIXES 中 ====================


class TestDeletionLogNotInHashIdPrefixes:
    """Seam 2: HASH_ID_PREFIXES 字典不应包含 deletion_log 键

    理由：
    - HASH_ID_PREFIXES 是"哪些表需要 hash_id"的判断依据，仅包含 6 张 AUTOINCREMENT 表
    - deletion_log 的 id 是 dl-{uuid[:8]}（前缀 + 8 位 hex），不是 hash_id
    - dl- 前缀在 PRD 3 的 DeletionLogProvider 中通过 _generic_insert(id_prefix='dl-') 直接传入
    - 若将 dl- 加入 HASH_ID_PREFIXES，会让 _generic_insert 的 HASH_ID_PREFIXES.get()
      兜底逻辑误认为 deletion_log 是需要 hash_id 的表，产生概念混淆
    """

    def test_deletion_log_not_in_hash_id_prefixes(self):
        """若 HASH_ID_PREFIXES 已存在（Issue 01），deletion_log 不应在其 keys 中

        若 HASH_ID_PREFIXES 尚不存在（Issue 01 未完成），跳过测试
        """
        try:
            from lifeprism.sync.constants import HASH_ID_PREFIXES
        except ImportError:
            pytest.skip(
                "HASH_ID_PREFIXES 尚未在 lifeprism.sync.constants 中定义"
                "（Issue 01 未完成），跳过 deletion_log 不在 HASH_ID_PREFIXES 的断言"
            )

        assert "deletion_log" not in HASH_ID_PREFIXES, (
            f"HASH_ID_PREFIXES 不应包含 'deletion_log' 键（dl- 不是 hash_id 前缀），"
            f"当前 keys: {sorted(HASH_ID_PREFIXES.keys())}"
        )

    def test_dl_prefix_not_in_hash_id_prefixes_values(self):
        """若 HASH_ID_PREFIXES 已存在（Issue 01），'dl-' 前缀不应在 values 中"""
        try:
            from lifeprism.sync.constants import HASH_ID_PREFIXES
        except ImportError:
            pytest.skip(
                "HASH_ID_PREFIXES 尚未在 lifeprism.sync.constants 中定义"
                "（Issue 01 未完成），跳过 dl- 前缀不在 values 的断言"
            )

        values = list(HASH_ID_PREFIXES.values())
        assert "dl-" not in values, (
            f"HASH_ID_PREFIXES 的 values 不应包含 'dl-'（dl- 不是 hash_id 前缀），"
            f"当前 values: {values}"
        )
