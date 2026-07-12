"""
Goal Journal 数据提供者
提供 Goal Journal 日志的数据库操作
"""

import uuid
from typing import Any

from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.time_utils import get_utc_now_iso

logger = get_logger(__name__)


class JournalProvider(LWBaseDataProvider):
    """
    目标日志数据提供者

    继承 LWBaseDataProvider，提供 Goal Journal 的 CRUD 操作
    """

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_journals_by_goal(self, goal_id: str) -> list[dict[str, Any]]:
        """
        获取指定目标的所有日志

        Args:
            goal_id: 目标 ID

        Returns:
            List[Dict]: 日志列表，按日期降序排列
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

        except Exception as e:
            logger.error("获取目标 %s 的日志失败: error=%s", goal_id, e)
            return []

    def get_journal_by_id(self, journal_id: str) -> dict[str, Any] | None:
        """
        按 ID 获取单个日志

        Args:
            journal_id: 日志 ID (格式: journal-xxx)

        Returns:
            Optional[Dict]: 日志数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM goal_journal WHERE id = ?", (journal_id,))

                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row, strict=False))
                return None

        except Exception as e:
            logger.error("获取日志 %s 失败: error=%s", journal_id, e)
            return None

    def create_journal(self, data: dict[str, Any]) -> str | None:
        """
        创建新日志

        Args:
            data: 日志数据

        Returns:
            Optional[str]: 新日志 ID (格式: journal-xxx)，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 生成唯一 ID
                journal_id = f"journal-{str(uuid.uuid4())[:8]}"

                now_iso = get_utc_now_iso()

                # 构建插入数据
                columns = [
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
                ]
                values = [
                    journal_id,
                    data.get("goal_id"),
                    data.get("date"),
                    data.get("time"),
                    data.get("content"),
                    data.get("mood", "neutral"),
                    data.get("duration", 0),
                    data.get("tags", "[]"),
                    now_iso,
                    now_iso,
                ]

                placeholders = ", ".join(["?" for _ in columns])
                columns_str = ", ".join(columns)

                cursor.execute(
                    f"INSERT INTO goal_journal ({columns_str}) VALUES ({placeholders})", values
                )

                logger.info("创建日志成功，ID: %s", journal_id)
                return journal_id

        except Exception as e:
            logger.error("创建日志失败: error=%s", e)
            return None

    def update_journal(self, journal_id: str, data: dict[str, Any]) -> bool:
        """
        更新日志

        Args:
            journal_id: 日志 ID (格式: journal-xxx)
            data: 要更新的字段

        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 允许更新的字段
                allowed_fields = ["date", "time", "content", "mood", "duration", "tags"]

                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if not set_clauses:
                    return True

                # 追加 updated_at（ISO 8601 + UTC 格式）
                set_clauses.append("updated_at = ?")
                values.append(get_utc_now_iso())

                values.append(journal_id)
                sql = f"UPDATE goal_journal SET {', '.join(set_clauses)} WHERE id = ?"

                cursor.execute(sql, values)
                success = cursor.rowcount > 0

                if success:
                    logger.info("更新日志 %s 成功", journal_id)
                return success

        except Exception as e:
            logger.error("更新日志 %s 失败: error=%s", journal_id, e)
            return False

    def delete_journal(self, journal_id: str) -> bool:
        """
        删除日志

        Args:
            journal_id: 日志 ID (格式: journal-xxx)

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM goal_journal WHERE id = ?", (journal_id,))

                success = cursor.rowcount > 0
                if success:
                    logger.info("删除日志 %s 成功", journal_id)
                return success

        except Exception as e:
            logger.error("删除日志 %s 失败: error=%s", journal_id, e)
            return False


# 创建全局单例
journal_provider = LazySingleton(JournalProvider)
