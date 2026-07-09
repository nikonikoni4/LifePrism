"""
动态自定义记录表同步测试（Issue #10 修复验证）

测试 seam:
- Seam 1: _is_dynamic_table() - 动态表识别
- Seam 2: _validate_table_name() - 动态表白名单放行
- Seam 3: _validate_columns() - 动态表跳过列验证
- Seam 4: get_primary_key_field() - 动态表主键返回 "id"
- Seam 5: has_updated_at() - 动态表返回 True
- Seam 6: query_incremental() - 动态表增量查询端到端
- Seam 7: upsert_rows_with_lww() - 动态表 LWW 写入端到端

参考: test/core/integration/repository/test_sync_repository.py
"""

import sqlite3

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

    LWBaseDataProvider = __import__(
        "lifeprism.repository.base_providers.lw_base_data_provider",
        fromlist=["LWBaseDataProvider"],
    ).LWBaseDataProvider
    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def sync_repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo


@pytest.fixture
def dynamic_table(initialized_db):
    """创建一个动态表 custom_sport 用于测试

    表结构模拟 CustomRecordRepository.create_type() 生成的 DDL：
    - id TEXT PRIMARY KEY
    - activity TEXT（用户定义字段）
    - duration TEXT（用户定义字段）
    - created_at TEXT
    - updated_at TEXT
    """
    table_name = "custom_sport"
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute(
            f"CREATE TABLE {table_name} ("
            "id TEXT PRIMARY KEY, "
            "activity TEXT, "
            "duration TEXT, "
            "created_at TEXT, "
            "updated_at TEXT)"
        )
        conn.commit()

    yield table_name

    # Teardown
    with initialized_db.get_connection() as conn:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()


@pytest.fixture
def clean_dynamic_table(initialized_db):
    """清理动态表数据（测试后执行）"""
    yield
    with initialized_db.get_connection() as conn:
        conn.execute("DELETE FROM custom_sport")
        conn.commit()


# ==================== Seam 1: _is_dynamic_table() ====================


class TestIsDynamicTable:
    """Seam 1: _is_dynamic_table() - 动态表识别"""

    def test_dynamic_table_identified(self, sync_repository):
        """custom_sport 被识别为动态表"""
        # Act
        result = sync_repository._is_dynamic_table("custom_sport")

        # Assert
        assert result is True

    def test_static_meta_table_not_dynamic(self, sync_repository):
        """custom_record_types 不被识别为动态表（在 TABLE_CONFIGS 中）"""
        # Act
        result = sync_repository._is_dynamic_table("custom_record_types")

        # Assert
        assert result is False

    def test_static_data_table_not_dynamic(self, sync_repository):
        """diary 不被识别为动态表"""
        # Act
        result = sync_repository._is_dynamic_table("diary")

        # Assert
        assert result is False

    def test_nonexistent_table_not_dynamic(self, sync_repository):
        """不存在的表不被识别为动态表（不以 custom_ 开头）"""
        # Act
        result = sync_repository._is_dynamic_table("nonexistent_table")

        # Assert
        assert result is False


# ==================== Seam 2: _validate_table_name() ====================


class TestValidateTableNameDynamic:
    """Seam 2: _validate_table_name() - 动态表白名单放行"""

    def test_dynamic_table_passes_validation(self, sync_repository):
        """动态表 custom_sport 通过验证（不抛异常）"""
        # Act + Assert: 不抛异常
        sync_repository._validate_table_name("custom_sport")

    def test_static_table_passes_validation(self, sync_repository):
        """静态表 diary 通过验证"""
        # Act + Assert: 不抛异常
        sync_repository._validate_table_name("diary")

    def test_non_custom_table_still_rejected(self, sync_repository):
        """非 custom_ 前缀的未知表仍被拒绝"""
        # Act + Assert
        from lifeprism.utils.exceptions import DataAccessError

        with pytest.raises(DataAccessError, match="无效的表名"):
            sync_repository._validate_table_name("nonexistent_table")


