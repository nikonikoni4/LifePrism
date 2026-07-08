"""
SyncRepository 集成测试

测试 seam:
- Seam 1: query_incremental() - 增量查询、空结果、数据库异常
- Seam 2: upsert_rows() - 插入新行、覆盖旧行、AUTOINCREMENT id 剥离、数据库异常
- Seam 3: get_primary_key_field() - 解析 TEXT 主键、AUTOINCREMENT 主键
- Seam 4: upsert_rows_with_lww() - LWW 跳过旧数据、写入新数据、插入新记录
- Seam 5: get_unique_fields() / _is_autoincrement_table() - 元数据解析

参考: test/core/integration/repository/test_sync_schema.py
"""
import sqlite3

import pytest

from lifeprism.utils.exceptions import DataAccessError

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo

    # 清理：删除所有同步表中的测试数据
    sync_tables = [
        "mood_entries",
        "todo_list",
        "goal",
        "diary",
        "timeline_custom_block",
        "user_app_behavior_log",
        "category_map_cache",
    ]
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in sync_tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


# ==================== Seam 1: query_incremental() ====================


class TestQueryIncremental:
    """测试 query_incremental() 方法"""

    def test_query_incremental_returns_rows_after_last_sync_time(self, repository, initialized_db):
        """增量查询：返回 last_sync_time 之后更新的记录"""
        # Arrange: 插入 3 条记录，updated_at 不同
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-001", "happy", 8, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-002", "calm", 6, "2026-07-01 11:00:00", "2026-07-01 11:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-003", "joy", 9, "2026-07-01 12:00:00", "2026-07-01 12:00:00"),
            )
            conn.commit()

        # Act: 查询 10:30:00 之后的记录
        rows = repository.query_incremental("mood_entries", "2026-07-01 10:30:00")

        # Assert: 应返回 mood-002 和 mood-003
        assert len(rows) == 2
        ids = {row["id"] for row in rows}
        assert ids == {"mood-002", "mood-003"}

    def test_query_incremental_returns_empty_when_no_changes(self, repository, initialized_db):
        """增量查询：无增量数据时返回空列表"""
        # Arrange: 插入一条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-old", "happy", 5, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # Act: 查询比所有记录都晚的时间
        rows = repository.query_incremental("mood_entries", "2026-12-31 23:59:59")

        # Assert
        assert rows == []

    def test_query_incremental_returns_all_when_last_sync_is_empty(self, repository, initialized_db):
        """增量查询：last_sync_time 为空字符串时返回全部记录"""
        # Arrange
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-a", "happy", 5, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-b", "calm", 7, "2026-07-01 11:00:00", "2026-07-01 11:00:00"),
            )
            conn.commit()

        # Act: last_sync_time 为空字符串（大于空字符串的条件对所有记录都成立）
        rows = repository.query_incremental("mood_entries", "")

        # Assert: 返回全部 2 条记录
        assert len(rows) == 2

    def test_query_incremental_results_ordered_by_updated_at_asc(self, repository, initialized_db):
        """增量查询：结果按 updated_at ASC 排序"""
        # Arrange: 故意乱序插入
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-late", "happy", 5, "2026-07-01 10:00:00", "2026-07-01 12:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-early", "calm", 7, "2026-07-01 11:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # Act
        rows = repository.query_incremental("mood_entries", "2026-07-01 09:00:00")

        # Assert: mood-early 在前（updated_at = 10:00:00），mood-late 在后（12:00:00）
        assert len(rows) == 2
        assert rows[0]["id"] == "mood-early"
        assert rows[1]["id"] == "mood-late"

    def test_query_incremental_raises_data_access_error_on_nonexistent_table(
        self, repository, initialized_db
    ):
        """增量查询：表名不在白名单中时抛出 DataAccessError（SQL 注入防护）"""
        # Act + Assert
        with pytest.raises(DataAccessError):
            repository.query_incremental("nonexistent_table_xyz", "2026-07-01 00:00:00")


# ==================== Seam 2: upsert_rows() ====================


