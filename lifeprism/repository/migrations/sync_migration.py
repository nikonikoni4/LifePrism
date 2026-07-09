"""
同步功能迁移脚本

为旧版数据库（表已创建但缺少 updated_at 列）添加：
1. updated_at 列（初始值为当前时间）
2. idx_{table}_updated_at 索引
3. timeline_custom_block 的 UNIQUE(start_time) 约束（通过 UNIQUE INDEX 实现）

幂等设计：所有操作使用 IF NOT EXISTS，可安全重复执行。
"""

import logging

logger = logging.getLogger(__name__)

# 需要迁移的 9 个表
SYNC_TABLES = [
    "goal",
    "behavior_analysis",
    "category",
    "category_map_cache",
    "mood_entries",
    "sub_category",
    "timeline_custom_block",
    "todo_list",
    "user_app_behavior_log",
    # P2 补充：原本遗漏的同步表
    "goal_journal",
    "daily_focus",
    "weekly_focus",
]


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    """检查表中是否存在指定列"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def _index_exists(cursor, table_name: str, index_name: str) -> bool:
    """检查表上是否存在指定索引"""
    cursor.execute(f"PRAGMA index_list({table_name})")
    return any(row[1] == index_name for row in cursor.fetchall())


def run_sync_migration(db_manager) -> None:
    """
    执行同步功能迁移：为旧版表添加 updated_at 列、索引和 UNIQUE 约束。

    幂等设计，可安全重复执行。

    Args:
        db_manager: 数据库管理器（LWDatabaseManager 实例）
    """
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        for table_name in SYNC_TABLES:
            # 1. 检查表是否存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if cursor.fetchone() is None:
                logger.warning("表 %s 不存在，跳过迁移", table_name)
                continue

            # 2. 添加 updated_at 列（如果不存在）
            if not _column_exists(cursor, table_name, "updated_at"):
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN updated_at TIMESTAMP")
                # 填充初始值
                cursor.execute(
                    f"UPDATE {table_name} SET updated_at = datetime('now', 'localtime') WHERE updated_at IS NULL"
                )
                logger.info("已为表 %s 添加 updated_at 列", table_name)

            # 3. 创建 updated_at 索引
            index_name = f"idx_{table_name}_updated_at"
            if not _index_exists(cursor, table_name, index_name):
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}(updated_at)"
                )
                logger.info("已为表 %s 创建索引 %s", table_name, index_name)

        # 4. 为 timeline_custom_block 添加 UNIQUE(start_time) 约束
        # SQLite 不支持 ALTER TABLE ADD CONSTRAINT，通过 UNIQUE INDEX 实现
        unique_index_name = "idx_timeline_custom_block_start_time_unique"
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (unique_index_name,),
        )
        if cursor.fetchone() is None:
            # 检查是否有重复 start_time 数据，如有则保留最新一条
            cursor.execute(
                """SELECT start_time, COUNT(*) as cnt
                   FROM timeline_custom_block
                   GROUP BY start_time
                   HAVING cnt > 1"""
            )
            duplicates = cursor.fetchall()
            if duplicates:
                for dup_start_time, _ in duplicates:
                    # 保留 id 最大的（最新）记录，删除其余重复
                    cursor.execute(
                        """DELETE FROM timeline_custom_block
                           WHERE start_time = ?
                           AND id NOT IN (
                               SELECT MAX(id) FROM timeline_custom_block
                               WHERE start_time = ?
                           )""",
                        (dup_start_time, dup_start_time),
                    )
                    logger.warning("清理 timeline_custom_block 重复 start_time: %s", dup_start_time)

            cursor.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {unique_index_name} "
                f"ON timeline_custom_block(start_time)"
            )
            logger.info("已为 timeline_custom_block 创建 UNIQUE(start_time) 索引")

        conn.commit()
        logger.info("同步功能迁移完成")
