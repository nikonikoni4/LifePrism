"""
Server Providers 模块

统一导出所有数据提供者的懒加载单例
"""
from lifewatch.utils import LazySingleton

# 导入 Provider 类
from .statistical_data_providers import ServerLWDataProvider
from .goal_provider import GoalProvider

# 创建懒加载单例
server_lw_data_provider = LazySingleton(ServerLWDataProvider)
goal_provider = LazySingleton(GoalProvider)

# 对外导出
__all__ = [
    "server_lw_data_provider",
    "goal_provider",
]
