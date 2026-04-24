"""
Storage Aggregators - 数据聚合层

聚合多个相关 Provider，提供统一的业务数据视图。
"""
from lifeprism.storage.aggregators.habit_aggregator import habit_aggregator
from lifeprism.storage.aggregators.mood_aggregator import mood_aggregator
from lifeprism.storage.aggregators.map_cache_aggregator import map_cache_aggregator

__all__ = [
    'habit_aggregator',
    'mood_aggregator',
    'map_cache_aggregator',
]
