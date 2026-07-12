"""
Value 数据提供者
提供 user_values 表的 CRUD 操作 + 级联删除事务
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.exceptions import DataAccessError
from lifeprism.utils.time_utils import get_utc_now_iso

logger = get_logger(__name__)


class ValueProvider(LWBaseDataProvider):
    """
    价值模块数据提供者

    继承 LWBaseDataProvider，提供 user_values 的 CRUD 操作。
    """

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_values(self) -> list[dict[str, Any]]:
        """
        获取所有价值（按 sort_order DESC, created_at DESC 排序）

        Returns:
            List[Dict]: 价值列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM user_values ORDER BY sort_order DESC, created_at DESC"
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("获取价值列表失败: error=%s", e)
            raise DataAccessError(message="获取价值列表失败", details={"error": str(e)}) from e

    def get_value_by_id(self, value_id: str) -> dict[str, Any] | None:
        """
        按 ID 获取价值

        Args:
            value_id: 价值 ID (格式: val-xxx)

        Returns:
            Optional[Dict]: 价值记录，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_values WHERE id = ?", (value_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row, strict=False))
                return None
        except sqlite3.Error as e:
            logger.error("获取价值失败: value_id=%s, error=%s", value_id, e)
            raise DataAccessError(
                message="获取价值失败", details={"value_id": value_id, "error": str(e)}
            ) from e

    def create_value(self, data: dict[str, Any]) -> str | None:
        """
        创建价值

        Args:
            data: 价值数据（需包含 keywords）

        Returns:
            Optional[str]: 新创建的 ID，失败返回 None
        """
        try:
            new_id = f"val-{str(uuid.uuid4())[:8]}"
            now_iso = get_utc_now_iso()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_values (id, keywords, content_positive, content_negative, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        new_id,
                        data["keywords"],
                        data.get("content_positive"),
                        data.get("content_negative"),
                        data.get("sort_order", 0),
                        now_iso,
                        now_iso,
                    ),
                )
            logger.info(f"创建价值成功: {new_id}")
            return new_id
        except sqlite3.IntegrityError:
            raise
        except sqlite3.Error as e:
            logger.error("创建价值失败: keywords=%s, error=%s", data.get("keywords"), e)
            raise DataAccessError(
                message="创建价值失败", details={"keywords": data.get("keywords"), "error": str(e)}
            ) from e

    def update_value(self, value_id: str, data: dict[str, Any]) -> bool:
        """
        更新价值（动态构建 SET，手动追加 updated_at）

        Args:
            value_id: 价值 ID
            data: 要更新的字段

        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                allowed_fields = ["keywords", "content_positive", "content_negative", "sort_order"]
                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                if not set_clauses:
                    return True
                set_clauses.append("updated_at = ?")
                values.append(datetime.now(timezone.utc).isoformat())
                values.append(value_id)
                sql = f"UPDATE user_values SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(sql, values)
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("更新价值失败: value_id=%s, error=%s", value_id, e)
            raise DataAccessError(
                message="更新价值失败", details={"value_id": value_id, "error": str(e)}
            ) from e

    def delete_value_with_cascade(self, value_id: str, cascade: bool) -> bool:
        """
        删除价值（事务内处理关联承诺）

        Args:
            value_id: 价值 ID
            cascade: True=级联删除承诺，False=置空承诺的 value_id

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                if cascade:
                    cursor.execute("DELETE FROM commitments WHERE value_id = ?", (value_id,))
                else:
                    cursor.execute(
                        "UPDATE commitments SET value_id = NULL WHERE value_id = ?", (value_id,)
                    )
                cursor.execute("DELETE FROM user_values WHERE id = ?", (value_id,))
                deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"删除价值成功: {value_id} (cascade={cascade})")
            return deleted
        except sqlite3.Error as e:
            logger.error("删除价值失败: value_id=%s, cascade=%s, error=%s", value_id, cascade, e)
            raise DataAccessError(
                message="删除价值失败",
                details={"value_id": value_id, "cascade": cascade, "error": str(e)},
            ) from e

    def count_commitments_by_value(self, value_id: str) -> int:
        """
        统计某价值关联的承诺数

        Args:
            value_id: 价值 ID

        Returns:
            int: 承诺数，查询失败返回 -1
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM commitments WHERE value_id = ?", (value_id,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("统计价值关联承诺数失败: value_id=%s, error=%s", value_id, e)
            raise DataAccessError(
                message="统计价值关联承诺数失败", details={"value_id": value_id, "error": str(e)}
            ) from e


value_provider = LazySingleton(ValueProvider)
