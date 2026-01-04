"""
LangGraph 私有数据传递机制测试

测试结论：
1. 私有数据能否传递，取决于下一个节点的输入参数类型声明
2. 下一个节点声明 PrivateState 类型 → 收到私有数据
3. 下一个节点声明 MainState / dict / 无声明 → 收到主 State
4. 混合返回时，私有数据和 State 数据会分离处理
"""

from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel


# ============================================================
# 定义 State 类型
# ============================================================

class MainState(TypedDict):
    """主 State（图的整体状态）"""
    count: int
    messages: Annotated[list, operator.add]


class PrivateState(TypedDict):
    """私有 State（用于节点间传递）"""
    private_data: str
    temp_value: int


# ============================================================
# 测试 1: 接收方声明 PrivateState → 收到私有数据
# ============================================================

def test_1_receive_private_state():
    """
    场景：Node B 声明输入类型为 PrivateState
    预期：Node B 收到私有数据，而不是主 State
    """
    received = {}
    
    def node_a(state: MainState):
        received["node_a"] = dict(state)
        return {"private_data": "secret", "temp_value": 999}
    
    def node_b(state: PrivateState):  # ← 关键：声明为 PrivateState
        received["node_b"] = dict(state)
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    app = graph.compile()
    
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证
    assert "private_data" in received["node_b"], "Node B 应该收到 private_data"
    assert "temp_value" in received["node_b"], "Node B 应该收到 temp_value"
    assert "count" not in received["node_b"], "Node B 不应该收到 count"
    
    print("✅ 测试 1 通过: 声明 PrivateState → 收到私有数据")
    print(f"   Node B 收到: {received['node_b']}")
    return True


# ============================================================
# 测试 2: 接收方声明 MainState → 收到主 State
# ============================================================

def test_2_receive_main_state():
    """
    场景：Node B 声明输入类型为 MainState（或不声明）
    预期：Node B 收到主 State，私有数据丢失
    """
    received = {}
    
    def node_a(state: MainState):
        received["node_a"] = dict(state)
        return {"private_data": "secret", "temp_value": 999}
    
    def node_b(state: MainState):  # ← 声明为 MainState
        received["node_b"] = dict(state)
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    app = graph.compile()
    
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证
    assert "count" in received["node_b"], "Node B 应该收到 count"
    assert "messages" in received["node_b"], "Node B 应该收到 messages"
    assert "private_data" not in received["node_b"], "Node B 不应该收到 private_data"
    
    print("✅ 测试 2 通过: 声明 MainState → 收到主 State")
    print(f"   Node B 收到: {received['node_b']}")
    return True


# ============================================================
# 测试 3: 接收方声明 dict → 收到主 State
# ============================================================

def test_3_receive_dict():
    """
    场景：Node B 声明输入类型为 dict
    预期：Node B 收到主 State，私有数据丢失
    """
    received = {}
    
    def node_a(state: MainState):
        received["node_a"] = dict(state)
        return {"private_data": "secret", "temp_value": 999}
    
    def node_b(state: dict):  # ← 声明为 dict
        received["node_b"] = dict(state)
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    app = graph.compile()
    
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证
    assert "count" in received["node_b"], "Node B 应该收到 count"
    assert "private_data" not in received["node_b"], "Node B 不应该收到 private_data"
    
    print("✅ 测试 3 通过: 声明 dict → 收到主 State")
    print(f"   Node B 收到: {received['node_b']}")
    return True


# ============================================================
# 测试 4: 混合返回（State key + 私有 key）
# ============================================================

def test_4_mixed_return():
    """
    场景：Node A 返回混合数据（State key + 私有 key）
    预期：
      - Node B（声明 PrivateState）只收到私有数据
      - State key（count）更新到主 State，但不传给 Node B
    """
    received = {}
    
    def node_a(state: MainState):
        received["node_a"] = dict(state)
        # 混合返回：count 是 State key，private_data 是私有 key
        return {
            "count": 100,             # State key
            "private_data": "secret", # 私有 key
            "temp_value": 999         # 私有 key
        }
    
    def node_b(state: PrivateState):  # ← 声明为 PrivateState
        received["node_b"] = dict(state)
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    app = graph.compile()
    
    result = app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证 Node B 只收到私有数据
    assert "private_data" in received["node_b"], "Node B 应该收到 private_data"
    assert "count" not in received["node_b"], "Node B 不应该收到 count（混合时分离）"
    
    # 验证主 State 中的 count 被更新
    assert result["count"] == 100, "主 State 的 count 应该被更新为 100"
    
    print("✅ 测试 4 通过: 混合返回时，私有数据和 State 数据分离")
    print(f"   Node B 收到: {received['node_b']}")
    print(f"   最终 State: count={result['count']}")
    return True


