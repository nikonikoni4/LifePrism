"""
Tokens Usage Provider - Token 使用统计数据访问层

职责：提供 tokens_usage_log 表的所有数据访问接口
"""
import sqlite3
from typing import Optional, List, Dict, Any, Tuple, Set

from lifeprism.repository import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError, ConflictError, ValidationError

logger = get_logger(__name__)


class TokensUsageProvider(LWBaseDataProvider):
    """
    Token 使用统计数据提供者（对应 tokens_usage_log 表）

    职责：提供 tokens_usage_log 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "tokens_usage_log"
    _PRIMARY_KEY = "session_id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'session_id', 'mode', 'created_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'session_id', 'created_at', 'mode'
    }
    _SELECT_FIELDS: Set[str] = {
        'session_id', 'input_tokens', 'output_tokens', 'total_tokens',
        'search_count', 'result_items_count', 'mode', 'created_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'input_tokens', 'output_tokens', 'total_tokens',
        'search_count', 'result_items_count', 'mode'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_tokens_usage(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 查询指定日期范围的记录
            options = QueryOptions(
                filters={'created_at': ('>=', '2026-01-01')},
                order_by='created_at'
            )
            records, total = provider.query_tokens_usage(options)

            # 查询指定 mode 的记录
            options = QueryOptions(filters={'mode': 'classification'})
            records, total = provider.query_tokens_usage(options)
        """
        return self._generic_query(options)

    def get_tokens_usage_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        按会话 ID 获取单条记录

        Args:
            session_id: 会话ID

        Returns:
            记录，不存在返回 None
        """
        options = QueryOptions(
            filters={'session_id': session_id},
            order_by='session_id'
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_tokens_usage(self, data: Dict[str, Any]) -> bool:
        """
        创建 token 使用记录

        Args:
            data: 记录数据（必须包含 session_id）

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            # 必填字段检查
            required_fields = {'session_id'}
            missing_fields = required_fields - set(data.keys())
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            # 设置默认值
            if 'mode' not in data:
                data['mode'] = 'classification'
            if 'search_count' not in data:
                data['search_count'] = 0
            if 'input_tokens' not in data:
                data['input_tokens'] = 0
            if 'output_tokens' not in data:
                data['output_tokens'] = 0
            if 'total_tokens' not in data:
                data['total_tokens'] = 0
            if 'result_items_count' not in data:
                data['result_items_count'] = 0

            self._generic_insert(data)
            logger.info(f"创建 token 使用记录成功: {data.get('session_id')}")
            return True
        except Exception as e:
            logger.error(f"创建 token 使用记录失败: {e}")
            raise DataAccessError(f"创建 token 使用记录失败: {e}") from e

    def update_tokens_usage(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        更新 token 使用记录

        Args:
            session_id: 会话ID
            data: 要更新的字段

        Returns:
            是否成功

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

            return self._generic_update(session_id, data)
        except Exception as e:
            logger.error(f"更新 token 使用记录 {session_id} 失败: {e}")
            raise DataAccessError(f"更新 token 使用记录 {session_id} 失败: {e}") from e

    def delete_tokens_usage(self, session_id: str) -> bool:
        """
        删除 token 使用记录

        Args:
            session_id: 会话ID

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(session_id)
            if success:
                logger.info(f"删除 token 使用记录 {session_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除 token 使用记录 {session_id} 失败: {e}")
            raise DataAccessError(f"删除 token 使用记录 {session_id} 失败: {e}") from e

    def upsert_tokens_usage(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        更新或插入 token 使用记录（基于 session_id）

        如果记录存在则更新，不存在则插入

        Args:
            session_id: 会话ID
            data: 使用量数据（不需要包含 session_id，会自动添加）

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 检查记录是否存在
            existing = self.get_tokens_usage_by_session_id(session_id)

            if existing:
                # 记录存在，执行更新
                return self.update_tokens_usage(session_id, data)
            else:
                # 记录不存在，执行插入
                data['session_id'] = session_id
                return self.create_tokens_usage(data)
        except Exception as e:
            logger.error(f"Upsert token 使用记录 {session_id} 失败: {e}")
            raise DataAccessError(f"Upsert token 使用记录 {session_id} 失败: {e}") from e

    def batch_insert_tokens_usage(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入 token 使用记录

        Args:
            data_list: 记录数据列表

        Returns:
            成功插入的记录数

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 为每条记录设置默认值
            for data in data_list:
                if 'mode' not in data:
                    data['mode'] = 'classification'
                if 'search_count' not in data:
                    data['search_count'] = 0
                if 'input_tokens' not in data:
                    data['input_tokens'] = 0
                if 'output_tokens' not in data:
                    data['output_tokens'] = 0
                if 'total_tokens' not in data:
                    data['total_tokens'] = 0
                if 'result_items_count' not in data:
                    data['result_items_count'] = 0

            affected = self.db.insert_many(self._TABLE_NAME, data_list)
            logger.info(f"批量插入 {affected} 条 token 使用记录成功")
            return affected
        except Exception as e:
            logger.error(f"批量插入 token 使用记录失败: {e}")
            raise DataAccessError(f"批量插入 token 使用记录失败: {e}") from e