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

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    # 旧数据库可能缺少 hash_id 列（CREATE TABLE IF NOT EXISTS 不添加新列）
    # 用 ALTER TABLE 补列，使测试库与 TABLE_CONFIGS 一致
    # SQLite 不允许 ALTER TABLE ADD COLUMN 带 UNIQUE，分两步：加列 + 建 UNIQUE INDEX
    from lifeprism.sync.constants import HASH_ID_PREFIXES

    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in HASH_ID_PREFIXES:
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "hash_id" not in existing_cols:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN hash_id TEXT")
            # 确保 hash_id 有 UNIQUE 索引（与 TABLE_CONFIGS 的 NOT NULL UNIQUE 一致）
            cursor.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table_name}_hash_id "
                f"ON {table_name}(hash_id)"
            )

        # 确保 table_constraints 中的业务 UNIQUE 约束存在
        # （旧库 CREATE TABLE IF NOT EXISTS 不补约束，需手动创建 UNIQUE INDEX，
        # 否则 INSERT OR REPLACE 不会按业务 UNIQUE 触发替换，与 LWW 查找键不一致）
        from lifeprism.config.database import TABLE_CONFIGS

        # 先清理 sync 表残留数据（上次失败测试可能留下重复行，会阻止 UNIQUE INDEX 创建）
        _sync_tables = [
            "mood_entries", "todo_list", "goal", "diary",
            "timeline_custom_block", "user_app_behavior_log",
            "category_map_cache", "mood_impacts", "time_paradoxes",
            "deletion_log",
        ]
        for t_name in _sync_tables:
            cursor.execute(f'DELETE FROM "{t_name}"')

        for t_name, t_config in TABLE_CONFIGS.items():
            for constraint in t_config.get("table_constraints", []):
                constraint_stripped = constraint.strip()
                if not constraint_stripped.upper().startswith("UNIQUE"):
                    continue
                open_paren = constraint_stripped.find("(")
                close_paren = constraint_stripped.rfind(")")
                if open_paren == -1 or close_paren == -1:
                    continue
                unique_fields = [
                    f.strip()
                    for f in constraint_stripped[open_paren + 1 : close_paren].split(",")
                ]
                # 检查是否已有对应的 UNIQUE 索引
                cursor.execute(f'PRAGMA index_list("{t_name}")')
                has_unique = False
                for idx in cursor.fetchall():
                    if not idx[2]:  # not unique
                        continue
                    cursor.execute(f'PRAGMA index_info("{idx[1]}")')
                    idx_cols = [c[2] for c in cursor.fetchall()]
                    if idx_cols == unique_fields:
                        has_unique = True
                        break
                if not has_unique:
                    # 用 uq_ 前缀避免与 indexes 配置中的非唯一索引同名（IF NOT EXISTS 按名跳过）
                    index_name = f"uq_{t_name}_" + "_".join(unique_fields)
                    cursor.execute(
                        f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} '
                        f'ON {t_name}({", ".join(unique_fields)})'
                    )
        conn.commit()

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
        "mood_impacts",
        "time_paradoxes",
        "deletion_log",
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

    def test_query_incremental_returns_all_when_last_sync_is_empty(
        self, repository, initialized_db
    ):
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

    def test_upsert_rows_strips_id_for_autoincrement_table(self, repository, initialized_db):
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

    def test_upsert_rows_with_lww_returns_zero_for_empty_list(self, repository, initialized_db):
        """LWW：空列表返回 0"""
        # Act
        affected = repository.upsert_rows_with_lww("todo_list", [])

        # Assert
        assert affected == 0

    def test_upsert_rows_with_lww_skips_older_data_on_autoincrement_table(
        self, repository, initialized_db
    ):
        """LWW：AUTOINCREMENT 表用业务 UNIQUE 去重，正确跳过旧数据（不同 hash_id + 相同业务键）"""
        # Arrange: 先写入新数据（包含 hash_id）
        new_row = {
            "hash_id": "awbl-lww-auto-001",
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

        # Act: 推送不同 hash_id、相同业务键 (app, start_time)、更旧的 updated_at
        # LWW 按 (app, start_time) 匹配 → 找到已有记录 → updated_at 更旧 → 跳过
        old_row = {
            "hash_id": "awbl-lww-auto-002",  # 不同的 hash_id
            "app": "lww_auto.exe",
            "start_time": "2026-07-08 16:00:00",  # 相同的业务 UNIQUE 键
            "end_time": "2026-07-08 17:30:00",
            "duration": 90,
            "title": "LWW Auto Old",
            "is_multipurpose_app": 1,
            "created_at": "2026-07-08 16:00:00",
            "updated_at": "2026-07-08 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("user_app_behavior_log", [old_row])

        # Assert: 旧数据被跳过（LWW 按业务 UNIQUE 匹配，updated_at 更旧）
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, duration FROM user_app_behavior_log "
                "WHERE hash_id = ?",
                ("awbl-lww-auto-001",),
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


# ==================== Seam 4b: batch_get_existing_updated_at() ====================


class TestBatchGetExistingUpdatedAt:
    """测试 batch_get_existing_updated_at() 方法"""

    def test_batch_get_existing_updated_at_returns_correct_mapping(
        self, repository, initialized_db
    ):
        """批量查询：返回正确的 {pk_value: updated_at} 映射"""
        # Arrange: 插入 3 条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-001", "happy", 5, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-002", "calm", 7, "2026-07-01 11:00:00", "2026-07-01 11:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-003", "joy", 9, "2026-07-01 12:00:00", "2026-07-01 12:00:00"),
            )
            conn.commit()

        # Act: 批量查询 3 个主键
        pk_values = ["batch-001", "batch-002", "batch-003"]
        result = repository.batch_get_existing_updated_at("mood_entries", "id", pk_values)

        # Assert: 返回正确的映射
        assert isinstance(result, dict)
        assert len(result) == 3
        assert result["batch-001"] == "2026-07-01 10:00:00"
        assert result["batch-002"] == "2026-07-01 11:00:00"
        assert result["batch-003"] == "2026-07-01 12:00:00"

    def test_batch_get_existing_updated_at_returns_empty_for_empty_pk_values(
        self, repository, initialized_db
    ):
        """批量查询：空 pk_values 列表返回空 dict"""
        # Act
        result = repository.batch_get_existing_updated_at("mood_entries", "id", [])

        # Assert
        assert result == {}

    def test_batch_get_existing_updated_at_excludes_nonexistent_pk(
        self, repository, initialized_db
    ):
        """批量查询：不存在的 pk 不在返回结果中"""
        # Arrange: 只插入 1 条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("batch-exist", "happy", 5, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # Act: 查询 1 个存在 + 2 个不存在的 pk
        pk_values = ["batch-exist", "nonexistent-001", "nonexistent-002"]
        result = repository.batch_get_existing_updated_at("mood_entries", "id", pk_values)

        # Assert: 只有存在的 pk 在结果中
        assert len(result) == 1
        assert "batch-exist" in result
        assert "nonexistent-001" not in result
        assert "nonexistent-002" not in result
        assert result["batch-exist"] == "2026-07-01 10:00:00"


# ==================== Seam 5: get_unique_fields() / _is_autoincrement_table() ====================


class TestGetUniqueFields:
    """测试 get_unique_fields() 方法"""

    def test_get_unique_fields_for_user_app_behavior_log(self, repository):
        """业务 UNIQUE 优先于 hash_id：user_app_behavior_log -> [app, start_time]"""
        fields = repository.get_unique_fields("user_app_behavior_log")
        assert fields == ["app", "start_time"]

    def test_get_unique_fields_for_category_map_cache(self, repository):
        """解析 UNIQUE 约束（带空格格式）：category_map_cache -> [app, title, state]"""
        fields = repository.get_unique_fields("category_map_cache")
        assert fields == ["app", "title", "state"]

    def test_get_unique_fields_for_timeline_custom_block(self, repository):
        """业务 UNIQUE 优先于 hash_id：timeline_custom_block -> [start_time]"""
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

    def test_count_rows_raises_error_for_invalid_table_name(self, repository, initialized_db):
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

    def test_count_rows_batch_returns_zero_for_empty_tables(self, repository, initialized_db):
        """count_rows_batch：批量查询空表，全部返回 0"""
        # Act
        table_names = ["mood_entries", "todo_list"]
        result = repository.count_rows_batch(table_names)

        # Assert
        assert isinstance(result, dict)
        assert result["mood_entries"] == 0
        assert result["todo_list"] == 0


# ==================== Seam 7: hash_id 同步去重（HASH_ID_PREFIXES 表） ====================


class TestHashIdSyncDedup:
    """测试 HASH_ID_PREFIXES 中的表的同步去重逻辑

    覆盖 Issue 04 + Issue 1 修复（代码审查回归）:
    - get_unique_fields 优先返回业务 UNIQUE（table_constraints），无业务 UNIQUE 时回退 hash_id
    - upsert_rows_with_lww 用业务 UNIQUE 去重（与 INSERT OR REPLACE 键一致）
    - 不同 hash_id + 相同业务 UNIQUE → LWW 正确保护较新数据（Issue 1 回归测试）
    - mood_impacts 返回业务 UNIQUE(name)，LWW 与 INSERT OR REPLACE 冲突键一致
    - TEXT 主键表不受影响
    """

    def test_get_unique_fields_returns_business_unique_for_timeline_custom_block(self, repository):
        """get_unique_fields: timeline_custom_block 有业务 UNIQUE(start_time) → 返回 ["start_time"]"""
        fields = repository.get_unique_fields("timeline_custom_block")
        assert fields == ["start_time"]

    def test_get_unique_fields_returns_business_unique_for_user_app_behavior_log(self, repository):
        """get_unique_fields: user_app_behavior_log 有业务 UNIQUE(app, start_time) → 返回业务键"""
        fields = repository.get_unique_fields("user_app_behavior_log")
        assert fields == ["app", "start_time"]

    def test_get_unique_fields_returns_business_unique_for_time_paradoxes(self, repository):
        """get_unique_fields: time_paradoxes 有业务 UNIQUE(user_id, mode, version) → 返回业务键"""
        fields = repository.get_unique_fields("time_paradoxes")
        assert fields == ["user_id", "mode", "version"]

    def test_get_unique_fields_returns_business_unique_for_mood_impacts(self, repository):
        """get_unique_fields: mood_impacts 有业务 UNIQUE(name) → 返回 ["name"]"""
        fields = repository.get_unique_fields("mood_impacts")
        assert fields == ["name"]

    # ---------- upsert_rows_with_lww: 保留 hash_id + 剥离 id ----------

    def test_upsert_rows_with_lww_preserves_hash_id(self, repository, initialized_db):
        """upsert_rows_with_lww: 对 HASH_ID_PREFIXES 表保留 hash_id 字段（不剥离）"""
        # Act: 推送一条带 hash_id 的新记录
        new_row = {
            "hash_id": "tcb-preserve-001",
            "start_time": "2026-07-15T10:00:00",
            "end_time": "2026-07-15T11:00:00",
            "duration": 60,
            "content": "保留 hash_id 测试",
            "color": "#FF0000",
            "created_at": "2026-07-15 10:00:00",
            "updated_at": "2026-07-15 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("timeline_custom_block", [new_row])

        # Assert: 写入成功
        assert affected == 1

        # Assert: hash_id 被保留在数据库中
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id, content FROM timeline_custom_block WHERE hash_id = ?",
                ("tcb-preserve-001",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "tcb-preserve-001"  # hash_id 保留
            assert row[1] == "保留 hash_id 测试"

    def test_upsert_rows_with_lww_strips_id_for_hash_id_table(self, repository, initialized_db):
        """upsert_rows_with_lww: 对 HASH_ID_PREFIXES 表仍然剥离 id（不污染 sqlite_sequence）"""
        # Act: 推送一条带远程 id=999 的新记录
        new_row = {
            "id": 999,  # 远程 id，应被剥离
            "hash_id": "tcb-strip-id-001",
            "start_time": "2026-07-15T14:00:00",
            "end_time": "2026-07-15T15:00:00",
            "duration": 60,
            "content": "剥离 id 测试",
            "color": "#00FF00",
            "created_at": "2026-07-15 14:00:00",
            "updated_at": "2026-07-15 14:00:00",
        }
        affected = repository.upsert_rows_with_lww("timeline_custom_block", [new_row])

        # Assert: 写入成功
        assert affected == 1

        # Assert: 本地 id 不是 999，而是自增值
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM timeline_custom_block WHERE hash_id = ?",
                ("tcb-strip-id-001",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] != 999  # id 被剥离
            assert row[0] >= 1  # 是自增值

    # ---------- Issue 1 回归测试：不同 hash_id + 相同业务 UNIQUE ----------

    def test_lww_skips_older_data_same_business_unique_diff_hash_id(self, repository, initialized_db):
        """回归测试 (Issue 1): 不同 hash_id + 相同业务 UNIQUE → LWW 正确跳过旧数据

        场景: 两设备独立创建相同业务键、不同 hash_id 的记录
        - 本地: start_time=X, hash_id=hashA, updated_at=T2 (新)
        - 远程: start_time=X, hash_id=hashB, updated_at=T1 (旧)
        预期: LWW 按 start_time 匹配 → T1 < T2 → 跳过 → 本地新数据保留
        修复前: LWW 按 hash_id 查找 → 不匹配 → 放行 → INSERT OR REPLACE 删新插旧
        """
        # Arrange: 先写入新数据
        new_row = {
            "hash_id": "tcb-lww-new-001",
            "start_time": "2026-07-16T10:00:00",
            "end_time": "2026-07-16T11:00:00",
            "duration": 60,
            "content": "新内容",
            "color": "#FF0000",
            "created_at": "2026-07-16 10:00:00",
            "updated_at": "2026-07-16 12:00:00",
        }
        repository.upsert_rows("timeline_custom_block", [new_row])

        # Act: 推送不同 hash_id、相同 start_time、更旧的 updated_at
        old_row = {
            "hash_id": "tcb-lww-old-001",  # 不同的 hash_id
            "start_time": "2026-07-16T10:00:00",  # 相同的业务 UNIQUE 键
            "end_time": "2026-07-16T12:00:00",
            "duration": 120,
            "content": "旧内容",
            "color": "#00FF00",
            "created_at": "2026-07-16 10:00:00",
            "updated_at": "2026-07-16 10:00:00",  # 更旧
        }
        affected = repository.upsert_rows_with_lww("timeline_custom_block", [old_row])

        # Assert: 旧数据被跳过（LWW 正确匹配到业务 UNIQUE）
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, hash_id FROM timeline_custom_block WHERE start_time = ?",
                ("2026-07-16T10:00:00",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "新内容"  # 仍然是新数据
            assert row[1] == "tcb-lww-new-001"  # hash_id 未被覆盖

    def test_lww_writes_newer_data_same_business_unique_diff_hash_id(self, repository, initialized_db):
        """回归测试 (Issue 1): 不同 hash_id + 相同业务 UNIQUE → LWW 正确写入新数据

        场景: 远程数据更新 → 应替换本地旧数据
        - 本地: start_time=X, hash_id=hashA, updated_at=T1 (旧)
        - 远程: start_time=X, hash_id=hashB, updated_at=T2 (新)
        预期: LWW 按 start_time 匹配 → T2 > T1 → 写入 → 新数据替换旧数据
        """
        # Arrange: 先写入旧数据
        old_row = {
            "hash_id": "tcb-lww-old-002",
            "start_time": "2026-07-17T10:00:00",
            "end_time": "2026-07-17T11:00:00",
            "duration": 60,
            "content": "旧内容",
            "color": "#FF0000",
            "created_at": "2026-07-17 10:00:00",
            "updated_at": "2026-07-17 10:00:00",
        }
        repository.upsert_rows("timeline_custom_block", [old_row])

        # Act: 推送不同 hash_id、相同 start_time、更新的 updated_at
        new_row = {
            "hash_id": "tcb-lww-new-002",  # 不同的 hash_id
            "start_time": "2026-07-17T10:00:00",  # 相同的业务 UNIQUE 键
            "end_time": "2026-07-17T12:00:00",
            "duration": 120,
            "content": "新内容",
            "color": "#00FF00",
            "created_at": "2026-07-17 10:00:00",
            "updated_at": "2026-07-17 12:00:00",  # 更新
        }
        affected = repository.upsert_rows_with_lww("timeline_custom_block", [new_row])

        # Assert: 新数据被写入
        assert affected == 1

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, hash_id FROM timeline_custom_block WHERE start_time = ?",
                ("2026-07-17T10:00:00",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "新内容"  # 新数据
            assert row[1] == "tcb-lww-new-002"  # hash_id 被更新为新值

    def test_lww_skips_older_data_same_name_diff_hash_id_on_mood_impacts(
        self, repository, initialized_db
    ):
        """mood_impacts：相同 name、不同 hash_id 时，LWW 跳过较旧数据"""
        local_newer = {
            "id": 101,
            "hash_id": "mi-local-newer-001",
            "name": "工作-LWW-旧数据跳过",
            "sort_order": 20,
            "created_at": "2026-07-23 10:00:00",
            "updated_at": "2026-07-23 12:00:00",
        }
        repository.upsert_rows("mood_impacts", [local_newer])

        remote_older = {
            "id": 202,
            "hash_id": "mi-remote-older-001",
            "name": "工作-LWW-旧数据跳过",
            "sort_order": 5,
            "created_at": "2026-07-23 09:00:00",
            "updated_at": "2026-07-23 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("mood_impacts", [remote_older])

        assert affected == 0
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id, name, sort_order, updated_at FROM mood_impacts WHERE name = ?",
                ("工作-LWW-旧数据跳过",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "mi-local-newer-001"
            assert row[1] == "工作-LWW-旧数据跳过"
            assert row[2] == 20
            assert row[3] == "2026-07-23 12:00:00"

    def test_lww_writes_newer_data_same_name_diff_hash_id_on_mood_impacts(
        self, repository, initialized_db
    ):
        """mood_impacts：相同 name、不同 hash_id 时，LWW 写入较新数据"""
        local_older = {
            "id": 303,
            "hash_id": "mi-local-older-001",
            "name": "健康-LWW-新数据写入",
            "sort_order": 5,
            "created_at": "2026-07-23 09:00:00",
            "updated_at": "2026-07-23 10:00:00",
        }
        repository.upsert_rows("mood_impacts", [local_older])

        remote_newer = {
            "id": 404,
            "hash_id": "mi-remote-newer-001",
            "name": "健康-LWW-新数据写入",
            "sort_order": 30,
            "created_at": "2026-07-23 09:00:00",
            "updated_at": "2026-07-23 12:00:00",
        }
        affected = repository.upsert_rows_with_lww("mood_impacts", [remote_newer])

        assert affected == 1
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id, name, sort_order, updated_at FROM mood_impacts WHERE name = ?",
                ("健康-LWW-新数据写入",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "mi-remote-newer-001"
            assert row[1] == "健康-LWW-新数据写入"
            assert row[2] == 30
            assert row[3] == "2026-07-23 12:00:00"

    def test_lww_skips_older_data_same_business_unique_diff_hash_id_on_time_paradoxes(
        self, repository, initialized_db
    ):
        """time_paradoxes：相同 (user_id,mode,version)、不同 hash_id 时，LWW 跳过较旧数据"""
        local_newer = {
            "hash_id": "tp-local-newer-001",
            "user_id": 1,
            "mode": "past",
            "version": 1,
            "content": '{"local": "newer"}',
            "ai_abstract": None,
            "created_at": "2026-07-23 10:00:00",
            "updated_at": "2026-07-23 12:00:00",
        }
        repository.upsert_rows("time_paradoxes", [local_newer])

        remote_older = {
            "hash_id": "tp-remote-older-001",
            "user_id": 1,
            "mode": "past",
            "version": 1,
            "content": '{"remote": "older"}',
            "ai_abstract": None,
            "created_at": "2026-07-23 09:00:00",
            "updated_at": "2026-07-23 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("time_paradoxes", [remote_older])

        assert affected == 0
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id, content, updated_at FROM time_paradoxes "
                "WHERE user_id = ? AND mode = ? AND version = ?",
                (1, "past", 1),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "tp-local-newer-001"
            assert row[1] == '{"local": "newer"}'
            assert row[2] == "2026-07-23 12:00:00"

    def test_lww_writes_newer_data_same_business_unique_diff_hash_id_on_time_paradoxes(
        self, repository, initialized_db
    ):
        """time_paradoxes：相同 (user_id,mode,version)、不同 hash_id 时，LWW 写入较新数据"""
        local_older = {
            "hash_id": "tp-local-older-001",
            "user_id": 2,
            "mode": "future",
            "version": 1,
            "content": '{"local": "older"}',
            "ai_abstract": None,
            "created_at": "2026-07-23 09:00:00",
            "updated_at": "2026-07-23 10:00:00",
        }
        repository.upsert_rows("time_paradoxes", [local_older])

        remote_newer = {
            "hash_id": "tp-remote-newer-001",
            "user_id": 2,
            "mode": "future",
            "version": 1,
            "content": '{"remote": "newer"}',
            "ai_abstract": "AI总结",
            "created_at": "2026-07-23 09:00:00",
            "updated_at": "2026-07-23 12:00:00",
        }
        affected = repository.upsert_rows_with_lww("time_paradoxes", [remote_newer])

        assert affected == 1
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id, content, ai_abstract, updated_at FROM time_paradoxes "
                "WHERE user_id = ? AND mode = ? AND version = ?",
                (2, "future", 1),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "tp-remote-newer-001"
            assert row[1] == '{"remote": "newer"}'
            assert row[2] == "AI总结"
            assert row[3] == "2026-07-23 12:00:00"

    # ---------- _batch_get_existing_updated_at_by_unique / _find_existing_updated_at ----------

    def test_batch_get_existing_updated_at_by_business_unique(self, repository, initialized_db):
        """_batch_get_existing_updated_at_by_unique: 按业务 UNIQUE (start_time) 查询"""
        # Arrange: 插入 2 条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO timeline_custom_block "
                "(hash_id, start_time, end_time, duration, content, color, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "tcb-batch-001",
                    "2026-07-20T10:00:00",
                    "2026-07-20T11:00:00",
                    60,
                    "batch1",
                    "#FF0000",
                    "2026-07-20 10:00:00",
                    "2026-07-20 10:00:00",
                ),
            )
            cursor.execute(
                "INSERT INTO timeline_custom_block "
                "(hash_id, start_time, end_time, duration, content, color, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "tcb-batch-002",
                    "2026-07-20T12:00:00",
                    "2026-07-20T13:00:00",
                    60,
                    "batch2",
                    "#00FF00",
                    "2026-07-20 12:00:00",
                    "2026-07-20 12:00:00",
                ),
            )
            conn.commit()

        # Act: 按 start_time 批量查询
        rows = [
            {"start_time": "2026-07-20T10:00:00"},
            {"start_time": "2026-07-20T12:00:00"},
            {"start_time": "2026-07-20T99:00:00"},  # 不存在
        ]
        result = repository._batch_get_existing_updated_at_by_unique(
            "timeline_custom_block", ["start_time"], rows
        )

        # Assert: 返回正确的映射
        assert len(result) == 2
        assert result[("2026-07-20T10:00:00",)] == "2026-07-20 10:00:00"
        assert result[("2026-07-20T12:00:00",)] == "2026-07-20 12:00:00"
        assert ("2026-07-20T99:00:00",) not in result

    def test_batch_get_existing_updated_at_by_hash_id_empty_rows(self, repository):
        """_batch_get_existing_updated_at_by_unique: 空 rows 返回空 dict"""
        result = repository._batch_get_existing_updated_at_by_unique(
            "timeline_custom_block", ["start_time"], []
        )
        assert result == {}

    def test_find_existing_updated_at_by_business_unique(self, repository, initialized_db):
        """_find_existing_updated_at: 自动用业务 UNIQUE (start_time) 查找（依赖 get_unique_fields）"""
        # Arrange: 插入一条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO timeline_custom_block "
                "(hash_id, start_time, end_time, duration, content, color, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "tcb-find-001",
                    "2026-07-21T10:00:00",
                    "2026-07-21T11:00:00",
                    60,
                    "find test",
                    "#FF0000",
                    "2026-07-21 10:00:00",
                    "2026-07-21 10:00:00",
                ),
            )
            conn.commit()

        # Act: 查找已存在记录（get_unique_fields 返回 ["start_time"]，按 start_time 查找）
        result = repository._find_existing_updated_at(
            "timeline_custom_block", {"start_time": "2026-07-21T10:00:00"}
        )

        # Assert: 返回正确的 updated_at
        assert result == "2026-07-21 10:00:00"

    def test_find_existing_updated_at_returns_none_for_nonexistent(self, repository):
        """_find_existing_updated_at: 业务 UNIQUE 不存在时返回 None"""
        result = repository._find_existing_updated_at(
            "timeline_custom_block", {"start_time": "2099-01-01T00:00:00"}
        )
        assert result is None

    # ---------- TEXT 主键表 / 非 HASH_ID_PREFIXES 表不受影响 ----------

    def test_get_unique_fields_returns_none_for_diary(self, repository):
        """TEXT 主键表（不在 HASH_ID_PREFIXES）：diary -> None"""
        fields = repository.get_unique_fields("diary")
        assert fields is None

    def test_get_unique_fields_returns_original_unique_for_category_map_cache(self, repository):
        """非 HASH_ID_PREFIXES 的 AUTOINCREMENT+UNIQUE 表：category_map_cache -> [app, title, state]"""
        fields = repository.get_unique_fields("category_map_cache")
        assert fields == ["app", "title", "state"]

    def test_upsert_rows_with_lww_works_for_text_pk_table(self, repository, initialized_db):
        """TEXT 主键表（diary）LWW 逻辑不受 hash_id 改造影响"""
        # Arrange: 先写入新数据
        new_row = {
            "date": "2026-07-20",
            "mood": "happy",
            "importance": "important",
            "created_at": "2026-07-20 10:00:00",
            "updated_at": "2026-07-20 12:00:00",
        }
        repository.upsert_rows("diary", [new_row])

        # Act: 推送更旧的数据
        old_row = {
            "date": "2026-07-20",
            "mood": "bad",
            "importance": "unimportant",
            "created_at": "2026-07-20 10:00:00",
            "updated_at": "2026-07-20 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("diary", [old_row])

        # Assert: 旧数据被跳过（TEXT 主键路径仍按 date 去重）
        assert affected == 0

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mood FROM diary WHERE date = ?", ("2026-07-20",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "happy"  # 仍然是新数据

    # ---------- deletion_log: 业务 UNIQUE 跨端去重 ----------

    def test_get_unique_fields_returns_business_unique_for_deletion_log(self, repository):
        """deletion_log 有业务 UNIQUE(target_table, record_id) → 返回业务键"""
        fields = repository.get_unique_fields("deletion_log")
        assert fields == ["target_table", "record_id"]

    def test_lww_dedupes_duplicate_tombstones_same_target_table_record_id(
        self, repository, initialized_db
    ):
        """deletion_log: 两设备删除同一记录生成不同 dl-* 主键墓碑，LWW 按 (target_table, record_id) 去重"""
        # Arrange: 设备 A 先删除（旧墓碑）
        tombstone_a = {
            "id": "dl-a-001",
            "target_table": "todo_list",
            "record_id": "t-abc123",
            "source": "local",
            "created_at": "2026-07-23 10:00:00",
            "updated_at": "2026-07-23 10:00:00",
        }
        repository.upsert_rows("deletion_log", [tombstone_a])

        # Act: 设备 B 后删除（新墓碑，不同主键，相同业务键）
        tombstone_b = {
            "id": "dl-b-002",
            "target_table": "todo_list",
            "record_id": "t-abc123",
            "source": "cloud",
            "created_at": "2026-07-23 12:00:00",
            "updated_at": "2026-07-23 12:00:00",
        }
        affected = repository.upsert_rows_with_lww("deletion_log", [tombstone_b])

        # Assert: 新墓碑覆盖旧墓碑（LWW 写入较新数据）
        assert affected == 1
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, source, updated_at FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("todo_list", "t-abc123"),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "dl-b-002"  # 新墓碑覆盖旧墓碑
            assert row[1] == "cloud"
            assert row[2] == "2026-07-23 12:00:00"

    def test_lww_skips_older_tombstone_same_target_table_record_id(
        self, repository, initialized_db
    ):
        """deletion_log: 旧墓碑推送时被 LWW 跳过（本地已有新墓碑）"""
        # Arrange: 本地已有新墓碑
        new_tombstone = {
            "id": "dl-new-001",
            "target_table": "mood_entries",
            "record_id": "mood-xyz",
            "source": "local",
            "created_at": "2026-07-23 12:00:00",
            "updated_at": "2026-07-23 12:00:00",
        }
        repository.upsert_rows("deletion_log", [new_tombstone])

        # Act: 推送旧墓碑（不同主键，相同业务键，更旧的 updated_at）
        old_tombstone = {
            "id": "dl-old-001",
            "target_table": "mood_entries",
            "record_id": "mood-xyz",
            "source": "cloud",
            "created_at": "2026-07-23 10:00:00",
            "updated_at": "2026-07-23 10:00:00",
        }
        affected = repository.upsert_rows_with_lww("deletion_log", [old_tombstone])

        # Assert: 旧墓碑被跳过
        assert affected == 0
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("mood_entries", "mood-xyz"),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "dl-new-001"  # 仍然是新墓碑
