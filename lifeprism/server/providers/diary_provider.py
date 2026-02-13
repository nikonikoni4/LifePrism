"""
Diary 数据提供者
提供日记的数据库操作（仅 meta 信息，内容存 md 文件）
"""
from typing import Optional, List, Dict, Any

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger, LazySingleton

logger = get_logger(__name__)


class DiaryProvider(LWBaseDataProvider):
    """
    日记数据提供者

    继承 LWBaseDataProvider，提供 diary 表的 CRUD 操作。
    date (YYYY-MM-DD) 作为主键。
    """

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_diary_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """
        按日期获取单条日记 meta

        Args:
            date: 日期 YYYY-MM-DD

        Returns:
            Optional[Dict]: 日记 meta，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM diary WHERE date = ?", (date,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.error(f"获取日记 {date} 失败: {e}")
            return None

    def get_diaries_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        获取日期范围内的日记列表

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            List[Dict]: 日记 meta 列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM diary WHERE date >= ? AND date <= ? ORDER BY date DESC",
                    (start_date, end_date)
                )
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"获取日记列表 {start_date}~{end_date} 失败: {e}")
            return []

    def create_diary(self, date: str) -> bool:
        """
        创建日记记录（只传 date，其他字段用 DB 默认值）

        Args:
            date: 日期 YYYY-MM-DD

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO diary (date) VALUES (?)", (date,))
                logger.info(f"创建日记 {date} 成功")
                return True
        except Exception as e:
            logger.error(f"创建日记 {date} 失败: {e}")
            return False

    def update_diary(self, date: str, data: Dict[str, Any]) -> bool:
        """
        更新日记 meta

        Args:
            date: 日期 YYYY-MM-DD
            data: 要更新的字段

        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                allowed_fields = ['mood', 'importance', 'custom_tags', 'word_count', 'ai_summary']

                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if not set_clauses:
                    return True

                set_clauses.append("updated_at = datetime('now','localtime')")
                values.append(date)
                sql = f"UPDATE diary SET {', '.join(set_clauses)} WHERE date = ?"

                cursor.execute(sql, values)
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"更新日记 {date} 失败: {e}")
            return False


# 创建全局单例
diary_provider = LazySingleton(DiaryProvider)