# ============================================================
# 测试 5: 私有数据连续传递
# ============================================================

def test_5_chain_private_state():
    """
    场景：A → B → C，私有数据能否连续传递？
    预期：如果每个节点都声明正确的类型，私有数据可以持续传递
    """
    received = {}
    
    def node_a(state: MainState):
        received["node_a"] = dict(state)
        return {"private_data": "secret", "temp_value": 999}
    
    def node_b(state: PrivateState):  # ← 声明为 PrivateState
        received["node_b"] = dict(state)
        # 继续返回私有数据
        return {"private_data": state["private_data"] + "_b", "temp_value": state["temp_value"] + 1}
    
    def node_c(state: PrivateState):  # ← 声明为 PrivateState
        received["node_c"] = dict(state)
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_node("node_c", node_c)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", "node_c")
    graph.add_edge("node_c", END)
    app = graph.compile()
    
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证私有数据连续传递
    assert received["node_b"]["private_data"] == "secret", "Node B 收到原始私有数据"
    assert received["node_c"]["private_data"] == "secret_b", "Node C 收到 Node B 修改后的私有数据"
    assert received["node_c"]["temp_value"] == 1000, "Node C 收到 Node B 修改后的 temp_value"
    
    print("✅ 测试 5 通过: 私有数据可以连续传递")
    print(f"   Node B 收到: {received['node_b']}")
    print(f"   Node C 收到: {received['node_c']}")
    return True


# ============================================================
# 测试 6: 私有数据传递中断（中间节点不声明类型）
# ============================================================

def test_6_chain_break():
    """
    场景：A → B → C，但 B 声明 MainState
    预期：私有数据传递中断，C 收不到私有数据
    """
    received = {}
    
    def node_a(state: MainState):
        received["node_a"] = dict(state)
        return {"private_data": "secret", "temp_value": 999}
    
    def node_b(state: MainState):  # ← 声明为 MainState，会中断私有数据传递
        received["node_b"] = dict(state)
        return {"private_data": "from_b", "temp_value": 111}  # 尝试返回新的私有数据
    
    def node_c(state: PrivateState):  # ← 声明为 PrivateState
        received["node_c"] = dict(state)
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_node("node_c", node_c)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", "node_c")
    graph.add_edge("node_c", END)
    app = graph.compile()
    
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证
    assert "private_data" not in received["node_b"], "Node B 声明 MainState，收不到私有数据"
    assert received["node_c"]["private_data"] == "from_b", "Node C 收到 Node B 新返回的私有数据"
    
    print("✅ 测试 6 通过: 中间节点声明 MainState 会中断私有数据传递")
    print(f"   Node B 收到: {received['node_b']}")
    print(f"   Node C 收到: {received['node_c']}")
    return True


# ============================================================
# 测试 7: 混合返回（使用 BaseModel）
# ============================================================

# 定义 BaseModel 版本的 State
class MainStatePydantic(BaseModel):
    """主 State（使用 Pydantic BaseModel）"""
    count: int
    messages: Annotated[list, operator.add]


class PrivateStatePydantic(BaseModel):
    """私有 State（使用 Pydantic BaseModel）"""
    private_data: str
    temp_value: int


def test_7_mixed_return_basemodel():
    """
    场景：使用 BaseModel 定义 State，Node A 返回混合数据
    预期：与 TypedDict 行为一致，但需要发送方声明返回类型
    """
    received = {}
    
    def node_a(state: MainStatePydantic) -> PrivateStatePydantic:
        received["node_a"] = state.model_dump()
        # 混合返回：count 是 State key，private_data 是私有 key
        return {
            "count": 100,             # State key
            "private_data": "secret", # 私有 key
            "temp_value": 999         # 私有 key
        }
    
    def node_b(state: PrivateStatePydantic):  # ← 声明为 PrivateStatePydantic
        received["node_b"] = state.model_dump()
        return {}
    
    graph = StateGraph(MainStatePydantic)
    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    app = graph.compile()
    
    result = app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证 Node B 只收到私有数据
    assert "private_data" in received["node_b"], "Node B 应该收到 private_data"
    assert "temp_value" in received["node_b"], "Node B 应该收到 temp_value"
    
    print("✅ 测试 7 通过: BaseModel 混合返回时数据分离")
    print(f"   Node B 收到: {received['node_b']}")
    print(f"   最终 State: count={result.get('count', result)}")
    return True



