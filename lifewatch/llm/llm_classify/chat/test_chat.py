from langchain_core.messages import HumanMessage,SystemMessage
from lifewatch.llm.llm_classify.utils.create_model import create_ChatTongyiModel
from langchain.agents import create_agent
from langchain.tools import tool,ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from dataclasses import dataclass
# 测试 获取当前地点的天气


# 创建system prompt
system_prompt = """
You are an expert weather forecaster, who speaks in puns.
You have access to one tool : 
- get_weather : use this to get the weather 
- get_location : use this to get the location
"""
system_prompt = """
你是一个专业的天气预报员
你有下面一个工具可以使用:
- get_weather : 获取天气信息
""" 
# 创建工具

@dataclass
class Context:
    user_name: str
    location: str
    language: str
@tool
def get_weather(runtime : ToolRuntime[Context]) -> str:
    """Search for information on the web."""
    return f"Weather in {runtime.context.location} is sunny."
# 创建记忆
checkpointer = InMemorySaver()
chat_model = create_ChatTongyiModel(enable_search = False)
system_message = SystemMessage(content="You are a helpful assistant.")
agent = create_agent(chat_model, 
            tools=[get_weather],
            checkpointer = checkpointer,
            system_prompt = system_prompt,
            context_schema =Context)

config = {"configurable": {"thread_id": "1"}}
# result = agent.invoke(
#     {"messages": [{"role": "user", "content": "你好"}]},
#     config = config,
#     context = Context(user_name="John", location="Beijing", language="chinese"))
# print(result)
# print("="*30)
# print(result["messages"][-1].content)
# print("="*30)
# print(len(result["messages"]))
# result = agent.invoke(
#     {"messages": [{"role": "user", "content": "当前天气是？"}]},
#     config = config,
#     context = Context(user_name="John", location="Beijing", language="chinese"))
# print(result)
# print("="*30)
# print(result["messages"][-1].content)
# print("="*30)
# print(len(result["messages"]))

# 流式输出
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "当前天气是？"}]},
    config = config,
    context = Context(user_name="John", location="Beijing", language="chinese"),
    stream_mode = "updates"
):
    print("="*30)
    for step, data in chunk.items():
        print(f"step: {step}")
        print(f"content: {data['messages'][-1].content_blocks}")

for token, metadata in agent.stream(  
    {"messages": [{"role": "user", "content": "当前天气是？"}]},
    config = config,
    context = Context(user_name="John", location="Beijing", language="chinese"),
    stream_mode="messages",
):
    print(f"node: {metadata["langgraph_node"]}")
    print(f"content: {token.content_blocks}")
    print("\n")