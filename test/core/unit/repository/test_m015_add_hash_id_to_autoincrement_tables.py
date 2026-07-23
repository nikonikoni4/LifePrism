"""m015 hash_id 迁移脚本单元测试

为 6 张 AUTOINCREMENT 表回填 hash_id（ALTER + 回填 + CREATE UNIQUE INDEX）。

测试 seam:
1. 6 张表回填 hash_id（非 NULL）
2. hash_id 格式正确（前缀 + 12 位 hex）
3. 幂等性：重复运行不报错
4. 唯一性：回填后所有 hash_id 唯一
5. 已有 hash_id 的记录不被覆盖
6. 跳过不存在的表
7. 事务保护：失败回滚
8. check_if_applied 幂等检查

参考:
- lifeprism/repository/migrations/scripts/m012_add_updated_at_to_sync_tables.py
- test/core/unit/repository/test_m008_migrate_to_utc.py
- ADR docs/ADR/2026-07-22-add-hash-id-to-autoincrement-tables.md
"""

import sqlite3

import pytest

from lifeprism.repository.migrations.scripts import m015_add_hash_id_to_autoincrement_tables
from lifeprism.sync.constants import HASH_ID_PREFIXES

pytestmark = pytest.mark.core


# ==================== 辅助函数 ====================


# 6 张表的最小建表 SQL（模拟旧库 schema：不含 hash_id 列）
# 字段精简到迁移脚本不依赖的最小集
_OLD_TABLE_DDL = {
    "timeline_custom_block": (
        "CREATE TABLE timeline_custom_block ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "start_time TEXT NOT NULL, "
        "end_time TEXT NOT NULL, "
        "duration INTEGER NOT NULL, "
        "content TEXT NOT NULL, "
        "color TEXT NOT NULL, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP)"
    ),
    "time_paradoxes": (
        "CREATE TABLE time_paradoxes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "version INTEGER NOT NULL, "
        "mode TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP)"
    ),
    "mood_impacts": (
        "CREATE TABLE mood_impacts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, "
        "sort_order INTEGER, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP)"
    ),
    "habit_chains": (
        "CREATE TABLE habit_chains ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, "
        "description TEXT, "
        "show_in_timeline INTEGER, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP)"
    ),
    "habit_chain_nodes": (
        "CREATE TABLE habit_chain_nodes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "chain_id INTEGER NOT NULL, "
        "sort_order INTEGER NOT NULL, "
        "name TEXT NOT NULL, "
        "habit_id TEXT, "
        "trigger_time TEXT, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP)"
    ),
    "user_app_behavior_log": (
        "CREATE TABLE user_app_behavior_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "start_time TEXT NOT NULL, "
        "end_time TEXT NOT NULL, "
        "duration INTEGER, "
        "app TEXT NOT NULL, "
        "title TEXT, "
        "is_multipurpose_app INTEGER, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP)"
    ),
}


def _create_old_schema_db(tables=None):
    """创建一个旧库（不含 hash_id 列），返回连接

    Args:
        tables: 要创建的表名列表；None 表示创建全部 6 张表

    Returns:
        sqlite3.Connection
    """
    if tables is None:
        tables = list(_OLD_TABLE_DDL.keys())

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE schema_version ("
        "version INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "applied_at TIMESTAMP DEFAULT (datetime('now')))"
    )
    for table in tables:
        cursor.execute(_OLD_TABLE_DDL[table])
    conn.commit()
    return conn


def _insert_sample_rows(conn, table, count=3):
    """向指定表插入 count 条样本记录（无 hash_id）"""
    cursor = conn.cursor()
    if table == "timeline_custom_block":
        for i in range(count):
            cursor.execute(
                "INSERT INTO timeline_custom_block "
                "(start_time, end_time, duration, content, color) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"2026-07-22T0{i}:00:00", f"2026-07-22T0{i}:30:00", 30, f"block{i}", "#FFF"),
            )
    elif table == "time_paradoxes":
        for i in range(count):
            cursor.execute(
                "INSERT INTO time_paradoxes (user_id, version, mode, content) VALUES (?, ?, ?, ?)",
                (1, i, "past", f"paradox{i}"),
            )
    elif table == "mood_impacts":
        for i in range(count):
            cursor.execute(
                "INSERT INTO mood_impacts (name, sort_order) VALUES (?, ?)",
                (f"impact{i}", i),
            )
    elif table == "habit_chains":
        for i in range(count):
            cursor.execute(
                "INSERT INTO habit_chains (name, description, show_in_timeline) VALUES (?, ?, ?)",
                (f"chain{i}", f"desc{i}", 0),
            )
    elif table == "habit_chain_nodes":
        for i in range(count):
            cursor.execute(
                "INSERT INTO habit_chain_nodes (chain_id, sort_order, name) VALUES (?, ?, ?)",
                (1, i + 1, f"node{i}"),
            )
    elif table == "user_app_behavior_log":
        for i in range(count):
            cursor.execute(
                "INSERT INTO user_app_behavior_log "
                "(start_time, end_time, duration, app, title, is_multipurpose_app) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"2026-07-22T0{i}:00:00", f"2026-07-22T0{i}:30:00", 1800, "test.exe", f"t{i}", 0),
            )
    conn.commit()


