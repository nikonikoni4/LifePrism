"""
Map Cache Providers

提供 multi_purpose_map_cache 和 single_purpose_map_cache 表的数据访问接口。
"""
from typing import Dict, Any, List, Optional, Tuple, Set
from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger,LazySingleton

logger = get_logger(__name__)


# ==================== MultiPurposeMapCacheProvider ====================

class MultiPurposeMapCacheProvider(LWBaseDataProvider):
    """
    多用途应用映射缓存数据提供者（对应 multi_purpose_map_cache 表）

    职责：提供 multi_purpose_map_cache 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "multi_purpose_map_cache"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'app', 'title', 'category_id', 'sub_category_id',
        'state', 'link_to_goal_id', 'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'app', 'title', 'created_at', 'updated_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'app', 'title', 'app_description', 'title_analysis',
        'category_id', 'sub_category_id', 'state', 'link_to_goal_id',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'app', 'title', 'app_description', 'title_analysis',
        'category_id', 'sub_category_id', 'state', 'link_to_goal_id'
    }

    # ==================== 核心方法（使用通用方法） ====================

    def query_multi_purpose_map_cache(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项

        Returns:
            (记录列表, 总记录数)
        """
        # 如果没有提供 options，使用默认的 order_by
        if options is None:
            options = QueryOptions(order_by='id')
        elif options.order_by == 'date':
            # 如果是默认的 'date'，改为 'id'
            options = QueryOptions(
                date_range=options.date_range,
                time_range=options.time_range,
                filters=options.filters,
                order_by='id',
                order_desc=options.order_desc,
                page=options.page,
                page_size=options.page_size,
                fields=options.fields
            )
        return self._generic_query(options)

    def get_multi_purpose_map_cache_by_id(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        按主键获取单条记录

        Args:
            cache_id: 主键值（格式：m-xxx）

        Returns:
            记录，不存在返回 None
        """
        options = QueryOptions(filters={'id': cache_id}, order_by='id')
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_multi_purpose_map_cache(self, data: Dict[str, Any]) -> bool:
        """
        创建记录

        Args:
            data: 记录数据（必须包含 id, app, title）

        Returns:
            是否成功
        """
        try:
            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            # 验证必需字段
            if 'id' not in data or 'app' not in data or 'title' not in data:
                raise ValueError("Missing required fields: id, app, title")

            self._generic_insert(data)
            logger.info(f"创建 multi_purpose_map_cache 记录成功: {data.get('id')}")
            return True
        except Exception as e:
            logger.error(f"创建 multi_purpose_map_cache 记录失败: {e}")
            return False

    def update_multi_purpose_map_cache(self, cache_id: str, data: Dict[str, Any]) -> bool:
        """
        更新记录

        Args:
            cache_id: 主键值（格式：m-xxx）
            data: 要更新的字段

        Returns:
            是否成功
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            return self._generic_update(cache_id, data)
        except Exception as e:
            logger.error(f"更新 multi_purpose_map_cache 记录 {cache_id} 失败: {e}")
            return False

    def delete_multi_purpose_map_cache(self, cache_id: str) -> bool:
        """
        删除记录

        Args:
            cache_id: 主键值（格式：m-xxx）

        Returns:
            是否成功
        """
        try:
            success = self._generic_delete(cache_id)
            if success:
                logger.info(f"删除 multi_purpose_map_cache 记录 {cache_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除 multi_purpose_map_cache 记录 {cache_id} 失败: {e}")
            return False

    def batch_insert_multi_purpose_map_cache(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入记录

        Args:
            data_list: 记录列表

        Returns:
            成功插入的数量
        """
        if not data_list:
            return 0

        try:
            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
            for data in data_list:
                invalid_fields = set(data.keys()) - allowed_fields
                if invalid_fields:
                    raise ValueError(f"Invalid insert fields: {invalid_fields}")

                # 验证必需字段
                if 'id' not in data or 'app' not in data or 'title' not in data:
                    raise ValueError("Missing required fields: id, app, title")

            # 手动实现批量插入
            count = 0
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for data in data_list:
                    # 构建字段列表和占位符
                    fields = list(data.keys())
                    placeholders = ','.join('?' * len(fields))
                    fields_str = ','.join(fields)
                    values = [data[f] for f in fields]

                    sql = f"INSERT INTO {self._TABLE_NAME} ({fields_str}) VALUES ({placeholders})"
                    cursor.execute(sql, values)
                    count += cursor.rowcount

                conn.commit()

            logger.info(f"批量插入 {count} 条 multi_purpose_map_cache 记录")
            return count
        except Exception as e:
            logger.error(f"批量插入 multi_purpose_map_cache 记录失败: {e}")
            return 0

    def batch_update_multi_purpose_map_cache(
        self,
        cache_ids: List[str],
        data: Dict[str, Any]
    ) -> int:
        """
        批量更新记录

        Args:
            cache_ids: 主键列表
            data: 要更新的字段

        Returns:
            成功更新的数量
        """
        if not cache_ids or not data:
            return 0

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            # 手动实现批量更新
            from datetime import datetime
            if 'updated_at' not in data:
                data['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
            placeholders = ','.join('?' * len(cache_ids))
            values = list(data.values()) + cache_ids

            sql = f"""
                UPDATE {self._TABLE_NAME}
                SET {set_clause}
                WHERE {self._PRIMARY_KEY} IN ({placeholders})
            """

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                count = cursor.rowcount

            logger.info(f"批量更新 {count} 条 multi_purpose_map_cache 记录")
            return count
        except Exception as e:
            logger.error(f"批量更新 multi_purpose_map_cache 记录失败: {e}")
            return 0

    def batch_delete_multi_purpose_map_cache(self, cache_ids: List[str]) -> int:
        """
        批量删除记录

        Args:
            cache_ids: 主键列表

        Returns:
            成功删除的数量
        """
        if not cache_ids:
            return 0

        try:
            # 手动实现批量删除
            placeholders = ','.join('?' * len(cache_ids))
            sql = f"DELETE FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} IN ({placeholders})"

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, cache_ids)
                conn.commit()
                count = cursor.rowcount

            logger.info(f"批量删除 {count} 条 multi_purpose_map_cache 记录")
            return count
        except Exception as e:
            logger.error(f"批量删除 multi_purpose_map_cache 记录失败: {e}")
            return 0


# ==================== SinglePurposeMapCacheProvider ====================

class SinglePurposeMapCacheProvider(LWBaseDataProvider):
    """
    单用途应用映射缓存数据提供者（对应 single_purpose_map_cache 表）

    职责：提供 single_purpose_map_cache 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "single_purpose_map_cache"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'app', 'title', 'category_id', 'sub_category_id',
        'state', 'link_to_goal_id', 'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'app', 'title', 'created_at', 'updated_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'app', 'title', 'app_description',
        'category_id', 'sub_category_id', 'state', 'link_to_goal_id',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'app', 'title', 'app_description',
        'category_id', 'sub_category_id', 'state', 'link_to_goal_id'
    }

    # ==================== 核心方法（使用通用方法） ====================

    def query_single_purpose_map_cache(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项

        Returns:
            (记录列表, 总记录数)
        """
        # 如果没有提供 options，使用默认的 order_by
        if options is None:
            options = QueryOptions(order_by='id')
        elif options.order_by == 'date':
            # 如果是默认的 'date'，改为 'id'
            options = QueryOptions(
                date_range=options.date_range,
                time_range=options.time_range,
                filters=options.filters,
                order_by='id',
                order_desc=options.order_desc,
                page=options.page,
                page_size=options.page_size,
                fields=options.fields
            )
        return self._generic_query(options)

    def get_single_purpose_map_cache_by_id(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        按主键获取单条记录

        Args:
            cache_id: 主键值（格式：s-xxx）

        Returns:
            记录，不存在返回 None
        """
        options = QueryOptions(filters={'id': cache_id}, order_by='id')
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_single_purpose_map_cache(self, data: Dict[str, Any]) -> bool:
        """
        创建记录

        Args:
            data: 记录数据（必须包含 id, app, title）

        Returns:
            是否成功
        """
        try:
            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            # 验证必需字段
            if 'id' not in data or 'app' not in data or 'title' not in data:
                raise ValueError("Missing required fields: id, app, title")

            self._generic_insert(data)
            logger.info(f"创建 single_purpose_map_cache 记录成功: {data.get('id')}")
            return True
        except Exception as e:
            logger.error(f"创建 single_purpose_map_cache 记录失败: {e}")
            return False

    def update_single_purpose_map_cache(self, cache_id: str, data: Dict[str, Any]) -> bool:
        """
        更新记录

        Args:
            cache_id: 主键值（格式：s-xxx）
            data: 要更新的字段

        Returns:
            是否成功
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            return self._generic_update(cache_id, data)
        except Exception as e:
            logger.error(f"更新 single_purpose_map_cache 记录 {cache_id} 失败: {e}")
            return False

    def delete_single_purpose_map_cache(self, cache_id: str) -> bool:
        """
        删除记录

        Args:
            cache_id: 主键值（格式：s-xxx）

        Returns:
            是否成功
        """
        try:
            success = self._generic_delete(cache_id)
            if success:
                logger.info(f"删除 single_purpose_map_cache 记录 {cache_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除 single_purpose_map_cache 记录 {cache_id} 失败: {e}")
            return False

    def batch_insert_single_purpose_map_cache(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入记录

        Args:
            data_list: 记录列表

        Returns:
            成功插入的数量
        """
        if not data_list:
            return 0

        try:
            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
            for data in data_list:
                invalid_fields = set(data.keys()) - allowed_fields
                if invalid_fields:
                    raise ValueError(f"Invalid insert fields: {invalid_fields}")

                # 验证必需字段
                if 'id' not in data or 'app' not in data or 'title' not in data:
                    raise ValueError("Missing required fields: id, app, title")

            # 手动实现批量插入
            count = 0
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for data in data_list:
                    # 构建字段列表和占位符
                    fields = list(data.keys())
                    placeholders = ','.join('?' * len(fields))
                    fields_str = ','.join(fields)
                    values = [data[f] for f in fields]

                    sql = f"INSERT INTO {self._TABLE_NAME} ({fields_str}) VALUES ({placeholders})"
                    cursor.execute(sql, values)
                    count += cursor.rowcount

                conn.commit()

            logger.info(f"批量插入 {count} 条 single_purpose_map_cache 记录")
            return count
        except Exception as e:
            logger.error(f"批量插入 single_purpose_map_cache 记录失败: {e}")
            return 0

    def batch_update_single_purpose_map_cache(
        self,
        cache_ids: List[str],
        data: Dict[str, Any]
    ) -> int:
        """
        批量更新记录

        Args:
            cache_ids: 主键列表
            data: 要更新的字段

        Returns:
            成功更新的数量
        """
        if not cache_ids or not data:
            return 0

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            # 手动实现批量更新
            from datetime import datetime
            if 'updated_at' not in data:
                data['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
            placeholders = ','.join('?' * len(cache_ids))
            values = list(data.values()) + cache_ids

            sql = f"""
                UPDATE {self._TABLE_NAME}
                SET {set_clause}
                WHERE {self._PRIMARY_KEY} IN ({placeholders})
            """

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                count = cursor.rowcount

            logger.info(f"批量更新 {count} 条 single_purpose_map_cache 记录")
            return count
        except Exception as e:
            logger.error(f"批量更新 single_purpose_map_cache 记录失败: {e}")
            return 0

    def batch_delete_single_purpose_map_cache(self, cache_ids: List[str]) -> int:
        """
        批量删除记录

        Args:
            cache_ids: 主键列表

        Returns:
            成功删除的数量
        """
        if not cache_ids:
            return 0

        try:
            # 手动实现批量删除
            placeholders = ','.join('?' * len(cache_ids))
            sql = f"DELETE FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} IN ({placeholders})"

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, cache_ids)
                conn.commit()
                count = cursor.rowcount

            logger.info(f"批量删除 {count} 条 single_purpose_map_cache 记录")
            return count
        except Exception as e:
            logger.error(f"批量删除 single_purpose_map_cache 记录失败: {e}")
            return 0

