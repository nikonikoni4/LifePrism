"""
m009_migrate_history_to_utc - 将历史数据从本地时区(UTC+8)转换为 UTC

假设所有历史数据都是 UTC+8（北京时间），统一减 8 小时转为 UTC。
所有后端代码迁移（#2-#11）已完成，新数据已使用 UTC 写入，
本脚本仅处理历史数据。

排除的字段：
1. 日期字段（YYYY-MM-DD 格式）：date, start_date, end_date,
   expected_finished_at, actual_finished_at 等
3. 时间字段（HH:MM 格式）：time, trigger_time
4. 整数字段：year, month, week_num
5. schema_version.applied_at（内部元数据，不参与业务）

注意事项：
- 本迁移使用 SQLite strftime() + datetime() 函数，输出 ISO 8601 格式 'YYYY-MM-DDTHH:MM:SS+00:00'
- 空字符串和 NULL 值会被跳过（避免 NULL 污染）
- 幂等性由 schema_version 表保证（迁移记录后不会重复执行）
- 迁移在事务内执行，失败时自动回滚（由 migration_runner 保证）

字段清单来源：docs/generated/backend-time-fields-inventory.md
"""

import logging
import re

logger = logging.getLogger(__name__)

VERSION = 9
NAME = "m009_migrate_history_to_utc"

# 时区偏移量（小时）：UTC+8 → UTC 需要减 8 小时
_TIMEZONE_OFFSET = "-8 hours"

# 含 PRIMARY KEY / UNIQUE / CHECK 约束的时间字段所在的表
# 这些表不能使用逐字段 UPDATE，因为：
# 1. PRIMARY KEY/UNIQUE 字段逐行更新时新值可能与未更新行的值冲突（Bug #1）
# 2. CHECK(end_time > start_time) 约束在分步更新时可能被违反（Bug #2）
# 这些表使用表重建模式：建新表 → 复制数据（同时迁移所有时间字段）→ 删旧表 → 重命名
# 来源：lifeprism/config/database.py 中定义的表约束
_TABLES_WITH_TIME_CONSTRAINTS = {
    "raw_behavior_analysis",  # PRIMARY KEY(start_time), CHECK(end_time > start_time)
    "behavior_analysis",  # PRIMARY KEY(start_time), CHECK(end_time > start_time)
    "user_app_behavior_log",  # UNIQUE(app, start_time), CHECK(end_time > start_time)
    "timeline_custom_block",  # CHECK(end_time > start_time) — start_time/end_time 同时迁移
}

# 需要迁移的时间戳字段（表名, 字段名）
# 已排除：
# - 日期字段（YYYY-MM-DD 格式）
# - 时间字段（HH:MM 格式）
# - 整数字段（year/month/week_num）
# - 3 张 UTC 旧表的字段
# - schema_version.applied_at（内部元数据）
_MIGRATION_FIELDS = [
    # === 自动生成的 created_at / updated_at（datetime('now', 'localtime') DEFAULT） ===
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
    ("todo_list", "created_at"),
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
    ("timeline_custom_block", "created_at"),
    ("timeline_custom_block", "updated_at"),
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
    # schema_version.applied_at 已排除（内部元数据）
    # === 业务时间字段（代码手动写入，本地时间） ===
    ("user_app_behavior_log", "start_time"),
    ("user_app_behavior_log", "end_time"),
    ("goal", "time_invested_updated_at"),
    # timeline_custom_block.start_time/end_time 是代码写入的本地时间（非 UTC）
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
]


