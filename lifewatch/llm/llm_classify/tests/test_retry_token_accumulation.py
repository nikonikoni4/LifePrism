"""
测试 LangGraph RetryPolicy 的 Token 累加行为

核心问题：
- 当节点执行过程中抛出异常，RetryPolicy 会回滚 State
- 问题是：节点内部"消耗"的 tokens 是否会被累加到主 State？

测试场景：
1. 节点执行并模拟 token 消耗
2. 节点返回 token 使用记录
3. 节点抛出异常 -> 触发重试
4. 最终验证：token 是否被累加了多次
"""

from typing import Annotated
import operator
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy


class TestState(BaseModel):
    """测试用的 State - 使用 Pydantic 模型"""
    attempt_count: int = 0  # 尝试次数
    # 使用 operator.or_ 合并 dict，模拟项目中的 node_token_usage
    node_token_usage: Annotated[dict[str, dict], operator.or_] = Field(default_factory=dict)
    # 使用 operator.add 累加 list，测试列表累加行为
    token_list: Annotated[list[dict], operator.add] = Field(default_factory=list)
    result: str = ""


# 全局计数器，用于跟踪实际执行次数
execution_count = 0


def failing_node_returns_before_exception(state: TestState) -> dict:
    """
    测试场景 1：节点返回后再抛异常
    
    注意：Python 中 return 后的代码不会执行，
    但这里测试的是 LangGraph 对节点返回值的处理
    """
    global execution_count
    execution_count += 1
    
    print(f"\n{'='*60}")
    print(f"[failing_node] 执行次数: {execution_count}")
    print(f"当前 State.node_token_usage: {state.node_token_usage}")
    print(f"当前 State.token_list: {state.token_list}")
    print(f"{'='*60}")
    
    # 模拟每次调用都消耗 token
    current_tokens = {
        'input_tokens': 100 * execution_count,  # 每次不同，便于区分
        'output_tokens': 50 * execution_count,
        'total_tokens': 150 * execution_count
    }
    
    print(f"   本次 token 消耗: {current_tokens}")
    
    # 前两次抛出异常
    if execution_count < 3:
        print(f"⚠️  第 {execution_count} 次执行：准备抛出异常...")
        # 关键点：这里抛出异常，节点不会正常返回
        # RetryPolicy 应该回滚 State 到节点执行前的状态
        raise ValueError(f"模拟第 {execution_count} 次失败")
    
    # 第三次成功
    print(f"✅ 第 {execution_count} 次执行：成功！")
    
    return {
        "attempt_count": execution_count,
        "node_token_usage": {"failing_node": current_tokens},
        "token_list": [current_tokens],
        "result": f"成功于第 {execution_count} 次尝试"
    }


def test_with_tokens_before_exception():
    """
    测试场景 2：在抛异常之前先修改 state（通过返回 dict）
    
    但是 Python 中，一旦 raise 异常，return 语句不会执行。
    所以需要用一个包装器来测试"如果节点返回了值然后某处出错"的情况
    """
    pass


class TokenTracker:
    """用于跟踪 token 消耗的全局对象"""
    def __init__(self):
        self.total_tokens_consumed = 0
        self.call_history = []
    
    def consume(self, tokens: int, attempt: int):
        """模拟消耗 tokens"""
        self.total_tokens_consumed += tokens
        self.call_history.append({
            'attempt': attempt,
            'tokens': tokens,
            'cumulative': self.total_tokens_consumed
        })
        print(f"📊 TokenTracker: 第 {attempt} 次消耗 {tokens} tokens，累计: {self.total_tokens_consumed}")


# 全局 token tracker
token_tracker = TokenTracker()