class TestUpsertRows:
    """测试 upsert_rows() 方法"""

    def test_upsert_rows_inserts_new_rows(self, repository, initialized_db):
        """upsert_rows：插入新行"""
        # Arrange
        rows = [
            {
                "id": "todo-001",
                "content": "测试任务1",
                "state": "pool",
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-01 10:00:00",
            },
            {
                "id": "todo-002",
                "content": "测试任务2",
                "state": "scheduled",
                "created_at": "2026-07-01 11:00:00",
                "updated_at": "2026-07-01 11:00:00",
            },
        ]

        # Act
        affected = repository.upsert_rows("todo_list", rows)

        # Assert: 返回受影响行数
        assert affected == 2

        # Assert: 数据库中有 2 条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content, state FROM todo_list ORDER BY id")
            db_rows = cursor.fetchall()
            assert len(db_rows) == 2
            assert db_rows[0][0] == "todo-001"
            assert db_rows[0][1] == "测试任务1"
            assert db_rows[1][0] == "todo-002"
            assert db_rows[1][1] == "测试任务2"

    def test_upsert_rows_overwrites_existing_row(self, repository, initialized_db):
        """upsert_rows：覆盖已存在的行（INSERT OR REPLACE）"""
        # Arrange: 先插入一条记录
        original_row = {
            "id": "todo-overwrite",
            "content": "原始内容",
            "state": "pool",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        repository.upsert_rows("todo_list", [original_row])

        # Act: 用相同 id 插入新内容（覆盖）
        new_row = {
            "id": "todo-overwrite",
            "content": "更新后的内容",
            "state": "completed",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 12:00:00",
        }
        affected = repository.upsert_rows("todo_list", [new_row])

        # Assert
        assert affected == 1

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, state FROM todo_list WHERE id = ?", ("todo-overwrite",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "更新后的内容"
            assert row[1] == "completed"

    def test_upsert_rows_returns_zero_for_empty_list(self, repository, initialized_db):
        """upsert_rows：空列表返回 0"""
        # Act
        affected = repository.upsert_rows("todo_list", [])

        # Assert
        assert affected == 0

    def test_upsert_rows_handles_autoincrement_table_with_unique_constraint(
        self, repository, initialized_db
    ):
        """upsert_rows：AUTOINCREMENT + UNIQUE 约束表（Category B）覆盖逻辑"""
        # Arrange: 插入第一条记录
        rows = [
            {
                "app": "chrome.exe",
                "start_time": "2026-07-08 10:00:00",
                "end_time": "2026-07-08 11:00:00",
                "duration": 60,
                "title": "Google Chrome",
                "is_multipurpose_app": 0,
                "created_at": "2026-07-08 10:00:00",
                "updated_at": "2026-07-08 10:00:00",
            }
        ]
        repository.upsert_rows("user_app_behavior_log", rows)

        # Act: 用相同 (app, start_time) 插入新数据（UNIQUE 约束触发 REPLACE）
        overwrite_rows = [
            {
                "app": "chrome.exe",
                "start_time": "2026-07-08 10:00:00",
                "end_time": "2026-07-08 11:30:00",
                "duration": 90,
                "title": "Google Chrome - Updated",
                "is_multipurpose_app": 1,
                "created_at": "2026-07-08 10:00:00",
                "updated_at": "2026-07-08 12:00:00",
            }
        ]
        repository.upsert_rows("user_app_behavior_log", overwrite_rows)

        # Assert: 只有一条记录，且是被覆盖后的
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT duration, title, is_multipurpose_app FROM user_app_behavior_log "
                "WHERE app = ? AND start_time = ?",
                ("chrome.exe", "2026-07-08 10:00:00"),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 90  # duration 被覆盖
            assert row[1] == "Google Chrome - Updated"
            assert row[2] == 1  # is_multipurpose_app 被覆盖

    def test_upsert_rows_strips_id_for_autoincrement_table(
        self, repository, initialized_db
    ):
        """upsert_rows：AUTOINCREMENT 表传入远程 id 时被剥离，本地 id 为自增值"""
        # Arrange: 传入远程 id=999
        rows = [
            {
                "id": 999,  # 远程 id，应被剥离
                "app": "test_strip.exe",
                "start_time": "2026-07-08 14:00:00",
                "end_time": "2026-07-08 15:00:00",
                "duration": 60,
                "title": "Test Strip App",
                "is_multipurpose_app": 0,
                "created_at": "2026-07-08 14:00:00",
                "updated_at": "2026-07-08 14:00:00",
            }
        ]

        # Act
        repository.upsert_rows("user_app_behavior_log", rows)

        # Assert: 本地 id 不是 999，而是自增值
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM user_app_behavior_log WHERE app = ? AND start_time = ?",
                ("test_strip.exe", "2026-07-08 14:00:00"),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] != 999  # id 不是传入的 999
            assert row[0] >= 1  # id 是自增值

    def test_upsert_rows_raises_data_access_error_on_nonexistent_table(
        self, repository, initialized_db
    ):
        """upsert_rows：表名不在白名单中时抛出 DataAccessError（SQL 注入防护）"""
        # Arrange
        rows = [{"id": "x", "content": "test"}]

        # Act + Assert
        with pytest.raises(DataAccessError):
            repository.upsert_rows("nonexistent_table_xyz", rows)

    def test_upsert_rows_raises_data_access_error_on_invalid_column(
        self, repository, initialized_db
    ):
        """upsert_rows：列名不在白名单中时抛出 DataAccessError（SQL 注入防护）"""
        # Arrange
        rows = [{"id": "todo-bad", "nonexistent_column": "value"}]

        # Act + Assert
        with pytest.raises(DataAccessError):
            repository.upsert_rows("todo_list", rows)


