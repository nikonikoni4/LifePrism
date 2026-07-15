"""
SyncRepository 对 wechat_account_state 表的同步集成测试

测试 seam:
- Seam 1: 表名校验 - wechat_account_state 通过 _validate_table_name（在 TABLE_CONFIGS 中）
- Seam 2: query_incremental() - 增量查询 wechat_account_state
- Seam 3: upsert_rows() - 批量写入 wechat_account_state
- Seam 4: upsert_rows_with_lww() - LWW 冲突解决（跳过旧数据、跳过相同 updated_at、写入新数据）

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
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
    from lifeprism.repository.lw_table_manager import LWTableManager

    from lifeprism.repository.base_providers.lw_base_data_provider import (
        LWBaseDataProvider,
    )

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo
    # 清理
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wechat_account_state")
        conn.commit()


@pytest.fixture
def clean_wechat_account_state(initialized_db):
    """清理 wechat_account_state 表"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wechat_account_state")
        conn.commit()
    yield


# ==================== Seam 1: 表名校验 ====================


class TestWechatAccountStateTableValidation:
    """Seam 1: wechat_account_state 通过 _validate_table_name"""

    def test_validate_table_name_passes_for_wechat_account_state(
        self, repository, clean_wechat_account_state
    ):
        """wechat_account_state 在 TABLE_CONFIGS 中，校验应通过"""
        # Act + Assert: 不抛出异常即通过
        repository._validate_table_name("wechat_account_state")

    def test_get_primary_key_field_returns_wechat_user_id(self, repository):
        """主键字段应为 wechat_user_id"""
        pk = repository.get_primary_key_field("wechat_account_state")
        assert pk == "wechat_user_id"


# ==================== Seam 2: query_incremental() ====================


class TestQueryIncrementalWechatAccountState:
    """Seam 2: query_incremental() 增量查询 wechat_account_state"""

    def test_query_incremental_returns_rows_after_last_sync(
        self, repository, initialized_db, clean_wechat_account_state
    ):
        """增量查询：返回 last_sync_time 之后更新的记录"""
        # Arrange: 插入 2 条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO wechat_account_state "
                "(wechat_user_id, context_token, last_session_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "user_sync_001",
                    "ctx_001",
                    "sess_001",
                    "2026-07-01 10:00:00",
                    "2026-07-01 10:00:00",
                ),
            )
            cursor.execute(
                "INSERT INTO wechat_account_state "
                "(wechat_user_id, context_token, last_session_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "user_sync_002",
                    "ctx_002",
                    "sess_002",
                    "2026-07-01 11:00:00",
                    "2026-07-01 11:00:00",
                ),
            )
            conn.commit()

        # Act: 查询 10:30:00 之后的记录
        rows = repository.query_incremental(
            "wechat_account_state", "2026-07-01 10:30:00"
        )

        # Assert: 应返回 user_sync_002
        assert len(rows) == 1
        assert rows[0]["wechat_user_id"] == "user_sync_002"
        assert rows[0]["context_token"] == "ctx_002"

    def test_query_incremental_returns_empty_when_no_changes(
        self, repository, clean_wechat_account_state
    ):
        """增量查询：无增量数据时返回空列表"""
        # Act: 查询未来时间
        rows = repository.query_incremental(
            "wechat_account_state", "2026-12-31 23:59:59"
        )

        # Assert: 返回空列表
        assert rows == []


# ==================== Seam 3: upsert_rows() ====================


