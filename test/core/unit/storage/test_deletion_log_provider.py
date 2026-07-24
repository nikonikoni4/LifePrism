"""DeletionLogProvider 单元测试（Slice 01）

测试 seam:
- Seam 1: 表元数据 + 单例注册（_TABLE_NAME / _ON_CONFLICT / 单例导出）
- Seam 2: create_tombstone 写入墓碑（dl- 前缀、created_at == updated_at、显式 created_at 保留）
- Seam 3: write_tombstone_with_cursor 同事务写入（供 Aggregator 调用）
- Seam 4: get_tombstones_since 增量查询 + source 过滤
- Seam 5: get_tombstone 按 (target_table, record_id) 查询
- Seam 6: cleanup_before 清理
- Seam 7: source 字段校验（ValidationError）
- Seam 8: _ON_CONFLICT='ignore' 冲突时保留旧墓碑

参考:
- Issue: .scratch/deletion-sync-03-tombstone/issues/01-deletion-log-provider.md
- PRD: .scratch/deletion-sync-03-tombstone/prd.md
- ADR: docs/adr/2026-07-22-deletion-log-table.md
- Prior art: test/core/unit/storage/test_wechat_account_state_provider.py
"""

import uuid

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def deletion_log_provider(initialized_db):
    """创建 DeletionLogProvider 实例

    每个测试前后清理 deletion_log 表，保证测试隔离。
    """
    from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

    provider = DeletionLogProvider(db_manager=initialized_db)
    yield provider

    # 清理：删除所有测试数据
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


# ==================== Seam 1: 表元数据 + 单例注册 ====================


class TestDeletionLogProviderMetadata:
    """Seam 1: DeletionLogProvider 元数据与单例注册"""

    def test_table_name_defined(self):
        """_TABLE_NAME 应为 'deletion_log'"""
        from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

        assert DeletionLogProvider._TABLE_NAME == "deletion_log"

    def test_primary_key_is_id(self):
        """_PRIMARY_KEY 应为 'id'"""
        from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

        assert DeletionLogProvider._PRIMARY_KEY == "id"

    def test_on_conflict_is_ignore(self):
        """_ON_CONFLICT 应为 'ignore'

        与 _write_tombstone 的 INSERT OR IGNORE 语义一致。
        """
        from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

        assert DeletionLogProvider._ON_CONFLICT == "ignore"

    def test_filter_fields_contains_source_and_target_table(self):
        """_FILTER_FIELDS 应包含 source 和 target_table"""
        from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

        assert "source" in DeletionLogProvider._FILTER_FIELDS
        assert "target_table" in DeletionLogProvider._FILTER_FIELDS

    def test_order_fields_contains_created_at(self):
        """_ORDER_FIELDS 应包含 created_at"""
        from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

        assert "created_at" in DeletionLogProvider._ORDER_FIELDS

    def test_select_fields_complete(self):
        """_SELECT_FIELDS 应包含所有业务字段 + 时间戳"""
        from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider

        expected = {"id", "target_table", "record_id", "source", "created_at", "updated_at"}
        assert DeletionLogProvider._SELECT_FIELDS == expected

    def test_provider_singleton_registered_in_providers_init(self):
        """providers/__init__.py 应注册 deletion_log_provider 单例"""
        from lifeprism.repository.providers import deletion_log_provider

        assert deletion_log_provider is not None

    def test_repository_alias_exported(self):
        """repository/__init__.py 应以 deletion_log_repository 别名导出"""
        from lifeprism.repository import deletion_log_repository

        assert deletion_log_repository is not None

    def test_external_import_from_lifeprism_repository(self):
        """外部调用方应从 lifeprism.repository 导入 deletion_log_repository"""
        # 模拟外部调用方导入
        import lifeprism.repository

        assert hasattr(lifeprism.repository, "deletion_log_repository")


# ==================== Seam 2: create_tombstone 写入墓碑 ====================