# ==================== Seam 3: _validate_columns() ====================


class TestValidateColumnsDynamic:
    """Seam 3: _validate_columns() - 动态表跳过列验证"""

    def test_dynamic_table_skips_column_validation(self, sync_repository):
        """动态表的列验证被跳过（不抛异常）"""
        # Act + Assert: 任意列名都不抛异常
        sync_repository._validate_columns("custom_sport", ["id", "activity", "unknown_col"])

    def test_static_table_still_validates_columns(self, sync_repository):
        """静态表的列验证仍然生效"""
        # Act + Assert
        from lifeprism.utils.exceptions import DataAccessError

        with pytest.raises(DataAccessError, match="无效的列名"):
            sync_repository._validate_columns("diary", ["nonexistent_column"])


# ==================== Seam 4: get_primary_key_field() ====================


class TestGetPrimaryKeyFieldDynamic:
    """Seam 4: get_primary_key_field() - 动态表主键返回 'id'"""

    def test_dynamic_table_returns_id(self, sync_repository):
        """动态表 custom_sport 的主键返回 'id'"""
        # Act
        pk = sync_repository.get_primary_key_field("custom_sport")

        # Assert
        assert pk == "id"

    def test_static_table_returns_correct_pk(self, sync_repository):
        """静态表 mood_entries 的主键仍正确返回"""
        # Act
        pk = sync_repository.get_primary_key_field("mood_entries")

        # Assert: mood_entries 的主键是 id
        assert pk == "id"

    def test_nonexistent_table_returns_none(self, sync_repository):
        """不在 TABLE_CONFIGS 中的非动态表返回 None"""
        # Act
        pk = sync_repository.get_primary_key_field("nonexistent_table")

        # Assert
        assert pk is None


# ==================== Seam 5: has_updated_at() ====================


class TestHasUpdatedAtDynamic:
    """Seam 5: has_updated_at() - 动态表返回 True"""

    def test_dynamic_table_has_updated_at(self, sync_repository):
        """动态表 custom_sport 有 updated_at 列"""
        # Act
        result = sync_repository.has_updated_at("custom_sport")

        # Assert
        assert result is True

    def test_static_table_without_updated_at(self, sync_repository):
        """静态表 mood_types 无 updated_at（配置 update_at=False）"""
        # Act
        result = sync_repository.has_updated_at("mood_types")

        # Assert
        assert result is False


# ==================== Seam 6: query_incremental() 端到端 ====================


