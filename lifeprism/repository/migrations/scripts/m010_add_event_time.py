"""
m010_add_event_time - 为已有自定义数据表新增 event_time 字段

1. ALTER TABLE ADD COLUMN event_time TEXT（SQLite 不允许 NOT NULL + DEFAULT(datetime('now'))）
2. UPDATE 回填：event_time = created_at（将创建时间作为初始事件时间）

之后新创建的自定义表在 custom_record_aggregator 建表时已包含 event_time 列，
插入时由代码控制 event_time 值。
"""

import logging

logger = logging.getLogger(__name__)

VERSION = 10
NAME = "m010_add_event_time"


def check_if_applied(cursor) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_record_types'"
    )
    if not cursor.fetchone():
        logger.info("m010: custom_record_types 表不存在，跳过")
        return

    cursor.execute("SELECT slug FROM custom_record_types")
    slugs = [row[0] for row in cursor.fetchall()]
    if not slugs:
        logger.info("m010: 无自定义记录类型，跳过")
        return

    for slug in slugs:
        table_name = f"custom_{slug}"

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            logger.debug("m010: 动态表 %s 不存在，跳过", table_name)
            continue

        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "event_time" in columns:
            logger.debug("m010: 动态表 %s 已存在 event_time 列，跳过", table_name)
            continue

        # ADD COLUMN（不加 NOT NULL，先允许 NULL）
        cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "event_time" TEXT')
        logger.info("m010: 动态表 %s 新增 event_time 列", table_name)

        # 回填：event_time = created_at
        cursor.execute(
            f'UPDATE "{table_name}" SET "event_time" = "created_at"'
            f' WHERE "event_time" IS NULL AND "created_at" IS NOT NULL'
        )
        affected = cursor.rowcount
        logger.info("m010: 动态表 %s 回填 event_time，影响 %d 行", table_name, affected)

    logger.info("m010: event_time 迁移完成")
