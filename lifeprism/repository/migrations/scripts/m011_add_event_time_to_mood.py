"""
m011_add_event_time_to_mood - 为 mood_entries 表新增 event_time 字段

1. ALTER TABLE ADD COLUMN event_time TEXT（SQLite 不允许 NOT NULL + DEFAULT(datetime('now'))）
2. UPDATE 回填：event_time = created_at（将创建时间作为初始事件时间）

之后新创建的 mood_entries 表在 database.py DDL 中已包含 event_time 列，
插入时由代码控制 event_time 值（mood_providers.create_mood_entry）。
"""

import logging

logger = logging.getLogger(__name__)

VERSION = 11
NAME = "m011_add_event_time_to_mood"


def check_if_applied(cursor) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='mood_entries'"
    )
    if not cursor.fetchone():
        logger.info("m011: mood_entries 表不存在，跳过")
        return

    cursor.execute("PRAGMA table_info(mood_entries)")
    columns = {row[1] for row in cursor.fetchall()}
    if "event_time" in columns:
        logger.info("m011: mood_entries 已存在 event_time 列，跳过")
        return

    # ADD COLUMN（不加 NOT NULL，先允许 NULL）
    cursor.execute('ALTER TABLE mood_entries ADD COLUMN "event_time" TEXT')
    logger.info("m011: mood_entries 新增 event_time 列")

    # 回填：event_time = created_at
    cursor.execute(
        'UPDATE mood_entries SET "event_time" = "created_at"'
        ' WHERE "event_time" IS NULL AND "created_at" IS NOT NULL'
    )
    affected = cursor.rowcount
    logger.info("m011: mood_entries 回填 event_time，影响 %d 行", affected)

    # 创建索引
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_mood_entries_event_time ON mood_entries(event_time)"
    )
    logger.info("m011: 创建索引 idx_mood_entries_event_time")

    logger.info("m011: event_time 迁移完成")
