"""
Map Cache Aggregator - 映射缓存数据聚合层

聚合 MultiPurposeMapCacheProvider, SinglePurposeMapCacheProvider
提供映射缓存相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers.map_cache_providers import (
    MultiPurposeMapCacheProvider,
    SinglePurposeMapCacheProvider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class MapCacheAggregator:
    """
    映射缓存聚合器

    职责：
    1. 聚合 multi_purpose_map_cache、single_purpose_map_cache 两个表的数据（核心价值）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.multi_purpose_provider = MultiPurposeMapCacheProvider()
        self.single_purpose_provider = SinglePurposeMapCacheProvider()

    # ==================== 聚合方法（核心价值）====================

    def get_all_caches(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有缓存数据（包含多用途和单用途）

        Returns:
            Dict: {
                'multi_purpose': [...],
                'single_purpose': [...]
            }
        """
        try:
            # 获取多用途缓存
            multi_purpose_caches, _ = self.multi_purpose_provider.query_multi_purpose_map_cache()

            # 获取单用途缓存
            single_purpose_caches, _ = self.single_purpose_provider.query_single_purpose_map_cache()

            return {
                'multi_purpose': multi_purpose_caches,
                'single_purpose': single_purpose_caches
            }
        except Exception as e:
            logger.error(f"获取所有缓存数据失败: {e}")
            return {
                'multi_purpose': [],
                'single_purpose': []
            }

    def get_cache_by_purpose(
        self,
        purpose: str,
        is_multi_purpose: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        按用途查找缓存

        Args:
            purpose: 用途标识（app 字段值）
            is_multi_purpose: 是否为多用途应用

        Returns:
            Optional[Dict]: 缓存记录，不存在返回 None
        """
        try:
            if is_multi_purpose:
                # 查询多用途缓存
                from lifeprism.storage.providers.common_query_options import QueryOptions
                options = QueryOptions(filters={'app': purpose}, order_by='id')
                results, _ = self.multi_purpose_provider.query_multi_purpose_map_cache(options)
                return results[0] if results else None
            else:
                # 查询单用途缓存
                from lifeprism.storage.providers.common_query_options import QueryOptions
                options = QueryOptions(filters={'app': purpose}, order_by='id')
                results, _ = self.single_purpose_provider.query_single_purpose_map_cache(options)
                return results[0] if results else None
        except Exception as e:
            logger.error(f"按用途查找缓存失败 (purpose={purpose}, is_multi_purpose={is_multi_purpose}): {e}")
            return None

    # ==================== MultiPurposeMapCache 核心 CRUD 透传 ====================

    def insert_multi_purpose_map_cache(self, data: Dict[str, Any]) -> bool:
        """透传：插入多用途映射缓存"""
        return self.multi_purpose_provider.insert_multi_purpose_map_cache(data)

    def update_multi_purpose_map_cache(self, cache_id: str, data: Dict[str, Any]) -> bool:
        """透传：更新多用途映射缓存"""
        return self.multi_purpose_provider.update_multi_purpose_map_cache(cache_id, data)

    def delete_multi_purpose_map_cache(self, cache_id: str) -> bool:
        """透传：删除多用途映射缓存"""
        return self.multi_purpose_provider.delete_multi_purpose_map_cache(cache_id)

    def query_multi_purpose_map_cache(self, options=None):
        """透传：查询多用途映射缓存"""
        return self.multi_purpose_provider.query_multi_purpose_map_cache(options)

    def batch_delete_multi_purpose_map_cache(self, cache_ids: List[str]) -> int:
        """透传：批量删除多用途映射缓存"""
        return self.multi_purpose_provider.batch_delete_multi_purpose_map_cache(cache_ids)

    def batch_update_multi_purpose_map_cache(self, cache_ids: List[str], data: Dict[str, Any]) -> int:
        """透传：批量更新多用途映射缓存"""
        return self.multi_purpose_provider.batch_update_multi_purpose_map_cache(cache_ids, data)

    # ==================== SinglePurposeMapCache 核心 CRUD 透传 ====================

    def insert_single_purpose_map_cache(self, data: Dict[str, Any]) -> bool:
        """透传：插入单用途映射缓存"""
        return self.single_purpose_provider.insert_single_purpose_map_cache(data)

    def update_single_purpose_map_cache(self, cache_id: str, data: Dict[str, Any]) -> bool:
        """透传：更新单用途映射缓存"""
        return self.single_purpose_provider.update_single_purpose_map_cache(cache_id, data)

    def delete_single_purpose_map_cache(self, cache_id: str) -> bool:
        """透传：删除单用途映射缓存"""
        return self.single_purpose_provider.delete_single_purpose_map_cache(cache_id)

    def query_single_purpose_map_cache(self, options=None):
        """透传：查询单用途映射缓存"""
        return self.single_purpose_provider.query_single_purpose_map_cache(options)

    def batch_delete_single_purpose_map_cache(self, cache_ids: List[str]) -> int:
        """透传：批量删除单用途映射缓存"""
        return self.single_purpose_provider.batch_delete_single_purpose_map_cache(cache_ids)

    def batch_update_single_purpose_map_cache(self, cache_ids: List[str], data: Dict[str, Any]) -> int:
        """透传：批量更新单用途映射缓存"""
        return self.single_purpose_provider.batch_update_single_purpose_map_cache(cache_ids, data)

    # ==================== 批量操作透传 ====================

    def clear_all_caches(self) -> Dict[str, int]:
        """
        清理所有缓存

        Returns:
            Dict: {
                'multi_purpose_deleted': int,
                'single_purpose_deleted': int,
                'total_deleted': int
            }
        """
        try:
            # 获取所有缓存 ID
            multi_purpose_caches, _ = self.multi_purpose_provider.query_multi_purpose_map_cache()
            single_purpose_caches, _ = self.single_purpose_provider.query_single_purpose_map_cache()

            multi_purpose_ids = [cache['id'] for cache in multi_purpose_caches]
            single_purpose_ids = [cache['id'] for cache in single_purpose_caches]

            # 批量删除
            multi_deleted = 0
            single_deleted = 0

            if multi_purpose_ids:
                multi_deleted = self.multi_purpose_provider.batch_delete_multi_purpose_map_cache(multi_purpose_ids)

            if single_purpose_ids:
                single_deleted = self.single_purpose_provider.batch_delete_single_purpose_map_cache(single_purpose_ids)

            total_deleted = multi_deleted + single_deleted

            logger.info(f"清理缓存完成: 多用途={multi_deleted}, 单用途={single_deleted}, 总计={total_deleted}")

            return {
                'multi_purpose_deleted': multi_deleted,
                'single_purpose_deleted': single_deleted,
                'total_deleted': total_deleted
            }
        except Exception as e:
            logger.error(f"清理所有缓存失败: {e}")
            return {
                'multi_purpose_deleted': 0,
                'single_purpose_deleted': 0,
                'total_deleted': 0
            }


# ==================== 导出单例 ====================

from lifeprism.utils import LazySingleton

map_cache_aggregator = LazySingleton(MapCacheAggregator)