def check_if_applied(cursor) -> bool:
    """
    检查迁移是否已应用。

    通过 schema_version 表检查 version=9 是否已记录。
    由于 migration_runner 已根据 current_version 过滤待执行迁移，
    此函数主要作为安全网：当 schema_version 表存在且记录了 version 9
    但 current_version 计算异常时，跳过迁移避免重复执行。

    Args:
        cursor: 数据库游标

    Returns:
        bool: True 表示已迁移，False 表示需要执行
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    """
    对每个时间戳字段执行 UPDATE，将本地时间（UTC+8）减 8 小时转为 UTC。

    使用 SQLite datetime() 函数：
        UPDATE "table" SET "field" = datetime("field", '-8 hours')
        WHERE "field" IS NOT NULL AND "field" != ''

    注意事项：
    - datetime() 会将时间格式统一为 'YYYY-MM-DD HH:MM:SS'
    - 跳过 NULL 和空字符串，避免数据污染
    - 自动跳过不存在的表和字段
    - 迁移日志记录每个字段的表名、字段名和影响行数
    - 含 PRIMARY KEY/UNIQUE/CHECK 约束的表使用表重建模式（Bug #1/#2 修复）

    Args:
        cursor: 数据库游标
    """
    total_fields = len(_MIGRATION_FIELDS)
    migrated_fields = 0
    skipped_fields = 0
    total_rows = 0

    logger.info(
        "m009: 开始历史数据时区迁移（UTC+8 → UTC，减 8 小时），共 %d 个字段",
        total_fields,
    )

    # Bug #1/#2 修复：优先处理含约束的表（表重建模式）
    handled_constraint_tables = set()
    for table_name in _TABLES_WITH_TIME_CONSTRAINTS:
        # 收集该表在 _MIGRATION_FIELDS 中的所有字段
        table_fields = [f for (t, f) in _MIGRATION_FIELDS if t == table_name]
        if not table_fields:
            continue
        affected = _migrate_table_with_constraints(cursor, table_name, table_fields)
        if affected is None:
            # 表或字段不存在，跳过
            skipped_fields += len(table_fields)
        else:
            migrated_fields += len(table_fields)
            total_rows += affected
        handled_constraint_tables.add(table_name)

    for table_name, field_name in _MIGRATION_FIELDS:
        # 跳过已通过表重建模式处理的表
        if table_name in handled_constraint_tables:
            continue

        # 检查表是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            logger.debug("m009: 表 %s 不存在，跳过 %s.%s", table_name, table_name, field_name)
            skipped_fields += 1
            continue

        # 检查字段是否存在
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = {row[1] for row in cursor.fetchall()}
        if field_name not in columns:
            logger.debug("m009: 表 %s 无字段 %s，跳过", table_name, field_name)
            skipped_fields += 1
            continue

        # 执行 UPDATE：将时间减 8 小时并转为 ISO 8601 格式（含时区标识 +00:00）
        # 输出格式：YYYY-MM-DDTHH:MM:SS+00:00
        # 跳过 NULL 和空字符串（datetime('') 返回 NULL，会污染数据）
        sql = (
            f'UPDATE "{table_name}" '
            f"SET \"{field_name}\" = strftime('%Y-%m-%dT%H:%M:%f', datetime(\"{field_name}\", ?)) || '+00:00' "
            f'WHERE "{field_name}" IS NOT NULL AND "{field_name}" != ?'
        )
        cursor.execute(sql, (_TIMEZONE_OFFSET, ""))
        affected = cursor.rowcount

        logger.info(
            "m009: 迁移 %s.%s，影响 %d 行",
            table_name,
            field_name,
            affected,
        )

        migrated_fields += 1
        total_rows += affected

    # 迁移动态自定义数据表 custom_<slug> 的 created_at / updated_at
    # 这些表不在 TABLE_CONFIGS 中，由 custom_record_types.slug 运行时决定
    custom_migrated, custom_skipped, custom_rows = _migrate_custom_data_tables(cursor)
    migrated_fields += custom_migrated
    skipped_fields += custom_skipped
    total_rows += custom_rows

    logger.info(
        "m009: 历史数据迁移完成 — 迁移 %d 个字段，跳过 %d 个（表/字段不存在），共更新 %d 行",
        migrated_fields,
        skipped_fields,
        total_rows,
    )


def _migrate_table_with_constraints(cursor, table_name: str, fields: list) -> int | None:
    """
    使用表重建模式迁移含 PRIMARY KEY/UNIQUE/CHECK 约束的表的时间字段。

    表重建模式：
    1. 获取原始 CREATE TABLE 语句和索引
    2. 创建临时新表（相同 schema）
    3. INSERT INTO temp SELECT ... FROM original（同时迁移所有时间字段）
    4. DROP 原表
    5. RENAME temp TO 原表名
    6. 重建索引

    这种方式同时更新所有时间字段，避免了：
    - PRIMARY KEY/UNIQUE 字段逐行更新时的值冲突（Bug #1）
    - CHECK 约束在分步更新时被违反（Bug #2）

    Args:
        cursor: 数据库游标
        table_name: 表名
        fields: 需要迁移的时间字段列表

    Returns:
        影响的行数，如果表或字段不存在则返回 None
    """
    # 检查表是否存在
    cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    row = cursor.fetchone()
    if not row:
        logger.debug("m009: 表 %s 不存在，跳过（表重建）", table_name)
        return None

    _, create_sql = row

    # 检查哪些字段存在
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    # PRAGMA table_info 返回 (cid, name, type, notnull, dflt_value, pk)
    column_info = cursor.fetchall()
    all_columns = [col[1] for col in column_info]  # 按顺序的列名
    column_set = set(all_columns)

    # 过滤出实际存在的需迁移字段
    existing_fields = [f for f in fields if f in column_set]
    if not existing_fields:
        logger.debug("m009: 表 %s 无需迁移的字段，跳过（表重建）", table_name)
        return None

    # 获取索引（重建表后需要重新创建）
    cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table_name,),
    )
    indexes = cursor.fetchall()

    temp_table_name = f"_m009_{table_name}"

    logger.info(
        "m009: 表重建 %s（处理 PRIMARY KEY/CHECK 约束，迁移字段: %s）",
        table_name,
        existing_fields,
    )

    # 1. 生成临时表的 CREATE 语句（替换表名）
    # 使用与 m008 相同的正则替换逻辑，支持带引号的表名
    temp_create_sql = re.sub(
        r'(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)["\'`]?'
        + re.escape(table_name)
        + r'["\'`]?(?=\s|\()',
        r'\1"' + temp_table_name + r'"',
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    )

    # 清理可能残留的临时表
    cursor.execute(f'DROP TABLE IF EXISTS "{temp_table_name}"')

    # 2. 创建临时新表
    cursor.execute(temp_create_sql)

    # 3. 复制数据，同时对时间字段执行减 8 小时并转为 ISO 8601 格式（含时区标识 +00:00）
    # 输出格式：YYYY-MM-DDTHH:MM:SS+00:00
    # 使用 CASE WHEN 跳过 NULL 和空字符串（避免 datetime('') 返回 NULL 污染数据）
    select_cols = []
    for col in all_columns:
        if col in existing_fields:
            select_cols.append(
                f'CASE WHEN "{col}" IS NOT NULL AND "{col}" != ? '
                f"THEN strftime('%Y-%m-%dT%H:%M:%f', datetime(\"{col}\", ?)) || '+00:00' "
                f'ELSE "{col}" END AS "{col}"'
            )
        else:
            select_cols.append(f'"{col}"')

    columns_str = ", ".join([f'"{col}"' for col in all_columns])
    select_str = ", ".join(select_cols)

    # 构建 INSERT 语句
    # CASE WHEN 中的 ? 参数需要为每个迁移字段提供两个参数（空字符串和时区偏移）
    params = []
    for col in all_columns:
        if col in existing_fields:
            params.extend(["", _TIMEZONE_OFFSET])

    cursor.execute(
        f'INSERT INTO "{temp_table_name}" ({columns_str}) SELECT {select_str} FROM "{table_name}"',
        params,
    )
    copied_rows = cursor.rowcount
    logger.info(
        "m009: 表重建 %s 复制了 %d 行数据（%d 个时间字段同时迁移）",
        table_name,
        copied_rows,
        len(existing_fields),
    )

    # 4. 删除旧表
    cursor.execute(f'DROP TABLE "{table_name}"')

    # 5. 重命名新表为原始表名
    cursor.execute(f'ALTER TABLE "{temp_table_name}" RENAME TO "{table_name}"')

    # 6. 重建索引
    for index_name, index_sql in indexes:
        cursor.execute(index_sql)
        logger.debug("m009: 重建索引 %s", index_name)

    return copied_rows


def _migrate_custom_data_tables(cursor) -> tuple[int, int, int]:
    """
    迁移动态自定义数据表 custom_<slug> 的 created_at / updated_at。

    这些表不在 TABLE_CONFIGS 中静态注册，由 custom_record_types.slug 运行时决定表名。
    遍历 custom_record_types 获取所有 slug，对存在的 custom_<slug> 表执行逐字段 UPDATE。

    Args:
        cursor: 数据库游标

    Returns:
        tuple[int, int, int]: (迁移字段数, 跳过的表数, 总影响行数)
    """
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_record_types'"
    )
    if not cursor.fetchone():
        logger.debug("m009: custom_record_types 表不存在，跳过动态表迁移")
        return 0, 0, 0

    cursor.execute("SELECT slug FROM custom_record_types")
    slugs = [row[0] for row in cursor.fetchall()]
    if not slugs:
        return 0, 0, 0

    total_migrated = 0
    total_skipped = 0
    total_rows = 0

    for slug in slugs:
        table_name = f"custom_{slug}"

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            logger.debug("m009: 动态表 %s 不存在，跳过", table_name)
            total_skipped += 2
            continue

        for field_name in ("created_at", "updated_at"):
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = {row[1] for row in cursor.fetchall()}
            if field_name not in columns:
                logger.debug("m009: 动态表 %s 无字段 %s，跳过", table_name, field_name)
                total_skipped += 1
                continue

            sql = (
                f'UPDATE "{table_name}" '
                f"SET \"{field_name}\" = strftime('%Y-%m-%dT%H:%M:%f', datetime(\"{field_name}\", ?)) || '+00:00' "
                f'WHERE "{field_name}" IS NOT NULL AND "{field_name}" != ?'
            )
            cursor.execute(sql, (_TIMEZONE_OFFSET, ""))
            affected = cursor.rowcount

            logger.info(
                "m009: 迁移动态表 %s.%s，影响 %d 行",
                table_name,
                field_name,
                affected,
            )
            total_migrated += 1
            total_rows += affected

    logger.info(
        "m009: 动态表迁移完成 — 迁移 %d 个字段，跳过 %d 个，共更新 %d 行",
        total_migrated,
        total_skipped,
        total_rows,
    )
    return total_migrated, total_skipped, total_rows
