"""
定义一个简单的工作流来熟悉langgraph
意图识别：判断用户说想干什么
1. 用户想要知道自己干了什么
2. 用户想要了解活动数据,并进行简单分析分析
"""
from lifewatch.llm.langchain_test.creat_model import create_ChatTongyiModel 
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

chat_model = create_ChatTongyiModel()

class myMessagesState(TypedDict):
    message:str
    activity_data:list
    result:str
def get_activity_data():
    """获取活动数据"""
    return [
        {"name": "写代码", "duration": "120分钟", "timestamp": "2023-10-01 10:00:00"},
        {"name": "看文档", "duration": "45分钟", "timestamp": "2023-10-01 13:00:00"},
        {"name": "摸鱼", "duration": "30分钟", "timestamp": "2023-10-01 15:00:00"}
    ]

def tool_node(state:myMessagesState):
    data = get_activity_data()
    state['activity_data'] = data
    return state
def activity_node(state:myMessagesState):
    """活动分析"""
    # 先获取活动数据
    activity_data = get_activity_data()
    
    # 然后进行分析
    m = [
        {"role": "system", "content": "你是一个用户活动分析师，你需要简单分析用户的活动数据。"},
        {"role": "user", "content": str(activity_data)}
    ]
    result = chat_model.invoke(m)
    state['result'] = result.content
    state['activity_data'] = activity_data  # 保存到 state 中
    return state
def get_data(state:myMessagesState):
    """活动分析"""
    state['result'] = str(get_activity_data())
    return state

def router(state:myMessagesState):
    system_message = """
    你是一个用户意图识别专家，你需要根据用户输入判断用户想干什么。
    activity: 用户想要知道自己干了什么
    analyze : 用户想要了解活动数据,并进行简单分析分析
    你返回到结果应该是activity或analyze。
    """
    message = [
        {"role":"system","content":system_message},
        {"role":"user","content":state['message']} 
    ]   
    result = chat_model.invoke(message)
    return result.content
def should_continue(state: myMessagesState):
    """决定是否继续循环或停止，基于LLM是否进行了工具调用"""
    # 这个函数不再需要，因为我们直接连接到 END
    return state

if __name__ == "__main__":
    graph = StateGraph(myMessagesState)
    # 只添加实际的处理节点
    graph.add_node("activity_node", activity_node)
    graph.add_node("get_data", get_data)
    
    # 定义路由映射
    path_map = {
        "activity": "get_data",
        "analyze": "activity_node"
    }
     
    # 从 START 开始，使用 router 函数进行条件路由
    graph.add_conditional_edges(START, router, path_map)
    
    # 两个节点都直接连接到 END
    graph.add_edge("activity_node", END)
    graph.add_edge("get_data", END)
    
    agent = graph.compile()
    m = myMessagesState(message="分析我最近都干了什么")
    m = agent.invoke(m)
    print(m)