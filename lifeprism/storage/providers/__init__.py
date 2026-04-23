"""
Storage Providers - 数据访问层

提供所有表的数据访问接口。
"""
from lifeprism.storage.providers.diary_provider import DiaryProvider, QueryOptions
from lifeprism.storage.providers.mood_providers import (
    MoodTypeProvider,
    MoodEntryProvider,
    MoodImpactProvider,
    mood_type_provider,
    mood_entry_provider,
    mood_impact_provider,
)
from lifeprism.utils import LazySingleton

# 创建全局单例（已重构为使用通用方法）
diary_provider = LazySingleton(DiaryProvider)

__all__ = [
    'DiaryProvider',
    'QueryOptions',
    'diary_provider',
    'MoodTypeProvider',
    'MoodEntryProvider',
    'MoodImpactProvider',
    'mood_type_provider',
    'mood_entry_provider',
    'mood_impact_provider',
]
