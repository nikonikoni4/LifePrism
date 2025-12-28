"""
测试 LangGraph RetryPolicy 的 State 回滚和累加行为

测试目标:
1. 验证 RetryPolicy 是否会回滚 State
2. 验证重试时返回的 token 消耗是否会被累加
"""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy


class TestState(TypedDict):
    """测试用的 State"""
    attempt_count: int  # 尝试次数
    token_usage: dict  # Token 使用情况
    result: str  # 结果



# 全局计数器，用于跟踪实际执行次数
execution_count = 0


def test_node_with_retry(state: TestState) -> dict:
    """
    测试节点：前两次会抛出异常，第三次成功
    每次都会返回 token 消耗
    """
    global execution_count
    execution_count += 1
    
    print(f"\n{'='*60}")
    print(f"执行次数: {execution_count}")
    print(f"当前 State.attempt_count: {state.get('attempt_count', 0)}")
    print(f"当前 State.token_usage: {state.get('token_usage', {})}")
    print(f"{'='*60}")
    
    # 模拟每次调用都消耗 token
    current_tokens = {
        'input_tokens': 100,
        'output_tokens': 50,
        'total_tokens': 150
    }
    
    # 前两次抛出异常
    if execution_count < 3:
        print(f"⚠️  第 {execution_count} 次执行：准备抛出异常...")
        print(f"   本次 token 消耗: {current_tokens}")
        
        # 尝试返回 token（测试是否会被累加）
        # 注意：这里会抛异常，所以这个返回值理论上不应该被应用
        raise ValueError(f"模拟第 {execution_count} 次失败")
    
    # 第三次成功
    print(f"✅ 第 {execution_count} 次执行：成功！")
    print(f"   本次 token 消耗: {current_tokens}")
    
    return {
        "attempt_count": execution_count,
        "token_usage": current_tokens,
        "result": f"成功于第 {execution_count} 次尝试"
    }


def main():
    """运行测试"""
    global execution_count
    execution_count = 0
    
    # 创建图
    graph = StateGraph(TestState)
    
    # 添加节点，配置重试策略（最多 3 次）
    graph.add_node(
        "test_node",
        test_node_with_retry,
        retry_policy=RetryPolicy(max_attempts=3)
    )
    
    graph.add_edge(START, "test_node")
    graph.add_edge("test_node", END)
    
    app = graph.compile()
    
    # 初始 State
    initial_state = {
        "attempt_count": 0,
        "token_usage": {},
        "result": ""
    }
    
    print("\n" + "="*60)
    print("开始测试 LangGraph RetryPolicy")
    print("="*60)
    print(f"初始 State: {initial_state}")
    
    # 执行图
    try:
        final_state = app.invoke(initial_state)
        
        print("\n" + "="*60)
        print("测试完成！最终 State:")
        print("="*60)
        print(f"attempt_count: {final_state.get('attempt_count')}")
        print(f"token_usage: {final_state.get('token_usage')}")
        print(f"result: {final_state.get('result')}")
        print(f"\n实际执行次数: {execution_count}")
        
        # 验证结果
        print("\n" + "="*60)
        print("验证结果:")
        print("="*60)
        
        expected_tokens = {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150}
        actual_tokens = final_state.get('token_usage', {})
        
        if actual_tokens == expected_tokens:
            print("✅ Token 消耗正确：只统计了最后一次成功的消耗")
            print(f"   期望: {expected_tokens}")
            print(f"   实际: {actual_tokens}")
        else:
            print("❌ Token 消耗异常：可能累加了重试的消耗")
            print(f"   期望: {expected_tokens}")
            print(f"   实际: {actual_tokens}")
            
            if actual_tokens.get('total_tokens', 0) == 450:  # 150 * 3
                print("   ⚠️  确认：累加了所有 3 次尝试的 token！")
        
        if final_state.get('attempt_count') == 3:
            print("✅ attempt_count 正确：记录了第 3 次尝试")
        else:
            print(f"❌ attempt_count 错误：{final_state.get('attempt_count')}")
            
    except Exception as e:
        print(f"\n❌ 测试失败，抛出异常: {e}")


if __name__ == "__main__":
    main()
