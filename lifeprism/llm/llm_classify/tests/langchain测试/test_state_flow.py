"""
测试 LangGraph Send 状态流转机制

验证问题：当 B 通过 Send 传递"私有数据"给 C 时，C 收到的是什么？
- 是 B 传的私有数据？
- 还是主状态 MainState？

图结构: A -> B -> (Send) -> C -> D -> END
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from pydantic import BaseModel
from typing import Annotated


# 主状态：只有一个 str 字段
class MainState(BaseModel):
    main_data: str = "初始值"


def node_a(state: MainState) -> dict:
    """节点 A：修改主状态"""
    print(f"[A] 收到主状态: main_data = '{state.main_data}'")
    return {"main_data": "A修改后的值"}


def router_b(state: MainState) -> list[Send]:
    """节点 B：作为路由，使用 Send 传递'私有数据'给 C"""
    print(f"[B] 收到主状态: main_data = '{state.main_data}'")
    
    # 关键点：Send 只传递 {"private_data": "..."} 这个"私有数据"
    # 而不是整个 MainState
    return [
        Send("node_c", {"private_data": "B传给C的私有数据"})
    ]


def node_c(input_data) -> dict:
    """节点 C：接收 B 的输出，打印看看收到了什么"""
    print(f"[C] 收到的input类型: {type(input_data)}")
    print(f"[C] 收到的input内容: {input_data}")
    
    # 尝试访问 main_data 看是否存在
    if hasattr(input_data, 'main_data'):
        print(f"[C] input_data.main_data = '{input_data.main_data}'")
    elif isinstance(input_data, dict) and 'main_data' in input_data:
        print(f"[C] input_data['main_data'] = '{input_data['main_data']}'")
    else:
        print("[C] ⚠️ input 中没有 main_data 字段!")
    
    # 返回更新主状态
    return {"main_data": "C修改后的值"}


def node_d(state: MainState) -> dict:
    """节点 D：打印最终状态"""
    print(f"[D] 收到主状态: main_data = '{state.main_data}'")
    return {"main_data": "D修改后的最终值"}


def build_and_run():
    # 构建图
    graph = StateGraph(MainState)
    
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", lambda state: {})  # B 作为空节点，路由在 conditional_edges 中
    graph.add_node("node_c", node_c)
    graph.add_node("node_d", node_d)
    
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_conditional_edges("node_b", router_b)
    graph.add_edge("node_c", "node_d")
    graph.add_edge("node_d", END)
    
    app = graph.compile()
    
    # 运行
    print("=" * 60)
    print("开始执行图")
    print("=" * 60)
    
    initial_state = MainState(main_data="初始主状态数据")
    result = app.invoke(initial_state)
    
    print("=" * 60)
    print(f"最终结果: {result}")
    print("=" * 60)


if __name__ == "__main__":
    build_and_run()