# ============================================================
# 测试 8: 并行超步私有状态合并规则
# ============================================================
# 
# 关键发现：
# 1. 并行分支返回的所有 key 会被收集到一起
# 2. 如果不同分支返回相同的 key 且没有 Annotated reducer → 报错
# 3. 如果 key 名称不同 → 各分支独立传递，不冲突
# 4. 如果使用 Annotated reducer → 相同 key 的值会被合并
# ============================================================


def test_8a_parallel_same_key_no_reducer():
    """
    测试 8a: 并行分支返回相同 key，无 reducer
    预期：抛出 InvalidUpdateError
    """
    from langgraph.types import Send
    
    # 两个分支使用相同的 key 名称 "branch"
    class PrivateStateConflict(TypedDict):
        branch: str
        value: int
    
    def router(state: MainState):
        return [Send("branch_a", state), Send("branch_b", state)]
    
    def branch_a(state: MainState):
        return {"branch": "A", "value": 111}
    
    def branch_b(state: MainState):
        return {"branch": "B", "value": 222}
    
    def next_node(state: PrivateStateConflict):
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("branch_a", branch_a)
    graph.add_node("branch_b", branch_b)
    graph.add_node("next_node", next_node)
    
    graph.add_conditional_edges(START, router)
    graph.add_edge("branch_a", "next_node")
    graph.add_edge("branch_b", "next_node")
    graph.add_edge("next_node", END)
    
    app = graph.compile()
    
    # 预期抛出异常
    try:
        app.invoke({"count": 0, "messages": ["init"]})
        print("❌ 测试 8a 失败: 应该抛出异常但没有")
        return False
    except Exception as e:
        error_msg = str(e)
        if "Can receive only one value per step" in error_msg or "already exists" in error_msg:
            print(f"✅ 测试 8a 通过: 相同 key 无 reducer 时正确抛出异常")
            print(f"   异常信息: {error_msg[:80]}...")
            return True
        else:
            print(f"❌ 测试 8a 失败: 异常类型不对 - {error_msg}")
            return False


def test_8b_parallel_different_keys():
    """
    测试 8b: 并行分支返回不同 key
    预期：各分支独立传递，不冲突
    """
    from langgraph.types import Send
    
    # 两个分支使用不同的 key 名称
    class PrivateStateA(TypedDict):
        branch_a: str
        value_a: int
    
    class PrivateStateB(TypedDict):
        branch_b: str
        value_b: int
    
    received = {}
    
    def router(state: MainState):
        print(f"[Router] 收到: {state}")
        return [Send("branch_a", state), Send("branch_b", state)]
    
    def branch_a(state: MainState):
        print(f"[Branch A] 收到: {state}")
        return {"branch_a": "A", "value_a": 111}
    
    def branch_b(state: MainState):
        print(f"[Branch B] 收到: {state}")
        return {"branch_b": "B", "value_b": 222}
    
    def next_a(state: PrivateStateA):
        received["next_a"] = dict(state)
        print(f"[Next A] 收到: {state}")
        return {}
    
    def next_b(state: PrivateStateB):
        received["next_b"] = dict(state)
        print(f"[Next B] 收到: {state}")
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("branch_a", branch_a)
    graph.add_node("branch_b", branch_b)
    graph.add_node("next_a", next_a)
    graph.add_node("next_b", next_b)
    
    graph.add_conditional_edges(START, router)
    graph.add_edge("branch_a", "next_a")
    graph.add_edge("branch_b", "next_b")
    graph.add_edge("next_a", END)
    graph.add_edge("next_b", END)
    
    app = graph.compile()
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证
    assert received["next_a"]["branch_a"] == "A", "Next A 应该收到 branch_a='A'"
    assert received["next_a"]["value_a"] == 111, "Next A 应该收到 value_a=111"
    assert received["next_b"]["branch_b"] == "B", "Next B 应该收到 branch_b='B'"
    assert received["next_b"]["value_b"] == 222, "Next B 应该收到 value_b=222"
    
    print(f"\n验证结果:")
    print(f"  Next A 收到: {received['next_a']}")
    print(f"  Next B 收到: {received['next_b']}")
    print("✅ 测试 8b 通过: 不同 key 各分支独立传递")
    return True


