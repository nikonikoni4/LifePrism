"""备份服务（单例）

职责：执行备份逻辑（不负责调度，调度由 ScheduleService 负责）

设计决策:
- 平铺存储（非 zip）：每个时间戳一个目录，目录内是原始文件结构
  - 用户可直接用文件管理器查看备份内容（关键需求）
  - 单文件恢复只需复制，无需解压
  - 数据库 .db 文件可用 DB Browser 直接打开
- SQLite Online Backup API：``sqlite3.Connection.backup(target)``
  - 在线拷贝，不阻塞业务读写
  - 路径完全自定义，避免文件锁冲突
- 完整性校验（方案 A 完整校验）：
  - 文档：文件数量比对 + 每个文件 SHA-256 hash 比对
  - 数据库：``PRAGMA integrity_check``
- 校验失败处理：删除损坏的备份目录/文件 + 记录 ERROR 日志 + 不影响其他任务
- 保留策略：按时间戳字符串排序（ISO-like 字典序 = 时间序），保留最新 3 份
- 时间戳目录名使用本地时区（与 cron 触发时间一致，便于用户理解）

时间戳格式说明:
- 目录/文件名时间戳使用本地时区 ``YYYY-MM-DDTHH-MM-SS``（冒号替换为短横，文件系统友好）
- 这是文件系统 artifact，不是数据库时间戳字段
- cron 触发时间也是本地时区（``CronTrigger.from_crontab(expr, timezone=local_tz)``）
- 内部日志记录使用 UTC ISO 8601（遵循 time-handling-rules §3.1）

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-7-backup-service-and-scheduler.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 14-18
- ADR: docs/adr/2026-07-17-data-backup-strategy.md（数据备份策略）
- ADR: docs/adr/2026-07-17-backup-sync-decoupled-scope.md（备份范围与同步范围解耦）
- ADR: docs/adr/2026-07-17-conflict-failure-policy.md（云端 agent_only 模式不备份）
"""

import contextlib
import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pytz

from lifeprism.backup.constants import (
    BACKUP_DB_FILES,
    BACKUP_DIRS,
    BACKUP_EXCLUDED_FILENAMES,
)
from lifeprism.config import get_user_timezone
from lifeprism.config.settings_manager import settings
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# 备份保留份数（文档与数据库各自独立保留）
BACKUP_RETENTION_COUNT = 3

# 备份目录/文件名时间戳格式（本地时区，文件系统友好：冒号替换为短横）
# 使用本地时间让用户直观看到备份发生时刻（与 cron 触发时间一致）
_BACKUP_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%S"


