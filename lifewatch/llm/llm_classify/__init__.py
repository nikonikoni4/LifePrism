"""
LifeWatch LLM 分类模块

这个模块提供基于 LLM 的用户行为分类功能，包括：
- 数据模型定义 (schemas)
- 分类图逻辑 (classify)
- 数据提供者 (providers)
- LLM 工具 (tools)
- 工具类 (utils)
"""

# 导出核心组件
from .schemas import classifyState, LogItem, Goal, AppInFo
from .classify import llm_classify


__all__ = [
    # 数据模型
    "classifyState",
    "LogItem",
    "Goal",
    "AppInFo",
    "",
    # 工具类
    "create_ChatTongyiModel",
    "LangChainToonAdapter",
    # 数据提供者
    "LWDataProviders",
]

__version__ = "0.1.0"
