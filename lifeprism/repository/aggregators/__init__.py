"""
repository Aggregators - 数据聚合层

聚合多个相关 Provider，提供统一的业务数据视图。
"""

from lifeprism.repository.aggregators.category_aggregator import CategoryAggregator
from lifeprism.repository.aggregators.computer_usage_aggregator import ComputerUsageAggregator
from lifeprism.repository.aggregators.goal_aggregator import GoalAggregator
from lifeprism.repository.aggregators.habit_aggregator import HabitAggregator
from lifeprism.repository.aggregators.habit_chain_aggregator import HabitChainAggregator
from lifeprism.repository.aggregators.map_cache_aggregator import MapCacheAggregator
from lifeprism.repository.aggregators.mood_aggregator import MoodAggregator
from lifeprism.repository.aggregators.plan_doc_aggregator import PlanDocAggregator
from lifeprism.repository.aggregators.todo_aggregator import TodoAggregator
from lifeprism.utils import LazySingleton

# 创建全局单例
habit_aggregator: HabitAggregator = LazySingleton(HabitAggregator)
mood_aggregator: MoodAggregator = LazySingleton(MoodAggregator)
goal_aggregator: GoalAggregator = LazySingleton(GoalAggregator)
habit_chain_aggregator: HabitChainAggregator = LazySingleton(HabitChainAggregator)
category_aggregator: CategoryAggregator = LazySingleton(CategoryAggregator)
map_cache_aggregator: MapCacheAggregator = LazySingleton(MapCacheAggregator)
todo_aggregator: TodoAggregator = LazySingleton(TodoAggregator)
plan_doc_aggregator: PlanDocAggregator = LazySingleton(PlanDocAggregator)
computer_usage_aggregator: ComputerUsageAggregator = LazySingleton(ComputerUsageAggregator)

__all__ = [
    # 类
    "HabitAggregator",
    "MoodAggregator",
    "GoalAggregator",
    "HabitChainAggregator",
    "CategoryAggregator",
    "MapCacheAggregator",
    "TodoAggregator",
    "PlanDocAggregator",
    "ComputerUsageAggregator",
    # 单例
    "habit_aggregator",
    "mood_aggregator",
    "goal_aggregator",
    "habit_chain_aggregator",
    "category_aggregator",
    "map_cache_aggregator",
    "todo_aggregator",
    "plan_doc_aggregator",
    "computer_usage_aggregator",
]
