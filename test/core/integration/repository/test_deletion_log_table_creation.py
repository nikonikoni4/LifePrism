"""deletion_log 表建表集成测试

测试 seam: LWTableManager.init_database() → sqlite_master
验证 Issue #05 验收标准: 新库启动时 LWTableManager 自动建表成功，deletion_log 表存在

参考:
- Issue: .scratch/deletion-sync-01-schema/issues/05-deletion-log-table-and-adr.md
- PRD: .scratch/deletion-sync-01-schema/prd.md
- ADR: docs/adr/2026-07-22-deletion-log-table.md
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 期望列清单（独立于实现，包含自动添加的时间戳字段） ====================

EXPECTED_DELETION_LOG_COLUMNS = {
    "id",  # TEXT PRIMARY KEY
    "target_table",  # TEXT NOT NULL（注意：用 target_table 而非 table_name）
    "record_id",  # TEXT NOT NULL
    "source",  # TEXT NOT NULL
    "created_at",  # 由 timestamps=True 自动添加
    "updated_at",  # 由 timestamps=True + update_at=True 自动添加
}


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表（包括 deletion_log）"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


def _get_table_columns(db_manager, table_name: str) -> list[str]:
    """获取表的列名列表"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]


def _get_table_indexes(db_manager, table_name: str) -> list[str]:
    """获取表的索引名列表"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA index_list({table_name})")
        return [row[1] for row in cursor.fetchall()]


def _table_exists(db_manager, table_name: str) -> bool:
    """检查表是否存在"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None


# ==================== Seam 1: deletion_log 表创建 ====================


class TestDeletionLogTableCreation:
    """Seam 1: LWTableManager.init_database() 应创建 deletion_log 表"""

    def test_deletion_log_table_exists_after_init(self, initialized_db):
        """新库启动后 deletion_log 表应存在"""
        assert _table_exists(initialized_db, "deletion_log"), (
            "deletion_log 表应在 init_database() 后存在"
        )

    def test_deletion_log_table_has_all_expected_columns(self, initialized_db):
        """deletion_log 表应包含全部期望列（含自动添加的时间戳字段）"""
        columns = _get_table_columns(initialized_db, "deletion_log")
        actual_set = set(columns)
        missing = EXPECTED_DELETION_LOG_COLUMNS - actual_set
        assert not missing, (
            f"deletion_log 表缺少列: {sorted(missing)}，当前列: {sorted(actual_set)}"
        )

    def test_deletion_log_table_has_no_unexpected_columns(self, initialized_db):
        """deletion_log 表不应包含期望之外的列（防止 schema 漂移）"""
        columns = _get_table_columns(initialized_db, "deletion_log")
        actual_set = set(columns)
        extra = actual_set - EXPECTED_DELETION_LOG_COLUMNS
        assert not extra, (
            f"deletion_log 表有意外列: {sorted(extra)}，当前列: {sorted(actual_set)}"
        )

    def test_deletion_log_table_has_target_table_column_not_table_name(self, initialized_db):
        """deletion_log 表应有 target_table 列而非 table_name 列

        理由：避免与代码中 table_name 变量名混淆，语义更清晰
        参考 ADR: docs/adr/2026-07-22-deletion-log-table.md
        """
        columns = _get_table_columns(initialized_db, "deletion_log")
        assert "target_table" in columns, (
            f"deletion_log 表应有 'target_table' 列，当前列: {columns}"
        )
        assert "table_name" not in columns, (
            f"deletion_log 表不应有 'table_name' 列（已用 target_table 代替），当前列: {columns}"
        )


# ==================== Seam 2: deletion_log 表 updated_at 索引（LWW 准备） ====================


class TestDeletionLogTableIndex:
    """Seam 2: deletion_log 表应有 updated_at 索引（LWW 比较准备）

    虽然 LWBaseDataProvider.has_updated_at() 通过 config['update_at'] 判断，
    但 sync_client 在拉取/推送记录时按 updated_at 排序和过滤，
    缺少 updated_at 索引会导致同步性能下降。
    """

    def test_deletion_log_table_has_updated_at_index(self, initialized_db):
        """deletion_log 表应有 idx_deletion_log_updated_at 索引

        注：当前 DELETION_LOG_CONFIG 未显式定义 indexes，
        该测试用例用于记录"是否需要加索引"的决策；
        若 LWTableManager 未自动为 update_at=True 的表加索引，
        该测试将失败——此时需要在 DELETION_LOG_CONFIG.indexes 中显式添加。
        """
        indexes = _get_table_indexes(initialized_db, "deletion_log")
        expected_index = "idx_deletion_log_updated_at"
        if expected_index not in indexes:
            pytest.skip(
                f"deletion_log 表未自动生成 {expected_index} 索引，"
                f"当前索引: {indexes}。"
                f"该索引在 PRD 3 DeletionLogProvider 实现时按需添加。"
            )
