"""
file_sync_state 表注册 + FileSyncStateProvider 集成测试

测试 seam:
- Seam 1: TABLE_CONFIGS 注册 + init_database 创建表（Schema 层）
- Seam 2: SYNC_TABLES 防御性排除（file_sync_state 不在 SYNC_TABLES 中）
- Seam 3: FileSyncStateProvider CRUD（get_state / get_all_states / upsert_state / delete_state）

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 1（per-file version tracking）
"""

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def file_sync_state_provider(initialized_db):
    """创建 FileSyncStateProvider 实例（使用测试数据库）"""
    from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

    provider = FileSyncStateProvider(db_manager=initialized_db)
    yield provider


@pytest.fixture
def clean_file_sync_state(initialized_db):
    """每个测试前后清理 file_sync_state 表"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()


# ==================== Seam 1: TABLE_CONFIGS 注册 + init_database ====================


class TestFileSyncStateTableRegistration:
    """Seam 1: file_sync_state 表在 TABLE_CONFIGS 中注册且 init_database 自动创建"""

    def test_file_sync_state_in_table_configs(self):
        """file_sync_state 应在 TABLE_CONFIGS 中注册"""
        from lifeprism.config.database import TABLE_CONFIGS

        assert "file_sync_state" in TABLE_CONFIGS, "file_sync_state 应在 TABLE_CONFIGS 中注册"

    def test_file_sync_state_table_created_by_init_database(self, initialized_db):
        """init_database 应自动创建 file_sync_state 表"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_sync_state'"
            )
            result = cursor.fetchone()
        assert result is not None, "file_sync_state 表应被 init_database 创建"

    def test_file_sync_state_table_columns(self, initialized_db):
        """file_sync_state 表应有正确的列：file_path, parent_hash, current_hash, updated_at"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(file_sync_state)")
            columns = {row[1]: row for row in cursor.fetchall()}

        expected_columns = {"file_path", "parent_hash", "current_hash", "updated_at"}
        assert set(columns.keys()) == expected_columns, (
            f"file_sync_state 列应为 {expected_columns}，实际 {set(columns.keys())}"
        )

    def test_file_path_is_primary_key(self, initialized_db):
        """file_path 应为主键"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(file_sync_state)")
            columns = {row[1]: row for row in cursor.fetchall()}

        # pk 列：row[5] == 1 表示主键
        assert columns["file_path"][5] == 1, "file_path 应为主键"

    def test_updated_at_is_not_null(self, initialized_db):
        """updated_at 应为 NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(file_sync_state)")
            columns = {row[1]: row for row in cursor.fetchall()}

        # notnull 列：row[3] == 1 表示 NOT NULL
        assert columns["updated_at"][3] == 1, "updated_at 应为 NOT NULL"

    def test_parent_hash_and_current_hash_are_nullable(self, initialized_db):
        """parent_hash 和 current_hash 应可空（NULL = 从未同步 / 无内容）"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(file_sync_state)")
            columns = {row[1]: row for row in cursor.fetchall()}

        assert columns["parent_hash"][3] == 0, "parent_hash 应可空"
        assert columns["current_hash"][3] == 0, "current_hash 应可空"


# ==================== Seam 2: SYNC_TABLES 防御性排除 ====================


class TestFileSyncStateNotInSyncTables:
    """Seam 2: file_sync_state 不在 SYNC_TABLES 中（它是同步元数据，不走数据库同步链路）"""

    def test_file_sync_state_not_in_sync_tables(self):
        """file_sync_state 不应在 SYNC_TABLES 中"""
        from lifeprism.sync.sync_client import SYNC_TABLES

        assert "file_sync_state" not in SYNC_TABLES, (
            "file_sync_state 是同步元数据，不应加入 SYNC_TABLES"
        )


# ==================== Seam 3: FileSyncStateProvider CRUD ====================


class TestUpsertAndGetState:
    """Seam 3: upsert_state + get_state 往返测试"""

    def test_upsert_then_get_returns_state(self, file_sync_state_provider, clean_file_sync_state):
        """upsert_state 后 get_state 应返回 parent_hash + current_hash"""
        # Act: upsert 一条记录
        result = file_sync_state_provider.upsert_state(
            file_path="user/user.md",
            parent_hash=None,
            current_hash="abc123",
        )
        assert result is True

        # Assert: get_state 返回插入的数据
        state = file_sync_state_provider.get_state("user/user.md")
        assert state is not None
        assert state["file_path"] == "user/user.md"
        assert state["parent_hash"] is None
        assert state["current_hash"] == "abc123"
        assert state["updated_at"] is not None

    def test_upsert_with_parent_hash_then_get(
        self, file_sync_state_provider, clean_file_sync_state
    ):
        """upsert 带 parent_hash 后 get_state 返回完整状态"""
        file_sync_state_provider.upsert_state(
            file_path="diary/2026-07-14.md",
            parent_hash="old_hash_111",
            current_hash="new_hash_222",
        )

        state = file_sync_state_provider.get_state("diary/2026-07-14.md")
        assert state is not None
        assert state["parent_hash"] == "old_hash_111"
        assert state["current_hash"] == "new_hash_222"

    def test_get_state_returns_none_for_nonexistent(
        self, file_sync_state_provider, clean_file_sync_state
    ):
        """get_state 对不存在的 file_path 返回 None"""
        state = file_sync_state_provider.get_state("nonexistent/file.md")
        assert state is None


