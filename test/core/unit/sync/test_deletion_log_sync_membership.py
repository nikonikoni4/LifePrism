"""deletion_log 在同步常量中的归属关系测试

测试 seam:
- Seam 1: SYNC_TABLES 常量 - 验证 deletion_log 加入同步表列表
- Seam 2: HASH_ID_PREFIXES 字典 - 验证 deletion_log 不在 HASH_ID_PREFIXES 中

Issue #05 验收标准:
- deletion_log 加入 lifeprism/sync/constants.py 的 SYNC_TABLES
- 不将 dl- 前缀加入 HASH_ID_PREFIXES（deletion_log 的 id 是 dl- 前缀的 8 位 hex，
  不是 hash_id；id 生成在 PRD 3 的 DeletionLogProvider 中通过
  _generic_insert(id_prefix='dl-') 实现）

参考:
- Issue: .scratch/deletion-sync-01-schema/issues/05-deletion-log-table-and-adr.md
- PRD: .scratch/deletion-sync-01-schema/prd.md
- ADR: docs/adr/2026-07-22-deletion-log-table.md
- 相关 ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md
"""

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: deletion_log 在 SYNC_TABLES 中 ====================


class TestDeletionLogInSyncTables:
    """Seam 1: SYNC_TABLES 常量应包含 deletion_log

    deletion_log 加入 SYNC_TABLES 后，sync_client 会自动同步墓碑记录到对端，
    实现删除操作的跨端传播。
    """

    def test_deletion_log_in_sync_tables_constant(self):
        """lifeprism.sync.constants.SYNC_TABLES 应包含 'deletion_log'"""
        from lifeprism.sync.constants import SYNC_TABLES

        assert "deletion_log" in SYNC_TABLES, (
            f"SYNC_TABLES 应包含 'deletion_log'，当前列表: {SYNC_TABLES}"
        )

    def test_deletion_log_in_sync_tables_via_sync_client_reexport(self):
        """lifeprism.sync.sync_client.SYNC_TABLES（向后兼容重导出）应包含 'deletion_log'"""
        from lifeprism.sync.sync_client import SYNC_TABLES

        assert "deletion_log" in SYNC_TABLES, (
            "sync_client 重导出的 SYNC_TABLES 应包含 'deletion_log'"
        )

    def test_deletion_log_appears_exactly_once_in_sync_tables(self):
        """SYNC_TABLES 中 'deletion_log' 应只出现一次（防止重复注册）"""
        from lifeprism.sync.constants import SYNC_TABLES

        count = SYNC_TABLES.count("deletion_log")
        assert count == 1, (
            f"SYNC_TABLES 中 'deletion_log' 应出现 1 次，实际出现 {count} 次"
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