class TestCreateTombstone:
    """Seam 2: create_tombstone 写入墓碑"""

    def test_create_tombstone_returns_id_with_dl_prefix(self, deletion_log_provider):
        """create_tombstone 返回的 id 应以 'dl-' 前缀 + 8 位 hex"""
        tombstone_id = deletion_log_provider.create_tombstone(
            target_table="mood_entries",
            record_id="mood-12345678",
            source="local",
        )

        assert tombstone_id is not None
        assert tombstone_id.startswith("dl-")
        # dl- 后 8 位 hex
        suffix = tombstone_id[3:]
        assert len(suffix) == 8
        # 验证是 hex
        int(suffix, 16)

    def test_create_tombstone_writes_all_fields(self, deletion_log_provider):
        """create_tombstone 应写入所有业务字段"""
        deletion_log_provider.create_tombstone(
            target_table="mood_entries",
            record_id="mood-12345678",
            source="local",
        )

        tombstone = deletion_log_provider.get_tombstone("mood_entries", "mood-12345678")
        assert tombstone is not None
        assert tombstone["target_table"] == "mood_entries"
        assert tombstone["record_id"] == "mood-12345678"
        assert tombstone["source"] == "local"

    def test_create_tombstone_created_at_equals_updated_at(self, deletion_log_provider):
        """create_tombstone 默认 created_at == updated_at（墓碑不修改语义）"""
        deletion_log_provider.create_tombstone(
            target_table="mood_entries",
            record_id="mood-12345678",
            source="local",
        )

        tombstone = deletion_log_provider.get_tombstone("mood_entries", "mood-12345678")
        assert tombstone is not None
        assert tombstone["created_at"] == tombstone["updated_at"]

    def test_create_tombstone_with_explicit_created_at_preserves_timestamp(
        self, deletion_log_provider
    ):
        """create_tombstone 显式传入 created_at 时应保留原时间戳（用于 Pull/Push 写副本）

        updated_at 同步设为同值，保持墓碑"不修改"语义，LWW 比较正确。
        """
        original_timestamp = "2026-07-22T10:00:00+00:00"
        deletion_log_provider.create_tombstone(
            target_table="mood_entries",
            record_id="mood-12345678",
            source="cloud",
            created_at=original_timestamp,
        )

        tombstone = deletion_log_provider.get_tombstone("mood_entries", "mood-12345678")
        assert tombstone is not None
        assert tombstone["created_at"] == original_timestamp
        assert tombstone["updated_at"] == original_timestamp  # 保持 == created_at

    def test_create_tombstone_with_explicit_created_at_used_for_cloud_copy(
        self, deletion_log_provider
    ):
        """Pull/Push 场景：写云端副本时传入原始 created_at，保持两端 LWW 一致"""
        # 模拟 Pull：云端墓碑 created_at = '2026-07-22T10:00:00+00:00'
        cloud_tombstone_created_at = "2026-07-22T10:00:00+00:00"
        deletion_log_provider.create_tombstone(
            target_table="todo_list",
            record_id="t-abcdef12",
            source="cloud",
            created_at=cloud_tombstone_created_at,
        )

        tombstone = deletion_log_provider.get_tombstone("todo_list", "t-abcdef12")
        assert tombstone is not None
        assert tombstone["source"] == "cloud"
        assert tombstone["created_at"] == cloud_tombstone_created_at
        assert tombstone["updated_at"] == cloud_tombstone_created_at

    def test_create_tombstone_id_is_unique(self, deletion_log_provider):
        """create_tombstone 多次调用应生成不同 id"""
        id1 = deletion_log_provider.create_tombstone(
            target_table="mood_entries",
            record_id="mood-11111111",
            source="local",
        )
        id2 = deletion_log_provider.create_tombstone(
            target_table="mood_entries",
            record_id="mood-22222222",
            source="local",
        )

        assert id1 != id2


# ==================== Seam 3: write_tombstone_with_cursor 同事务写入 ====================


