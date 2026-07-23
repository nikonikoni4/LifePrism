"""
JournalProvider - Goal Journal 数据访问层

从 server/providers/journal_provider.py 迁移而来，统一走 _generic_* CRUD 通道。

迁移要点：
- create_journal 走 _generic_insert(data, id_prefix="journal-")
- update_journal 走 _generic_update（自动更新 updated_at 为 ISO 8601 + UTC）
- delete_journal 走 _generic_delete（含写墓碑到 deletion_log）
- 异常处理抛出 DataAccessError（而非静默返回 None/False）

表特征：
- TEXT 主键表（id 格式：journal-{uuid[:8]}）
- 在 SYNC_TABLES 中（删除时写墓碑，墓碑 record_id = 主键值）
- 不在 HASH_ID_PREFIXES 中（无 hash_id 字段）
- timestamps=True, update_at=True
"""

import sqlite3
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class JournalProvider(LWBaseDataProvider):
    """Goal Journal 数据提供者

    职责：提供 goal_journal 表的 CRUD 操作，统一走 _generic_* 通道。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "goal_journal"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "date"  # goal_journal 有 date 字段（YYYY-MM-DD）
    _TIME_FIELD = "time"  # goal_journal 有 time 字段（HH:MM）
    _ON_CONFLICT = "abort"  # 不应有重复 ID，冲突时抛异常

    _FILTER_FIELDS: set[str] = {
        "id",
        "goal_id",
        "date",
        "time",
        "mood",
        "duration",
        "tags",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"date", "time", "created_at", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "goal_id",
        "date",
        "time",
        "content",
        "mood",
        "duration",
        "tags",
        "created_at",
        "updated_at",
    }
    # 允许更新的字段（不含 id/goal_id 主键和外键，不含 created_at/updated_at 系统字段）
    _UPDATE_FIELDS: set[str] = {
        "date",
        "time",
        "content",
        "mood",
        "duration",
        "tags",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 查询方法（直接 SQL，保持原 ORDER BY 行为）====================

    def get_journals_by_goal(self, goal_id: str) -> list[dict[str, Any]]:
        """获取指定目标的所有日志（按 date DESC, time DESC 排序）

        注：使用直接 SQL 而非 _generic_query，因为 _generic_query 仅支持单字段排序，
        而原实现需要 date DESC, time DESC 双字段排序以保持行为等价。

        Args:
            goal_id: 目标 ID

        Returns:
            日志列表（无匹配返回空列表，这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回空列表）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM goal_journal
                    WHERE goal_id = ?
                    ORDER BY date DESC, time DESC
                    """,
                    (goal_id,),
                )
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row, strict=False)) for row in rows]
        except sqlite3.Error as e:
            logger.error("获取目标 %s 的日志失败: error=%s", goal_id, e)
            raise DataAccessError(
                message=f"获取目标 {goal_id} 的日志失败",
                details={"goal_id": goal_id, "error": str(e)},
                cause=e,
            ) from e

    def get_journal_by_id(self, journal_id: str) -> dict[str, Any] | None:
        """按 ID 获取单个日志

        Args:
            journal_id: 日志 ID（格式：journal-xxx）

        Returns:
            日志数据；不存在返回 None（这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回 None）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM goal_journal WHERE id = ?", (journal_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row, strict=False))
        except sqlite3.Error as e:
            logger.error("获取日志 %s 失败: error=%s", journal_id, e)
            raise DataAccessError(
                message=f"获取日志 {journal_id} 失败",
                details={"journal_id": journal_id, "error": str(e)},
                cause=e,
            ) from e

    # ==================== 核心方法（使用通用方法） ====================

    def create_journal(self, data: dict[str, Any]) -> str:
        """创建新日志（走 _generic_insert 通道）

        _generic_insert 自动处理：
        - 生成 journal- 前缀 ID（8 位 hex）
        - 写入 created_at/updated_at（ISO 8601 + UTC，goal_journal 配置了 timestamps=True）
        - 走 _ON_CONFLICT = "abort" 策略（重复 ID 抛异常）

        Args:
            data: 日志数据，应包含 goal_id, date, content 等字段

        Returns:
            新日志 ID（格式：journal-{8 位 hex}）

        Raises:
            DataAccessError: 数据库操作失败（如重复 ID、外键约束失败等）
        """
        journal_id = self._generic_insert(data, id_prefix="journal-")
        logger.info("创建日志成功，ID: %s", journal_id)
        return journal_id

    def update_journal(self, journal_id: str, data: dict[str, Any]) -> bool:
        """更新日志（走 _generic_update 通道）

        _generic_update 自动处理：
        - 更新 updated_at（ISO 8601 + UTC，goal_journal 配置 update_at=True）
        - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）
        - 空数据返回 True（无操作）

        Args:
            journal_id: 日志 ID（格式：journal-xxx）
            data: 要更新的字段

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            ValueError: 字段不在 _UPDATE_FIELDS 白名单中
            DataAccessError: 数据库操作失败
        """
        success = self._generic_update(journal_id, data)
        if success:
            logger.info("更新日志 %s 成功", journal_id)
        return success

    def delete_journal(self, journal_id: str) -> bool:
        """删除日志（走 _generic_delete 通道）

        _generic_delete 自动处理：
        - 删除 goal_journal 表中的记录
        - 写墓碑到 deletion_log（goal_journal 在 SYNC_TABLES 中）
        - 墓碑 record_id = 主键值（TEXT 主键表，不在 HASH_ID_PREFIXES 中）
        - 墓碑与 DELETE 在同一事务（DELETE 失败时墓碑回滚）

        Args:
            journal_id: 日志 ID（格式：journal-xxx）

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            DataAccessError: 数据库操作失败
        """
        success = self._generic_delete(journal_id)
        if success:
            logger.info("删除日志 %s 成功", journal_id)
        return success


# 创建全局单例
journal_provider = LazySingleton(JournalProvider)
