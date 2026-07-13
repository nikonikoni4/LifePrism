"""
m013_add_updated_at_to_tokens_usage_log - 为 tokens_usage_log 补充 updated_at 列

tokens_usage_log 在 SYNC_TABLES 中，但 TABLE_CONFIGS 曾缺少 update_at=True，
建表时没有 updated_at 列，导致同步 Pull 时报错: no such column: updated_at。

database.py 中已补上 update_at=True，新建库会自动包含该列。
本迁移为旧库 ALTER TABLE ADD COLUMN updated_at，回填 created_at（UTC），并创建索引。
"""

import logging

logger = logging.getLogger(__name__)

VERSION = 13
NAME = "m013_add_updated_at_to_tokens_usage_log"

TABLE = "tokens_usage_log"


def check_if_applied(cursor) -> bool:
    """检查是否已应用：schema_version 表存在且含 version=13 记录"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    """为 tokens_usage_log 添加 updated_at 列、回填 created_at、创建索引"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (TABLE,),
    )
    if not cursor.fetchone():
        logger.info("m013: 表 %s 不存在，跳过", TABLE)
        return

    cursor.execute(f'PRAGMA table_info("{TABLE}")')
    columns = {row[1] for row in cursor.fetchall()}
    if "updated_at" in columns:
        logger.info("m013: 表 %s 已存在 updated_at 列，跳过", TABLE)
        return

    cursor.execute(f'ALTER TABLE "{TABLE}" ADD COLUMN updated_at TIMESTAMP')

    cursor.execute(
        f'UPDATE "{TABLE}" SET "updated_at" = "created_at" '
        f'WHERE "updated_at" IS NULL AND "created_at" IS NOT NULL'
    )
    affected = cursor.rowcount
    logger.info("m013: 表 %s 回填 %d 行 updated_at", TABLE, affected)

    cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{TABLE}_updated_at ON "{TABLE}"(updated_at)')