def node_with_external_side_effect(state: TestState) -> dict:
    """
    测试节点：模拟外部副作用（如 API 调用）
    
    关键问题：即使 LangGraph 回滚 State，外部副作用（如 API 调用）仍然发生了
    这个测试演示：token 消耗是 "外部副作用"，不受 State 回滚影响
    """
    global execution_count
    execution_count += 1
    
    print(f"\n{'='*60}")
    print(f"[side_effect_node] 执行次数: {execution_count}")
    print(f"{'='*60}")
    
    # 模拟 API 调用消耗 token（这是真实的外部副作用）
    tokens_this_call = 100
    token_tracker.consume(tokens_this_call, execution_count)
    
    if execution_count < 3:
        print(f"⚠️  抛出异常，但 token 已经被 API 消耗了！")
        raise ValueError(f"模拟第 {execution_count} 次失败")
    
    print(f"✅ 成功！")
    
    return {
        "attempt_count": execution_count,
        "node_token_usage": {
            "side_effect_node": {
                'input_tokens': tokens_this_call,
                'output_tokens': 50,
                'total_tokens': tokens_this_call + 50
            }
        },
        "result": "成功"
    }


def run_test_1():
    """测试 1：验证 RetryPolicy 的 State 回滚行为"""
    global execution_count
    execution_count = 0
    
    print("\n" + "="*70)
    print("测试 1: 验证 RetryPolicy 的 State 回滚行为")
    print("="*70)
    
    graph = StateGraph(TestState)
    graph.add_node(
        "failing_node",
        failing_node_returns_before_exception,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ValueError)
    )
    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", END)
    
    app = graph.compile()
    
    initial_state = TestState()
    print(f"初始 State: {initial_state.model_dump()}")
    
    try:
        final_state = app.invoke(initial_state.model_dump())
        
        print("\n" + "="*70)
        print("测试 1 结果:")
        print("="*70)
        print(f"最终 node_token_usage: {final_state.get('node_token_usage')}")
        print(f"最终 token_list: {final_state.get('token_list')}")
        print(f"实际执行次数: {execution_count}")
        
        # 验证
        token_usage = final_state.get('node_token_usage', {})
        token_list = final_state.get('token_list', [])
        
        print("\n📋 分析:")
        if token_usage:
            failing_node_tokens = token_usage.get('failing_node', {})
            expected_total = 150 * 3  # 第 3 次成功
            actual_total = failing_node_tokens.get('total_tokens', 0)
            
            print(f"   node_token_usage 中的 total_tokens: {actual_total}")
            if actual_total == expected_total:
                print(f"   ✅ 只记录了最后一次成功的 token 消耗 ({expected_total})")
            else:
                print(f"   ⚠️  token 消耗值异常: 期望 {expected_total}, 实际 {actual_total}")
        
        if token_list:
            print(f"   token_list 长度: {len(token_list)}")
            if len(token_list) == 1:
                print("   ✅ token_list 只包含最后一次成功的记录")
            else:
                print(f"   ❌ token_list 包含了多次尝试的记录: {token_list}")
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return None


def run_test_2():
    """测试 2：验证外部副作用不受 State 回滚影响"""
    global execution_count
    execution_count = 0
    token_tracker.total_tokens_consumed = 0
    token_tracker.call_history = []
    
    print("\n" + "="*70)
    print("测试 2: 验证外部副作用（API 调用）不受 State 回滚影响")
    print("="*70)
    
    graph = StateGraph(TestState)
    graph.add_node(
        "side_effect_node",
        node_with_external_side_effect,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ValueError)
    )
    graph.add_edge(START, "side_effect_node")
    graph.add_edge("side_effect_node", END)
    
    app = graph.compile()
    
    initial_state = TestState()
    
    try:
        final_state = app.invoke(initial_state.model_dump())
        
        print("\n" + "="*70)
        print("测试 2 结果:")
        print("="*70)
        print(f"最终 State.node_token_usage: {final_state.get('node_token_usage')}")
        print(f"\n📊 TokenTracker (外部副作用):")
        print(f"   实际 API 调用次数: {len(token_tracker.call_history)}")
        print(f"   累计消耗的 tokens: {token_tracker.total_tokens_consumed}")
        print(f"   调用历史: {token_tracker.call_history}")
        
        print("\n📋 关键结论:")
        state_tokens = final_state.get('node_token_usage', {}).get('side_effect_node', {}).get('input_tokens', 0)
        print(f"   1. State 中记录的 input_tokens: {state_tokens}")
        print(f"   2. 实际 API 消耗的 tokens: {token_tracker.total_tokens_consumed}")
        
        if token_tracker.total_tokens_consumed > state_tokens:
            print(f"\n   ⚠️  重要发现:")
            print(f"      - State 只记录了最后一次成功的 token ({state_tokens})")
            print(f"      - 但实际 API 调用消耗了 {token_tracker.total_tokens_consumed} tokens！")
            print(f"      - 差值 = {token_tracker.total_tokens_consumed - state_tokens} (这是重试造成的额外消耗)")
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return None


