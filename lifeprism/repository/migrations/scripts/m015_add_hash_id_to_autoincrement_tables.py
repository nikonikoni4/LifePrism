"""
m015_add_hash_id_to_autoincrement_tables - 为 6 张 AUTOINCREMENT 表回填 hash_id

hash_id 定位为同步专用标识（参考 ADR docs/adr/2026-07-22-hash-id-sync-only-identifier.md）。
但 6 张 AUTOINCREMENT 表（timeline_custom_block、time_paradoxes、mood_impacts、
habit_chains、habit_chain_nodes、user_app_behavior_log）在旧库中无 hash_id 列，
导致同步无法用 hash_id 做去重/删除映射。

本迁移采用 ALTER + CREATE UNIQUE INDEX + 回填（不删表重建，避免数据丢失风险，
与 m012/m013 风格一致）。database.py 中已为这 6 张表加上 hash_id 列配置，
新建库会自动包含该列；本迁移仅处理旧库。

方法（参考 ADR docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md）:
1. ALTER TABLE ADD COLUMN hash_id TEXT（允许 NULL，绕过 SQLite 不能直接加
   NOT NULL UNIQUE 列的限制）
2. CREATE UNIQUE INDEX IF NOT EXISTS（NULL 列上允许多 NULL，不会失败；
   在 UPDATE 之前创建，使碰撞能触发 IntegrityError 并重试）
3. UPDATE 回填：为每条 hash_id IS NULL 的记录生成 前缀 + uuid.uuid4().hex[:12]，
   碰撞时由 _backfill_row_hash_id 重试

幂等性天然实现：
- PRAGMA table_info 检查 hash_id 列是否已存在
- CREATE UNIQUE INDEX IF NOT EXISTS 天然幂等
- UPDATE ... WHERE hash_id IS NULL 天然跳过已回填记录
"""

import logging
import sqlite3

from lifeprism.sync.constants import HASH_ID_PREFIXES, generate_hash_id

logger = logging.getLogger(__name__)

VERSION = 15
NAME = "m015_add_hash_id_to_autoincrement_tables"

# hash_id 回填时 UNIQUE 冲突的最大重试次数（12 位 hex 碰撞概率极低，重试是防御性措施）
_MAX_HASH_ID_RETRIES = 5


