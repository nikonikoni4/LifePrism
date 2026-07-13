"""
m012_add_updated_at_to_sync_tables - 为 5 张同步表补充 updated_at 列

sync_repository.query_incremental() 通过 WHERE updated_at > ? 做增量同步，
但以下 5 张表在 TABLE_CONFIGS 中曾配置 update_at=False，建表时缺少 updated_at 列，
导致云端同步 Pull 时报错: no such column: updated_at。

本迁移为这些表 ALTER TABLE ADD COLUMN updated_at，回填 created_at（UTC），
并创建索引。database.py 中已将它们的 update_at 改为 True，新建库会自动包含该列。
"""

import logging

logger = logging.getLogger(__name__)

VERSION = 12
NAME = "m012_add_updated_at_to_sync_tables"

# 需要补充 updated_at 列的同步表
TABLES_TO_MIGRATE = [
    "mood_types",
    "mood_impacts",
    "habit_checkins",
    "raw_behavior_analysis",
    "custom_record_fields",
]


def check_if_applied(cursor) -> bool:
    """检查是否已应用：schema_version 表存在且含 version=12 记录"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    """为 5 张同步表添加 updated_at 列、回填 created_at、创建索引

    SQLite ALTER TABLE ADD COLUMN 不支持非常量默认值（如 datetime('now')），
    因此先加无默认值的列，再用 created_at 回填（与 m010/m011 event_time 回填策略一致，
    created_at 已为 UTC），最后建索引。
    """
    for table in TABLES_TO_MIGRATE:
        # 检查表是否已存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            logger.info("m012: 表 %s 不存在，跳过", table)
            continue

        # 幂等检查：已有 updated_at 列则跳过
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "updated_at" in columns:
            logger.info("m012: 表 %s 已存在 updated_at 列，跳过", table)
            continue

        # 添加 updated_at 列（SQLite 限制：无常量默认值）
        cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN updated_at TIMESTAMP')

        # 回填：updated_at = created_at（created_at 已为 UTC，保持时区一致）
        cursor.execute(
            f'UPDATE "{table}" SET "updated_at" = "created_at" '
            f'WHERE "updated_at" IS NULL AND "created_at" IS NOT NULL'
        )
        affected = cursor.rowcount
        logger.info("m012: 表 %s 回填 %d 行 updated_at", table, affected)

        # 创建索引（与 TABLE_CONFIGS 命名规范一致）
        index_name = f"idx_{table}_updated_at"
        cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON "{table}"(updated_at)')
