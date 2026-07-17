"""m009 历史数据时区迁移脚本单元测试

测试 seam:
1. 时间减 8 小时计算正确性（UTC+8 → UTC）
2. 排除 3 张 UTC 旧表的 created_at/updated_at 字段
3. 跳过日期字段、时间字段、整数字段
4. 跳过 NULL 和空字符串
5. 幂等性检查（check_if_applied）
6. 跳过不存在的表和字段
7. 事务回滚（通过 migration_runner 保证）

参考:
- docs/generated/backend-time-fields-inventory.md
- .scratch/utc-timezone-migration/16-database-migration-script.md
"""

import sqlite3

import pytest

from lifeprism.repository.migrations.scripts import m009_migrate_history_to_utc

pytestmark = pytest.mark.core


# ==================== 辅助函数 ====================


def _create_table_with_data(cursor, table_name, columns_def, rows):
    """创建表并插入数据

    Args:
        cursor: 数据库游标
        table_name: 表名
        columns_def: 列定义列表，如 [("id", "TEXT"), ("created_at", "TIMESTAMP")]
        rows: 数据行列表，每行为元组，顺序与 columns_def 一致
    """
    cols_sql = ", ".join([f'"{name}" {type_}' for name, type_ in columns_def])
    cursor.execute(f'CREATE TABLE "{table_name}" ({cols_sql})')
    placeholders = ", ".join(["?"] * len(columns_def))
    col_names = ", ".join([f'"{name}"' for name, _ in columns_def])
    for row in rows:
        cursor.execute(
            f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})',
            row,
        )


# ==================== Seam 1: check_if_applied 幂等性检查 ====================