# ==================== Seam 3: get_primary_key_field() ====================


class TestGetPrimaryKeyField:
    """测试 get_primary_key_field() 方法"""

    def test_get_primary_key_field_returns_text_pk_for_mood_entries(self, repository):
        """解析 TEXT 主键：mood_entries -> id"""
        pk = repository.get_primary_key_field("mood_entries")
        assert pk == "id"

    def test_get_primary_key_field_returns_text_pk_for_diary(self, repository):
        """解析 TEXT 主键：diary -> date"""
        pk = repository.get_primary_key_field("diary")
        assert pk == "date"

    def test_get_primary_key_field_returns_text_pk_for_todo_list(self, repository):
        """解析 TEXT 主键：todo_list -> id"""
        pk = repository.get_primary_key_field("todo_list")
        assert pk == "id"

    def test_get_primary_key_field_returns_text_pk_for_behavior_analysis(self, repository):
        """解析 TEXT 主键：behavior_analysis -> start_time"""
        pk = repository.get_primary_key_field("behavior_analysis")
        assert pk == "start_time"

    def test_get_primary_key_field_returns_autoincrement_pk_for_user_app_behavior_log(
        self, repository
    ):
        """解析 AUTOINCREMENT 主键：user_app_behavior_log -> id"""
        pk = repository.get_primary_key_field("user_app_behavior_log")
        assert pk == "id"

    def test_get_primary_key_field_returns_autoincrement_pk_for_timeline_custom_block(
        self, repository
    ):
        """解析 AUTOINCREMENT 主键：timeline_custom_block -> id"""
        pk = repository.get_primary_key_field("timeline_custom_block")
        assert pk == "id"

    def test_get_primary_key_field_returns_autoincrement_pk_for_category_map_cache(
        self, repository
    ):
        """解析 AUTOINCREMENT 主键：category_map_cache -> id"""
        pk = repository.get_primary_key_field("category_map_cache")
        assert pk == "id"

    def test_get_primary_key_field_returns_none_for_nonexistent_table(self, repository):
        """不存在的表：返回 None"""
        pk = repository.get_primary_key_field("nonexistent_table_xyz")
        assert pk is None


# ==================== Seam 4: upsert_rows_with_lww() ====================