class TestGetAllStates:
    """Seam 3: get_all_states(directory) 按目录前缀过滤"""

    def test_get_all_states_returns_files_under_directory(
        self, file_sync_state_provider, clean_file_sync_state
    ):
        """get_all_states 返回指定目录下的所有文件状态"""
        # Arrange: 插入多个目录的文件
        file_sync_state_provider.upsert_state("user/user.md", None, "hash1")
        file_sync_state_provider.upsert_state("user/psychological_model/behavior.md", "p1", "hash2")
        file_sync_state_provider.upsert_state("diary/2026-07-14.md", None, "hash3")
        file_sync_state_provider.upsert_state("agent/identity.md", "p2", "hash4")

        # Act: 查询 user/ 目录
        states = file_sync_state_provider.get_all_states("user/")

        # Assert: 只返回 user/ 下的文件
        assert len(states) == 2
        paths = {s["file_path"] for s in states}
        assert "user/user.md" in paths
        assert "user/psychological_model/behavior.md" in paths
        assert "diary/2026-07-14.md" not in paths

    def test_get_all_states_without_trailing_slash(
        self, file_sync_state_provider, clean_file_sync_state
    ):
        """get_all_states 目录参数不带尾部 / 也能正确过滤"""
        file_sync_state_provider.upsert_state("user/user.md", None, "hash1")
        file_sync_state_provider.upsert_state("user_backup/x.md", None, "hash2")
        file_sync_state_provider.upsert_state("diary/d.md", None, "hash3")

        # "user" 不带 / 也能匹配 user/ 下的文件，但不匹配 user_backup/
        states = file_sync_state_provider.get_all_states("user")

        paths = {s["file_path"] for s in states}
        assert "user/user.md" in paths
        assert "user_backup/x.md" not in paths
        assert "diary/d.md" not in paths

    def test_get_all_states_empty_result(self, file_sync_state_provider, clean_file_sync_state):
        """get_all_states 对不存在的目录返回空列表"""
        file_sync_state_provider.upsert_state("user/user.md", None, "hash1")

        states = file_sync_state_provider.get_all_states("nonexistent/")
        assert states == []


class TestDeleteState:
    """Seam 3: delete_state 删除记录"""

    def test_delete_state_removes_record(self, file_sync_state_provider, clean_file_sync_state):
        """delete_state 删除已存在的记录"""
        # Arrange: 插入记录
        file_sync_state_provider.upsert_state("user/user.md", None, "hash1")
        assert file_sync_state_provider.get_state("user/user.md") is not None

        # Act: 删除
        result = file_sync_state_provider.delete_state("user/user.md")

        # Assert: 删除成功且 get_state 返回 None
        assert result is True
        assert file_sync_state_provider.get_state("user/user.md") is None

    def test_delete_state_nonexistent_returns_false(
        self, file_sync_state_provider, clean_file_sync_state
    ):
        """delete_state 对不存在的记录返回 False"""
        result = file_sync_state_provider.delete_state("nonexistent/file.md")
        assert result is False


class TestUpsertStateUpdate:
    """Seam 3: upsert_state 更新已存在的记录（INSERT OR REPLACE）"""

    def test_upsert_updates_existing_record(self, file_sync_state_provider, clean_file_sync_state):
        """upsert_state 对已存在的 file_path 执行更新而非报错"""
        # Arrange: 第一次 upsert
        file_sync_state_provider.upsert_state(
            file_path="user/user.md",
            parent_hash=None,
            current_hash="hash_v1",
        )
        state_before = file_sync_state_provider.get_state("user/user.md")
        assert state_before["parent_hash"] is None
        assert state_before["current_hash"] == "hash_v1"

        # Act: 第二次 upsert（更新 parent_hash + current_hash）
        result = file_sync_state_provider.upsert_state(
            file_path="user/user.md",
            parent_hash="hash_v1",
            current_hash="hash_v2",
        )
        assert result is True

        # Assert: 记录被更新，不是新增
        state_after = file_sync_state_provider.get_state("user/user.md")
        assert state_after["parent_hash"] == "hash_v1"
        assert state_after["current_hash"] == "hash_v2"

        # 确认只有一条记录（不是重复插入）
        all_states = file_sync_state_provider.get_all_states("user/")
        assert len(all_states) == 1

    def test_upsert_updates_updated_at_timestamp(
        self, file_sync_state_provider, clean_file_sync_state
    ):
        """upsert_state 更新时 updated_at 时间戳应刷新"""
        import time

        # Arrange: 第一次 upsert
        file_sync_state_provider.upsert_state("user/user.md", None, "hash_v1")
        state_before = file_sync_state_provider.get_state("user/user.md")
        updated_at_before = state_before["updated_at"]

        # 等待一小段时间确保时间戳不同
        time.sleep(0.05)

        # Act: 第二次 upsert
        file_sync_state_provider.upsert_state("user/user.md", "hash_v1", "hash_v2")

        # Assert: updated_at 已刷新
        state_after = file_sync_state_provider.get_state("user/user.md")
        assert state_after["updated_at"] != updated_at_before, (
            f"updated_at 应在更新后变化，更新前: {updated_at_before}, 更新后: {state_after['updated_at']}"
        )