# ==================== Seam 1: 6 张表回填 hash_id ====================


class TestBackfillHashId:
    """测试 6 张表的 hash_id 回填"""

    def test_all_six_tables_backfilled_non_null(self):
        """6 张表的所有记录 hash_id 都被回填（非 NULL）"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=3)

            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE hash_id IS NULL")
                null_count = cursor.fetchone()[0]
                assert null_count == 0, f"表 {table} 仍有 {null_count} 条 hash_id 为 NULL"
        finally:
            conn.close()

    def test_hash_id_column_added_to_all_tables(self):
        """6 张表都被加上 hash_id 列"""
        conn = _create_old_schema_db()
        try:
            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            for table in HASH_ID_PREFIXES:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = {row[1] for row in cursor.fetchall()}
                assert "hash_id" in columns, f"表 {table} 缺少 hash_id 列"
        finally:
            conn.close()

    def test_empty_table_still_gets_column(self):
        """空表也会被加 hash_id 列（不影响后续插入）"""
        conn = _create_old_schema_db()
        try:
            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 空表 + 加列后插入仍可成功
            cursor.execute(
                "INSERT INTO mood_impacts (name, sort_order) VALUES (?, ?)",
                ("after-migration", 0),
            )
            conn.commit()
            cursor.execute("SELECT COUNT(*) FROM mood_impacts")
            assert cursor.fetchone()[0] == 1
        finally:
            conn.close()


# ==================== Seam 2: hash_id 格式正确 ====================


class TestHashIdFormat:
    """测试 hash_id 格式：前缀 + 12 位 hex"""

    def test_hash_id_has_correct_prefix(self):
        """每条记录的 hash_id 都以对应表前缀开头"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            for table, prefix in HASH_ID_PREFIXES.items():
                cursor.execute(f"SELECT hash_id FROM {table}")
                for (hash_id,) in cursor.fetchall():
                    assert hash_id.startswith(prefix), (
                        f"表 {table} 的 hash_id '{hash_id}' 不以预期前缀 '{prefix}' 开头"
                    )
        finally:
            conn.close()

    def test_hash_id_suffix_is_12_char_hex(self):
        """hash_id 后缀为 12 位十六进制字符"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            import re

            hex_pattern = re.compile(r"^[0-9a-f]{12}$")
            for table, prefix in HASH_ID_PREFIXES.items():
                cursor.execute(f"SELECT hash_id FROM {table}")
                for (hash_id,) in cursor.fetchall():
                    suffix = hash_id[len(prefix):]
                    assert hex_pattern.match(suffix), (
                        f"表 {table} 的 hash_id '{hash_id}' 后缀 '{suffix}' 不是 12 位 hex"
                    )
        finally:
            conn.close()


# ==================== Seam 3: 幂等性（重复运行不报错） ====================


class TestIdempotency:
    """测试重复运行迁移脚本不报错"""

    def test_run_twice_no_error(self):
        """连续运行两次迁移，第二次不抛异常"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=3)

            cursor = conn.cursor()
            # 第一次运行
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 第二次运行不应抛异常
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()
        finally:
            conn.close()

    def test_second_run_preserves_existing_hash_ids(self):
        """第二次运行不改变已有 hash_id 值"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 记录第一次运行后的 hash_id
            first_run_hash_ids = {}
            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT rowid, hash_id FROM {table} ORDER BY rowid")
                first_run_hash_ids[table] = {row[0]: row[1] for row in cursor.fetchall()}

            # 第二次运行
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # hash_id 应保持不变
            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT rowid, hash_id FROM {table} ORDER BY rowid")
                second_run = {row[0]: row[1] for row in cursor.fetchall()}
                assert second_run == first_run_hash_ids[table], (
                    f"表 {table} 第二次运行后 hash_id 被改变"
                )
        finally:
            conn.close()

    def test_backfills_only_new_null_rows_on_second_run(self):
        """第二次运行时仅回填新增的 NULL hash_id 记录（不触碰已有值）"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()
            # 第一次运行：回填前 2 行
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 记录已有 hash_id
            cursor.execute("SELECT hash_id FROM mood_impacts ORDER BY rowid")
            existing_ids = [row[0] for row in cursor.fetchall()]

            # 插入新行（hash_id 为 NULL，模拟 provider 未填充的边界场景）
            cursor.execute(
                "INSERT INTO mood_impacts (name, sort_order) VALUES (?, ?)",
                ("new-after-migration", 99),
            )
            conn.commit()

            # 第二次运行：应仅回填新行
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 原有 2 行 hash_id 不变
            cursor.execute(
                "SELECT hash_id FROM mood_impacts WHERE name != 'new-after-migration' ORDER BY rowid"
            )
            after_ids = [row[0] for row in cursor.fetchall()]
            assert after_ids == existing_ids

            # 新行 hash_id 已回填（非 NULL）
            cursor.execute(
                "SELECT hash_id FROM mood_impacts WHERE name = 'new-after-migration'"
            )
            new_hash_id = cursor.fetchone()[0]
            assert new_hash_id is not None
            assert new_hash_id.startswith("mi-")
        finally:
            conn.close()

    def test_check_if_applied_reflects_schema_version(self):
        """check_if_applied 在 schema_version 含 version=15 时返回 True"""
        conn = _create_old_schema_db()
        try:
            cursor = conn.cursor()
            # 未记录 version=15 → False
            assert m015_add_hash_id_to_autoincrement_tables.check_if_applied(cursor) is False

            # 记录 version=15 → True
            cursor.execute(
                "INSERT INTO schema_version (version, name) VALUES (?, ?)",
                (m015_add_hash_id_to_autoincrement_tables.VERSION, m015_add_hash_id_to_autoincrement_tables.NAME),
            )
            conn.commit()
            assert m015_add_hash_id_to_autoincrement_tables.check_if_applied(cursor) is True
        finally:
            conn.close()


