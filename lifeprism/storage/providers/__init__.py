"""
Storage Providers - 数据访问层

提供所有表的数据访问接口。
"""
from lifeprism.storage.providers.diary_provider import DiaryProvider, QueryOptions
from lifeprism.utils import LazySingleton

# 创建全局单例
diary_provider = LazySingleton(DiaryProvider)

__all__ = [
    'DiaryProvider',
    'QueryOptions',
    'diary_provider',
]
