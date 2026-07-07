"""
Mood Providers - 心情模块数据访问层

提供 mood_types / mood_entries / mood_impacts 三张表的数据访问接口。
按照架构原则：一个 Provider 对应一张表，多个 Provider 写在同一个文件内。
"""

import uuid
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

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

    _FILTER_FIELDS: set[str] = {
        "id",
        "name",
        "icon",
        "color",
        "score",
        "is_dark",
        "sort_order",
        "created_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "name", "score", "sort_order", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "name",
        "icon",
        "color",
        "score",
        "is_dark",
        "sort_order",
        "created_at",
    }
    _UPDATE_FIELDS: set[str] = {"name", "icon", "color", "score", "is_dark", "sort_order"}

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_mood_types(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'is_dark': True})
            records, total = provider.query_mood_types(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_mood_types(options)
        """
        return self._generic_query(options)

    def get_mood_types(self) -> list[dict[str, Any]]:
        """
        获取所有心情类型（按 sort_order DESC 排序）

        Returns:
            List[Dict]: 心情类型列表
        """
        options = QueryOptions(order_by="sort_order", order_desc=True)
        results, _ = self._generic_query(options)
        return results

    def get_mood_type_by_id(self, mood_type_id: str) -> dict[str, Any] | None:
        """
        按 ID 获取心情类型

        Args:
            mood_type_id: 心情类型 ID

        Returns:
            Optional[Dict]: 心情类型，不存在返回 None
        """
        options = QueryOptions(filters={"id": mood_type_id}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_mood_type(self, data: dict[str, Any]) -> str:
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
            insert_data = {"id": new_id}

            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            insert_data.update(data)
            self._generic_insert(insert_data)
            logger.info("创建心情类型成功: %s", new_id)
            return new_id
        except Exception as e:
            logger.error("创建心情类型失败: %s", e)
            raise DataAccessError(f"创建心情类型失败: {e}") from e

    def update_mood_type(self, mood_type_id: str, data: dict[str, Any]) -> bool:
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
            logger.error("更新心情类型 %s 失败: %s", mood_type_id, e)
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
                logger.info("删除心情类型 %s 成功", mood_type_id)
            return success
        except Exception as e:
            logger.error("删除心情类型 %s 失败: %s", mood_type_id, e)
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
                cursor.execute(
                    "SELECT COUNT(*) FROM mood_entries WHERE mood_type_id = ?", (mood_type_id,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error("统计心情类型 %s 关联记录数失败: %s", mood_type_id, e)
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

    _FILTER_FIELDS: set[str] = {"id", "mood_type_id", "score", "content", "factors", "created_at"}
    _ORDER_FIELDS: set[str] = {"id", "score", "created_at"}
    _SELECT_FIELDS: set[str] = {"id", "mood_type_id", "score", "content", "factors", "created_at"}
    _UPDATE_FIELDS: set[str] = {"mood_type_id", "score", "content", "factors"}

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_mood_entries(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'mood_type_id': 'mood-type-abc'})
            records, total = provider.query_mood_entries(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_mood_entries(options)
        """
        return self._generic_query(options)

    def get_mood_entries(
        self, start_time: str | None = None, end_time: str | None = None
    ) -> list[dict[str, Any]]:
        """
        获取心情记录列表（按 created_at ASC 排序）

        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS（可选）
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS（可选，不包含此时刻）

        Returns:
            List[Dict]: 心情记录列表

        Raises:
            DataAccessError: 数据库操作失败
        """
        # 使用自定义 SQL 处理时间范围
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                conditions = []
                params = []
                if start_time:
                    conditions.append("created_at >= ?")
                    params.append(start_time)
                if end_time:
                    conditions.append("created_at < ?")
                    params.append(end_time)
                where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
                cursor.execute(f"SELECT * FROM mood_entries{where} ORDER BY created_at ASC", params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error("获取心情记录列表失败: %s", e)
            raise DataAccessError(f"获取心情记录列表失败: {e}") from e

    def get_mood_entry_by_id(self, entry_id: str) -> dict[str, Any] | None:
        """
        按 ID 获取心情记录

        Args:
            entry_id: 心情记录 ID

        Returns:
            Optional[Dict]: 心情记录，不存在返回 None
        """
        options = QueryOptions(filters={"id": entry_id}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_mood_entry(self, data: dict[str, Any]) -> str:
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
            insert_data = {"id": new_id}

            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            insert_data.update(data)
            self._generic_insert(insert_data)
            logger.info("创建心情记录成功: %s", new_id)
            return new_id
        except Exception as e:
            logger.error("创建心情记录失败: %s", e)
            raise DataAccessError(f"创建心情记录失败: {e}") from e

    def update_mood_entry(self, entry_id: str, data: dict[str, Any]) -> bool:
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
            logger.error("更新心情记录 %s 失败: %s", entry_id, e)
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
                logger.info("删除心情记录 %s 成功", entry_id)
            return success
        except Exception as e:
            logger.error("删除心情记录 %s 失败: %s", entry_id, e)
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

    _FILTER_FIELDS: set[str] = {"id", "name", "sort_order", "created_at"}
    _ORDER_FIELDS: set[str] = {"id", "name", "sort_order", "created_at"}
    _SELECT_FIELDS: set[str] = {"id", "name", "sort_order", "created_at"}
    _UPDATE_FIELDS: set[str] = {"name", "sort_order"}

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_mood_impacts(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'name': '工作'})
            records, total = provider.query_mood_impacts(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_mood_impacts(options)
        """
        return self._generic_query(options)

    def get_mood_impacts(self) -> list[dict[str, Any]]:
        """
        获取所有影响因素（按 sort_order DESC 排序）

        Returns:
            List[Dict]: 影响因素列表
        """
        options = QueryOptions(order_by="sort_order", order_desc=True)
        results, _ = self._generic_query(options)
        return results

    def create_mood_impact(self, data: dict[str, Any]) -> int:
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
                cursor.execute(
                    """
                    INSERT INTO mood_impacts (name, sort_order)
                    VALUES (?, ?)
                """,
                    (data["name"], data.get("sort_order", 0)),
                )
                new_id = cursor.lastrowid
                logger.info("创建影响因素成功: %s", data["name"])
                return new_id
        except Exception as e:
            logger.error("创建影响因素失败: %s", e)
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
                logger.info("删除影响因素 %s 成功", impact_id)
            return success
        except Exception as e:
            logger.error("删除影响因素 %s 失败: %s", impact_id, e)
            raise DataAccessError(f"删除影响因素 {impact_id} 失败: {e}") from e
