"""
Server Providers 模块

统一导出所有数据提供者的懒加载单例
"""

# 导入 Provider 实例
from .statistical_data_providers import server_lw_data_provider
from .todo_provider import todo_provider
from .goal_provider import goal_provider
from .timeline_provider import timeline_provider
from .reward_provider import reward_provider
from .goal_stats_provider import goal_stats_provider

# 对外导出
__all__ = [
    "server_lw_data_provider",
    "todo_provider",
    "goal_provider",
    "timeline_provider",
    "reward_provider",
    "goal_stats_provider",
]
 