"""
Computer Usage Aggregator - 计算机使用数据聚合层

聚合 ComputerUsageProvider, CategoryProvider, SubCategoryProvider
提供带分类名称的数据视图
"""
from typing import Optional, List, Dict, Any, Tuple
from lifeprism.repository.providers.computer_usage_provider import ComputerUsageProvider
from lifeprism.repository.providers.category_provider import CategoryProvider, SubCategoryProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class ComputerUsageAggregator:
    """
    计算机使用数据聚合器

    职责：
    1. 聚合 user_app_behavior_log、category、sub_category 三个表的数据
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.computer_usage_provider = ComputerUsageProvider()
        self.category_provider = CategoryProvider()
        self.sub_category_provider = SubCategoryProvider()
        self._category_map: Dict[str, str] = {}
        self._sub_category_map: Dict[str, str] = {}
        self._refresh_cache()

    def _refresh_cache(self):
        """刷新分类名称缓存"""
        try:
            categories, _ = self.category_provider.query_categories(QueryOptions())
            self._category_map = {c['id']: c['name'] for c in categories}

            sub_categories, _ = self.sub_category_provider.query_sub_categories(QueryOptions())
            self._sub_category_map = {s['id']: s['name'] for s in sub_categories}
        except Exception as e:
            logger.error(f"刷新分类缓存失败: {e}")

    def _enrich_with_names(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """为记录添加分类名称"""
        if record.get('category_id'):
            record['category_name'] = self._category_map.get(record['category_id'], '')
        if record.get('sub_category_id'):
            record['sub_category_name'] = self._sub_category_map.get(record['sub_category_id'], '')
        return record

    # ==================== 聚合方法（核心价值）====================

    def query_computer_usage_with_names(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        查询记录并附加分类名称

        自动为返回的记录添加 category_name 和 sub_category_name 字段。
        只有当记录包含 category_id 或 sub_category_id 时才会添加对应的名称字段。

        Args:
            options: 查询选项（与 query_computer_usage 相同）

        Returns:
            (记录列表, 总记录数)
            - 每条记录会额外包含：
              - category_name: 分类名称（如果有 category_id ）
              - sub_category_name: 子分类名称（如果有 sub_category_id）

        Examples:
            # 查询 2026-04-28 的所有记录并附加分类名称
            options = QueryOptions(
                time_range=("2026-04-28 00:00:00", "2026-04-28 23:59:59")
            )
            records, total = aggregator.query_computer_usage_with_names(options)
            # 返回: [{'id': '...', 'app': '...', 'category_id': 'cat-001',
            #         'category_name': '工作', 'sub_category_id': 'sub-001',
            #         'sub_category_name': '编程'}, ...]
        """
        records, total = self.computer_usage_provider.query_computer_usage(options)
        return [self._enrich_with_names(r) for r in records], total

    def get_computer_usage_by_id_with_names(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取记录并附加分类名称

        自动为返回的记录添加 category_name 和 sub_category_name 字段。

        Args:
            record_id: 记录 ID

        Returns:
            dict | None: 记录或 None
            - 记录会额外包含：
              - category_name: 分类名称（如果有 category_id）
              - sub_category_name: 子分类名称（如果有 sub_category_id）

        Examples:
            record = aggregator.get_computer_usage_by_id_with_names("some-id")
            # 返回: {'id': 'some-id', 'app': 'chrome.exe',
            #        'category_id': 'cat-001', 'category_name': '工作', ...}
        """
        record = self.computer_usage_provider.get_computer_usage_by_id(record_id)
        return self._enrich_with_names(record) if record else None

    # ==================== 透传 Provider 方法 ====================

    def query_computer_usage(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """透传：通用查询接口"""
        return self.computer_usage_provider.query_computer_usage(options)

    def get_computer_usage_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """透传：根据 ID 获取记录"""
        return self.computer_usage_provider.get_computer_usage_by_id(record_id)

    def create_computer_usage(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """透传：创建记录"""
        return self.computer_usage_provider.create_computer_usage(data)

    def update_computer_usage(self, record_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """透传：更新记录"""
        return self.computer_usage_provider.update_computer_usage(record_id, data)

    def delete_computer_usage(self, record_id: str) -> bool:
        """透传：删除记录"""
        return self.computer_usage_provider.delete_computer_usage(record_id)
