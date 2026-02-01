"""
Business logic services

V2 架构：
- Service 类通过单例导出（适用于有状态或需要缓存的服务）
- 纯函数模块直接导入
"""

# 有状态服务单例（有内存缓存或运行时状态）
from .category_service import category_service
from .goal_service import goal_service        # 有 goal_name_map 缓存
from .chatbot_service import chatbot_service  # 有运行时状态

# 纯函数服务模块（无状态缓存）
from . import timeline_service
from . import usage_service
from . import todo_service
from . import journal_service   # 已改为纯函数
from . import activity_service  # 已改为纯函数
from . import setting_service   # 已改为纯函数
from . import plan_doc_service

__all__ = [
    # 有状态服务单例
    "category_service",
    "goal_service",
    "chatbot_service",
    # 纯函数模块
    "timeline_service",
    "usage_service",
    "todo_service",
    "journal_service",
    "activity_service",
    "setting_service",
    "plan_doc_service",
]
