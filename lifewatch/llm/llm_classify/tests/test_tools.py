"""
测试 LLM 工具的使用
演示本地 tool 和云端 web_search 的协同使用
"""
from lifewatch.llm.llm_classify.utils import create_ChatTongyiModel
from lifewatch.llm.llm_classify.utils.langchain_toon_adapter import LangChainToonAdapter
from lifewatch.llm.llm_classify.tools import search_website_by_database
from langchain_core.messages import HumanMessage


def test_tool_with_web_search():
    """测试本地工具和云端搜索的协同使用"""
    # 创建模型
    model = create_ChatTongyiModel()
    
    # 定义工具
    tools = [search_website_by_database]
    
    # 构建系统消息（使用 Toon 格式）
    system_message = LangChainToonAdapter.build_system_message_with_toon_tools(
        tools,
        "你是一个智能助手，可以使用以下工具，优先使用 search_website_by_database。"
    )
    
    # 发送请求
    response = model.invoke([
        system_message,
        HumanMessage(content="帮我搜索数据库中戏谶的描述")
    ])
    
    print("=" * 80)
    print("测试结果：")
    print("=" * 80)
    print(response.content)
    print("=" * 80)


if __name__ == "__main__":
    test_tool_with_web_search()