class TestUpsertRowsWechatAccountState:
    """Seam 3: upsert_rows() 批量写入 wechat_account_state"""

    def test_upsert_rows_inserts_new_records(
        self, repository, initialized_db, clean_wechat_account_state
    ):
        """upsert_rows: 插入新记录"""
        # Arrange
        rows = [
            {
                "wechat_user_id": "upsert_user_001",
                "context_token": "ctx_001",
                "last_session_id": "sess_001",
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-01 10:00:00",
            },
            {
                "wechat_user_id": "upsert_user_002",
                "context_token": "ctx_002",
                "last_session_id": None,
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-01 10:00:00",
            },
        ]

        # Act
        affected = repository.upsert_rows("wechat_account_state", rows)

        # Assert
        assert affected == 2

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT wechat_user_id, context_token, last_session_id "
                "FROM wechat_account_state WHERE wechat_user_id = ?",
                ("upsert_user_001",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "upsert_user_001"
            assert row[1] == "ctx_001"
            assert row[2] == "sess_001"

    def test_upsert_rows_replaces_existing_record(
        self, repository, initialized_db, clean_wechat_account_state
    ):
        """upsert_rows: INSERT OR REPLACE 覆盖已有记录"""
        # Arrange: 先插入一条记录
        repository.upsert_rows(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "replace_user",
                    "context_token": "old_token",
                    "last_session_id": "old_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 10:00:00",
                }
            ],
        )

        # Act: 用相同主键插入新数据
        repository.upsert_rows(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "replace_user",
                    "context_token": "new_token",
                    "last_session_id": "new_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 12:00:00",
                }
            ],
        )

        # Assert: 记录被覆盖
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_token, last_session_id FROM wechat_account_state "
                "WHERE wechat_user_id = ?",
                ("replace_user",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "new_token"
            assert row[1] == "new_session"


# ==================== Seam 4: upsert_rows_with_lww() ====================


class TestUpsertRowsWithLwwWechatAccountState:
    """Seam 4: upsert_rows_with_lww() LWW 冲突解决"""

    def test_lww_skips_older_data(self, repository, initialized_db, clean_wechat_account_state):
        """LWW: 本地数据更新时跳过传入的旧数据"""
        # Arrange: 先写入新数据
        repository.upsert_rows(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_skip_user",
                    "context_token": "new_token",
                    "last_session_id": "new_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 12:00:00",
                }
            ],
        )

        # Act: 用 LWW 推送更旧的数据
        affected = repository.upsert_rows_with_lww(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_skip_user",
                    "context_token": "old_token",
                    "last_session_id": "old_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 10:00:00",
                }
            ],
        )

        # Assert: 旧数据被跳过
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_token FROM wechat_account_state "
                "WHERE wechat_user_id = ?",
                ("lww_skip_user",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "new_token"

    def test_lww_skips_equal_updated_at(
        self, repository, initialized_db, clean_wechat_account_state
    ):
        """LWW: updated_at 相同时跳过写入（不覆盖）"""
        # Arrange: 先写入数据
        repository.upsert_rows(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_equal_user",
                    "context_token": "original_token",
                    "last_session_id": "original_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 12:00:00",
                }
            ],
        )

        # Act: 用 LWW 推送相同 updated_at 的数据（但内容不同）
        affected = repository.upsert_rows_with_lww(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_equal_user",
                    "context_token": "different_token",
                    "last_session_id": "different_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 12:00:00",  # 相同 updated_at
                }
            ],
        )

        # Assert: 相同 updated_at 被跳过，返回 0
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_token FROM wechat_account_state "
                "WHERE wechat_user_id = ?",
                ("lww_equal_user",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "original_token", "相同 updated_at 时不应覆盖"

    def test_lww_writes_newer_data(self, repository, initialized_db, clean_wechat_account_state):
        """LWW: 传入数据更新时覆盖本地旧数据"""
        # Arrange: 先写入旧数据
        repository.upsert_rows(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_overwrite_user",
                    "context_token": "old_token",
                    "last_session_id": "old_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 10:00:00",
                }
            ],
        )

        # Act: 用 LWW 推送更新的数据
        affected = repository.upsert_rows_with_lww(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_overwrite_user",
                    "context_token": "new_token",
                    "last_session_id": "new_session",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 12:00:00",
                }
            ],
        )

        # Assert: 新数据被写入
        assert affected == 1

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_token FROM wechat_account_state "
                "WHERE wechat_user_id = ?",
                ("lww_overwrite_user",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "new_token"

    def test_lww_inserts_new_record(self, repository, initialized_db, clean_wechat_account_state):
        """LWW: 本地不存在记录时直接插入"""
        # Act: 推送新数据
        affected = repository.upsert_rows_with_lww(
            "wechat_account_state",
            [
                {
                    "wechat_user_id": "lww_new_user",
                    "context_token": "new_ctx",
                    "last_session_id": "new_sess",
                    "created_at": "2026-07-01 10:00:00",
                    "updated_at": "2026-07-01 10:00:00",
                }
            ],
        )

        # Assert: 新数据被写入
        assert affected == 1

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_token FROM wechat_account_state "
                "WHERE wechat_user_id = ?",
                ("lww_new_user",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "new_ctx"
