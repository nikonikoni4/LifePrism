"""
LLM 调用的工具集合

支持两种使用方式：

方式 1 - 直接使用函数（简单）：
    from lifewatch.llm.llm_classify.tools import query_title_description
    tools = [query_title_description]

方式 2 - 使用工具类（推荐，可共享状态）：
    from lifewatch.llm.llm_classify.tools import DatabaseTools
    db_tools = DatabaseTools()
    tools = [db_tools.query_title_description]
"""
from .database_tools import query_title_description

__all__ = [
    "query_title_description",
]
