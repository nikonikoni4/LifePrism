"""
m014_drop_order_index_from_category_tables - 清理 category/sub_category 表的 order_index 死列

历史原因：category 和 sub_category 表曾被试验性代码直接 ALTER TABLE ADD COLUMN order_index，
但 database.py 的 TABLE_CONFIGS 从未定义此列，前后端代码也未使用。
云端新建库不会有此列，但旧库（生产环境）可能存在，导致同步 Push 时报错: 无效的列名: {'order_index'}。

本迁移幂等：检测到列存在才执行 DROP，不存在则跳过。
SQLite 3.35+ 要求由 main.py 启动时的全局前置检查保证，此处不再重复校验。
"""

import logging

logger = logging.getLogger(__name__)

VERSION = 14
NAME = "m014_drop_order_index_from_category_tables"

TABLES = ["category", "sub_category"]
COLUMN = "order_index"


def _has_column(cursor, table: str, column: str) -> bool:
    """检查指定表是否存在指定列"""
    cursor.execute(f'PRAGMA table_info("{table}")')
    return any(row[1] == column for row in cursor.fetchall())


def check_if_applied(cursor) -> bool:
    """检查迁移是否已实际生效。

    判定逻辑（按优先级）：
    1. 目标列在所有目标表中都不存在 → True（工作实际完成，无需重复执行）
    2. 目标列仍存在于任一目标表 → False（需要执行 DROP COLUMN）

    注意：不再仅依赖 schema_version 表记录判断，而是验证实际工作是否完成。
    这样即使之前因为 SQLite 版本过低被跳过，升级 SQLite 后也能自动重新执行。
    """
    for table in TABLES:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            # 表不存在 → 此表无需处理，继续检查下一张表
            continue

        if _has_column(cursor, table, COLUMN):
            # 列仍存在 → 工作未完成
            return False

    # 所有目标表都不存在该列 → 工作已完成
    return True


def upgrade(cursor) -> None:
    """删除 category/sub_category 表的 order_index 列（如果存在）

    SQLite 3.35+ 前提已由 main.py 全局前置检查保证，
    此处直接执行 ALTER TABLE DROP COLUMN。
    """
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
