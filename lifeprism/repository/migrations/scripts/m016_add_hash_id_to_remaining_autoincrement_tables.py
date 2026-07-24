"""
m016_add_hash_id_to_remaining_autoincrement_tables - 为遗漏的 3 张 AUTOINCREMENT 表回填 hash_id

m015 迁移审计时遗漏了 daily_focus、weekly_focus、category_map_cache 三张 AUTOINCREMENT 同步表，
导致墓碑同步跨端删除时这些表 fallback 到整数主键 id，而 id 在两端不同，
可能命中错误记录。

本迁移采用与 m015 相同的方法（ALTER + CREATE UNIQUE INDEX + 回填），
为这 3 张表补充 hash_id 字段。

方法（参考 ADR docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md）:
1. ALTER TABLE ADD COLUMN hash_id TEXT（允许 NULL）
2. CREATE UNIQUE INDEX IF NOT EXISTS
3. UPDATE 回填：为每条 hash_id IS NULL 的记录生成 前缀 + uuid.uuid4().hex[:12]

幂等性天然实现：
- PRAGMA table_info 检查 hash_id 列是否已存在
- CREATE UNIQUE INDEX IF NOT EXISTS 天然幂等
- UPDATE ... WHERE hash_id IS NULL 天然跳过已回填记录

参考 ADR: docs/adr/2026-07-24-add-hash-id-to-remaining-autoincrement-tables.md
"""

import logging
import sqlite3

from lifeprism.sync.constants import HASH_ID_PREFIXES, generate_hash_id

logger = logging.getLogger(__name__)

VERSION = 16
NAME = "m016_add_hash_id_to_remaining_autoincrement_tables"

# 本迁移仅处理 m015 遗漏的 3 张表（HASH_ID_PREFIXES 中其余 6 张已在 m015 处理）
_REMAINING_TABLES = {
    "daily_focus": HASH_ID_PREFIXES["daily_focus"],
    "weekly_focus": HASH_ID_PREFIXES["weekly_focus"],
    "category_map_cache": HASH_ID_PREFIXES["category_map_cache"],
}

_MAX_HASH_ID_RETRIES = 5


def check_if_applied(cursor) -> bool:
    """检查是否已应用：schema_version 表存在且含 version=16 记录"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    """为 3 张遗漏的 AUTOINCREMENT 表添加 hash_id 列、创建唯一索引、回填

    执行顺序与 m015 一致：
    1. ALTER TABLE ADD COLUMN hash_id TEXT（允许 NULL）
    2. CREATE UNIQUE INDEX（在 NULL 列上允许多 NULL，不会失败）
    3. 逐行 UPDATE 回填（此时有 UNIQUE 索引，碰撞触发 IntegrityError 并重试）
    """
    cursor.execute("BEGIN")

    for table, prefix in _REMAINING_TABLES.items():
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            logger.info("m016: 表 %s 不存在，跳过", table)
            continue

        # 步骤 1: 幂等检查 + ALTER ADD COLUMN（允许 NULL）
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "hash_id" not in columns:
            cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN hash_id TEXT')
            logger.info("m016: 表 %s 已添加 hash_id 列", table)

        # 步骤 2: 创建唯一索引
        if not _has_unique_index_on_hash_id(cursor, table):
            index_name = f"idx_{table}_hash_id"
            cursor.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON "{table}"(hash_id)')

        # 步骤 3: 逐行 UPDATE 回填
        cursor.execute(f'SELECT rowid FROM "{table}" WHERE hash_id IS NULL')
        null_rowids = [row[0] for row in cursor.fetchall()]

        backfilled = 0
        for rowid in null_rowids:
            _backfill_row_hash_id(cursor, table, prefix, rowid)
            backfilled += 1

        if backfilled:
            logger.info("m016: 表 %s 回填 %d 行 hash_id", table, backfilled)


def _backfill_row_hash_id(cursor, table: str, prefix: str, rowid: int) -> None:
    """为单行回填 hash_id，处理 UNIQUE 冲突重试"""
    for attempt in range(_MAX_HASH_ID_RETRIES):
        hash_id = generate_hash_id(prefix)
        try:
            cursor.execute(
                f'UPDATE "{table}" SET hash_id = ? WHERE rowid = ? AND hash_id IS NULL',
                (hash_id, rowid),
            )
            return
        except sqlite3.IntegrityError:
            logger.warning(
                "m016: 表 %s 行 %d hash_id 冲突，重试 %d/%d",
                table,
                rowid,
                attempt + 1,
                _MAX_HASH_ID_RETRIES,
            )
            continue
    raise RuntimeError(
        f"m016: 表 {table} 行 {rowid} hash_id 回填失败，{_MAX_HASH_ID_RETRIES} 次重试均冲突"
    )


def _has_unique_index_on_hash_id(cursor, table: str) -> bool:
    """检查表是否已有 hash_id 列上的唯一索引"""
    cursor.execute(f'PRAGMA index_list("{table}")')
    for idx in cursor.fetchall():
        idx_name = idx[1]
        is_unique = idx[2]
        if is_unique:
            cursor.execute(f'PRAGMA index_info("{idx_name}")')
            cols = cursor.fetchall()
            if len(cols) == 1 and cols[0][2] == "hash_id":
                return True
    return False
