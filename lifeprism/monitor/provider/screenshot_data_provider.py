"""
Screenshot 元数据提供者
"""
from typing import Any, Dict, List

from lifeprism.storage.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class ScreenshotDataProvider(LWBaseDataProvider):
    """负责 screen_captures 表的持久化操作。"""

    def create_capture(self, data: Dict[str, Any]) -> bool:
        try:
            return self.db.insert("screen_captures", data) > 0
        except Exception as exc:
            logger.error(f"保存截图元数据失败: {exc}")
            raise

    def list_expired_captures(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        query = """
            SELECT id, file_path, captured_at
            FROM screen_captures
            WHERE captured_at < ?
            ORDER BY captured_at ASC
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_iso,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def delete_capture(self, capture_id: str) -> bool:
        try:
            return self.db.delete("screen_captures", {"id": capture_id}) > 0
        except Exception as exc:
            logger.error(f"删除截图元数据失败: {exc}")
            raise