class TestWriteTombstoneWithCursor:
    """Seam 3: write_tombstone_with_cursor 同事务写入（供 Aggregator 调用）"""

    def test_write_tombstone_with_cursor_writes_within_transaction(
        self, deletion_log_provider, initialized_db
    ):
        """write_tombstone_with_cursor 应在外部 cursor 的事务内写入墓碑"""
        target_table = "custom_sport"
        record_id = "cre-abcdef12"

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            deletion_log_provider.write_tombstone_with_cursor(
                cursor, target_table, record_id, source="local"
            )
            conn.commit()

        tombstone = deletion_log_provider.get_tombstone(target_table, record_id)
        assert tombstone is not None
        assert tombstone["source"] == "local"
        assert tombstone["target_table"] == target_table
        assert tombstone["record_id"] == record_id

    def test_write_tombstone_with_cursor_rollback_on_transaction_failure(
        self, deletion_log_provider, initialized_db
    ):
        """write_tombstone_with_cursor 在事务失败时墓碑应回滚

        场景：Aggregator 在写墓碑后执行 DELETE 失败，整个事务回滚，
        墓碑不应保留。

        使用 sqlite3.OperationalError 模拟真实 DB 失败。
        get_connection() 捕获 sqlite3.Error 后 rollback 并重新抛出为 DataAccessError。
        """
        import sqlite3 as _sqlite3

        from lifeprism.utils.exceptions import DataAccessError

        target_table = "custom_sport"
        record_id = "cre-rollback1"

        try:
            with initialized_db.get_connection() as conn:
                cursor = conn.cursor()
                deletion_log_provider.write_tombstone_with_cursor(
                    cursor, target_table, record_id, source="local"
                )
                # 模拟 DELETE 失败（抛 sqlite3 异常，触发 get_connection 回滚）
                raise _sqlite3.OperationalError("模拟 DELETE 失败")
        except DataAccessError:
            pass  # 异常被吞，事务应已回滚

        # 墓碑不应存在（事务回滚）
        tombstone = deletion_log_provider.get_tombstone(target_table, record_id)
        assert tombstone is None

    def test_write_tombstone_with_cursor_default_source_is_local(
        self, deletion_log_provider, initialized_db
    ):
        """write_tombstone_with_cursor 默认 source 为 'local'"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            deletion_log_provider.write_tombstone_with_cursor(
                conn.cursor(), "custom_sport", "cre-default1"
            )
            conn.commit()

        tombstone = deletion_log_provider.get_tombstone("custom_sport", "cre-default1")
        assert tombstone is not None
        assert tombstone["source"] == "local"

    def test_write_tombstone_with_cursor_uses_insert_or_ignore(
        self, deletion_log_provider, initialized_db
    ):
        """write_tombstone_with_cursor 使用 INSERT OR IGNORE 语义

        同 (target_table, record_id) 重复写入应保留旧墓碑，不刷新时间戳。
        """
        target_table = "custom_sport"
        record_id = "cre-duplicate1"

        # 第一次写入
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            deletion_log_provider.write_tombstone_with_cursor(
                cursor, target_table, record_id, source="local"
            )
            conn.commit()

        first_tombstone = deletion_log_provider.get_tombstone(target_table, record_id)
        assert first_tombstone is not None
        first_created_at = first_tombstone["created_at"]

        # 第二次写入同一 (target_table, record_id) 应被 IGNORE
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            deletion_log_provider.write_tombstone_with_cursor(
                cursor, target_table, record_id, source="local"
            )
            conn.commit()

        second_tombstone = deletion_log_provider.get_tombstone(target_table, record_id)
        assert second_tombstone is not None
        # 时间戳应保持不变（INSERT OR IGNORE 保留旧墓碑）
        assert second_tombstone["created_at"] == first_created_at


# ==================== Seam 4: get_tombstones_since 增量查询 + source 过滤 ====================


class TestGetTombstonesSince:
    """Seam 4: get_tombstones_since 增量查询 + source 过滤"""

    def test_get_tombstones_since_returns_records_after_threshold(
        self, deletion_log_provider
    ):
        """get_tombstones_since 返回 created_at > last_sync_time 的记录"""
        # 准备数据：用显式 created_at 控制时间
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-old", "local", created_at="2026-07-01T00:00:00+00:00"
        )
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-new", "local", created_at="2026-07-22T00:00:00+00:00"
        )

        # last_sync_time = '2026-07-15' 应只返回 mood-new
        results = deletion_log_provider.get_tombstones_since("2026-07-15T00:00:00+00:00")

        assert len(results) == 1
        assert results[0]["record_id"] == "mood-new"

    def test_get_tombstones_since_returns_all_when_empty_last_sync_time(
        self, deletion_log_provider
    ):
        """last_sync_time 为空字符串时应返回全部记录（全量查询）"""
        deletion_log_provider.create_tombstone("mood_entries", "mood-1", "local")
        deletion_log_provider.create_tombstone("mood_entries", "mood-2", "local")

        results = deletion_log_provider.get_tombstones_since("")
        assert len(results) == 2

    def test_get_tombstones_since_filter_by_source_local(
        self, deletion_log_provider
    ):
        """get_tombstones_since(source='local') 只返回 source=local 的记录"""
        deletion_log_provider.create_tombstone("mood_entries", "mood-1", "local")
        deletion_log_provider.create_tombstone("mood_entries", "mood-2", "cloud")

        results = deletion_log_provider.get_tombstones_since("", source="local")
        assert len(results) == 1
        assert results[0]["source"] == "local"
        assert results[0]["record_id"] == "mood-1"

    def test_get_tombstones_since_filter_by_source_cloud(
        self, deletion_log_provider
    ):
        """get_tombstones_since(source='cloud') 只返回 source=cloud 的记录"""
        deletion_log_provider.create_tombstone("mood_entries", "mood-1", "local")
        deletion_log_provider.create_tombstone("mood_entries", "mood-2", "cloud")
        deletion_log_provider.create_tombstone("todo_list", "t-1", "cloud")

        results = deletion_log_provider.get_tombstones_since("", source="cloud")
        assert len(results) == 2
        for r in results:
            assert r["source"] == "cloud"

    def test_get_tombstones_since_orders_by_created_at_asc(
        self, deletion_log_provider
    ):
        """get_tombstones_since 应按 created_at 升序排列"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-late", "local", created_at="2026-07-22T10:00:00+00:00"
        )
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-early", "local", created_at="2026-07-01T00:00:00+00:00"
        )

        results = deletion_log_provider.get_tombstones_since("")
        assert len(results) == 2
        assert results[0]["record_id"] == "mood-early"  # 早的在前
        assert results[1]["record_id"] == "mood-late"

    def test_get_tombstones_since_empty_when_no_records_match(
        self, deletion_log_provider
    ):
        """无匹配记录时返回空列表"""
        deletion_log_provider.create_tombstone("mood_entries", "mood-1", "local")

        results = deletion_log_provider.get_tombstones_since(
            "2099-12-31T23:59:59+00:00"
        )
        assert results == []


