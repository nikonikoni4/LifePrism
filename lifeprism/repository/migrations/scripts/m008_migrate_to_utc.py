"""
m008_migrate_to_utc - 将已有表的 DEFAULT 从 localtime 改为 UTC

SQLite 的 datetime('now', 'localtime') 返回本地时间，
datetime('now') 返回 UTC 时间。

本迁移通过表重建模式（SQLite ALTER TABLE 不支持修改 DEFAULT 子句），
将所有使用 datetime('now', 'localtime') 的表改为 datetime('now')。

注意：
- 本迁移仅修改 DEFAULT 子句，不修改已有数据（历史数据迁移由后续脚本处理）
- 3 张使用 CURRENT_TIMESTAMP 的旧表（todo_list、timeline_custom_block）已经是 UTC，无需处理
- 重建过程保留所有数据、约束和索引
- 跳过空名表和仅含空白字符的表名（异常数据，不处理）
- 支持带引号（双引号、单引号、反引号）的表名 CREATE SQL
"""

import logging
import re

logger = logging.getLogger(__name__)

VERSION = 8
NAME = "m008_migrate_to_utc"

# 旧 DEFAULT 子句（需要替换）
_OLD_DEFAULT = "datetime('now', 'localtime')"
# 新 DEFAULT 子句（UTC）
_NEW_DEFAULT = "datetime('now')"


def check_if_applied(cursor) -> bool:
    """
    检查是否所有表的 DEFAULT 子句都已迁移为 UTC。

    遍历 sqlite_master 中所有表的 CREATE 语句，
    如果没有任何表包含 datetime('now', 'localtime')，则视为已迁移。
    """
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    return all(
        not (create_sql and _OLD_DEFAULT in create_sql) for (create_sql,) in cursor.fetchall()
    )


def upgrade(cursor) -> None:
    """
    重建所有包含 datetime('now', 'localtime') 的表，将 DEFAULT 改为 datetime('now')。

    使用 SQLite 标准表重建模式：
    1. 获取原始 CREATE TABLE 语句
    2. 替换 DEFAULT 子句
    3. 创建临时新表
    4. 复制数据
    5. 删除旧表
    6. 重命名新表
    7. 重建索引

    注意：
    - 跳过空名表和仅含空白字符的表名（Bug #3 修复）
    - 支持带引号的表名 CREATE SQL（Bug #4 修复）
    """
    # 获取所有需要迁移的表及其 CREATE 语句
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    tables_to_migrate = []
    for table_name, create_sql in cursor.fetchall():
        # Bug #3 修复：跳过空名表和仅含空白字符的表名
        if not table_name or not table_name.strip():
            logger.debug("m008: 跳过空名表（sql=%s）", create_sql[:80] if create_sql else None)
            continue
        if create_sql and _OLD_DEFAULT in create_sql:
            tables_to_migrate.append((table_name, create_sql))

    if not tables_to_migrate:
        logger.info("m008: 没有需要迁移的表，所有表已使用 UTC DEFAULT")
        return

    logger.info(
        "m008: 需要迁移 %d 张表: %s", len(tables_to_migrate), [t[0] for t in tables_to_migrate]
    )

    for table_name, create_sql in tables_to_migrate:
        _rebuild_table_with_utc_default(cursor, table_name, create_sql)


def _rebuild_table_with_utc_default(cursor, table_name: str, create_sql: str) -> None:
    """
    重建单张表，将 DEFAULT 从 localtime 改为 UTC。

    Args:
        cursor: 数据库游标
        table_name: 表名
        create_sql: 原始 CREATE TABLE 语句

    Note:
        Bug #4 修复：使用正则表达式替换表名，支持带双引号、单引号、
        反引号或不带引号的表名格式。
    """
    # 获取该表的所有索引（重建表后需要重新创建）
    cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table_name,),
    )
    indexes = cursor.fetchall()

    # 生成新的 CREATE TABLE 语句（替换 DEFAULT 子句）
    new_create_sql = create_sql.replace(_OLD_DEFAULT, _NEW_DEFAULT)

    # 使用临时表名创建新表
    temp_table_name = f"_m008_{table_name}"

    # Bug #4 修复：使用正则表达式替换 CREATE TABLE 语句中的表名
    # 支持以下格式：
    #   CREATE TABLE "table_name" (
    #   CREATE TABLE 'table_name' (
    #   CREATE TABLE `table_name` (
    #   CREATE TABLE table_name (
    #   CREATE TABLE IF NOT EXISTS "table_name" (
    #   CREATE TABLE IF NOT EXISTS 'table_name' (
    #   CREATE TABLE IF NOT EXISTS `table_name` (
    #   CREATE TABLE IF NOT EXISTS table_name (
    # 正则中 \1 捕获 "CREATE TABLE" 或 "CREATE TABLE IF NOT EXISTS" 前缀
    # 表名两侧的引号可选匹配（双引号、单引号、反引号）
    # 使用 lookahead (?=\s|\() 确保表名后是空格或左括号，避免部分匹配
    temp_create_sql = re.sub(
        r'(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)["\'`]?'
        + re.escape(table_name)
        + r'["\'`]?(?=\s|\()',
        r'\1"' + temp_table_name + r'"',
        new_create_sql,
        count=1,
        flags=re.IGNORECASE,
    )

    logger.info("m008: 重建表 %s（DEFAULT: localtime → UTC）", table_name)

    # 1. 创建临时新表
    cursor.execute(temp_create_sql)

    # 2. 获取旧表的所有列名（按顺序）
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    columns = [row[1] for row in cursor.fetchall()]
    columns_str = ", ".join([f'"{col}"' for col in columns])

    # 3. 复制数据
    cursor.execute(
        f'INSERT INTO "{temp_table_name}" ({columns_str}) SELECT {columns_str} FROM "{table_name}"'
    )
    copied_rows = cursor.rowcount
    logger.info("m008: 表 %s 复制了 %d 行数据", table_name, copied_rows)

    # 4. 删除旧表
    cursor.execute(f'DROP TABLE "{table_name}"')

    # 5. 重命名新表为原始表名
    cursor.execute(f'ALTER TABLE "{temp_table_name}" RENAME TO "{table_name}"')

    # 6. 重建索引
    for index_name, index_sql in indexes:
        cursor.execute(index_sql)
        logger.debug("m008: 重建索引 %s", index_name)