class TestCheckIfApplied:
    """测试 check_if_applied 幂等性检查"""

    def test_returns_false_when_schema_version_table_not_exists(self):
        """schema_version 表不存在时返回 False（需要迁移）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        result = m009_migrate_history_to_utc.check_if_applied(cursor)
        assert result is False
        conn.close()

    def test_returns_false_when_version_9_not_recorded(self):
        """schema_version 表存在但没有 version 9 时返回 False"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE schema_version (version INTEGER, name TEXT)")
        cursor.execute("INSERT INTO schema_version (version, name) VALUES (8, 'm008')")
        conn.commit()
        result = m009_migrate_history_to_utc.check_if_applied(cursor)
        assert result is False
        conn.close()

    def test_returns_true_when_version_9_recorded(self):
        """schema_version 表存在且记录了 version 9 时返回 True（已迁移）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE schema_version (version INTEGER, name TEXT)")
        cursor.execute(
            "INSERT INTO schema_version (version, name) VALUES (9, 'm009_migrate_history_to_utc')"
        )
        conn.commit()
        result = m009_migrate_history_to_utc.check_if_applied(cursor)
        assert result is True
        conn.close()


# ==================== Seam 2: 时间减 8 小时计算正确性 ====================


class TestTimeSubtraction:
    """测试时间减 8 小时计算正确性（UTC+8 → UTC）"""

    def test_subtracts_8_hours_from_standard_format(self):
        """标准格式 'YYYY-MM-DD HH:MM:SS' 正确减 8 小时"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [("cat-001", "2026-07-12 10:00:00")],  # UTC+8 10:00
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT created_at FROM category WHERE id = ?", ("cat-001",))
        result = cursor.fetchone()[0]
        # UTC = 10:00 - 8h = 02:00
        assert result == "2026-07-12T02:00:00+00:00"
        conn.close()

    def test_subtracts_8_hours_crossing_date_boundary(self):
        """跨日期边界：UTC+8 凌晨 03:00 → UTC 前一天 19:00"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [("cat-002", "2026-07-12 03:00:00")],  # UTC+8 7/12 03:00
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT created_at FROM category WHERE id = ?", ("cat-002",))
        result = cursor.fetchone()[0]
        # UTC = 7/12 03:00 - 8h = 7/11 19:00
        assert result == "2026-07-11T19:00:00+00:00"
        conn.close()

    def test_subtracts_8_hours_from_iso_format_with_t(self):
        """ISO 格式（带 T）也能正确减 8 小时"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "habits",
            [("id", "TEXT"), ("created_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP")],
            [("habit-001", "2026-07-12T10:00:00", "2026-07-12T12:00:00.123456")],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT created_at, updated_at FROM habits WHERE id = ?", ("habit-001",))
        created, updated = cursor.fetchone()
        # strftime() + datetime() 将格式统一为 'YYYY-MM-DDTHH:MM:SS+00:00'
        assert created == "2026-07-12T02:00:00+00:00"
        # 微秒被丢弃，格式统一
        assert updated == "2026-07-12T04:00:00+00:00"
        conn.close()

    def test_multiple_rows_all_migrated(self):
        """多行数据都被正确迁移"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "diary",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [
                ("d-001", "2026-07-12 08:00:00"),  # → 00:00
                ("d-002", "2026-07-12 16:00:00"),  # → 08:00
                ("d-003", "2026-07-12 23:59:59"),  # → 15:59:59
            ],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT id, created_at FROM diary ORDER BY id")
        rows = cursor.fetchall()
        assert rows[0] == ("d-001", "2026-07-12T00:00:00+00:00")
        assert rows[1] == ("d-002", "2026-07-12T08:00:00+00:00")
        assert rows[2] == ("d-003", "2026-07-12T15:59:59+00:00")
        conn.close()


# ==================== Seam 3: 排除 UTC 旧表字段 ====================


class TestExcludeUtcOldTables:
    """测试排除 3 张 UTC 旧表的字段

    以下字段已经是 UTC（CURRENT_TIMESTAMP），不能减 8 小时：
    - todo_list.created_at
    - timeline_custom_block.created_at
    - timeline_custom_block.updated_at
    """

    def test_todo_list_created_at_not_migrated(self):
        """todo_list.created_at 不被迁移（已经是 UTC）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        original = "2026-07-12 10:00:00"  # 已经是 UTC
        _create_table_with_data(
            cursor,
            "todo_list",
            [("id", "TEXT"), ("created_at", "TEXT"), ("updated_at", "TIMESTAMP")],
            [("todo-001", original, "2026-07-12 10:00:00")],  # updated_at 是本地时间
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT created_at, updated_at FROM todo_list WHERE id = ?", ("todo-001",))
        created, updated = cursor.fetchone()
        # created_at 不变（UTC）
        assert created == original
        # updated_at 减 8 小时
        assert updated == "2026-07-12T02:00:00+00:00"
        conn.close()

    def test_timeline_custom_block_created_at_not_migrated(self):
        """timeline_custom_block.created_at 不被迁移（已经是 UTC）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        original_created = "2026-07-12 10:00:00"  # UTC
        original_updated = "2026-07-12 10:00:00"  # UTC
        _create_table_with_data(
            cursor,
            "timeline_custom_block",
            [
                ("id", "TEXT"),
                ("created_at", "TEXT"),
                ("updated_at", "TEXT"),
                ("start_time", "TEXT"),
                ("end_time", "TEXT"),
            ],
            [
                (
                    "block-001",
                    original_created,
                    original_updated,
                    "2026-07-12 10:00:00",  # start_time 是本地时间
                    "2026-07-12 11:00:00",  # end_time 是本地时间
                )
            ],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute(
            "SELECT created_at, updated_at, start_time, end_time FROM timeline_custom_block WHERE id = ?",
            ("block-001",),
        )
        created, updated, start, end = cursor.fetchone()
        # created_at 和 updated_at 不变（UTC）
        assert created == original_created
        assert updated == original_updated
        # start_time 和 end_time 减 8 小时（本地时间）
        assert start == "2026-07-12T02:00:00+00:00"
        assert end == "2026-07-12T03:00:00+00:00"
        conn.close()

    def test_excluded_fields_not_in_migration_list(self):
        """验证排除的字段不在迁移列表中"""
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)
        # 这 3 个字段不应在迁移列表中
        assert ("todo_list", "created_at") not in migration_set
        assert ("timeline_custom_block", "created_at") not in migration_set
        assert ("timeline_custom_block", "updated_at") not in migration_set

    def test_non_excluded_fields_in_migration_list(self):
        """验证非排除字段在迁移列表中"""
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)
        # todo_list.updated_at 应在迁移列表中
        assert ("todo_list", "updated_at") in migration_set
        # timeline_custom_block.start_time 和 end_time 应在迁移列表中
        assert ("timeline_custom_block", "start_time") in migration_set
        assert ("timeline_custom_block", "end_time") in migration_set


# ==================== Seam 4: 跳过日期字段、时间字段、整数字段 ====================


class TestSkipDateAndTimeFields:
    """测试跳过日期字段(YYYY-MM-DD)、时间字段(HH:MM)、整数字段"""

    def test_date_fields_not_in_migration_list(self):
        """日期字段不在迁移列表中"""
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)
        date_fields = [
            ("todo_list", "date"),
            ("todo_list", "expected_finished_at"),
            ("todo_list", "actual_finished_at"),
            ("daily_focus", "date"),
            ("goal", "start_date"),
            ("goal", "expected_finished_at"),
            ("goal_journal", "date"),
            ("goal_stats", "date"),
            ("daily_report", "date"),
            ("weekly_report", "date"),
            ("monthly_report", "date"),
            ("diary", "date"),
            ("habit_challenges", "start_date"),
            ("habit_challenges", "end_date"),
            ("habit_checkins", "date"),
        ]
        for field in date_fields:
            assert field not in migration_set, f"日期字段 {field} 不应在迁移列表中"

    def test_time_only_fields_not_in_migration_list(self):
        """时间字段（HH:MM）不在迁移列表中"""
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)
        time_fields = [
            ("goal_journal", "time"),  # HH:MM
            ("habit_chain_nodes", "trigger_time"),  # HH:mm
        ]
        for field in time_fields:
            assert field not in migration_set, f"时间字段 {field} 不应在迁移列表中"

    def test_integer_fields_not_in_migration_list(self):
        """整数字段不在迁移列表中"""
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)
        int_fields = [
            ("weekly_focus", "year"),
            ("weekly_focus", "month"),
            ("weekly_focus", "week_num"),
        ]
        for field in int_fields:
            assert field not in migration_set, f"整数字段 {field} 不应在迁移列表中"

    def test_schema_version_applied_at_not_in_migration_list(self):
        """schema_version.applied_at 不在迁移列表中（内部元数据）"""
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)
        assert ("schema_version", "applied_at") not in migration_set

    def test_date_field_not_modified_by_migration(self):
        """日期字段不会被迁移修改"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "diary",
            [("id", "TEXT"), ("date", "TEXT"), ("created_at", "TIMESTAMP")],
            [("d-001", "2026-07-12", "2026-07-12 10:00:00")],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT date, created_at FROM diary WHERE id = ?", ("d-001",))
        date_val, created = cursor.fetchone()
        # date 字段不变（YYYY-MM-DD 格式）
        assert date_val == "2026-07-12"
        # created_at 减 8 小时
        assert created == "2026-07-12T02:00:00+00:00"
        conn.close()


# ==================== Seam 5: 跳过 NULL 和空字符串 ====================


class TestSkipNullAndEmpty:
    """测试跳过 NULL 和空字符串"""

    def test_null_values_not_modified(self):
        """NULL 值不被修改（保持 NULL）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "habits",
            [("id", "TEXT"), ("paused_at", "TEXT")],
            [
                ("h-001", None),  # NULL
                ("h-002", "2026-07-12 10:00:00"),  # 有值
            ],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT id, paused_at FROM habits ORDER BY id")
        rows = cursor.fetchall()
        assert rows[0] == ("h-001", None)  # NULL 保持不变
        assert rows[1] == ("h-002", "2026-07-12T02:00:00+00:00")  # 有值被迁移
        conn.close()

    def test_empty_string_not_modified(self):
        """空字符串不被修改（避免 datetime('') 返回 NULL 污染数据）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "habits",
            [("id", "TEXT"), ("paused_at", "TEXT")],
            [
                ("h-001", ""),  # 空字符串
                ("h-002", "2026-07-12 10:00:00"),  # 有值
            ],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT id, paused_at FROM habits ORDER BY id")
        rows = cursor.fetchall()
        # 空字符串保持不变（不被 datetime('') 转为 NULL）
        assert rows[0] == ("h-001", "")
        assert rows[1] == ("h-002", "2026-07-12T02:00:00+00:00")
        conn.close()


# ==================== Seam 6: 跳过不存在的表和字段 ====================


class TestSkipMissingTablesAndFields:
    """测试跳过不存在的表和字段（优雅降级）"""

    def test_missing_table_skipped(self):
        """不存在的表被跳过（不报错）"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 只创建一个表，其他表不存在
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [("cat-001", "2026-07-12 10:00:00")],
        )
        conn.commit()

        # 执行迁移（大量表不存在，不应报错）
        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # category 表的数据应被迁移
        cursor.execute("SELECT created_at FROM category WHERE id = ?", ("cat-001",))
        assert cursor.fetchone()[0] == "2026-07-12T02:00:00+00:00"
        conn.close()

    def test_missing_field_skipped(self):
        """表中不存在某字段时跳过该字段"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 创建 category 表但没有 updated_at 字段
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [("cat-001", "2026-07-12 10:00:00")],
        )
        conn.commit()

        # 执行迁移（updated_at 不存在，应跳过）
        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # created_at 应被迁移
        cursor.execute("SELECT created_at FROM category WHERE id = ?", ("cat-001",))
        assert cursor.fetchone()[0] == "2026-07-12T02:00:00+00:00"
        conn.close()