# ==================== Seam 5: get_tombstone 按 (target_table, record_id) 查询 ====================


class TestGetTombstone:
    """Seam 5: get_tombstone 按 (target_table, record_id) 查询（用于 LWW 检查）"""

    def test_get_tombstone_returns_record_when_exists(self, deletion_log_provider):
        """get_tombstone 在记录存在时返回墓碑字典"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-12345678", "local"
        )

        tombstone = deletion_log_provider.get_tombstone(
            "mood_entries", "mood-12345678"
        )
        assert tombstone is not None
        assert tombstone["target_table"] == "mood_entries"
        assert tombstone["record_id"] == "mood-12345678"
        assert tombstone["source"] == "local"

    def test_get_tombstone_returns_none_when_not_exists(
        self, deletion_log_provider
    ):
        """get_tombstone 在记录不存在时返回 None"""
        tombstone = deletion_log_provider.get_tombstone(
            "mood_entries", "non-existent-id"
        )
        assert tombstone is None

    def test_get_tombstone_distinguishes_by_target_table(
        self, deletion_log_provider
    ):
        """get_tombstone 应区分不同 target_table（即使 record_id 相同）"""
        # 同一 record_id 但不同 target_table
        deletion_log_provider.create_tombstone("mood_entries", "shared-id", "local")
        deletion_log_provider.create_tombstone("todo_list", "shared-id", "local")

        mood_tombstone = deletion_log_provider.get_tombstone("mood_entries", "shared-id")
        todo_tombstone = deletion_log_provider.get_tombstone("todo_list", "shared-id")

        assert mood_tombstone is not None
        assert mood_tombstone["target_table"] == "mood_entries"
        assert todo_tombstone is not None
        assert todo_tombstone["target_table"] == "todo_list"

    def test_get_tombstone_unique_constraint_ensures_at_most_one(
        self, deletion_log_provider
    ):
        """UNIQUE(target_table, record_id) 约束保证至多返回一条"""
        # 第一次写入
        deletion_log_provider.create_tombstone("mood_entries", "mood-1", "local")
        # 第二次写入同一 (target_table, record_id) 应被 IGNORE
        deletion_log_provider.create_tombstone("mood_entries", "mood-1", "cloud")

        tombstone = deletion_log_provider.get_tombstone("mood_entries", "mood-1")
        assert tombstone is not None
        # 应保留第一次写入的 source=local（INSERT OR IGNORE 保留旧墓碑）
        assert tombstone["source"] == "local"


# ==================== Seam 6: cleanup_before 清理 ====================


class TestCleanupBefore:
    """Seam 6: cleanup_before 清理 created_at <= last_sync_time 的记录"""

    def test_cleanup_before_removes_records_at_or_before_threshold(
        self, deletion_log_provider
    ):
        """cleanup_before 清理 created_at <= last_sync_time 的记录"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-old-1", "local", created_at="2026-07-01T00:00:00+00:00"
        )
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-old-2", "local", created_at="2026-07-10T00:00:00+00:00"
        )
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-new", "local", created_at="2026-07-22T00:00:00+00:00"
        )

        # 清理 created_at <= '2026-07-15'，应删除前两条
        affected = deletion_log_provider.cleanup_before("2026-07-15T00:00:00+00:00")

        assert affected == 2
        remaining = deletion_log_provider.get_tombstones_since("")
        assert len(remaining) == 1
        assert remaining[0]["record_id"] == "mood-new"

    def test_cleanup_before_boundary_condition_includes_equal(
        self, deletion_log_provider
    ):
        """cleanup_before 边界条件：created_at == last_sync_time 也应被清理（<=）"""
        threshold = "2026-07-15T00:00:00+00:00"
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-equal", "local", created_at=threshold
        )

        affected = deletion_log_provider.cleanup_before(threshold)
        assert affected == 1

    def test_cleanup_before_returns_zero_when_no_records_match(
        self, deletion_log_provider
    ):
        """无匹配记录时返回 0"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-future", "local", created_at="2026-07-22T00:00:00+00:00"
        )

        affected = deletion_log_provider.cleanup_before("2026-07-01T00:00:00+00:00")
        assert affected == 0

    def test_cleanup_before_does_not_write_tombstone_for_itself(
        self, deletion_log_provider
    ):
        """cleanup_before 清理 deletion_log 表时不写墓碑（清理是内部操作）"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-1", "local", created_at="2026-07-01T00:00:00+00:00"
        )

        deletion_log_provider.cleanup_before("2026-07-15T00:00:00+00:00")

        # deletion_log 表不应有 target_table='deletion_log' 的墓碑
        tombstone = deletion_log_provider.get_tombstone("deletion_log", "any-id")
        assert tombstone is None