class TestQueryIncrementalDynamicTable:
    """Seam 6: query_incremental() - 动态表增量查询端到端"""

    def test_query_incremental_returns_all_when_empty_last_sync(
        self, sync_repository, dynamic_table, initialized_db
    ):
        """空 last_sync_time 返回动态表全部记录"""
        # Arrange: 插入测试数据
        with initialized_db.get_connection() as conn:
            conn.execute(
                f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("cre-001", "running", "30min", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.execute(
                f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("cre-002", "swimming", "45min", "2026-07-01 11:00:00", "2026-07-01 11:00:00"),
            )
            conn.commit()

        # Act
        rows = sync_repository.query_incremental(dynamic_table, "")

        # Assert
        assert len(rows) == 2
        activities = {row["activity"] for row in rows}
        assert activities == {"running", "swimming"}

    def test_query_incremental_filters_by_last_sync(
        self, sync_repository, dynamic_table, initialized_db
    ):
        """last_sync_time 过滤增量记录"""
        # Arrange: 插入测试数据
        with initialized_db.get_connection() as conn:
            conn.execute(
                f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("cre-001", "running", "30min", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.execute(
                f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("cre-002", "swimming", "45min", "2026-07-01 11:00:00", "2026-07-02 12:00:00"),
            )
            conn.commit()

        # Act: 只查询 2026-07-01 12:00:00 之后的记录
        rows = sync_repository.query_incremental(dynamic_table, "2026-07-01 12:00:00")

        # Assert: 只返回 swimming
        assert len(rows) == 1
        assert rows[0]["activity"] == "swimming"

    def test_query_incremental_supports_pagination(
        self, sync_repository, dynamic_table, initialized_db
    ):
        """动态表支持分页查询"""
        # Arrange: 插入 3 条记录
        with initialized_db.get_connection() as conn:
            for i in range(3):
                conn.execute(
                    f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        f"cre-00{i}",
                        f"activity_{i}",
                        f"{i*10}min",
                        "2026-07-01 10:00:00",
                        f"2026-07-01 1{i}:00:00",
                    ),
                )
            conn.commit()

        # Act: 第一页（limit=2, offset=0）
        page1 = sync_repository.query_incremental(dynamic_table, "", offset=0, limit=2)
        # 第二页（limit=2, offset=2）
        page2 = sync_repository.query_incremental(dynamic_table, "", offset=2, limit=2)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 1


# ==================== Seam 7: upsert_rows_with_lww() 端到端 ====================


class TestUpsertRowsWithLwwDynamicTable:
    """Seam 7: upsert_rows_with_lww() - 动态表 LWW 写入端到端"""

    def test_upsert_inserts_new_rows(self, sync_repository, dynamic_table):
        """动态表插入新记录"""
        # Arrange
        rows = [
            {
                "id": "cre-001",
                "activity": "running",
                "duration": "30min",
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-01 10:00:00",
            },
            {
                "id": "cre-002",
                "activity": "swimming",
                "duration": "45min",
                "created_at": "2026-07-01 11:00:00",
                "updated_at": "2026-07-01 11:00:00",
            },
        ]

        # Act
        written = sync_repository.upsert_rows_with_lww(dynamic_table, rows)

        # Assert
        assert written == 2

    def test_upsert_lww_skips_older_data(self, sync_repository, dynamic_table, initialized_db):
        """LWW：远程数据比本地旧时跳过"""
        # Arrange: 本地已有记录，updated_at 较新
        with initialized_db.get_connection() as conn:
            conn.execute(
                f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("cre-001", "running", "30min", "2026-07-01 10:00:00", "2026-07-02 12:00:00"),
            )
            conn.commit()

        # 远程数据 updated_at 较旧
        remote_rows = [
            {
                "id": "cre-001",
                "activity": "running_old",
                "duration": "20min",
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-01 10:00:00",  # 比本地旧
            }
        ]

        # Act
        written = sync_repository.upsert_rows_with_lww(dynamic_table, remote_rows)

        # Assert: 跳过（written=0），本地数据不变
        assert written == 0
        with initialized_db.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT activity FROM {dynamic_table} WHERE id = ?",
                ("cre-001",),
            )
            assert cursor.fetchone()[0] == "running"

    def test_upsert_lww_overwrites_when_newer(self, sync_repository, dynamic_table, initialized_db):
        """LWW：远程数据比本地新时覆盖"""
        # Arrange: 本地已有记录，updated_at 较旧
        with initialized_db.get_connection() as conn:
            conn.execute(
                f"INSERT INTO {dynamic_table} (id, activity, duration, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("cre-001", "running", "30min", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # 远程数据 updated_at 较新
        remote_rows = [
            {
                "id": "cre-001",
                "activity": "running_updated",
                "duration": "45min",
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-02 12:00:00",  # 比本地新
            }
        ]

        # Act
        written = sync_repository.upsert_rows_with_lww(dynamic_table, remote_rows)

        # Assert: 覆盖（written=1），本地数据被更新
        assert written == 1
        with initialized_db.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT activity, duration FROM {dynamic_table} WHERE id = ?",
                ("cre-001",),
            )
            row = cursor.fetchone()
            assert row[0] == "running_updated"
            assert row[1] == "45min"
