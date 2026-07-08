"""
数据同步 Schema 准备测试

测试 seam: 数据库 Schema（通过 init_database + sqlite_master）
验证 Issue #01: 为同步添加 updated_at 字段和索引
"""
import pytest
import sqlite3
from contextlib import contextmanager

from lifeprism.config.database import TABLE_CONFIGS

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


# ==================== goal 表 schema 测试 ====================


class TestGoalTableSchema:
    """测试 goal 表的 updated_at 字段和索引"""

    def test_goal_table_has_updated_at_column(self, initialized_db):
        """goal 表应包含 updated_at 列"""
        columns = _get_table_columns(initialized_db, "goal")
        assert "updated_at" in columns, (
            f"goal 表缺少 updated_at 列，当前列: {columns}"
        )

    def test_goal_table_has_updated_at_index(self, initialized_db):
        """goal 表应有 idx_goal_updated_at 索引"""
        indexes = _get_table_indexes(initialized_db, "goal")
        assert "idx_goal_updated_at" in indexes, (
            f"goal 表缺少 idx_goal_updated_at 索引，当前索引: {indexes}"
        )


# ==================== 其余 8 个表参数化测试 ====================

# 需要添加 update_at 的表（goal 已在 Slice 1 完成）
SYNC_TABLES_NEEDING_UPDATE_AT = [
    "behavior_analysis",
    "category",
    "category_map_cache",
    "mood_entries",
    "sub_category",
    "timeline_custom_block",
    "todo_list",
    "user_app_behavior_log",
]


class TestSyncTablesSchema:
    """参数化测试所有需要同步的表都有 updated_at 列和索引"""

    @pytest.mark.parametrize("table_name", SYNC_TABLES_NEEDING_UPDATE_AT)
    def test_table_has_updated_at_column(self, initialized_db, table_name):
        """每个同步表应包含 updated_at 列"""
        columns = _get_table_columns(initialized_db, table_name)
        assert "updated_at" in columns, (
            f"{table_name} 表缺少 updated_at 列，当前列: {columns}"
        )

    @pytest.mark.parametrize("table_name", SYNC_TABLES_NEEDING_UPDATE_AT)
    def test_table_has_updated_at_index(self, initialized_db, table_name):
        """每个同步表应有 idx_{table}_updated_at 索引"""
        indexes = _get_table_indexes(initialized_db, table_name)
        expected_index = f"idx_{table_name}_updated_at"
        assert expected_index in indexes, (
            f"{table_name} 表缺少 {expected_index} 索引，当前索引: {indexes}"
        )


# ==================== timeline_custom_block UNIQUE 约束测试 ====================


class TestTimelineCustomBlockUniqueConstraint:
    """测试 timeline_custom_block 的 UNIQUE(start_time) 约束"""

    def test_duplicate_start_time_raises_integrity_error(self, initialized_db):
        """插入相同 start_time 的两条记录应抛出 sqlite3.IntegrityError"""
        import sqlite3

        base_row = {
            "start_time": "2026-07-08T10:00:00",
            "end_time": "2026-07-08T11:00:00",
            "duration": 60,
            "content": "测试活动",
            "color": "#FF0000",
        }

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            # 插入第一条
            cursor.execute(
                """INSERT INTO timeline_custom_block
                   (start_time, end_time, duration, content, color)
                   VALUES (:start_time, :end_time, :duration, :content, :color)""",
                base_row,
            )
            # 插入第二条（相同 start_time）应失败
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    """INSERT INTO timeline_custom_block
                       (start_time, end_time, duration, content, color)
                       VALUES (:start_time, :end_time, :duration, :content, :color)""",
                    base_row,
                )


# ==================== 迁移脚本测试 ====================

# 需要迁移的表列表（与 Issue #01 需要修改的 9 个表一致）
MIGRATION_TABLES = [
    "goal",
    "behavior_analysis",
    "category",
    "category_map_cache",
    "mood_entries",
    "sub_category",
    "timeline_custom_block",
    "todo_list",
    "user_app_behavior_log",
]


