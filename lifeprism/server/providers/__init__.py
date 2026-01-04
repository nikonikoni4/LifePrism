"""
Server Providers 模块

统一导出所有数据提供者的懒加载单例
"""
from lifeprism.utils import LazySingleton

# 导入 Provider 类
from .statistical_data_providers import ServerLWDataProvider
from .todo_provider import TodoProvider
from .goal_provider import GoalProvider
from .timeline_provider import TimelineProvider
from .reward_provider import RewardProvider
from .goal_stats_provider import GoalStatsProvider

# 创建懒加载单例
server_lw_data_provider = LazySingleton(ServerLWDataProvider)
todo_provider = LazySingleton(TodoProvider)
goal_provider = LazySingleton(GoalProvider)
timeline_provider = LazySingleton(TimelineProvider)
reward_provider = LazySingleton(RewardProvider)
goal_stats_provider = LazySingleton(GoalStatsProvider)

# 对外导出
__all__ = [
    "server_lw_data_provider",
    "todo_provider",
    "goal_provider",
    "timeline_provider",
    "reward_provider",
    "goal_stats_provider",
]