def check_if_applied(cursor) -> bool:
    """检查是否已应用：schema_version 表存在且含 version=15 记录"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return False
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (VERSION,))
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    """为 6 张 AUTOINCREMENT 表添加 hash_id 列、创建唯一索引、回填

    执行顺序（关键：CREATE INDEX 在 UPDATE 之前，使重试逻辑真正生效）：
    1. ALTER TABLE ADD COLUMN hash_id TEXT（允许 NULL，绕过 SQLite 不能直接加
       NOT NULL UNIQUE 列的限制）
    2. CREATE UNIQUE INDEX（在 NULL 列上允许多 NULL，不会失败）
    3. 逐行 UPDATE 回填 hash_id（此时有 UNIQUE 索引，碰撞会触发 IntegrityError
       并由 _backfill_row_hash_id 重试）

    若顺序为 ALTER → UPDATE → CREATE INDEX（旧实现），UPDATE 阶段无 UNIQUE
    约束不会触发 IntegrityError，_backfill_row_hash_id 的重试逻辑是死代码；
    真正的冲突在 CREATE INDEX 时才抛出，此时无重试机制，整个迁移回滚。

    全程在显式事务内执行（BEGIN），保证原子性：
    任何一步失败时，由 migration_runner 调用 conn.rollback() 撤销全部变更
    （含 DDL），避免出现"列已加但索引未建/部分行已回填"的中间态。

    注：Python sqlite3 legacy 模式下 DDL（ALTER/CREATE INDEX）不会自动开启事务，
    仅 DML（UPDATE）会。显式 BEGIN 确保所有语句在同一事务内。
    """
    # 显式开启事务：DDL 不会自动开启事务，需手动 BEGIN 才能纳入回滚范围
    cursor.execute("BEGIN")

    for table, prefix in HASH_ID_PREFIXES.items():
        # 检查表是否已存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            logger.info("m015: 表 %s 不存在，跳过", table)
            continue

        # 步骤 1: 幂等检查 + ALTER ADD COLUMN（允许 NULL）
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "hash_id" not in columns:
            # 添加 hash_id 列（允许 NULL，SQLite 限制：无法直接加 NOT NULL UNIQUE 列）
            cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN hash_id TEXT')
            logger.info("m015: 表 %s 已添加 hash_id 列", table)

        # 步骤 2: 创建唯一索引（仅当尚无 hash_id 上的唯一索引时）
        # 必须在 UPDATE 之前创建：NULL 列上允许多 NULL，不会失败；
        # 使后续 UPDATE 回填时碰撞能触发 IntegrityError 并重试
        # 新库 init_database 已通过列级 UNIQUE 创建自动索引，无需再建 idx_{table}_hash_id
        if not _has_unique_index_on_hash_id(cursor, table):
            index_name = f"idx_{table}_hash_id"
            cursor.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON "{table}"(hash_id)')

        # 步骤 3: 逐行 UPDATE 回填（此时有 UNIQUE 索引，碰撞触发 IntegrityError 并重试）
        cursor.execute(f'SELECT rowid FROM "{table}" WHERE hash_id IS NULL')
        null_rowids = [row[0] for row in cursor.fetchall()]

        backfilled = 0
        for rowid in null_rowids:
            _backfill_row_hash_id(cursor, table, prefix, rowid)
            backfilled += 1

        if backfilled:
            logger.info("m015: 表 %s 回填 %d 行 hash_id", table, backfilled)


def _backfill_row_hash_id(cursor, table: str, prefix: str, rowid: int) -> None:
    """为单行回填 hash_id，处理 UNIQUE 冲突重试

    Args:
        cursor: 数据库游标
        table: 表名
        prefix: hash_id 前缀（来自 HASH_ID_PREFIXES）
        rowid: 待回填行的 rowid

    Raises:
        RuntimeError: 重试 _MAX_HASH_ID_RETRIES 次后仍冲突
    """
    for attempt in range(_MAX_HASH_ID_RETRIES):
        hash_id = generate_hash_id(prefix)
        try:
            cursor.execute(
                f'UPDATE "{table}" SET hash_id = ? WHERE rowid = ? AND hash_id IS NULL',
                (hash_id, rowid),
            )
            return
        except sqlite3.IntegrityError:
            # UNIQUE 冲突（极小概率，仅当唯一索引已存在且新值与现有值重复时触发）
            logger.warning(
                "m015: 表 %s 行 %d hash_id 冲突，重试 %d/%d",
                table,
                rowid,
                attempt + 1,
                _MAX_HASH_ID_RETRIES,
            )
            continue
    raise RuntimeError(
        f"m015: 表 {table} 行 {rowid} hash_id 回填失败，{_MAX_HASH_ID_RETRIES} 次重试均冲突"
    )


def _has_unique_index_on_hash_id(cursor, table: str) -> bool:
    """检查表是否已有 hash_id 列上的唯一索引

    新库 init_database 通过列级 UNIQUE 创建自动索引（sqlite_autoindex_*），
    旧库通过本迁移创建 idx_{table}_hash_id。
    两者都通过 PRAGMA index_list 检测到。

    Returns:
        True 如果已有 hash_id 上的唯一索引
    """
    cursor.execute(f'PRAGMA index_list("{table}")')
    for idx in cursor.fetchall():
        # idx 格式: (seq, name, unique, origin, partial)
        idx_name = idx[1]
        is_unique = idx[2]
        if is_unique:
            cursor.execute(f'PRAGMA index_info("{idx_name}")')
            cols = cursor.fetchall()
            # cols 格式: (seqno, cid, name)
            if len(cols) == 1 and cols[0][2] == "hash_id":
                return True
    return False
