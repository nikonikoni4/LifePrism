"""
m014_drop_order_index_from_category_tables - 清理 category/sub_category 表的 order_index 死列

历史原因：category 和 sub_category 表曾被试验性代码直接 ALTER TABLE ADD COLUMN order_index，
但 database.py 的 TABLE_CONFIGS 从未定义此列，前后端代码也未使用。
云端新建库不会有此列，但旧库（生产环境）可能存在，导致同步 Push 时报错: 无效的列名: {'order_index'}。

本迁移幂等：检测到列存在才执行 DROP，不存在则跳过。
要求 SQLite 3.35+（支持 ALTER TABLE DROP COLUMN）。
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)

VERSION = 14
NAME = "m014_drop_order_index_from_category_tables"

TABLES = ["category", "sub_category"]
COLUMN = "order_index"


def check_if_applied(cursor) -> bool:
    """检查是否已应用：schema_version 表存在且含 version=14 记录"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def _has_column(cursor, table: str, column: str) -> bool:
    """检查指定表是否存在指定列"""
    cursor.execute(f'PRAGMA table_info("{table}")')
    return any(row[1] == column for row in cursor.fetchall())


def _check_sqlite_version_supports_drop_column(conn) -> bool:
    """SQLite 3.35.0+ 支持 ALTER TABLE DROP COLUMN"""
    version = sqlite3.sqlite_version_info
    supported = version >= (3, 35, 0)
    if not supported:
        logger.warning(
            "m014: SQLite 版本 %s 低于 3.35.0，不支持 DROP COLUMN，跳过清理",
            ".".join(str(v) for v in version),
        )
    return supported


def upgrade(cursor) -> None:
    """删除 category/sub_category 表的 order_index 列（如果存在）"""
    conn = cursor.connection
    if not _check_sqlite_version_supports_drop_column(conn):
        return

    for table in TABLES:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            logger.info("m014: 表 %s 不存在，跳过", table)
            continue

        if not _has_column(cursor, table, COLUMN):
            logger.info("m014: 表 %s 无 %s 列，跳过", table, COLUMN)
            continue

        cursor.execute(f'ALTER TABLE "{table}" DROP COLUMN "{COLUMN}"')
        logger.info("m014: 表 %s 已删除列 %s", table, COLUMN)
