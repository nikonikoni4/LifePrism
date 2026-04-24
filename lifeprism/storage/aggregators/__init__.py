"""
Storage Aggregators - 数据聚合层

聚合多个相关 Provider，提供统一的业务数据视图。
"""
from lifeprism.storage.aggregators.habit_aggregator import HabitAggregator
from lifeprism.storage.aggregators.mood_aggregator import MoodAggregator
from lifeprism.storage.aggregators.goal_aggregator import GoalAggregator
from lifeprism.storage.aggregators.habit_chain_aggregator import HabitChainAggregator
from lifeprism.storage.aggregators.category_aggregator import CategoryAggregator
from lifeprism.storage.aggregators.map_cache_aggregator import MapCacheAggregator
from lifeprism.utils import LazySingleton

# 创建全局单例
habit_aggregator :HabitAggregator = LazySingleton(HabitAggregator)
mood_aggregator : MoodAggregator = LazySingleton(MoodAggregator)
goal_aggregator : GoalAggregator = LazySingleton(GoalAggregator)
habit_chain_aggregator : HabitChainAggregator = LazySingleton(HabitChainAggregator)
category_aggregator : CategoryAggregator = LazySingleton(CategoryAggregator)
map_cache_aggregator : MapCacheAggregator= LazySingleton(MapCacheAggregator)

__all__ = [ 
    # 类
    'HabitAggregator',
    'MoodAggregator',
    'GoalAggregator',
    'HabitChainAggregator',
    'CategoryAggregator',
    'MapCacheAggregator',
    # 单例
    'habit_aggregator',
    'mood_aggregator',
    'goal_aggregator',
    'habit_chain_aggregator',
    'category_aggregator',
    'map_cache_aggregator',
]
