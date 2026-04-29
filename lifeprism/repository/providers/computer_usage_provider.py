"""
Computer Usage 数据提供者

职责：提供 user_app_behavior_log 表的所有数据访问接口
"""
from typing import Dict, Any, Optional, List, Tuple, Set
from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class ComputerUsageProvider(LWBaseDataProvider):
    """
    Computer Usage 数据提供者

    职责：提供 user_app_behavior_log 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "user_app_behavior_log"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = "start_time"
    _ON_CONFLICT = "replace"

    _FILTER_FIELDS: Set[str] = {
        'id', 'start_time', 'end_time', 'duration', 'app', 'title',
        'is_multipurpose_app', 'category_id', 'sub_category_id', 'link_to_goal_id'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'start_time', 'end_time', 'duration'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'start_time', 'end_time', 'duration', 'app', 'title',
        'is_multipurpose_app', 'category_id', 'sub_category_id', 'link_to_goal_id'
    }
    _UPDATE_FIELDS: Set[str] = {
        'start_time', 'end_time', 'duration', 'app', 'title',
        'is_multipurpose_app', 'category_id', 'sub_category_id', 'link_to_goal_id'
    }

    # ==================== 核心 CRUD 方法 ====================

    def query_computer_usage(
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
        return self._generic_query(options)

    def get_computer_usage_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取单条记录

        Args:
            record_id: 记录 ID

        Returns:
            dict | None: 记录或 None
        """
        options = QueryOptions(
            filters={self._PRIMARY_KEY: record_id}
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_computer_usage(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建记录

        Args:
            data: 记录数据

        Returns:
            dict: 创建后的完整记录

        Raises:
            ValueError: 字段不合法
        """
        allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid insert fields: {invalid_fields}")

        record_id = self._generic_insert(data)
        if record_id:
            return self.get_computer_usage_by_id(str(record_id)) or {}
        return {}

    def update_computer_usage(self, record_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新记录

        Args:
            record_id: 记录 ID
            data: 要更新的字段

        Returns:
            dict | None: 更新后的完整记录或 None
        """
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return self.get_computer_usage_by_id(record_id)

        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {invalid_fields}")

        affected_rows = self.db.update(
            self._TABLE_NAME,
            data=update_data,
            where={"id": record_id}
        )
        if affected_rows > 0:
            return self.get_computer_usage_by_id(record_id)
        return None

    def delete_computer_usage(self, record_id: str) -> bool:
        """
        删除记录

        Args:
            record_id: 记录 ID

        Returns:
            bool: 是否删除成功
        """
        affected_rows = self.db.delete(self._TABLE_NAME, where={"id": record_id})
        return affected_rows > 0
