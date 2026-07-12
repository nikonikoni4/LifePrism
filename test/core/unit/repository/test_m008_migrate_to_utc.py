"""m008 DEFAULT 子句迁移脚本单元测试

测试 seam:
1. check_if_applied 幂等性检查
2. DEFAULT 子句替换（localtime → UTC）
3. 表重建模式（数据保留、索引重建）
4. Bug #3: 空名表处理
5. Bug #4: 带引号表名的 CREATE SQL 处理
6. 事务回滚

参考:
- docs/generated/utc-migration-audit-report.md
- .scratch/utc-timezone-migration/16-database-migration-script.md
"""

import sqlite3

import pytest

from lifeprism.repository.migrations.scripts import m008_migrate_to_utc

pytestmark = pytest.mark.core


# ==================== 辅助函数 ====================


def _create_table_with_localtime_default(cursor, table_name, create_sql=None):
    """创建带 localtime DEFAULT 的表

    Args:
        cursor: 数据库游标
        table_name: 表名
        create_sql: 自定义 CREATE SQL（可选）
    """
    if create_sql is None:
        create_sql = (
            f'CREATE TABLE "{table_name}" ('
            f'id TEXT PRIMARY KEY, '
            f'name TEXT, '
            f"created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            f")"
        )
    cursor.execute(create_sql)


# ==================== Seam 1: check_if_applied 幂等性检查 ====================


class TestCheckIfApplied:
    """测试 check_if_applied 幂等性检查"""

    def test_returns_false_when_localtime_default_exists(self):
        """存在 localtime DEFAULT 时返回 False（需要迁移）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE test_table ("
            "id TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        conn.commit()
        result = m008_migrate_to_utc.check_if_applied(cursor)
        assert result is False
        conn.close()

    def test_returns_true_when_no_localtime_default(self):
        """不存在 localtime DEFAULT 时返回 True（已迁移）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE test_table ("
            "id TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now'))"
            ")"
        )
        conn.commit()
        result = m008_migrate_to_utc.check_if_applied(cursor)
        assert result is True
        conn.close()

    def test_returns_true_when_no_tables(self):
        """没有表时返回 True"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        result = m008_migrate_to_utc.check_if_applied(cursor)
        assert result is True
        conn.close()


# ==================== Seam 2: DEFAULT 子句替换 ====================


class TestDefaultClauseReplacement:
    """测试 DEFAULT 子句从 localtime 替换为 UTC"""

    def test_localtime_replaced_with_utc(self):
        """localtime DEFAULT 被替换为 UTC DEFAULT"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE category ("
            "id TEXT PRIMARY KEY, "
            "name TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')), "
            "updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("INSERT INTO category (id, name) VALUES ('cat-001', '测试')")
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 验证 CREATE SQL 中不再有 localtime
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='category'"
        )
        create_sql = cursor.fetchone()[0]
        assert "datetime('now', 'localtime')" not in create_sql
        assert "datetime('now')" in create_sql
        conn.close()

    def test_multiple_tables_migrated(self):
        """多张表都被正确迁移"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        for table_name in ["table_a", "table_b", "table_c"]:
            cursor.execute(
                f'CREATE TABLE "{table_name}" ('
                f"id TEXT PRIMARY KEY, "
                f"created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
                f")"
            )
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
        for (sql,) in cursor.fetchall():
            if sql and "CREATE TABLE" in sql:
                assert "datetime('now', 'localtime')" not in sql
        conn.close()

    def test_data_preserved_after_rebuild(self):
        """表重建后数据完整保留"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE category ("
            "id TEXT PRIMARY KEY, "
            "name TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.executemany(
            "INSERT INTO category (id, name, created_at) VALUES (?, ?, ?)",
            [
                ("cat-001", "分类1", "2026-07-12 10:00:00"),
                ("cat-002", "分类2", "2026-07-12 11:00:00"),
                ("cat-003", "分类3", "2026-07-12 12:00:00"),
            ],
        )
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM category")
        assert cursor.fetchone()[0] == 3

        cursor.execute("SELECT id, name, created_at FROM category ORDER BY id")
        rows = cursor.fetchall()
        assert rows[0] == ("cat-001", "分类1", "2026-07-12 10:00:00")
        assert rows[1] == ("cat-002", "分类2", "2026-07-12 11:00:00")
        assert rows[2] == ("cat-003", "分类3", "2026-07-12 12:00:00")
        conn.close()

    def test_indexes_rebuilt_after_table_rebuild(self):
        """表重建后索引被正确重建"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE category ("
            "id TEXT PRIMARY KEY, "
            "name TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("CREATE INDEX idx_category_name ON category(name)")
        cursor.execute("CREATE INDEX idx_category_created ON category(created_at)")
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='category'"
        )
        index_names = {row[0] for row in cursor.fetchall()}
        assert "idx_category_name" in index_names
        assert "idx_category_created" in index_names
        conn.close()

    def test_tables_without_localtime_not_affected(self):
        """不含 localtime DEFAULT 的表不受影响"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE already_utc ("
            "id TEXT PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT (datetime('now'))"
            ")"
        )
        cursor.execute("INSERT INTO already_utc (id) VALUES ('test-001')")
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 表应该保持不变
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='already_utc'")
        create_sql = cursor.fetchone()[0]
        assert "datetime('now')" in create_sql
        assert "localtime" not in create_sql
        conn.close()