# ==================== Seam 7: 迁移完整性验证 ====================


class TestMigrationCompleteness:
    """测试迁移完整性"""

    def test_all_timestamp_fields_in_inventory_covered(self):
        """验证所有时间戳字段都被覆盖（对比 inventory 清单）

        参考: docs/generated/backend-time-fields-inventory.md
        确保没有遗漏需要迁移的时间戳字段。
        """
        migration_set = set(m009_migrate_history_to_utc._MIGRATION_FIELDS)

        # 从 inventory 中提取的应该被迁移的时间戳字段
        # （排除日期字段、时间字段、整数字段、3 个 UTC 旧表字段、schema_version.applied_at）
        expected_fields = {
            # 自动生成的 created_at/updated_at
            ("category_map_cache", "created_at"),
            ("category_map_cache", "updated_at"),
            ("multi_purpose_map_cache", "created_at"),
            ("multi_purpose_map_cache", "updated_at"),
            ("single_purpose_map_cache", "created_at"),
            ("single_purpose_map_cache", "updated_at"),
            ("user_app_behavior_log", "created_at"),
            ("user_app_behavior_log", "updated_at"),
            ("category", "created_at"),
            ("category", "updated_at"),
            ("sub_category", "created_at"),
            ("sub_category", "updated_at"),
            ("tokens_usage_log", "created_at"),
            ("todo_list", "updated_at"),
            ("daily_focus", "created_at"),
            ("daily_focus", "updated_at"),
            ("weekly_focus", "created_at"),
            ("weekly_focus", "updated_at"),
            ("goal", "created_at"),
            ("goal", "updated_at"),
            ("goal_journal", "created_at"),
            ("goal_journal", "updated_at"),
            ("plan_doc", "created_at"),
            ("plan_doc", "updated_at"),
            ("chat_session", "created_at"),
            ("chat_session", "updated_at"),
            ("goal_stats", "created_at"),
            ("daily_report", "created_at"),
            ("daily_report", "updated_at"),
            ("weekly_report", "created_at"),
            ("weekly_report", "updated_at"),
            ("monthly_report", "created_at"),
            ("monthly_report", "updated_at"),
            ("time_paradoxes", "created_at"),
            ("time_paradoxes", "updated_at"),
            ("diary", "created_at"),
            ("diary", "updated_at"),
            ("mood_types", "created_at"),
            ("mood_entries", "created_at"),
            ("mood_entries", "updated_at"),
            ("mood_impacts", "created_at"),
            ("user_values", "created_at"),
            ("user_values", "updated_at"),
            ("commitments", "created_at"),
            ("commitments", "updated_at"),
            ("habits", "created_at"),
            ("habits", "updated_at"),
            ("habit_challenges", "created_at"),
            ("habit_challenges", "updated_at"),
            ("habit_checkins", "created_at"),
            ("habit_chains", "created_at"),
            ("habit_chains", "updated_at"),
            ("habit_chain_nodes", "created_at"),
            ("habit_chain_nodes", "updated_at"),
            ("screen_captures", "created_at"),
            ("window_events", "created_at"),
            ("raw_behavior_analysis", "created_at"),
            ("behavior_analysis", "created_at"),
            ("behavior_analysis", "updated_at"),
            ("custom_record_types", "created_at"),
            ("custom_record_types", "updated_at"),
            ("custom_record_fields", "created_at"),
            # 业务时间字段
            ("user_app_behavior_log", "start_time"),
            ("user_app_behavior_log", "end_time"),
            ("goal", "time_invested_updated_at"),
            ("timeline_custom_block", "start_time"),
            ("timeline_custom_block", "end_time"),
            ("habits", "paused_at"),
            ("habit_challenges", "finished_at"),
            ("habit_checkins", "completed_at"),
            ("screen_captures", "captured_at"),
            ("window_events", "timestamp"),
            ("raw_behavior_analysis", "start_time"),
            ("raw_behavior_analysis", "end_time"),
            ("behavior_analysis", "start_time"),
            ("behavior_analysis", "end_time"),
        }

        # 验证迁移列表与预期一致
        missing = expected_fields - migration_set
        extra = migration_set - expected_fields
        assert not missing, f"迁移列表缺少字段: {missing}"
        assert not extra, f"迁移列表有额外字段: {extra}"

    def test_migration_affected_rows_count(self):
        """验证迁移影响行数正确"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 创建表并插入 3 行数据
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP")],
            [
                ("cat-001", "2026-07-12 10:00:00", "2026-07-12 10:00:00"),
                ("cat-002", "2026-07-12 11:00:00", "2026-07-12 11:00:00"),
                ("cat-003", None, "2026-07-12 12:00:00"),  # created_at 为 NULL
            ],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 验证所有非 NULL 值都被迁移
        cursor.execute("SELECT created_at, updated_at FROM category WHERE id = ?", ("cat-001",))
        created, updated = cursor.fetchone()
        assert created == "2026-07-12T02:00:00+00:00"
        assert updated == "2026-07-12T02:00:00+00:00"

        cursor.execute("SELECT created_at, updated_at FROM category WHERE id = ?", ("cat-003",))
        created, updated = cursor.fetchone()
        assert created is None  # NULL 保持不变
        assert updated == "2026-07-12T04:00:00+00:00"
        conn.close()


# ==================== Seam 8: 事务回滚验证 ====================


class TestTransactionRollback:
    """测试迁移在事务内执行，失败时可回滚

    migration_runner 保证每个迁移在独立事务内执行，
    如果 upgrade 抛出异常，整个迁移会回滚。
    """

    def test_migration_in_transaction_rollback_on_error(self):
        """迁移在事务内执行，异常时数据不变"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [("cat-001", "2026-07-12 10:00:00")],
        )
        conn.commit()

        # 模拟迁移过程中出错（在 upgrade 中间抛异常）
        original_upgrade = m009_migrate_history_to_utc.upgrade

        def failing_upgrade(cursor):
            # 先正常迁移一部分
            cursor.execute(
                'UPDATE "category" SET "created_at" = datetime("created_at", ?) '
                'WHERE "created_at" IS NOT NULL AND "created_at" != ?',
                ("-8 hours", ""),
            )
            # 然后抛异常
            raise RuntimeError("模拟迁移失败")

        try:
            m009_migrate_history_to_utc.upgrade = failing_upgrade
            try:
                m009_migrate_history_to_utc.upgrade(cursor)
            except RuntimeError:
                pass
            # 回滚事务
            conn.rollback()

            # 验证数据未被修改（回滚成功）
            cursor.execute("SELECT created_at FROM category WHERE id = ?", ("cat-001",))
            assert cursor.fetchone()[0] == "2026-07-12 10:00:00"
        finally:
            m009_migrate_history_to_utc.upgrade = original_upgrade
            conn.close()

    def test_migration_in_transaction_commit_on_success(self):
        """迁移成功后 commit，数据持久化"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        _create_table_with_data(
            cursor,
            "category",
            [("id", "TEXT"), ("created_at", "TIMESTAMP")],
            [("cat-001", "2026-07-12 10:00:00")],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 验证数据已持久化
        cursor.execute("SELECT created_at FROM category WHERE id = ?", ("cat-001",))
        assert cursor.fetchone()[0] == "2026-07-12T02:00:00+00:00"
        conn.close()


# ==================== Seam 9: PRIMARY KEY 字段迁移（Bug #1） ====================


class TestPrimaryKeyFieldMigration:
    """测试 PRIMARY KEY 字段的时间迁移

    Bug #1: raw_behavior_analysis.start_time 和 behavior_analysis.start_time
    是 PRIMARY KEY 字段，逐行 UPDATE 时新值可能与未更新行的值冲突。

    修复方案：使用表重建模式（建新表 → 复制数据 → 删旧表 → 重命名）
    """

    def _create_raw_behavior_analysis(self, cursor, rows):
        """创建 raw_behavior_analysis 表并插入数据

        表结构（来自 config/database.py RAW_BEHAVIOR_ANALYSIS_CONFIG）：
        - start_time TEXT PRIMARY KEY NOT NULL
        - end_time TEXT NOT NULL
        - behavior TEXT NOT NULL
        - screen_count INTEGER NOT NULL DEFAULT 0
        - created_at TIMESTAMP
        - CHECK(end_time > start_time)
        """
        cursor.execute("""
            CREATE TABLE raw_behavior_analysis (
                start_time TEXT PRIMARY KEY NOT NULL,
                end_time TEXT NOT NULL,
                behavior TEXT NOT NULL,
                screen_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP,
                CHECK(end_time > start_time)
            )
        """)
        for row in rows:
            cursor.execute(
                "INSERT INTO raw_behavior_analysis "
                "(start_time, end_time, behavior, screen_count, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                row,
            )

    def test_primary_key_field_migrated_without_collision(self):
        """PRIMARY KEY 字段迁移时不会因值冲突而失败

        场景：3 行数据，start_time 相差 8 小时，
        逐行 UPDATE 时新值会与未更新行的值冲突。
        """
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 插入 3 行数据，start_time 相差 8 小时
        # Row 1: start_time=18:00 → 10:00 (与 Row 2 的 10:00 冲突)
        # Row 2: start_time=10:00 → 02:00 (与 Row 3 的 02:00 冲突)
        # Row 3: start_time=02:00 → 18:00 (前一天)
        self._create_raw_behavior_analysis(
            cursor,
            [
                ("2026-07-12 18:00:00", "2026-07-12 19:00:00", "行为1", 1, "2026-07-12 18:00:00"),
                ("2026-07-12 10:00:00", "2026-07-12 11:00:00", "行为2", 2, "2026-07-12 10:00:00"),
                ("2026-07-12 02:00:00", "2026-07-12 03:00:00", "行为3", 3, "2026-07-12 02:00:00"),
            ],
        )
        conn.commit()

        # 执行迁移（不应抛出 IntegrityError）
        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 验证所有行都被正确迁移
        cursor.execute(
            "SELECT start_time, end_time, created_at FROM raw_behavior_analysis ORDER BY start_time"
        )
        rows = cursor.fetchall()
        assert len(rows) == 3

        # Row 3 (was 02:00, now 18:00 prev day)
        assert rows[0][0] == "2026-07-11T18:00:00+00:00"
        assert rows[0][1] == "2026-07-11T19:00:00+00:00"
        assert rows[0][2] == "2026-07-11T18:00:00+00:00"

        # Row 2 (was 10:00, now 02:00)
        assert rows[1][0] == "2026-07-12T02:00:00+00:00"
        assert rows[1][1] == "2026-07-12T03:00:00+00:00"
        assert rows[1][2] == "2026-07-12T02:00:00+00:00"

        # Row 1 (was 18:00, now 10:00)
        assert rows[2][0] == "2026-07-12T10:00:00+00:00"
        assert rows[2][1] == "2026-07-12T11:00:00+00:00"
        assert rows[2][2] == "2026-07-12T10:00:00+00:00"

        conn.close()

    def test_behavior_analysis_with_updated_at_migrated(self):
        """behavior_analysis 表（含 updated_at）的 PRIMARY KEY 字段迁移

        behavior_analysis 表结构：
        - start_time TEXT PRIMARY KEY NOT NULL
        - end_time TEXT NOT NULL
        - behavior TEXT NOT NULL
        - behavior_summary TEXT
        - title TEXT
        - screen_count INTEGER NOT NULL DEFAULT 0
        - created_at TIMESTAMP
        - updated_at TIMESTAMP
        - CHECK(end_time > start_time)
        """
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE behavior_analysis (
                start_time TEXT PRIMARY KEY NOT NULL,
                end_time TEXT NOT NULL,
                behavior TEXT NOT NULL,
                behavior_summary TEXT,
                title TEXT,
                screen_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                CHECK(end_time > start_time)
            )
        """)
        cursor.execute(
            "INSERT INTO behavior_analysis "
            "(start_time, end_time, behavior, behavior_summary, title, screen_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-07-12 10:00:00",
                "2026-07-12 11:00:00",
                "分析行为",
                "摘要",
                "标题",
                5,
                "2026-07-12 10:00:00",
                "2026-07-12 10:30:00",
            ),
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT start_time, end_time, created_at, updated_at FROM behavior_analysis")
        start, end, created, updated = cursor.fetchone()
        assert start == "2026-07-12T02:00:00+00:00"
        assert end == "2026-07-12T03:00:00+00:00"
        assert created == "2026-07-12T02:00:00+00:00"
        assert updated == "2026-07-12T02:30:00+00:00"
        conn.close()

    def test_primary_key_preserved_after_migration(self):
        """迁移后 PRIMARY KEY 约束仍然有效"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        self._create_raw_behavior_analysis(
            cursor,
            [("2026-07-12 10:00:00", "2026-07-12 11:00:00", "行为", 1, "2026-07-12 10:00:00")],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 尝试插入重复的 start_time 应该失败
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO raw_behavior_analysis (start_time, end_time, behavior, screen_count) "
                "VALUES (?, ?, ?, ?)",
                ("2026-07-12T02:00:00+00:00", "2026-07-12T03:00:00+00:00", "重复", 0),
            )
        conn.close()

    def test_check_constraint_preserved_after_migration(self):
        """迁移后 CHECK 约束仍然有效"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        self._create_raw_behavior_analysis(
            cursor,
            [("2026-07-12 10:00:00", "2026-07-12 11:00:00", "行为", 1, "2026-07-12 10:00:00")],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 尝试插入 end_time < start_time 的行应该失败
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO raw_behavior_analysis (start_time, end_time, behavior, screen_count) "
                "VALUES (?, ?, ?, ?)",
                ("2026-07-12 05:00:00", "2026-07-12 04:00:00", "违反约束", 0),
            )
        conn.close()

    def test_null_and_empty_values_in_primary_key_table(self):
        """PRIMARY KEY 表中 NULL 和空字符串的 created_at 被正确处理"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        self._create_raw_behavior_analysis(
            cursor,
            [
                ("2026-07-12 10:00:00", "2026-07-12 11:00:00", "行为1", 1, None),
                ("2026-07-12 12:00:00", "2026-07-12 13:00:00", "行为2", 2, ""),
                ("2026-07-12 14:00:00", "2026-07-12 15:00:00", "行为3", 3, "2026-07-12 14:00:00"),
            ],
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute(
            "SELECT start_time, created_at FROM raw_behavior_analysis ORDER BY start_time"
        )
        rows = cursor.fetchall()
        # NULL 保持 NULL
        assert rows[0][1] is None
        # 空字符串保持空字符串
        assert rows[1][1] == ""
        # 有值被迁移
        assert rows[2][1] == "2026-07-12T06:00:00+00:00"
        conn.close()

    def test_indexes_rebuilt_after_table_rebuild(self):
        """表重建后索引被正确重建"""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        self._create_raw_behavior_analysis(
            cursor,
            [("2026-07-12 10:00:00", "2026-07-12 11:00:00", "行为", 1, "2026-07-12 10:00:00")],
        )
        # 创建索引
        cursor.execute(
            "CREATE INDEX idx_raw_behavior_start_time ON raw_behavior_analysis(start_time)"
        )
        cursor.execute(
            "CREATE INDEX idx_raw_behavior_time_range ON raw_behavior_analysis(start_time, end_time)"
        )
        conn.commit()

        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 验证索引仍然存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='raw_behavior_analysis'"
        )
        index_names = {row[0] for row in cursor.fetchall()}
        assert "idx_raw_behavior_start_time" in index_names
        assert "idx_raw_behavior_time_range" in index_names
        conn.close()


# ==================== Seam 10: CHECK 约束迁移（Bug #2） ====================


class TestCheckConstraintMigration:
    """测试含 CHECK 约束的表的时间迁移

    Bug #2: raw_behavior_analysis 和 behavior_analysis 含 CHECK(end_time > start_time)
    约束，分步更新 start_time 和 end_time 时中间状态可能违反约束。

    修复方案：表重建模式同时更新所有时间字段，保持 end_time > start_time 关系
    """

    def test_check_constraint_not_violated_during_migration(self):
        """迁移过程中 CHECK 约束不被违反

        场景：start_time 和 end_time 非常接近（仅差 1 秒），
        确保同时迁移不会违反 CHECK(end_time > start_time)
        """
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE raw_behavior_analysis (
                start_time TEXT PRIMARY KEY NOT NULL,
                end_time TEXT NOT NULL,
                behavior TEXT NOT NULL,
                screen_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP,
                CHECK(end_time > start_time)
            )
        """)
        # end_time 仅比 start_time 大 1 秒
        cursor.execute(
            "INSERT INTO raw_behavior_analysis "
            "(start_time, end_time, behavior, screen_count, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "2026-07-12 10:00:00",
                "2026-07-12 10:00:01",
                "短行为",
                1,
                "2026-07-12 10:00:00",
            ),
        )
        conn.commit()

        # 迁移不应抛出 CHECK constraint failed
        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute("SELECT start_time, end_time FROM raw_behavior_analysis")
        start, end = cursor.fetchone()
        assert start == "2026-07-12T02:00:00+00:00"
        assert end == "2026-07-12T02:00:01+00:00"
        # CHECK 约束仍然满足
        assert end > start
        conn.close()

    def test_user_app_behavior_log_unique_constraint_migrated(self):
        """user_app_behavior_log 的 UNIQUE(app, start_time) 约束也能正确迁移

        user_app_behavior_log 表有 UNIQUE(app, start_time) 复合唯一约束，
        与 PRIMARY KEY 类似，逐行更新 start_time 可能导致冲突。
        """
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE user_app_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER,
                app TEXT NOT NULL,
                title TEXT,
                is_multipurpose_app INTEGER DEFAULT 0,
                category_id TEXT,
                sub_category_id TEXT,
                link_to_goal_id TEXT DEFAULT NULL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(app, start_time),
                CHECK(end_time > start_time)
            )
        """)
        # 插入 3 行同 app 数据，start_time 相差 8 小时
        cursor.execute(
            "INSERT INTO user_app_behavior_log "
            "(start_time, end_time, duration, app, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-07-12 18:00:00",
                "2026-07-12 19:00:00",
                3600,
                "chrome",
                "浏览",
                "2026-07-12 18:00:00",
                "2026-07-12 18:00:00",
            ),
        )
        cursor.execute(
            "INSERT INTO user_app_behavior_log "
            "(start_time, end_time, duration, app, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-07-12 10:00:00",
                "2026-07-12 11:00:00",
                3600,
                "chrome",
                "浏览",
                "2026-07-12 10:00:00",
                "2026-07-12 10:00:00",
            ),
        )
        cursor.execute(
            "INSERT INTO user_app_behavior_log "
            "(start_time, end_time, duration, app, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-07-12 02:00:00",
                "2026-07-12 03:00:00",
                3600,
                "chrome",
                "浏览",
                "2026-07-12 02:00:00",
                "2026-07-12 02:00:00",
            ),
        )
        conn.commit()

        # 迁移不应抛出 IntegrityError
        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        # 验证所有行被正确迁移
        cursor.execute(
            "SELECT start_time, end_time, created_at FROM user_app_behavior_log ORDER BY start_time"
        )
        rows = cursor.fetchall()
        assert len(rows) == 3
        assert rows[0][0] == "2026-07-11T18:00:00+00:00"
        assert rows[1][0] == "2026-07-12T02:00:00+00:00"
        assert rows[2][0] == "2026-07-12T10:00:00+00:00"
        conn.close()

    def test_timeline_custom_block_check_constraint_migrated(self):
        """timeline_custom_block 的 CHECK(end_time > start_time) 约束也能正确迁移

        Bug #3: timeline_custom_block 含 CHECK(end_time > start_time) 约束，
        但之前未纳入 _TABLES_WITH_TIME_CONSTRAINTS，使用逐字段 UPDATE 时：
        1. 先更新 start_time → ISO 8601 格式（带 T 分隔符）
        2. 此时 end_time 仍是旧格式（带空格分隔符）
        3. SQLite CHECK 用字符串比较：空格(0x20) < T(0x54)
        4. 导致 end_time < start_time，违反 CHECK 约束

        修复：将 timeline_custom_block 加入 _TABLES_WITH_TIME_CONSTRAINTS，
        使用表重建模式同时迁移 start_time 和 end_time。

        同时验证：created_at/updated_at 是 UTC 旧表字段，不被迁移。
        """
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE timeline_custom_block (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                content TEXT NOT NULL,
                todo_id TEXT,
                color TEXT NOT NULL,
                category_id TEXT,
                sub_category_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                CHECK(end_time > start_time)
            )
        """)
        # 插入数据：start_time/end_time 是本地时间（UTC+8），created_at/updated_at 是 UTC
        cursor.execute(
            "INSERT INTO timeline_custom_block "
            "(start_time, end_time, duration, content, color, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-07-12 10:00:00",  # UTC+8 10:00
                "2026-07-12 11:00:00",  # UTC+8 11:00
                60,
                "测试活动",
                "#ff0000",
                "2026-07-12 02:00:00",  # UTC（不迁移）
                "2026-07-12 02:00:00",  # UTC（不迁移）
            ),
        )
        conn.commit()

        # 迁移不应抛出 CHECK constraint failed
        m009_migrate_history_to_utc.upgrade(cursor)
        conn.commit()

        cursor.execute(
            "SELECT start_time, end_time, created_at, updated_at FROM timeline_custom_block WHERE id = 1"
        )
        start, end, created, updated = cursor.fetchone()
        # start_time 和 end_time 减 8 小时，转为 ISO 8601 格式
        assert start == "2026-07-12T02:00:00+00:00"
        assert end == "2026-07-12T03:00:00+00:00"
        # created_at 和 updated_at 不变（UTC 旧表字段，不在 _MIGRATION_FIELDS 中）
        assert created == "2026-07-12 02:00:00"
        assert updated == "2026-07-12 02:00:00"
        # CHECK 约束仍然满足（字符串比较：两个都是 ISO 格式，T > T 相同，看时间值 03:00 > 02:00）
        assert end > start
        conn.close()