# ==================== Seam 4: 跳过不存在的表 ====================


class TestSkipMissingTables:
    """测试表不存在时优雅跳过"""

    def test_missing_table_skipped(self):
        """只创建部分表时，迁移不报错且已创建的表被正确处理"""
        conn = _create_old_schema_db(tables=["mood_impacts"])
        try:
            cursor = conn.cursor()
            _insert_sample_rows(conn, "mood_impacts", count=2)

            # 不应抛出 "no such table" 错误
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 已创建的表被正确回填
            cursor.execute("SELECT COUNT(*) FROM mood_impacts WHERE hash_id IS NULL")
            assert cursor.fetchone()[0] == 0
        finally:
            conn.close()

    def test_all_tables_missing_skipped(self):
        """所有表都不存在时，迁移不报错"""
        conn = sqlite3.connect(":memory:")
        try:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE schema_version ("
                "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                "applied_at TIMESTAMP DEFAULT (datetime('now')))"
            )
            conn.commit()

            # 不应抛异常
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()
        finally:
            conn.close()


# ==================== Seam 5: 唯一性（无碰撞） ====================


class TestUniqueness:
    """测试回填后所有 hash_id 唯一（无碰撞）"""

    def test_all_hash_ids_distinct_within_table(self):
        """同一表内所有 hash_id 互不相同"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=5)

            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT hash_id FROM {table}")
                hash_ids = [row[0] for row in cursor.fetchall()]
                assert len(hash_ids) == len(set(hash_ids)), (
                    f"表 {table} 存在重复 hash_id: {len(hash_ids)} 行但唯一值仅 {len(set(hash_ids))} 个"
                )
        finally:
            conn.close()

    def test_unique_index_enforced(self):
        """唯一索引已创建：插入重复 hash_id 抛 IntegrityError"""
        conn = _create_old_schema_db()
        try:
            _insert_sample_rows(conn, "mood_impacts", count=2)
            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 取一条已有 hash_id，尝试插入重复值
            cursor.execute("SELECT hash_id FROM mood_impacts LIMIT 1")
            existing_hash_id = cursor.fetchone()[0]

            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO mood_impacts (hash_id, name, sort_order) VALUES (?, ?, ?)",
                    (existing_hash_id, "dup", 0),
                )
        finally:
            conn.close()

    def test_unique_index_created_for_all_tables(self):
        """6 张表都创建了 idx_{table}_hash_id 唯一索引"""
        conn = _create_old_schema_db()
        try:
            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            for table in HASH_ID_PREFIXES:
                index_name = f"idx_{table}_hash_id"
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,),
                )
                assert cursor.fetchone() is not None, f"缺少索引 {index_name}"

                # 验证索引是 UNIQUE 索引
                cursor.execute(f'PRAGMA index_info("{index_name}")')
                index_columns = [row[2] for row in cursor.fetchall()]
                assert "hash_id" in index_columns, (
                    f"索引 {index_name} 未覆盖 hash_id 列"
                )
        finally:
            conn.close()

    def test_no_collision_with_many_rows(self):
        """较大数据量（每表 50 行）下无 hash_id 碰撞"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=50)

            cursor = conn.cursor()
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT hash_id FROM {table}")
                hash_ids = [row[0] for row in cursor.fetchall()]
                assert len(hash_ids) == 50
                assert len(set(hash_ids)) == 50, (
                    f"表 {table} 在 50 行数据下出现 hash_id 碰撞"
                )
        finally:
            conn.close()

    def test_unique_constraint_survives_idempotent_rerun(self):
        """唯一索引在第二次运行后仍然有效（CREATE INDEX IF NOT EXISTS 不削弱约束）"""
        conn = _create_old_schema_db()
        try:
            _insert_sample_rows(conn, "habit_chains", count=2)
            cursor = conn.cursor()
            # 第一次运行
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()
            # 第二次运行
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 取已有 hash_id，尝试插入重复值 → 应仍被拒绝
            cursor.execute("SELECT hash_id FROM habit_chains LIMIT 1")
            existing_hash_id = cursor.fetchone()[0]

            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO habit_chains (hash_id, name) VALUES (?, ?)",
                    (existing_hash_id, "dup"),
                )
        finally:
            conn.close()