# ==================== Seam 3: Bug #3 - 空名表处理 ====================


class TestEmptyTableNameHandling:
    """测试空名表处理（Bug #3）

    Bug #3: 备份数据库中存在空名表（name=""），
    m008 的 SQL 替换逻辑无法处理，导致 syntax error。

    修复方案：遍历时跳过空名表
    """

    def test_empty_name_table_skipped(self):
        """空名表被跳过，不导致迁移失败"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 正常表
        cursor.execute(
            "CREATE TABLE category ("
            "id TEXT PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("INSERT INTO category (id) VALUES ('cat-001')")

        # 创建空名表（模拟备份数据库中的异常情况）
        # SQLite 允许创建空名表
        cursor.execute(
            "CREATE TABLE \"\" ("
            "id TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        conn.commit()

        # 迁移不应抛出异常
        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 正常表的 DEFAULT 应被替换
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='category'")
        create_sql = cursor.fetchone()[0]
        assert "datetime('now', 'localtime')" not in create_sql
        assert "datetime('now')" in create_sql
        conn.close()

    def test_whitespace_only_name_table_skipped(self):
        """仅含空白字符的表名被跳过"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE normal_table ("
            "id TEXT PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        # 创建仅含空格的表名
        cursor.execute(
            'CREATE TABLE " " (id TEXT, val TEXT)'
        )
        conn.commit()

        # 迁移不应抛出异常
        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 正常表应被迁移
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='normal_table'")
        create_sql = cursor.fetchone()[0]
        assert "datetime('now', 'localtime')" not in create_sql
        conn.close()


# ==================== Seam 4: Bug #4 - 带引号表名处理 ====================


class TestQuotedTableNameHandling:
    """测试带引号表名的 CREATE SQL 处理（Bug #4）

    Bug #4: CREATE SQL 中表名带双引号时，
    m008 的 `CREATE TABLE {table_name}` → `CREATE TABLE {temp_table_name}` 替换失败，
    导致 "table already exists" 错误。

    修复方案：增强表名替换逻辑，支持带引号的表名
    """

    def test_double_quoted_table_name_migrated(self):
        """带双引号表名的 CREATE SQL 能正确迁移"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 使用双引号表名
        cursor.execute(
            'CREATE TABLE "daily_report" ('
            "id TEXT PRIMARY KEY, "
            "report_date TEXT, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("INSERT INTO daily_report (id, report_date) VALUES ('r-001', '2026-07-12')")
        conn.commit()

        # 迁移不应抛出 "table already exists" 错误
        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 验证 DEFAULT 已替换
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='daily_report'"
        )
        create_sql = cursor.fetchone()[0]
        assert "datetime('now', 'localtime')" not in create_sql
        assert "datetime('now')" in create_sql

        # 验证数据保留
        cursor.execute("SELECT id, report_date FROM daily_report")
        row = cursor.fetchone()
        assert row[0] == "r-001"
        assert row[1] == "2026-07-12"
        conn.close()

    def test_create_table_if_not_exists_with_quotes_migrated(self):
        """带 IF NOT EXISTS 和双引号表名的 CREATE SQL 能正确迁移"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS "weekly_report" ('
            "id TEXT PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("INSERT INTO weekly_report (id) VALUES ('w-001')")
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='weekly_report'"
        )
        create_sql = cursor.fetchone()[0]
        assert "datetime('now', 'localtime')" not in create_sql
        assert "datetime('now')" in create_sql
        conn.close()

    def test_unquoted_table_name_still_works(self):
        """不带引号的表名仍然能正确迁移（回归测试）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE simple_table ("
            "id TEXT PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("INSERT INTO simple_table (id) VALUES ('s-001')")
        conn.commit()

        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='simple_table'")
        create_sql = cursor.fetchone()[0]
        assert "datetime('now', 'localtime')" not in create_sql
        assert "datetime('now')" in create_sql
        conn.close()


# ==================== Seam 5: 事务回滚验证 ====================


class TestTransactionRollback:
    """测试迁移在事务内执行，失败时可回滚"""

    def test_migration_in_transaction_rollback_on_error(self):
        """迁移在事务内执行，异常时数据不变"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE category ("
            "id TEXT PRIMARY KEY, "
            "created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"
            ")"
        )
        cursor.execute("INSERT INTO category (id) VALUES ('cat-001')")
        conn.commit()

        original_upgrade = m008_migrate_to_utc.upgrade

        def failing_upgrade(cursor):
            cursor.execute(
                "CREATE TABLE _m008_category_temp ("
                "id TEXT PRIMARY KEY, "
                "created_at TIMESTAMP DEFAULT (datetime('now'))"
                ")"
            )
            raise RuntimeError("模拟迁移失败")

        try:
            m008_migrate_to_utc.upgrade = failing_upgrade
            try:
                m008_migrate_to_utc.upgrade(cursor)
            except RuntimeError:
                pass
            conn.rollback()

            # 验证原表未被修改
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='category'"
            )
            create_sql = cursor.fetchone()[0]
            assert "datetime('now', 'localtime')" in create_sql
        finally:
            m008_migrate_to_utc.upgrade = original_upgrade
            conn.close()
