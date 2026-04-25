"""
Category Provider - 分类数据访问层

职责：提供 category 和 sub_category 表的所有数据访问接口
"""
import sqlite3
from typing import Optional, List, Dict, Any, Tuple, Set
from .common_query_options import QueryOptions

from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import get_logger,LazySingleton
from lifeprism.utils.exceptions import DataAccessError, ConflictError, ValidationError

logger = get_logger(__name__)


# ==================== CategoryProvider ====================
class CategoryProvider(LWBaseDataProvider):
    """
    主分类数据提供者（对应 category 表）

    职责：提供 category 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "category"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'name', 'color', 'state',
        'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'name', 'created_at', 'updated_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'name', 'color', 'state',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'color', 'state'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_categories(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
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
            # 查询所有启用的分类
            options = QueryOptions(filters={'state': 1})
            categories, total = provider.query_categories(options)

            # 按名称排序
            options = QueryOptions(order_by='name', order_desc=False)
            categories, total = provider.query_categories(options)
        """
        return self._generic_query(options)

    def get_category_by_id(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        按主键获取单条分类记录

        Args:
            category_id: 分类ID

        Returns:
            分类记录，不存在返回 None
        """
        options = QueryOptions(filters={'id': category_id}, order_by='id')
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_category(self, data: Dict[str, Any]) -> bool:
        """
        创建分类记录

        Args:
            data: 分类数据（必须包含 id, name, color）

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
            required_fields = {'id', 'name', 'color'}
            missing_fields = required_fields - set(data.keys())
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            self._generic_insert(data)
            logger.info(f"创建分类成功: {data.get('id')}")
            return True
        except Exception as e:
            logger.error(f"创建分类失败: {e}")
            raise DataAccessError(f"创建分类失败: {e}") from e

    def update_category(self, category_id: str, data: Dict[str, Any]) -> bool:
        """
        更新分类记录

        Args:
            category_id: 分类ID
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

            return self._generic_update(category_id, data)
        except Exception as e:
            logger.error(f"更新分类 {category_id} 失败: {e}")
            raise DataAccessError(f"更新分类 {category_id} 失败: {e}") from e

    def delete_category(self, category_id: str) -> bool:
        """
        删除分类记录

        Args:
            category_id: 分类ID

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(category_id)
            if success:
                logger.info(f"删除分类 {category_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除分类 {category_id} 失败: {e}")
            raise DataAccessError(f"删除分类 {category_id} 失败: {e}") from e


# ==================== SubCategoryProvider ====================
class SubCategoryProvider(LWBaseDataProvider):
    """
    子分类数据提供者（对应 sub_category 表）

    职责：提供 sub_category 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "sub_category"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'category_id', 'name', 'state',
        'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'name', 'category_id', 'created_at', 'updated_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'category_id', 'name', 'state',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'category_id', 'name', 'state'
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_sub_categories(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
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
            # 查询指定主分类下的子分类
            options = QueryOptions(filters={'category_id': 'cat-12345678'})
            sub_categories, total = provider.query_sub_categories(options)

            # 查询所有启用的子分类
            options = QueryOptions(filters={'state': 1})
            sub_categories, total = provider.query_sub_categories(options)
        """
        return self._generic_query(options)

    def get_sub_category_by_id(self, sub_category_id: str) -> Optional[Dict[str, Any]]:
        """
        按主键获取单条子分类记录

        Args:
            sub_category_id: 子分类ID

        Returns:
            子分类记录，不存在返回 None
        """
        options = QueryOptions(filters={'id': sub_category_id}, order_by='id')
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_sub_category(self, data: Dict[str, Any]) -> bool:
        """
        创建子分类记录

        Args:
            data: 子分类数据（必须包含 id, category_id, name）

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
            required_fields = {'id', 'category_id', 'name'}
            missing_fields = required_fields - set(data.keys())
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            self._generic_insert(data)
            logger.info(f"创建子分类成功: {data.get('id')}")
            return True
        except Exception as e:
            logger.error(f"创建子分类失败: {e}")
            raise DataAccessError(f"创建子分类失败: {e}") from e

    def update_sub_category(self, sub_category_id: str, data: Dict[str, Any]) -> bool:
        """
        更新子分类记录

        Args:
            sub_category_id: 子分类ID
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

            return self._generic_update(sub_category_id, data)
        except Exception as e:
            logger.error(f"更新子分类 {sub_category_id} 失败: {e}")
            raise DataAccessError(f"更新子分类 {sub_category_id} 失败: {e}") from e

    def delete_sub_category(self, sub_category_id: str) -> bool:
        """
        删除子分类记录

        Args:
            sub_category_id: 子分类ID

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(sub_category_id)
            if success:
                logger.info(f"删除子分类 {sub_category_id} 成功")
            return success
        except Exception as e:
            logger.error(f"删除子分类 {sub_category_id} 失败: {e}")
            raise DataAccessError(f"删除子分类 {sub_category_id} 失败: {e}") from e