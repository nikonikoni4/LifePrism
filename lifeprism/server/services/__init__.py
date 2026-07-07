"""
Business logic services

V2 架构：
- Service 类通过单例导出（适用于有状态或需要缓存的服务）
- 纯函数模块直接导入
"""

# 有状态服务单例（有内存缓存或运行时状态）
# 纯函数服务模块（无状态缓存）
from . import (
    activity_service,  # 已改为纯函数
    add_on_service,  # Add-on 扩展功能
    commitment_service,  # Mind Space 承诺
    custom_records_service,  # 自定义记录模块
    diary_service,  # Mind Space 日记
    journal_service,  # 已改为纯函数
    mood_service,  # Mind Space 心情
    plan_doc_service,
    plandoc_sync_service,  # PlanDoc MD 同步
    setting_service,  # 已改为纯函数
    taskpool_service,  # Task Pool V2
    timeline_service,
    usage_service,
    value_service,  # Mind Space 价值
)
from .category_service import category_service
from .chatbot_service import chatbot_service  # 有运行时状态
from .goal_service import goal_service  # 有 goal_name_map 缓存

__all__ = [
    # 有状态服务单例
    "category_service",
    "goal_service",
    "chatbot_service",
    # 纯函数模块
    "timeline_service",
    "usage_service",
    "journal_service",
    "activity_service",
    "setting_service",
    "plan_doc_service",
    "taskpool_service",
    "plandoc_sync_service",
    "diary_service",
    "mood_service",
    "value_service",
    "commitment_service",
    "add_on_service",
    "custom_records_service",
]