@pytest.fixture
def legacy_db(tmp_path):
    """模拟旧版数据库：使用独立的临时数据库文件，创建没有 updated_at 列的表"""

    class SimpleDBManager:
        """简单的数据库管理器，仅实现 get_connection() 供迁移脚本使用"""
        def __init__(self, db_path):
            self._db_path = str(db_path)

        @contextmanager
        def get_connection(self):
            conn = sqlite3.connect(self._db_path)
            try:
                yield conn
            finally:
                conn.close()

    db_path = tmp_path / "legacy_test.db"
    db_manager = SimpleDBManager(db_path)

    # 手动创建旧版表结构（没有 updated_at 列）
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS goal (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS behavior_analysis (
                start_time TEXT PRIMARY KEY NOT NULL,
                end_time TEXT NOT NULL,
                behavior TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS category (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                state INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS category_map_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app TEXT NOT NULL,
                title TEXT NOT NULL,
                state INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                UNIQUE(app, title, state)
            );
            CREATE TABLE IF NOT EXISTS mood_entries (
                id TEXT PRIMARY KEY NOT NULL,
                mood_type_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS sub_category (
                id TEXT PRIMARY KEY,
                category_id TEXT NOT NULL,
                name TEXT NOT NULL,
                state INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS timeline_custom_block (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                content TEXT NOT NULL,
                color TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS todo_list (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                state TEXT DEFAULT 'pool',
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS user_app_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                app TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                UNIQUE(app, start_time)
            );
        """)
        conn.commit()

    yield db_manager


class TestMigrationScript:
    """测试迁移脚本为旧版表添加 updated_at 列和索引"""

    @pytest.mark.parametrize("table_name", MIGRATION_TABLES)
    def test_migration_adds_updated_at_column(self, legacy_db, table_name):
        """迁移后旧版表应有 updated_at 列"""
        # 执行迁移
        from lifeprism.repository.migrations.sync_migration import run_sync_migration
        run_sync_migration(legacy_db)

        # 迁移后确认有 updated_at 列
        columns_after = _get_table_columns(legacy_db, table_name)
        assert "updated_at" in columns_after, (
            f"迁移后 {table_name} 应有 updated_at 列，当前列: {columns_after}"
        )

    @pytest.mark.parametrize("table_name", MIGRATION_TABLES)
    def test_migration_adds_updated_at_index(self, legacy_db, table_name):
        """迁移后旧版表应有 idx_{table}_updated_at 索引"""
        from lifeprism.repository.migrations.sync_migration import run_sync_migration
        run_sync_migration(legacy_db)

        indexes = _get_table_indexes(legacy_db, table_name)
        expected_index = f"idx_{table_name}_updated_at"
        assert expected_index in indexes, (
            f"迁移后 {table_name} 应有 {expected_index} 索引，当前索引: {indexes}"
        )

    def test_migration_adds_unique_start_time_to_timeline(self, legacy_db):
        """迁移后 timeline_custom_block 应有 UNIQUE(start_time) 约束"""
        import sqlite3

        from lifeprism.repository.migrations.sync_migration import run_sync_migration
        run_sync_migration(legacy_db)

        with legacy_db.get_connection() as conn:
            cursor = conn.cursor()
            # 插入第一条
            cursor.execute(
                """INSERT INTO timeline_custom_block
                   (start_time, end_time, duration, content, color)
                   VALUES ('2026-07-08T10:00:00', '2026-07-08T11:00:00', 60, 'test', '#FFF')"""
            )
            # 插入相同 start_time 应失败
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    """INSERT INTO timeline_custom_block
                       (start_time, end_time, duration, content, color)
                       VALUES ('2026-07-08T10:00:00', '2026-07-08T12:00:00', 120, 'test2', '#000')"""
                )


# ==================== Provider 行为测试 - updated_at 自动更新 ====================


class TestProviderUpdateAtBehavior:
    """测试 provider 的 update 方法是否自动设置 updated_at"""

    def test_update_goal_sets_updated_at(self, initialized_db):
        """GoalProvider.update_goal 应自动设置 updated_at"""
        import time

        from lifeprism.repository.providers.goal_providers import GoalProvider

        provider = GoalProvider(db_manager=initialized_db)

        # 创建 goal
        goal_id = provider.create_goal({"name": "测试目标", "start_date": "2026-07-08"})
        assert goal_id is not None

        # 查询 created_at
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at, updated_at FROM goal WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            created_at = row[0]
            updated_at_before = row[1]

        # 等待一小段时间确保时间戳不同
        time.sleep(0.1)

        # 更新 goal
        provider.update_goal(goal_id, {"name": "更新后的目标"})

        # 验证 updated_at 被设置且与 created_at 不同
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM goal WHERE id = ?", (goal_id,))
            updated_at_after = cursor.fetchone()[0]

        assert updated_at_after is not None, "updated_at 不应为 None"
        assert updated_at_after != updated_at_before, (
            f"updated_at 应在更新后变化，更新前: {updated_at_before}, 更新后: {updated_at_after}"
        )

    def test_update_todo_sets_updated_at(self, initialized_db):
        """TodoProvider.update_todo 应自动设置 updated_at"""
        import time

        from lifeprism.repository.providers.todo_provider import TodoProvider

        provider = TodoProvider(db_manager=initialized_db)

        # 创建 todo
        todo_id = provider.create_todo({"content": "测试任务", "order_index": 0})
        assert todo_id is not None

        # 查询 updated_at
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM todo_list WHERE id = ?", (todo_id,))
            updated_at_before = cursor.fetchone()[0]

        time.sleep(0.1)

        # 更新 todo
        provider.update_todo(todo_id, {"content": "更新后的任务"})

        # 验证 updated_at 变化
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM todo_list WHERE id = ?", (todo_id,))
            updated_at_after = cursor.fetchone()[0]

        assert updated_at_after is not None, "updated_at 不应为 None"
        assert updated_at_after != updated_at_before, (
            f"updated_at 应在更新后变化，更新前: {updated_at_before}, 更新后: {updated_at_after}"
        )

    def test_update_behavior_sets_updated_at(self, initialized_db):
        """BehaviorAnalysisProvider.update_behavior 应自动设置 updated_at"""
        import time

        from lifeprism.repository.providers.behavior_analysis_provider import (
            BehaviorAnalysisProvider,
        )

        provider = BehaviorAnalysisProvider(db_manager=initialized_db)

        # 直接插入行为分析记录
        start_time = "2026-07-08 10:00:00"
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO behavior_analysis (start_time, end_time, behavior, screen_count)
                   VALUES (?, ?, ?, ?)""",
                (start_time, "2026-07-08 11:00:00", "测试行为", 0),
            )
            conn.commit()

        # 查询 updated_at
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM behavior_analysis WHERE start_time = ?", (start_time,))
            updated_at_before = cursor.fetchone()[0]

        time.sleep(0.1)

        # 更新行为分析
        provider.update_behavior(start_time, {"behavior": "更新后的行为"})

        # 验证 updated_at 变化
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM behavior_analysis WHERE start_time = ?", (start_time,))
            updated_at_after = cursor.fetchone()[0]

        assert updated_at_after is not None, "updated_at 不应为 None"
        assert updated_at_after != updated_at_before, (
            f"updated_at 应在更新后变化，更新前: {updated_at_before}, 更新后: {updated_at_after}"
        )

    def test_update_custom_block_sets_updated_at(self, initialized_db):
        """CustomBlockProvider.update_custom_block 应自动设置 updated_at"""
        import time

        from lifeprism.repository.providers.custom_block_provider import (
            CustomBlockProvider,
        )

        provider = CustomBlockProvider(db_manager=initialized_db)

        # 插入自定义时间块
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO timeline_custom_block (start_time, end_time, duration, content, color)
                   VALUES (?, ?, ?, ?, ?)""",
                ("2026-07-08T14:00:00", "2026-07-08T15:00:00", 60, "测试活动", "#FF0000"),
            )
            block_id = cursor.lastrowid
            conn.commit()

        # 查询 updated_at
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM timeline_custom_block WHERE id = ?", (block_id,))
            updated_at_before = cursor.fetchone()[0]

        time.sleep(0.1)

        # 更新自定义时间块
        provider.update_custom_block(block_id, {"content": "更新后的活动"})

        # 验证 updated_at 变化
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM timeline_custom_block WHERE id = ?", (block_id,))
            updated_at_after = cursor.fetchone()[0]

        assert updated_at_after is not None, "updated_at 不应为 None"
        assert updated_at_after != updated_at_before, (
            f"updated_at 应在更新后变化，更新前: {updated_at_before}, 更新后: {updated_at_after}"
        )