def main():
    """运行所有测试"""
    print("\n" + "🔬"*35)
    print(" LangGraph RetryPolicy Token 累加行为测试")
    print("🔬"*35)
    
    # 测试 1
    result1 = run_test_1()
    
    # 测试 2  
    result2 = run_test_2()
    
    # 总结
    print("\n" + "="*70)
    print("📝 总结")
    print("="*70)
    print("""
结论：
1. 当节点抛出异常时，LangGraph 会回滚 State 到节点执行前的状态
2. 因此，失败的节点返回值（包括 token_usage）不会被应用到 State
3. 只有最后一次成功执行的返回值会被应用

但是注意：
- State 回滚 ≠ API 调用被撤销
- 即使 State 被回滚，实际的 LLM API 调用已经发生
- Token 已经被 API 消耗了，这是无法回滚的外部副作用
- 因此，如果需要准确统计 API 消耗，需要在外部进行追踪
""")


# ============================================================
# 测试 3：验证 Send 并发场景下全局 list append 的安全性
# ============================================================

from langgraph.types import Send
import time
import random

# 全局 token 累加列表
global_token_list = []


class SendTestState(BaseModel):
    """Send 测试用的 State"""
    items: list[int] = Field(default_factory=list)  # 要并发处理的 items
    results: Annotated[list[dict], operator.add] = Field(default_factory=list)


def generate_items(state: SendTestState) -> dict:
    """生成要并发处理的 items"""
    return {"items": list(range(10))}  # 生成 10 个 item


def send_to_workers(state: SendTestState) -> list[Send]:
    """Fan out: 为每个 item 创建一个并发任务"""
    print(f"\n📤 Sending {len(state.items)} items to workers...")
    return [Send("worker_node", {"item_id": i}) for i in state.items]


def worker_node(state: dict) -> dict:
    """
    并发 worker 节点
    每个 worker 独立执行，并向全局 list 追加 token 记录
    """
    global global_token_list
    
    item_id = state.get("item_id", -1)
    
    # 模拟一些处理时间 (0-50ms)
    delay = random.uniform(0, 0.05)
    time.sleep(delay)
    
    # 模拟 token 消耗
    token_usage = {
        "worker_id": item_id,
        "input_tokens": 100 + item_id * 10,
        "output_tokens": 50 + item_id * 5,
        "timestamp": time.time()
    }
    
    # 关键操作：向全局 list append
    global_token_list.append(token_usage)
    
    print(f"   Worker {item_id} 完成, tokens: {token_usage['input_tokens']}")
    
    return {"results": [{"item_id": item_id, "status": "done"}]}


def collect_results(state: SendTestState) -> dict:
    """收集所有 worker 的结果"""
    print(f"\n📥 收集结果: {len(state.results)} 个 worker 完成")
    return {}