# ==================== Seam 7: source 字段校验 ====================


class TestSourceValidation:
    """Seam 7: source 字段在 Provider 层校验"""

    def test_create_tombstone_invalid_source_raises_validation_error(
        self, deletion_log_provider
    ):
        """create_tombstone 非法 source 应抛 ValidationError"""
        from lifeprism.utils.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            deletion_log_provider.create_tombstone(
                "mood_entries", "mood-1", source="invalid"
            )

        assert exc_info.value.code == "INVALID_SOURCE"
        assert "invalid" in exc_info.value.message

    def test_write_tombstone_with_cursor_invalid_source_raises_validation_error(
        self, deletion_log_provider, initialized_db
    ):
        """write_tombstone_with_cursor 非法 source 应抛 ValidationError"""
        from lifeprism.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            with initialized_db.get_connection() as conn:
                cursor = conn.cursor()
                deletion_log_provider.write_tombstone_with_cursor(
                    cursor, "mood_entries", "mood-1", source="remote"
                )

    def test_get_tombstones_since_invalid_source_raises_validation_error(
        self, deletion_log_provider
    ):
        """get_tombstones_since 非法 source 应抛 ValidationError"""
        from lifeprism.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            deletion_log_provider.get_tombstones_since("", source="invalid")

    def test_create_tombstone_accepts_local_source(self, deletion_log_provider):
        """create_tombstone 接受 source='local'"""
        tombstone_id = deletion_log_provider.create_tombstone(
            "mood_entries", "mood-1", source="local"
        )
        assert tombstone_id is not None

    def test_create_tombstone_accepts_cloud_source(self, deletion_log_provider):
        """create_tombstone 接受 source='cloud'"""
        tombstone_id = deletion_log_provider.create_tombstone(
            "mood_entries", "mood-1", source="cloud"
        )
        assert tombstone_id is not None


