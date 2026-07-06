"""
数据库迁移运行器

在应用启动时自动检测并执行待运行的迁移脚本。
- 独立 sqlite3 连接（不走连接池）
- 每个迁移独立提交
- 迁移前自动备份数据库
- 支持幂等检查（check_if_applied）
"""

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from lifeprism.repository.migrations.scripts import MIGRATIONS

logger = logging.getLogger(__name__)


def run_migrations(db_path: str) -> None:
    """
    执行所有待运行的数据库迁移。

    Args:
        db_path: 数据库文件路径

    Raises:
        RuntimeError: 备份失败或迁移执行失败时抛出，阻止应用启动
    """
    db_file = Path(db_path)
    if not db_file.exists():
        logger.debug("数据库文件不存在，跳过迁移（将由 init_database 创建）")
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        current_version = _get_current_version(cursor)
        pending = [m for m in MIGRATIONS if current_version < m.VERSION]

        if not pending:
            logger.debug("数据库版本 v%s，无待执行迁移", current_version)
            return

        logger.info("数据库版本 v%s，待执行 %s 个迁移", current_version, len(pending))

        # 备份数据库
        _backup_database(db_file, current_version)

        # 逐个执行迁移
        for migration in pending:
            _execute_migration(conn, migration)

        logger.info("所有迁移执行完成，当前版本 v%s", pending[-1].VERSION)
    finally:
        conn.close()


def _get_current_version(cursor: sqlite3.Cursor) -> int:
    """获取当前数据库版本号，schema_version 表不存在或为空返回 0"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        return 0
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    return row[0] if row[0] is not None else 0


def _backup_database(db_file: Path, current_version: int) -> None:
    """
    备份数据库文件，备份前执行 WAL checkpoint。

    Raises:
        RuntimeError: 备份失败时抛出
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_name = f"{db_file.stem}.backup-v{current_version}-{timestamp}{db_file.suffix}"
    backup_path = db_file.parent / backup_name

    try:
        # WAL checkpoint：确保所有数据写入主文件
        conn = sqlite3.connect(str(db_file))
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()

        shutil.copy2(str(db_file), str(backup_path))
        logger.info("数据库已备份: %s", backup_path.name)
    except Exception as e:
        raise RuntimeError(f"数据库备份失败，迁移中止: {e}") from e

    # 清理旧备份，只保留最近 3 个
    _cleanup_old_backups(db_file)


def _cleanup_old_backups(db_file: Path, keep: int = 3) -> None:
    """清理旧备份文件，只保留最近 keep 个"""
    pattern = f"{db_file.stem}.backup-v*{db_file.suffix}"
    backups = sorted(db_file.parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for old_backup in backups[keep:]:
        old_backup.unlink()
        logger.debug("清理旧备份: %s", old_backup.name)


def _execute_migration(conn: sqlite3.Connection, migration) -> None:
    """
    执行单个迁移脚本。

    - check_if_applied() 返回 True：跳过 upgrade，仅插入版本记录
    - check_if_applied() 返回 False：执行 upgrade，插入版本记录
    - 每个迁移独立 commit，失败则 rollback 并抛异常
    """
    cursor = conn.cursor()
    try:
        already_applied = migration.check_if_applied(cursor)
        if already_applied:
            logger.debug("迁移 v%s (%s) 已生效，补录版本记录", migration.VERSION, migration.NAME)
        else:
            logger.info("执行迁移 v%s (%s)...", migration.VERSION, migration.NAME)
            migration.upgrade(cursor)
            logger.info("迁移 v%s (%s) 执行成功", migration.VERSION, migration.NAME)

        cursor.execute(
            "INSERT OR IGNORE INTO schema_version (version, name) VALUES (?, ?)",
            (migration.VERSION, migration.NAME),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"迁移 v{migration.VERSION} ({migration.NAME}) 失败: {e}") from e
