"""
Diary Provider - 日记数据访问层

职责：提供 diary 表的所有数据访问接口
"""
from typing import Optional, List, Dict, Any, Tuple, Set
from .common_query_options import QueryOptions

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger

logger = get_logger(__name__)




class DiaryProvider(LWBaseDataProvider):
    """
    日记数据提供者

    职责：提供 diary 表的所有数据访问接口
    注意：date (YYYY-MM-DD) 作为主键
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "diary"
    _PRIMARY_KEY = "date"          # ✅ diary 表使用 date 作为主键
    _DATE_FIELD = "date"           # ✅ diary 表有 date 字段
    _TIME_FIELD = None             # ❌ diary 表没有 time 字段

    _FILTER_FIELDS: Set[str] = {
        'date', 'mood', 'importance', 'custom_tags',
        'word_count', 'ai_summary', 'diary_source_hash',
        'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'date', 'created_at', 'updated_at', 'word_count'
    }
    _SELECT_FIELDS: Set[str] = {
        'date', 'mood', 'importance', 'custom_tags',
        'word_count', 'ai_summary', 'diary_source_hash',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'mood', 'importance', 'custom_tags',
        'word_count', 'ai_summary', 'diary_source_hash'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_diaries(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口（使用基类方法）

        Args:
            options: 查询选项

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 查询日期范围
            options = QueryOptions(date_range=("2026-04-01", "2026-04-30"))
            diaries, total = provider.query_diaries(options)

            # 查询特定心情
            options = QueryOptions(filters={'mood': 'happy'})
            diaries, total = provider.query_diaries(options)
        """
        return self._generic_query(options)  # ✅ 直接调用基类方法

    def get_diary_by_id(self, date: str) -> Optional[Dict[str, Any]]:
        """
        按主键（date）获取单条日记（使用基类方法）

        Args:
            date: 日期 YYYY-MM-DD

        Returns:
            日记记录，不存在返回 None
        """
        options = QueryOptions(filters={'date': date})
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def insert_diary(self, date: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        插入日记记录（使用基类方法）

        Args:
            date: 日期 YYYY-MM-DD（主键）
            data: 其他字段（可选）

        Returns:
            是否成功
        """
        try:
            insert_data = {'date': date}
            if data:
                # 白名单验证
                invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
                if invalid_fields:
                    raise ValueError(f"Invalid insert fields: {invalid_fields}")
                insert_data.update(data)

            self._generic_insert(insert_data)
            logger.info(f"创建日记 {date} 成功")
            return True
        except Exception as e:
            logger.error(f"创建日记 {date} 失败: {e}")
            return False

    def update_diary(self, date: str, data: Dict[str, Any]) -> bool:
        """
        更新日记记录

        注意：此方法使用自定义 SQL 是因为需要 SQLite 特定的时间戳函数
        datetime('now','localtime')，通用方法的 auto_timestamp 使用 UTC 时间

        Args:
            date: 日期 YYYY-MM-DD
            data: 要更新的字段

        Returns:
            是否成功
        """
        if not data:
            return True

        try:
            # 使用自定义 SQL 以支持 SQLite 的 datetime('now','localtime')
            if 'updated_at' not in data:
                # 使用 SQLite 特定的时间戳更新
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()

                    # 白名单验证
                    invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
                    if invalid_fields:
                        raise ValueError(f"Invalid update fields: {invalid_fields}")

                    set_clauses = [f"{key} = ?" for key in data.keys()]
                    set_clauses.append("updated_at = datetime('now','localtime')")
                    values = list(data.values()) + [date]

                    sql = f"UPDATE diary SET {', '.join(set_clauses)} WHERE date = ?"
                    cursor.execute(sql, values)
                    conn.commit()

                    return cursor.rowcount > 0
            else:
                # 如果已经提供了 updated_at，使用通用方法
                return self._generic_update(date, data, auto_timestamp=False)
        except Exception as e:
            logger.error(f"更新日记 {date} 失败: {e}")
            return False

    def delete_diary(self, date: str) -> bool:
        """
        删除日记记录（使用基类方法）

        Args:
            date: 日期 YYYY-MM-DD

        Returns:
            是否成功
        """
        try:
            # 现在可以使用通用删除方法（支持自定义主键）
            success = self._generic_delete(date)
            if success:
                logger.info(f"删除日记 {date} 成功")
            return success
        except Exception as e:
            logger.error(f"删除日记 {date} 失败: {e}")
            return False

    # ==================== 特殊方法（兼容旧接口）====================
    # 注意：以下方法是对通用方法的简单封装，提供更清晰的业务语义
    # 新 provider 不应创建此类便捷方法，应直接使用通用方法

    def get_diary_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """
        按日期获取日记（兼容旧接口）

        这是 get_diary_by_id 的别名，因为 diary 表使用 date 作为主键。

        注意：此方法是对 get_diary_by_id 的封装，仅为保持向后兼容。
        新代码应优先使用 get_diary_by_id 或 query_diaries。
        """
        return self.get_diary_by_id(date)

    def get_diaries_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        获取日期范围内的日记列表（兼容旧接口）

        注意：此方法是对 query_diaries 的封装，仅为保持向后兼容。
        新代码应优先使用 query_diaries(QueryOptions(date_range=(start, end)))。

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            日记列表，按日期降序排列
        """
        options = QueryOptions(
            date_range=(start_date, end_date),
            order_by='date',
            order_desc=True
        )
        results, _ = self.query_diaries(options)
        return results

    def create_diary(self, date: str) -> bool:
        """
        创建日记记录（兼容旧接口）

        注意：此方法是对 insert_diary 的封装，仅为保持向后兼容。
        新代码应优先使用 insert_diary(date, data)。

        这是 insert_diary 的简化版本，只传 date。
        """
        return self.insert_diary(date)