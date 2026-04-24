"""
Server Providers 模块

统一导出所有数据提供者的懒加载单例
"""

# 导入 Provider 实例
from .statistical_data_providers import server_lw_data_provider
# from .todo_provider import todo_provider
# from .goal_provider import goal_provider
# from .timeline_provider import timeline_provider
# from .goal_stats_provider import goal_stats_provider
from .journal_provider import journal_provider
# from .plan_doc_provider import plan_doc_provider
# from .diary_provider import diary_provider
# from .focus_provider import focus_provider

# 对外导出
__all__ = [
    "server_lw_data_provider",
    # "todo_provider",
    # "goal_provider",
    # "timeline_provider",
    # "goal_stats_provider",
    "journal_provider",
    # "plan_doc_provider",
   #  "diary_provider",
    # "focus_provider",
]
 