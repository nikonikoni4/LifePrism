"""
数据库相关的 LLM 工具

使用类方法包装工具，便于：
1. 共享数据库连接等资源
2. 组织相关工具
3. 管理工具状态
"""
from langchain_core.tools import tool
from lifewatch.llm.llm_classify.providers.lw_data_providers import lw_data_providers
from lifewatch.llm.llm_classify.schemas.database_tool_shemas import (
    TitleDescriptionInput,
    TitleDescriptionOutput
)

@tool(args_schema=TitleDescriptionInput)
def query_title_description(query_list: list[str]) -> TitleDescriptionOutput:
    """从数据库查询标题描述信息,适用于查询网站名称、实体名称等的详细描述"""
    results = lw_data_providers.query_title_description(query_list)
    if not results:
        return TitleDescriptionOutput(result={})
    
    descriptions = {}
    for item in results:
        descriptions[item['key_word']] = item['description']
    
    return TitleDescriptionOutput(result=descriptions)


if __name__ == "__main__": 
    result = query_title_description.invoke({"query_list": ["爱奇艺", "抖音"]})
    print(result)