def test_8c_parallel_same_key_with_reducer():
    """
    测试 8c: 并行分支返回相同 key，使用 Annotated reducer
    预期：相同 key 的值会被合并
    """
    from langgraph.types import Send
    
    # 使用 Annotated 定义 reducer
    class PrivateStateMerged(TypedDict):
        branches: Annotated[list, operator.add]
        values: Annotated[list, operator.add]
    
    received = {}
    
    def router(state: MainState):
        print(f"[Router] 收到: {state}")
        return [Send("branch_a", state), Send("branch_b", state)]
    
    def branch_a(state: MainState):
        print(f"[Branch A] 收到: {state}")
        # 返回 list 格式，配合 operator.add
        return {"branches": ["A"], "values": [111]}
    
    def branch_b(state: MainState):
        print(f"[Branch B] 收到: {state}")
        return {"branches": ["B"], "values": [222]}
    
    def next_node(state: PrivateStateMerged):
        received["next_node"] = dict(state)
        print(f"[Next Node] 收到合并后的数据: {state}")
        return {}
    
    graph = StateGraph(MainState)
    graph.add_node("branch_a", branch_a)
    graph.add_node("branch_b", branch_b)
    graph.add_node("next_node", next_node)
    
    graph.add_conditional_edges(START, router)
    graph.add_edge("branch_a", "next_node")
    graph.add_edge("branch_b", "next_node")
    graph.add_edge("next_node", END)
    
    app = graph.compile()
    app.invoke({"count": 0, "messages": ["init"]})
    
    # 验证合并结果
    assert set(received["next_node"]["branches"]) == {"A", "B"}, "branches 应该包含 A 和 B"
    assert set(received["next_node"]["values"]) == {111, 222}, "values 应该包含 111 和 222"
    
    print(f"\n验证结果:")
    print(f"  Next Node 收到合并后: {received['next_node']}")
    print("✅ 测试 8c 通过: 使用 reducer 的相同 key 会被合并")
    return True


# ============================================================
# 主测试入口
# ============================================================


if __name__ == "__main__":
    print("=" * 70)
    print("LangGraph 私有数据传递机制测试")
    print("=" * 70)
    
    tests = [
        ("测试 1: 声明 PrivateState → 收到私有数据", test_1_receive_private_state),
        ("测试 2: 声明 MainState → 收到主 State", test_2_receive_main_state),
        ("测试 3: 声明 dict → 收到主 State", test_3_receive_dict),
        ("测试 4: 混合返回时数据分离 (TypedDict)", test_4_mixed_return),
        ("测试 5: 私有数据连续传递", test_5_chain_private_state),
        ("测试 6: 中间节点中断传递", test_6_chain_break),
        ("测试 7: 混合返回时数据分离 (BaseModel)", test_7_mixed_return_basemodel),
        ("测试 8a: 并行相同key无reducer → 报错", test_8a_parallel_same_key_no_reducer),
        ("测试 8b: 并行不同key → 各自独立", test_8b_parallel_different_keys),
        ("测试 8c: 并行相同key有reducer → 合并", test_8c_parallel_same_key_with_reducer),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n{'─' * 70}")
        print(f"运行: {name}")
        print("─" * 70)
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"❌ 测试失败: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            failed += 1
    
    print(f"\n{'=' * 70}")
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)
    
    if failed == 0:
        print("""
┌─────────────────────────────────────────────────────────────────────────┐
│  结论总结：                                                              │
│                                                                         │
│  【基础规则】                                                            │
│  1. 私有数据能否传递，取决于下一个节点的输入参数类型声明                 │
│  2. 声明 PrivateState → 收到私有数据                                    │
│  3. 声明 MainState / dict / 无声明 → 收到主 State                       │
│  4. 混合返回时，State key 更新主 State，私有 key 传给下一节点           │
│  5. 私有数据可以连续传递，但中间节点类型声明会影响传递链                 │
│                                                                         │
│  【并行超步合并规则】                                                    │
│  6. 收集所有并行分支返回的 key，按 key 名称进行合并                      │
│  7. 相同 key 无 Annotated reducer → 报错 (Can receive only one value)  │
│  8. 不同 key → 各分支独立传递，根据下一节点类型声明匹配传入              │
│  9. 相同 key 有 Annotated reducer → 值被合并后传入                       │
│ 10. 若下一节点未声明私有类型，则传入公共 State    
|   【注意】                                                               │
|   所导入的schemas的key不能相同，否则就会报错：                            |
|Channel 'branch' already exists with a different type                      |
└─────────────────────────────────────────────────────────────────────────┘
""")

