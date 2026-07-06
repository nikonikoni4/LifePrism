"""
Category Aggregator - 分类数据聚合层

聚合 CategoryProvider, SubCategoryProvider
提供分类相关的统一数据视图
"""

from typing import Any

from lifeprism.repository.providers.category_provider import (
    CategoryProvider,
    SubCategoryProvider,
)
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import LazySingleton, get_logger

logger = get_logger(__name__)


class CategoryAggregator:
    """
    分类聚合器

    职责：
    1. 聚合 category、sub_category 两个表的数据（核心价值）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.category_provider = CategoryProvider()
        self.sub_category_provider = SubCategoryProvider()

    # ==================== 聚合方法（核心价值）====================

    def get_category_with_subs(self, category_id: str) -> dict[str, Any] | None:
        """
        获取分类详情（包含所有子分类）

        Args:
            category_id: 分类 ID

        Returns:
            包含 category 和 sub_categories 的字典，不存在返回 None
        """
        category = self.category_provider.get_category_by_id(category_id)
        if not category:
            return None

        # 获取该分类下的所有子分类
        options = QueryOptions(filters={"category_id": category_id}, order_by="name", order="ASC")
        sub_categories, _ = self.sub_category_provider.query_sub_categories(options)
        category["sub_categories"] = sub_categories

        return category

    def get_category_tree(self) -> list[dict[str, Any]]:
        """
        获取完整的分类树（所有分类及其子分类）

        Returns:
            分类列表，每个分类包含 sub_categories 字段
        """
        # 获取所有分类
        options = QueryOptions(order_by="name", order="ASC")
        categories, _ = self.category_provider.query_categories(options)

        # 获取所有子分类
        sub_options = QueryOptions(order_by="name", order="ASC")
        all_sub_categories, _ = self.sub_category_provider.query_sub_categories(sub_options)

        # 构建分类ID到子分类列表的映射
        sub_categories_map: dict[str, list[dict[str, Any]]] = {}
        for sub_cat in all_sub_categories:
            category_id = sub_cat["category_id"]
            if category_id not in sub_categories_map:
                sub_categories_map[category_id] = []
            sub_categories_map[category_id].append(sub_cat)

        # 为每个分类添加子分类列表
        for category in categories:
            category["sub_categories"] = sub_categories_map.get(category["id"], [])

        return categories

    # ==================== Category 核心 CRUD 透传 ====================

    def create_category(self, data: dict[str, Any]) -> bool:
        """透传：创建分类"""
        return self.category_provider.create_category(data)

    def update_category(self, category_id: str, data: dict[str, Any]) -> bool:
        """透传：更新分类"""
        return self.category_provider.update_category(category_id, data)

    def delete_category(self, category_id: str) -> bool:
        """透传：删除分类"""
        return self.category_provider.delete_category(category_id)

    def query_categories(self, options: QueryOptions):
        """透传：查询分类"""
        return self.category_provider.query_categories(options)

    def get_category_by_id(self, category_id: str) -> dict[str, Any] | None:
        """透传：根据ID获取分类"""
        return self.category_provider.get_category_by_id(category_id)

    # ==================== SubCategory 核心 CRUD 透传 ====================

    def create_sub_category(self, data: dict[str, Any]) -> bool:
        """透传：创建子分类"""
        return self.sub_category_provider.create_sub_category(data)

    def update_sub_category(self, sub_id: str, data: dict[str, Any]) -> bool:
        """透传：更新子分类"""
        return self.sub_category_provider.update_sub_category(sub_id, data)

    def delete_sub_category(self, sub_id: str) -> bool:
        """透传：删除子分类"""
        return self.sub_category_provider.delete_sub_category(sub_id)

    def query_sub_categories(self, options: QueryOptions):
        """透传：查询子分类"""
        return self.sub_category_provider.query_sub_categories(options)

    def get_sub_category_by_id(self, sub_id: str) -> dict[str, Any] | None:
        """透传：根据ID获取子分类"""
        return self.sub_category_provider.get_sub_category_by_id(sub_id)

    # ==================== 事务性聚合方法 ====================

    def create_category_with_subs(
        self,
        category_data: dict[str, Any],
        sub_categories_data: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        创建分类并可选创建子分类

        Args:
            category_data: 分类数据（必须包含 id, name, color）
            sub_categories_data: 子分类数据列表（可选）

        Returns:
            是否成功
        """
        # 创建分类
        success = self.category_provider.create_category(category_data)
        if not success:
            return False

        category_id = category_data["id"]

        # 如果提供了子分类数据，创建子分类
        if sub_categories_data:
            for sub_cat_data in sub_categories_data:
                sub_cat_data["category_id"] = category_id
                sub_success = self.sub_category_provider.create_sub_category(sub_cat_data)
                if not sub_success:
                    logger.warning("创建子分类失败: %s", sub_cat_data.get("id"))

        logger.info(
            "创建分类 %s，包含 %s 个子分类",
            category_id,
            len(sub_categories_data) if sub_categories_data else 0,
        )
        return True

    def delete_category_with_subs(self, category_id: str) -> bool:
        """
        删除分类及其所有子分类

        Args:
            category_id: 分类 ID

        Returns:
            是否成功
        """
        # 先获取所有子分类
        options = QueryOptions(filters={"category_id": category_id})
        sub_categories, _ = self.sub_category_provider.query_sub_categories(options)

        # 删除所有子分类
        for sub_cat in sub_categories:
            sub_success = self.sub_category_provider.delete_sub_category(sub_cat["id"])
            if not sub_success:
                logger.warning("删除子分类失败: %s", sub_cat["id"])

        # 删除主分类
        success = self.category_provider.delete_category(category_id)
        if success:
            logger.info("删除分类 %s 及其 %s 个子分类", category_id, len(sub_categories))

        return success


# ==================== 导出单例 ====================

category_aggregator = LazySingleton(CategoryAggregator)