# ==================== Seam 8: _ON_CONFLICT='ignore' 冲突时保留旧墓碑 ====================


class TestOnConflictIgnore:
    """Seam 8: _ON_CONFLICT='ignore'，UNIQUE 冲突时保留旧墓碑"""

    def test_duplicate_tombstone_keeps_first_one(self, deletion_log_provider):
        """重复写入同 (target_table, record_id) 应保留第一次的墓碑"""
        # 第一次写入 source=local
        deletion_log_provider.create_tombstone(
            "mood_entries",
            "mood-dup",
            "local",
            created_at="2026-07-22T10:00:00+00:00",
        )

        # 第二次写入 source=cloud（应被 IGNORE）
        result = deletion_log_provider.create_tombstone(
            "mood_entries",
            "mood-dup",
            "cloud",
            created_at="2026-07-23T10:00:00+00:00",  # 更晚的时间
        )

        # 第二次应返回 None（INSERT OR IGNORE 冲突）
        assert result is None

        # 验证保留的是第一次的墓碑
        tombstone = deletion_log_provider.get_tombstone("mood_entries", "mood-dup")
        assert tombstone is not None
        assert tombstone["source"] == "local"
        assert tombstone["created_at"] == "2026-07-22T10:00:00+00:00"

    def test_different_target_table_allows_same_record_id(
        self, deletion_log_provider
    ):
        """不同 target_table 但相同 record_id 应允许分别写入（UNIQUE 是复合约束）"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "shared-id", "local"
        )
        deletion_log_provider.create_tombstone(
            "todo_list", "shared-id", "local"
        )

        mood_tombstone = deletion_log_provider.get_tombstone("mood_entries", "shared-id")
        todo_tombstone = deletion_log_provider.get_tombstone("todo_list", "shared-id")

        assert mood_tombstone is not None
        assert todo_tombstone is not None

    def test_different_record_id_allows_same_target_table(
        self, deletion_log_provider
    ):
        """同 target_table 但不同 record_id 应允许分别写入"""
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-1", "local"
        )
        deletion_log_provider.create_tombstone(
            "mood_entries", "mood-2", "local"
        )

        results = deletion_log_provider.get_tombstones_since("")
        assert len(results) == 2
