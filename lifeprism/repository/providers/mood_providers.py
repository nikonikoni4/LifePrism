"""
Mood Providers - 心情模块数据访问层

提供 mood_types / mood_entries / mood_impacts 三张表的数据访问接口。
按照架构原则：一个 Provider 对应一张表，多个 Provider 写在同一个文件内。
"""
import sqlite3
import uuid
from typing import Optional, List, Dict, Any, Tuple, Set

from lifeprism.repository import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import DataAccessError, ConflictError, ValidationError

logger = get_logger(__name__)


# ==================== MoodTypeProvider ====================

class MoodTypeProvider(LWBaseDataProvider):
    """
    心情类型数据提供者（对应 mood_types 表）

    职责：提供 mood_types 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "mood_types"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    _FILTER_FIELDS: Set[str] = {
        'id', 'name', 'icon', 'color', 'score', 'is_dark', 'sort_order', 'created_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'name', 'score', 'sort_order', 'created_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'name', 'icon', 'color', 'score', 'is_dark', 'sort_order', 'created_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'icon', 'color', 'score', 'is_dark', 'sort_order'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def get_mood_types(self) -> List[Dict[str, Any]]:
        """
        获取所有心情类型（按 sort_order DESC 排序）

        Returns:
            List[Dict]: 心情类型列表
        """
        options = QueryOptions(
            order_by='sort_order',
            order_desc=True
        )
        results, _ = self._generic_query(options)
        return results

    def get_mood_type_by_id(self, mood_type_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取心情类型

        Args:
            mood_type_id: 心情类型 ID

        Returns:
            Optional[Dict]: 心情类型，不存在返回 None
        """
        options = QueryOptions(filters={'id': mood_type_id}, order_by='id', order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_mood_type(self, data: Dict[str, Any]) -> str:
        """
        创建心情类型

        Args:
            data: 心情类型数据

        Returns:
            str: 新创建的 ID

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 自动生成 ID
            new_id = f"mood-type-{str(uuid.uuid4())[:8]}"
            insert_data = {'id': new_id}

            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            insert_data.update(data)
            self._generic_insert(insert_data)
            logger.info(f"创建心情类型成功: {new_id}")
            return new_id
        except Exception as e:
            logger.error(f"创建心情类型失败: {e}")
            raise DataAccessError(f"创建心情类型失败: {e}") from e

    def update_mood_type(self, mood_type_id: str, data: Dict[str, Any]) -> bool:
        """
        更新心情类型

        Args:
            mood_type_id: 心情类型 ID
            data: 要更新的字段

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            return self._generic_update(mood_type_id, data)
        except Exception as e:
            logger.error(f"更新心情类型 {mood_type_id} 失败: {e}")
            raise DataAccessError(f"更新心情类型 {mood_type_id} 失败: {e}") from e

    def delete_mood_type(self, mood_type_id: str) -> bool:
        """
        删除心情类型

        Args:
            mood_type_id: 心情类型 ID

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(mood_type_id)
            if success:
                logger.info(f"删除心情类型 {mood_type_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除心情类型 {mood_type_id} 失败: {e}")
            raise DataAccessError(f"删除心情类型 {mood_type_id} 失败: {e}") from e

    def count_entries_by_type(self, mood_type_id: str) -> int:
        """
        统计某心情类型关联的记录数

        Args:
            mood_type_id: 心情类型 ID

        Returns:
            int: 记录数

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM mood_entries WHERE mood_type_id = ?", (mood_type_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"统计心情类型 {mood_type_id} 关联记录数失败: {e}")
            raise DataAccessError(f"统计心情类型 {mood_type_id} 关联记录数失败: {e}") from e


# ==================== MoodEntryProvider ====================

class MoodEntryProvider(LWBaseDataProvider):
    """
    心情记录数据提供者（对应 mood_entries 表）

    职责：提供 mood_entries 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "mood_entries"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None  # 没有独立的 date 字段，使用 created_at
    _TIME_FIELD = None

    _FILTER_FIELDS: Set[str] = {
        'id', 'mood_type_id', 'score', 'content', 'factors', 'created_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'score', 'created_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'mood_type_id', 'score', 'content', 'factors', 'created_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'mood_type_id', 'score', 'content', 'factors'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def get_mood_entries(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取心情记录列表（按 created_at ASC 排序）

        Args:
            start_date: 开始日期 YYYY-MM-DD（可选）
            end_date: 结束日期 YYYY-MM-DD（可选）

        Returns:
            List[Dict]: 心情记录列表

        Raises:
            DataAccessError: 数据库操作失败
        """
        # 使用自定义 SQL 处理日期范围（因为需要 date(created_at) 函数）
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                conditions = []
                params = []
                if start_date:
                    conditions.append("date(created_at) >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("date(created_at) <= ?")
                    params.append(end_date)
                where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
                cursor.execute(f"SELECT * FROM mood_entries{where} ORDER BY created_at ASC", params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取心情记录列表失败: {e}")
            raise DataAccessError(f"获取心情记录列表失败: {e}") from e

    def get_mood_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取心情记录

        Args:
            entry_id: 心情记录 ID

        Returns:
            Optional[Dict]: 心情记录，不存在返回 None
        """
        options = QueryOptions(filters={'id': entry_id}, order_by='id', order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_mood_entry(self, data: Dict[str, Any]) -> str:
        """
        创建心情记录

        Args:
            data: 心情记录数据（需包含 mood_type_id, score）

        Returns:
            str: 新创建的 ID

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 自动生成 ID
            new_id = f"mood-{str(uuid.uuid4())[:8]}"
            insert_data = {'id': new_id}

            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            insert_data.update(data)
            self._generic_insert(insert_data)
            logger.info(f"创建心情记录成功: {new_id}")
            return new_id
        except Exception as e:
            logger.error(f"创建心情记录失败: {e}")
            raise DataAccessError(f"创建心情记录失败: {e}") from e

    def update_mood_entry(self, entry_id: str, data: Dict[str, Any]) -> bool:
        """
        更新心情记录

        Args:
            entry_id: 心情记录 ID
            data: 要更新的字段

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            return self._generic_update(entry_id, data)
        except Exception as e:
            logger.error(f"更新心情记录 {entry_id} 失败: {e}")
            raise DataAccessError(f"更新心情记录 {entry_id} 失败: {e}") from e

    def delete_mood_entry(self, entry_id: str) -> bool:
        """
        删除心情记录

        Args:
            entry_id: 心情记录 ID

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(entry_id)
            if success:
                logger.info(f"删除心情记录 {entry_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除心情记录 {entry_id} 失败: {e}")
            raise DataAccessError(f"删除心情记录 {entry_id} 失败: {e}") from e


# ==================== MoodImpactProvider ====================

class MoodImpactProvider(LWBaseDataProvider):
    """
    影响因素数据提供者（对应 mood_impacts 表）

    职责：提供 mood_impacts 表的所有数据访问接口
    注意：此表使用 INTEGER PRIMARY KEY AUTOINCREMENT
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "mood_impacts"
    _PRIMARY_KEY = "id"  # INTEGER AUTOINCREMENT
    _DATE_FIELD = None
    _TIME_FIELD = None

    _FILTER_FIELDS: Set[str] = {
        'id', 'name', 'sort_order', 'created_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'name', 'sort_order', 'created_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'name', 'sort_order', 'created_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'sort_order'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def get_mood_impacts(self) -> List[Dict[str, Any]]:
        """
        获取所有影响因素（按 sort_order DESC 排序）

        Returns:
            List[Dict]: 影响因素列表
        """
        options = QueryOptions(
            order_by='sort_order',
            order_desc=True
        )
        results, _ = self._generic_query(options)
        return results

    def create_mood_impact(self, data: Dict[str, Any]) -> int:
        """
        创建影响因素

        Args:
            data: 影响因素数据（需包含 name）

        Returns:
            int: 新创建的 ID

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            # 使用自定义 SQL 获取 AUTOINCREMENT ID
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO mood_impacts (name, sort_order)
                    VALUES (?, ?)
                """, (data['name'], data.get('sort_order', 0)))
                new_id = cursor.lastrowid
                logger.info(f"创建影响因素成功: {data['name']}")
                return new_id
        except Exception as e:
            logger.error(f"创建影响因素失败: {e}")
            raise DataAccessError(f"创建影响因素失败: {e}") from e

    def delete_mood_impact(self, impact_id: int) -> bool:
        """
        删除影响因素

        Args:
            impact_id: 影响因素 ID

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(impact_id)
            if success:
                logger.info(f"删除影响因素 {impact_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除影响因素 {impact_id} 失败: {e}")
            raise DataAccessError(f"删除影响因素 {impact_id} 失败: {e}") from e