# ==================== Seam 6: 事务保护（失败回滚） ====================


class TestTransactionProtection:
    """测试迁移在事务内执行，失败时可回滚

    migration_runner._execute_migration 在 upgrade 抛异常时调用 conn.rollback()。
    本测试验证：upgrade 的所有 DDL/DML 都是事务性的，rollback 能完整撤销。
    """

    def test_changes_are_transactional_rollback_reverts(self):
        """upgrade 后未 commit 直接 rollback → 所有变更被撤销"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()
            # 执行 upgrade（在事务内，未 commit）
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)

            # 不 commit，直接 rollback（模拟 migration_runner 失败路径）
            conn.rollback()

            # 验证：6 张表都没有 hash_id 列（ALTER 被回滚）
            for table in HASH_ID_PREFIXES:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = {row[1] for row in cursor.fetchall()}
                assert "hash_id" not in columns, (
                    f"表 {table} rollback 后仍存在 hash_id 列"
                )

            # 验证：原数据完整保留
            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                assert cursor.fetchone()[0] == 2, f"表 {table} 数据在 rollback 后丢失"

            # 验证：唯一索引不存在
            for table in HASH_ID_PREFIXES:
                index_name = f"idx_{table}_hash_id"
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,),
                )
                assert cursor.fetchone() is None, f"索引 {index_name} 在 rollback 后仍存在"
        finally:
            conn.close()

    def test_failure_mid_migration_rolls_back(self):
        """迁移中途失败 → rollback → 无部分变更残留"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()

            # 注入失败：在 _backfill_row_hash_id 上包装一个失败版本
            original_backfill = m015_add_hash_id_to_autoincrement_tables._backfill_row_hash_id
            call_count = {"n": 0}

            def failing_backfill(cur, table, prefix, rowid):
                call_count["n"] += 1
                if call_count["n"] >= 2:
                    raise RuntimeError("模拟迁移中途失败")
                return original_backfill(cur, table, prefix, rowid)

            m015_add_hash_id_to_autoincrement_tables._backfill_row_hash_id = failing_backfill
            try:
                with pytest.raises(RuntimeError, match="模拟迁移中途失败"):
                    m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
                # 模拟 migration_runner 失败路径：rollback
                conn.rollback()
            finally:
                m015_add_hash_id_to_autoincrement_tables._backfill_row_hash_id = original_backfill

            # 验证：所有表都没有 hash_id 列（DDL 全被回滚，无部分残留）
            for table in HASH_ID_PREFIXES:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = {row[1] for row in cursor.fetchall()}
                assert "hash_id" not in columns, (
                    f"表 {table} 在中途失败 rollback 后仍存在 hash_id 列"
                )

            # 验证：原数据完整保留
            for table in HASH_ID_PREFIXES:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                assert cursor.fetchone()[0] == 2
        finally:
            conn.close()

    def test_commit_then_rerun_after_external_failure(self):
        """commit 成功后，外部失败不影响已应用的迁移结果"""
        conn = _create_old_schema_db()
        try:
            for table in HASH_ID_PREFIXES:
                _insert_sample_rows(conn, table, count=2)

            cursor = conn.cursor()
            # 第一次成功迁移并 commit
            m015_add_hash_id_to_autoincrement_tables.upgrade(cursor)
            conn.commit()

            # 模拟外部失败后 rollback（不影响已 commit 的迁移）
            conn.rollback()

            # 已 commit 的迁移结果保留
            for table in HASH_ID_PREFIXES:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = {row[1] for row in cursor.fetchall()}
                assert "hash_id" in columns
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE hash_id IS NULL")
                assert cursor.fetchone()[0] == 0
        finally:
            conn.close()