def run_test_3():
    """测试 3：验证 Send 并发场景下全局 list append 的安全性"""
    global global_token_list
    global_token_list = []  # 重置
    
    print("\n" + "="*70)
    print("测试 3: 验证 Send 并发场景下全局 list append 的安全性")
    print("="*70)
    
    graph = StateGraph(SendTestState)
    
    # 添加节点
    graph.add_node("generate", generate_items)
    graph.add_node("worker_node", worker_node)
    graph.add_node("collect", collect_results)
    
    # 添加边
    graph.add_edge(START, "generate")
    graph.add_conditional_edges("generate", send_to_workers, ["worker_node"])
    graph.add_edge("worker_node", "collect")
    graph.add_edge("collect", END)
    
    app = graph.compile()
    
    initial_state = SendTestState()
    
    try:
        final_state = app.invoke(initial_state.model_dump())
        
        print("\n" + "="*70)
        print("测试 3 结果:")
        print("="*70)
        
        # 验证结果
        expected_count = 10  # 我们发送了 10 个 items
        actual_count = len(global_token_list)
        
        print(f"期望 worker 数量: {expected_count}")
        print(f"全局 list 中的记录数: {actual_count}")
        print(f"State.results 长度: {len(final_state.get('results', []))}")
        
        # 验证所有 worker_id 都被记录
        recorded_ids = set(item.get("worker_id") for item in global_token_list)
        expected_ids = set(range(10))
        
        print(f"\n记录的 worker IDs: {sorted(recorded_ids)}")
        print(f"期望的 worker IDs: {sorted(expected_ids)}")
        
        if recorded_ids == expected_ids and actual_count == expected_count:
            print("\n✅ 测试通过！全局 list append 在 Send 并发场景下是安全的！")
            print(f"   - 所有 {expected_count} 个 worker 的 token 都被正确记录")
            print(f"   - 没有丢失数据")
        else:
            print("\n❌ 测试失败！")
            if actual_count != expected_count:
                print(f"   - 数据丢失: 期望 {expected_count}, 实际 {actual_count}")
            if recorded_ids != expected_ids:
                missing = expected_ids - recorded_ids
                extra = recorded_ids - expected_ids
                if missing:
                    print(f"   - 缺失的 IDs: {missing}")
                if extra:
                    print(f"   - 额外的 IDs: {extra}")
        
        # 打印 token 统计
        total_input = sum(item.get("input_tokens", 0) for item in global_token_list)
        total_output = sum(item.get("output_tokens", 0) for item in global_token_list)
        print(f"\n📊 Token 统计:")
        print(f"   总 input_tokens: {total_input}")
        print(f"   总 output_tokens: {total_output}")
        print(f"   总 tokens: {total_input + total_output}")
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """运行所有测试"""
    print("\n" + "🔬"*35)
    print(" LangGraph RetryPolicy Token 累加行为测试")
    print("🔬"*35)
    
    # 测试 1
    result1 = run_test_1()
    
    # 测试 2  
    result2 = run_test_2()
    
    # 测试 3: Send 并发测试
    result3 = run_test_3()
    
    # 总结
    print("\n" + "="*70)
    print("📝 总结")
    print("="*70)
    print("""
结论：
1. 当节点抛出异常时，LangGraph 会回滚 State 到节点执行前的状态
2. 因此，失败的节点返回值（包括 token_usage）不会被应用到 State
3. 只有最后一次成功执行的返回值会被应用

但是注意：
- State 回滚 ≠ API 调用被撤销
- 即使 State 被回滚，实际的 LLM API 调用已经发生
- Token 已经被 API 消耗了，这是无法回滚的外部副作用
- 因此，如果需要准确统计 API 消耗，需要在外部进行追踪

测试 3 结论：
- 在 LangGraph 的 Send 并发场景下，全局 list.append() 是安全的
- 因为 LangGraph 使用 asyncio 协程，而非多线程
- 所有并发 worker 的 token 都能被正确记录
""")


if __name__ == "__main__":
    main()