class BackupService:
    """备份服务（单例）

    职责：执行备份逻辑（不负责调度，调度由 ScheduleService 负责）

    设计要点：
    - ``backup_documents`` 文档全量备份（保留 3 份，每天本地 03:00）
    - ``backup_database`` 数据库全量备份（保留 3 份，每 8 小时本地 00/08/16 点）
    - ``run_mode != "full"`` 时跳过备份（云端 agent_only 模式不备份）
    - 完整性校验失败自动删除损坏备份，不影响其他任务
    """

    # ==================== 工具方法 ====================

    def _get_backup_root(self) -> Path:
        """获取备份根目录路径 ``{lifeprism_data_path}/backups/``"""
        return Path(settings.lifeprism_data_path) / "backups"

    def _get_local_timestamp(self) -> str:
        """生成本地时区时间戳字符串（文件系统友好）

        格式：``YYYY-MM-DDTHH-MM-SS``（冒号替换为短横，Windows 兼容）
        使用本地时区与 cron 触发时间一致，便于用户直观理解备份时刻。
        """
        local_tz = pytz.timezone(get_user_timezone())
        return datetime.now(local_tz).strftime(_BACKUP_TIMESTAMP_FORMAT)

    def _check_run_mode(self) -> bool:
        """检查 run_mode 是否允许备份

        Returns:
            True 表示允许备份，False 表示跳过（云端 agent_only / web_demo 模式）

        设计依据：ADR docs/adr/2026-07-17-conflict-failure-policy.md
        云端 agent_only 模式不执行备份，复用现有 ScheduleService 的 run_mode 守卫。
        """
        if settings.run_mode != "full":
            logger.info(
                "run_mode=%s，跳过备份（仅 full 模式启用）",
                settings.run_mode,
            )
            return False
        return True

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """计算文件内容的 SHA-256 hash（用于完整性校验）

        Args:
            file_path: 文件路径

        Returns:
            SHA-256 hex 字符串
        """
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ==================== 文档备份 ====================

    async def backup_documents(self) -> None:
        """文档全量备份（保留 3 份）

        流程：
        1. 检查 run_mode 守卫
        2. 创建 ``backups/docs/{timestamp}/`` 目录
        3. 复制 BACKUP_DIRS 下的文件（排除 BACKUP_EXCLUDED_FILENAMES）
        4. 完整性校验：文件数量比对 + 每个文件 hash 比对
        5. 校验失败 → 删除损坏备份 → 记录 ERROR 日志
        6. 清理超过 3 份的旧备份（按时间戳排序，保留最新 3 份）

        失败处理：
        - 校验失败：删除本次备份目录，记录 ERROR，不影响其他任务
        - 异常：清理本次可能创建的不完整备份目录，记录 ERROR
        """
        if not self._check_run_mode():
            return

        timestamp = self._get_local_timestamp()
        backup_dir = self._get_backup_root() / "docs" / timestamp
        data_path = Path(settings.lifeprism_data_path)

        try:
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 复制 BACKUP_DIRS 下的文件
            copied_count = 0
            for dir_name in BACKUP_DIRS:
                src_dir = data_path / dir_name
                if not src_dir.exists():
                    continue
                dst_dir = backup_dir / dir_name
                dst_dir.mkdir(parents=True, exist_ok=True)

                for src_file in src_dir.rglob("*"):
                    if not src_file.is_file():
                        continue
                    if src_file.name in BACKUP_EXCLUDED_FILENAMES:
                        continue
                    rel_path = src_file.relative_to(src_dir)
                    dst_file = dst_dir / rel_path
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    copied_count += 1

            # 完整性校验
            if not self._verify_docs_backup(data_path, backup_dir):
                # 校验失败 → 删除损坏备份
                logger.error(
                    "文档备份校验失败，删除损坏备份 timestamp=%s, backup_dir=%s",
                    timestamp,
                    backup_dir,
                )
                shutil.rmtree(backup_dir, ignore_errors=True)
                return

            logger.info(
                "文档备份完成 timestamp=%s, file_count=%d",
                timestamp,
                copied_count,
            )

            # 清理超过 3 份的旧备份
            self._cleanup_old_doc_backups(self._get_backup_root() / "docs", BACKUP_RETENTION_COUNT)
        except Exception as e:
            logger.error(
                "文档备份异常 timestamp=%s, error=%s",
                timestamp,
                e,
            )
            # 异常时也尝试清理可能创建的不完整备份目录
            shutil.rmtree(backup_dir, ignore_errors=True)

    def _verify_docs_backup(self, source_root: Path, backup_root: Path) -> bool:
        """校验文档备份完整性

        校验规则：
        1. 文件数量比对：源文件数 == 备份文件数
        2. 文件列表比对：相对路径集合一致
        3. 文件内容比对：每个文件 SHA-256 hash 一致

        Args:
            source_root: 源数据根目录（lifeprism_data_path）
            backup_root: 备份目录（backups/docs/{timestamp}/）

        Returns:
            True 表示校验通过，False 表示校验失败
        """
        # 收集源文件（应用相同的排除规则）
        source_files = []
        for dir_name in BACKUP_DIRS:
            src_dir = source_root / dir_name
            if not src_dir.exists():
                continue
            for src_file in src_dir.rglob("*"):
                if not src_file.is_file():
                    continue
                if src_file.name in BACKUP_EXCLUDED_FILENAMES:
                    continue
                source_files.append(src_file.relative_to(source_root))

        # 收集备份文件
        backup_files = []
        for f in backup_root.rglob("*"):
            if f.is_file():
                backup_files.append(f.relative_to(backup_root))

        # 1. 比对文件数量
        if len(source_files) != len(backup_files):
            logger.error(
                "文档备份校验失败：文件数量不一致 source_count=%d, backup_count=%d",
                len(source_files),
                len(backup_files),
            )
            return False

        # 2. 比对文件列表（相对路径集合）
        source_set = set(source_files)
        backup_set = set(backup_files)
        if source_set != backup_set:
            logger.error(
                "文档备份校验失败：文件列表不一致 missing=%s, extra=%s",
                source_set - backup_set,
                backup_set - source_set,
            )
            return False

        # 3. 比对每个文件的 hash
        for rel_path in source_files:
            src_file = source_root / rel_path
            bak_file = backup_root / rel_path
            if self._compute_file_hash(src_file) != self._compute_file_hash(bak_file):
                logger.error(
                    "文档备份校验失败：文件 hash 不一致 rel_path=%s",
                    rel_path,
                )
                return False

        return True

    def _cleanup_old_doc_backups(self, docs_root: Path, keep_count: int) -> None:
        """清理超过保留份数的旧文档备份

        策略：按时间戳目录名降序排序（ISO-like 字典序 = 时间序），保留最新 N 份。

        Args:
            docs_root: 文档备份根目录（backups/docs/）
            keep_count: 保留份数
        """
        if not docs_root.exists():
            return

        sub_dirs = [d for d in docs_root.iterdir() if d.is_dir()]
        sub_dirs.sort(key=lambda d: d.name, reverse=True)

        for old_dir in sub_dirs[keep_count:]:
            try:
                shutil.rmtree(old_dir)
                logger.info(
                    "清理旧文档备份 dir=%s",
                    old_dir,
                )
            except OSError as e:
                logger.warning(
                    "清理旧文档备份失败 dir=%s, error=%s",
                    old_dir,
                    e,
                )

    # ==================== 数据库备份 ====================

    async def backup_database(self) -> None:
        """数据库全量备份（保留 3 份，使用 SQLite Online Backup API）

        流程：
        1. 检查 run_mode 守卫
        2. 对 BACKUP_DB_FILES 中的每个数据库：
           a. SQLite Online Backup:
              source = sqlite3.connect(lifewatch_ai.db)
              target = sqlite3.connect(backups/db/lifewatch_ai-{timestamp}.db)
              source.backup(target)
           b. 完整性校验：``PRAGMA integrity_check``
           c. 校验失败 → 删除损坏备份 → 记录 ERROR 日志
        3. 清理超过 3 份的旧备份（按时间戳排序，保留最新 3 份）

        失败处理：
        - 校验失败：删除本次备份文件，记录 ERROR，继续下一个数据库
        - 异常：清理本次可能创建的不完整备份文件，记录 ERROR
        """
        if not self._check_run_mode():
            return

        timestamp = self._get_local_timestamp()
        db_root = self._get_backup_root() / "db"
        db_root.mkdir(parents=True, exist_ok=True)

        data_path = Path(settings.lifeprism_data_path)

        for db_rel_path in BACKUP_DB_FILES:
            src_db = data_path / db_rel_path
            if not src_db.exists():
                logger.warning(
                    "数据库文件不存在，跳过备份 db_path=%s",
                    src_db,
                )
                continue

            # 文件命名：{stem}-{timestamp}.db（如 lifewatch_ai-2026-07-17T08-00-00.db）
            db_filename = src_db.stem  # "lifewatch_ai"
            dst_db = db_root / f"{db_filename}-{timestamp}.db"

            try:
                # SQLite Online Backup API
                # 在线拷贝，不阻塞业务读写
                source = sqlite3.connect(str(src_db))
                target = sqlite3.connect(str(dst_db))
                try:
                    source.backup(target)
                finally:
                    target.close()
                    source.close()

                # 完整性校验
                if not self._verify_db_backup(dst_db):
                    logger.error(
                        "数据库备份校验失败，删除损坏备份 timestamp=%s, backup_path=%s",
                        timestamp,
                        dst_db,
                    )
                    with contextlib.suppress(OSError):
                        dst_db.unlink()
                    continue

                logger.info(
                    "数据库备份完成 timestamp=%s, backup_path=%s",
                    timestamp,
                    dst_db,
                )
            except Exception as e:
                logger.error(
                    "数据库备份异常 timestamp=%s, db_path=%s, error=%s",
                    timestamp,
                    src_db,
                    e,
                )
                # 异常时清理可能创建的不完整备份
                if dst_db.exists():
                    with contextlib.suppress(OSError):
                        dst_db.unlink()

        # 清理超过 3 份的旧备份
        self._cleanup_old_db_backups(db_root, BACKUP_RETENTION_COUNT)

    @staticmethod
    def _verify_db_backup(backup_path: Path) -> bool:
        """校验数据库备份完整性

        校验规则：``PRAGMA integrity_check`` 返回 ``"ok"``

        Args:
            backup_path: 备份数据库文件路径

        Returns:
            True 表示校验通过，False 表示校验失败
        """
        try:
            conn = sqlite3.connect(str(backup_path))
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                return result == "ok"
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.error(
                "数据库备份完整性校验异常 backup_path=%s, error=%s",
                backup_path,
                e,
            )
            return False

    def _cleanup_old_db_backups(self, db_root: Path, keep_count: int) -> None:
        """清理超过保留份数的旧数据库备份

        策略：按文件名降序排序（时间戳字典序 = 时间序），保留最新 N 份。

        Args:
            db_root: 数据库备份根目录（backups/db/）
            keep_count: 保留份数
        """
        if not db_root.exists():
            return

        db_files = [f for f in db_root.iterdir() if f.is_file() and f.suffix == ".db"]
        db_files.sort(key=lambda f: f.name, reverse=True)

        for old_file in db_files[keep_count:]:
            try:
                old_file.unlink()
                logger.info(
                    "清理旧数据库备份 file=%s",
                    old_file,
                )
            except OSError as e:
                logger.warning(
                    "清理旧数据库备份失败 file=%s, error=%s",
                    old_file,
                    e,
                )


# 单例实例（供 ScheduleService 注册为 cron 任务）
backup_service = BackupService()
