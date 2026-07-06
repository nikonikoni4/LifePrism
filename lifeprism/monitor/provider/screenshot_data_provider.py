"""
Screenshot 元数据提供者
"""
import sqlite3
from typing import Any, Dict, List

from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class ScreenshotDataProvider(LWBaseDataProvider):
    """负责 screen_captures 表的持久化操作。"""

    def create_capture(self, data: Dict[str, Any]) -> bool:
        """
        保存截图元数据到数据库。

        Args:
            data: 截图元数据字典

        Returns:
            bool: 是否保存成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            result = self.db.insert("screen_captures", data) > 0
            logger.debug("截图元数据保存: id=%s", data.get('id'))
            return result
        except sqlite3.Error as exc:
            logger.error("保存截图元数据失败: %s", exc)
            raise DataAccessError(f"Failed to insert screenshot metadata: {exc}") from exc
        except OSError as exc:
            logger.error("数据库 I/O 错误: %s", exc)
            raise DataAccessError(f"Database I/O error: {exc}") from exc

    def list_expired_captures(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        """
        查询过期的截图记录。

        Args:
            cutoff_iso: 截止时间（ISO格式）

        Returns:
            List[Dict]: 过期截图记录列表

        Raises:
            DataAccessError: 数据库查询失败
        """
        query = """
            SELECT id, file_path, captured_at
            FROM screen_captures
            WHERE captured_at < ?
            ORDER BY captured_at ASC
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (cutoff_iso,))
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except sqlite3.Error as exc:
            logger.error("查询过期截图失败: %s", exc)
            raise DataAccessError(f"Failed to query expired captures: {exc}") from exc

    def delete_capture(self, capture_id: str) -> bool:
        """
        删除截图元数据记录。

        Args:
            capture_id: 截图ID

        Returns:
            bool: 是否删除成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            result = self.db.delete("screen_captures", {"id": capture_id}) > 0
            logger.debug("截图元数据删除: id=%s", capture_id)
            return result
        except sqlite3.Error as exc:
            logger.error("删除截图元数据失败: %s", exc)
            raise DataAccessError(f"Failed to delete screenshot metadata: {exc}") from exc
        except OSError as exc:
            logger.error("数据库 I/O 错误: %s", exc)
            raise DataAccessError(f"Database I/O error: {exc}") from exc
