"""
LangGraph 并发节点数据合并示例
演示如何使用 Annotated 和 operator 来处理并发更新
"""
from dask.dot import name
from typing import Annotated
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
import operator
def remain_old_value(old_value,new_value):
    if old_value:
        return old_value
    else:
        return new_value
class SubState(BaseModel):
    name:str


# ===== 1. 定义状态 =====
class MyState(BaseModel):
    # 使用 operator.add 合并列表（拼接）
    items: Annotated[list[str], operator.add] = Field(default_factory=list)
    
    # 使用 operator.or_ 合并字典（合并键值对）
    registry: Annotated[dict[str, str], operator.or_] = Field(default_factory=dict)
    
    # 普通字段（不支持并发更新）
    count: int = 0

    test : Annotated[dict[int,SubState],operator.or_]


# ===== 2. 定义节点函数 =====
def start_node(state: MyState) -> MyState:
    """初始节点：设置初始数据"""
    print("📍 START: 初始化数据")
    return state

def router(state: MyState):
    """路由节点：创建两个并发分支"""
    print("\n🔀 ROUTER: 创建并发分支 A 和 B")
    return [
        Send("branch_a", state),
        Send("branch_b", state)
    ]

def branch_a(state: MyState) -> dict:
    """分支 A：添加自己的数据"""
    print("  🅰️  Branch A 执行")
    return {
        "items": ["A1", "A2"],  # 会被 add 到列表中
        "registry": {"app_a": "来自分支A", "shared": "A的值","test":"test_a"},  # 会被 or_ 合并
        "count": 10,  # ⚠️ 如果两个分支都返回 count，会报错！
        "test":{
            1:SubState(name="A")
        }
    }

def branch_b(state: MyState) -> dict:
    """分支 B：添加自己的数据"""
    print("  🅱️  Branch B 执行")
    return {
        "items": ["B1", "B2", "B3"],  # 会被 add 到列表中
        "registry": {"app_b": "来自分支B", "shared": "B的值","test":"test_b"},  # 会被 or_ 合并
        "test":{
            2:SubState(name="B")
        }
        # 注意：这里不返回 count，避免冲突
    }

def merge_node(state: MyState) -> MyState:
    """合并节点：查看合并后的结果"""
    print("\n✅ MERGE: 合并完成")
    print(f"   items (列表拼接): {state.items}")
    print(f"   registry (字典合并): {state.registry}")
    print(f"   count: {state.count}")
    return state

# ===== 3. 构建图 =====
def create_graph():
    graph = StateGraph(MyState)
    
    # 添加节点
    graph.add_node("start", start_node)
    graph.add_node("branch_a", branch_a)
    graph.add_node("branch_b", branch_b)
    graph.add_node("merge", merge_node)
    
    # 添加边
    graph.add_edge(START, "start")
    graph.add_conditional_edges("start", router)  # 并发分支
    graph.add_edge("branch_a", "merge")
    graph.add_edge("branch_b", "merge")
    graph.add_edge("merge", END)
    
    return graph.compile()

# ===== 4. 运行示例 =====
if __name__ == "__main__":

    print("=" * 60)
    print("LangGraph 并发节点数据合并示例")
    print("=" * 60)
    
    # 创建初始状态
    initial_state = MyState(
        items=["初始项"],
        registry={"initial": "初始值"},
        count=0,
        test={i:SubState(name="i") for i in range(2)}
    )
    
    # 运行图
    app = create_graph()
    result = app.invoke(initial_state)
    
    print("\n" + "=" * 60)
    print("📊 最终结果:")
    print("=" * 60)
    print(f"items: {result['items']}")
    print(f"registry: {result['registry']}")
    print(f"count: {result['count']}")
    print(f"Test: {result['test']}")
    print("\n" + "=" * 60)
    print("💡 关键点:")
    print("=" * 60)
    print("1. operator.add 用于列表：并发分支的列表会拼接")
    print("   初始: ['初始项'] + A: ['A1','A2'] + B: ['B1','B2','B3']")
    print("   结果: ['初始项','A1','A2','B1','B2','B3']")
    print("\n2. operator.or_ 用于字典：并发分支的字典会合并")
    print("   初始: {'initial':'初始值'}")
    print("   + A: {'app_a':'来自分支A', 'shared':'A的值'}")
    print("   + B: {'app_b':'来自分支B', 'shared':'B的值'}")
    print("   结果: 所有键合并，相同键后者覆盖前者")
    print("\n3. 普通字段：不能在并发分支中同时更新")
    print("   如果 A 和 B 都返回 count，会报错！")
    print("=" * 60)