class TestUpsertRowsWithLww:
    """测试 upsert_rows_with_lww() 方法"""

    def test_upsert_rows_with_lww_skips_older_data(self, repository, initialized_db):
        """LWW：本地数据更新时跳过传入的旧数据"""
        # Arrange: 先写入新数据（updated_at = 12:00:00）
        new_row = {
            "id": "todo-lww-skip",
            "content": "新内容",
            "state": "completed",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 12:00:00",
        }
        repository.upsert_rows("todo_list", [new_row])

        # Act: 用 LWW 推送更旧的数据（updated_at = 10:00:00）
        old_row = {
            "id": "todo-lww-skip",
            "content": "旧内容",
            "state": "pool",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("todo_list", [old_row])

        # Assert: 旧数据被跳过，返回 0
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, state FROM todo_list WHERE id = ?", ("todo-lww-skip",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "新内容"  # 仍然是新数据
            assert row[1] == "completed"

    def test_upsert_rows_with_lww_writes_newer_data(self, repository, initialized_db):
        """LWW：传入数据更新时覆盖本地旧数据"""
        # Arrange: 先写入旧数据（updated_at = 10:00:00）
        old_row = {
            "id": "todo-lww-overwrite",
            "content": "旧内容",
            "state": "pool",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        repository.upsert_rows("todo_list", [old_row])

        # Act: 用 LWW 推送更新的数据（updated_at = 12:00:00）
        new_row = {
            "id": "todo-lww-overwrite",
            "content": "新内容",
            "state": "completed",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 12:00:00",
        }
        affected = repository.upsert_rows_with_lww("todo_list", [new_row])

        # Assert: 新数据被写入
        assert affected == 1

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?",
                ("todo-lww-overwrite",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "新内容"
            assert row[1] == "completed"

    def test_upsert_rows_with_lww_inserts_new_data(self, repository, initialized_db):
        """LWW：本地不存在记录时直接插入"""
        # Act: 推送新数据（本地不存在）
        new_row = {
            "id": "todo-lww-insert",
            "content": "全新数据",
            "state": "pool",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("todo_list", [new_row])

        # Assert: 新数据被写入
        assert affected == 1

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM todo_list WHERE id = ?", ("todo-lww-insert",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "全新数据"

    def test_upsert_rows_with_lww_returns_zero_for_empty_list(
        self, repository, initialized_db
    ):
        """LWW：空列表返回 0"""
        # Act
        affected = repository.upsert_rows_with_lww("todo_list", [])

        # Assert
        assert affected == 0

    def test_upsert_rows_with_lww_skips_older_data_on_autoincrement_table(
        self, repository, initialized_db
    ):
        """LWW：AUTOINCREMENT + UNIQUE 表也正确跳过旧数据"""
        # Arrange: 先写入新数据
        new_row = {
            "app": "lww_auto.exe",
            "start_time": "2026-07-08 16:00:00",
            "end_time": "2026-07-08 17:00:00",
            "duration": 60,
            "title": "LWW Auto New",
            "is_multipurpose_app": 0,
            "created_at": "2026-07-08 16:00:00",
            "updated_at": "2026-07-08 12:00:00",
        }
        repository.upsert_rows("user_app_behavior_log", [new_row])

        # Act: 推送相同 UNIQUE 键但更旧的数据
        old_row = {
            "app": "lww_auto.exe",
            "start_time": "2026-07-08 16:00:00",
            "end_time": "2026-07-08 17:30:00",
            "duration": 90,
            "title": "LWW Auto Old",
            "is_multipurpose_app": 1,
            "created_at": "2026-07-08 16:00:00",
            "updated_at": "2026-07-08 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("user_app_behavior_log", [old_row])

        # Assert: 旧数据被跳过
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, duration FROM user_app_behavior_log "
                "WHERE app = ? AND start_time = ?",
                ("lww_auto.exe", "2026-07-08 16:00:00"),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "LWW Auto New"  # 仍然是新数据
            assert row[1] == 60

    def test_upsert_rows_with_lww_raises_data_access_error_on_nonexistent_table(
        self, repository, initialized_db
    ):
        """LWW：表名不在白名单中时抛出 DataAccessError"""
        # Arrange
        rows = [{"id": "x", "content": "test", "updated_at": "2026-07-01 10:00:00"}]

        # Act + Assert
        with pytest.raises(DataAccessError):
            repository.upsert_rows_with_lww("nonexistent_table_xyz", rows)


# ==================== Seam 5: get_unique_fields() / _is_autoincrement_table() ====================


class TestGetUniqueFields:
    """测试 get_unique_fields() 方法"""

    def test_get_unique_fields_for_user_app_behavior_log(self, repository):
        """解析 UNIQUE 约束：user_app_behavior_log -> [app, start_time]"""
        fields = repository.get_unique_fields("user_app_behavior_log")
        assert fields == ["app", "start_time"]

    def test_get_unique_fields_for_category_map_cache(self, repository):
        """解析 UNIQUE 约束（带空格格式）：category_map_cache -> [app, title, state]"""
        fields = repository.get_unique_fields("category_map_cache")
        assert fields == ["app", "title", "state"]

    def test_get_unique_fields_for_timeline_custom_block(self, repository):
        """解析 UNIQUE 约束（单字段）：timeline_custom_block -> [start_time]"""
        fields = repository.get_unique_fields("timeline_custom_block")
        assert fields == ["start_time"]

    def test_get_unique_fields_returns_none_for_text_pk_table(self, repository):
        """TEXT 主键表无 UNIQUE 约束：mood_entries -> None"""
        fields = repository.get_unique_fields("mood_entries")
        assert fields is None

    def test_get_unique_fields_returns_none_for_todo_list(self, repository):
        """TEXT 主键表无 UNIQUE 约束：todo_list -> None"""
        fields = repository.get_unique_fields("todo_list")
        assert fields is None


class TestIsAutoincrementTable:
    """测试 _is_autoincrement_table() 方法"""

    def test_is_autoincrement_true_for_user_app_behavior_log(self, repository):
        """AUTOINCREMENT 表：user_app_behavior_log -> True"""
        assert repository._is_autoincrement_table("user_app_behavior_log") is True

    def test_is_autoincrement_true_for_category_map_cache(self, repository):
        """AUTOINCREMENT 表：category_map_cache -> True"""
        assert repository._is_autoincrement_table("category_map_cache") is True

    def test_is_autoincrement_true_for_timeline_custom_block(self, repository):
        """AUTOINCREMENT 表：timeline_custom_block -> True"""
        assert repository._is_autoincrement_table("timeline_custom_block") is True

    def test_is_autoincrement_false_for_mood_entries(self, repository):
        """TEXT 主键表：mood_entries -> False"""
        assert repository._is_autoincrement_table("mood_entries") is False

    def test_is_autoincrement_false_for_todo_list(self, repository):
        """TEXT 主键表：todo_list -> False"""
        assert repository._is_autoincrement_table("todo_list") is False


# ==================== Seam 6: count_rows() / count_rows_batch() ====================


class TestCountRows:
    """测试 count_rows() 和 count_rows_batch() 方法"""

    def test_count_rows_returns_correct_count(self, repository, initialized_db):
        """count_rows：插入 3 条记录，返回 3"""
        # Arrange: 插入 3 条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            for i in range(3):
                cursor.execute(
                    "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        f"count-{i:03d}",
                        "happy",
                        5,
                        "2026-07-01 10:00:00",
                        "2026-07-01 10:00:00",
                    ),
                )
            conn.commit()

        # Act
        count = repository.count_rows("mood_entries")

        # Assert
        assert count == 3

    def test_count_rows_returns_zero_for_empty_table(self, repository, initialized_db):
        """count_rows：空表返回 0"""
        # Act
        count = repository.count_rows("mood_entries")

        # Assert
        assert count == 0

    def test_count_rows_raises_error_for_invalid_table_name(
        self, repository, initialized_db
    ):
        """count_rows：无效表名抛出 DataAccessError（SQL 注入防护）"""
        # Act + Assert
        with pytest.raises(DataAccessError):
            repository.count_rows("nonexistent_table_xyz")

    def test_count_rows_batch_returns_all_tables(self, repository, initialized_db):
        """count_rows_batch：批量查询多张表，返回各表记录数"""
        # Arrange: 向多张表插入数据
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-mood-1", "happy", 5, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-todo-1", "测试任务", "pool", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-todo-2", "测试任务2", "pool", "2026-07-01 11:00:00", "2026-07-01 11:00:00"),
            )
            conn.commit()

        # Act
        table_names = ["mood_entries", "todo_list"]
        result = repository.count_rows_batch(table_names)

        # Assert
        assert isinstance(result, dict)
        assert result["mood_entries"] == 1
        assert result["todo_list"] == 2

    def test_count_rows_batch_returns_zero_for_empty_tables(
        self, repository, initialized_db
    ):
        """count_rows_batch：批量查询空表，全部返回 0"""
        # Act
        table_names = ["mood_entries", "todo_list"]
        result = repository.count_rows_batch(table_names)

        # Assert
        assert isinstance(result, dict)
        assert result["mood_entries"] == 0
        assert result["todo_list"] == 0
