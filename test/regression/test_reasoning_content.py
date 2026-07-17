"""
回归测试：reasoning_content 在多轮对话中的传递

问题背景：
MiniMax API 要求在多轮对话中，如果模型返回了 reasoning_content（思考过程），
后续请求必须将这个 reasoning_content 传回 API，否则会报错：
"The reasoning_content in the thinking mode must be passed back to the API."

修复方案：
在 loop.py 的 session.add_message() 调用中添加 reasoning_content 参数
"""

import json
from pathlib import Path

from lifeprism.llm.providers import LLMResponse, ToolCallRequest
from lifeprism.llm.session import Session, session_manager


def test_reasoning_content_in_memory():
    """测试 reasoning_content 是否正确保存到内存"""
    print("=" * 60)
    print("Test 1: reasoning_content in memory")
    print("=" * 60)

    session = Session()

    # 模拟 LLM 返回带 reasoning_content 的响应
    response = LLMResponse(
        content="This is the response",
        reasoning_content="This is the reasoning process",
        tool_calls=[],
        finish_reason="stop",
    )

    # 正确的实现：传递 reasoning_content
    session.add_message(
        "assistant",
        content=response.content or "",
        tool_calls=[],
        reasoning_content=response.reasoning_content,
    )

    # 检查消息是否包含 reasoning_content
    messages = session.get_history_message()
    last_msg = messages[-1]

    print(f"Message keys: {list(last_msg.keys())}")

    if (
        "reasoning_content" in last_msg
        and last_msg["reasoning_content"] == response.reasoning_content
    ):
        print("[PASS] reasoning_content correctly saved in memory")
        return True
    else:
        print("[FAIL] reasoning_content not saved or incorrect")
        return False


def test_reasoning_content_persistence():
    """测试 reasoning_content 是否正确持久化到文件"""
    print("\n" + "=" * 60)
    print("Test 2: reasoning_content persistence")
    print("=" * 60)

    # 创建新 session
    session = session_manager.get_or_create_session()

    # 添加带 reasoning_content 的消息
    response = LLMResponse(
        content="Persistent response",
        reasoning_content="Persistent reasoning",
        tool_calls=[],
        finish_reason="stop",
    )

    session.add_message(
        "assistant",
        content=response.content or "",
        tool_calls=[],
        reasoning_content=response.reasoning_content,
    )

    # 保存到文件
    session_manager.save_session(session)
    session_id = session.id

    # 清空缓存
    session_manager._cache.clear()

    # 重新加载
    loaded_session = session_manager.get_or_create_session(session_id)
    messages = loaded_session.get_history_message()

    # 检查是否包含 reasoning_content
    if messages:
        last_msg = messages[-1]
        if (
            "reasoning_content" in last_msg
            and last_msg["reasoning_content"] == response.reasoning_content
        ):
            print("[PASS] reasoning_content correctly persisted and loaded")
            # 清理测试文件
            session_manager.delete_session(session_id)
            return True
        else:
            print("[FAIL] reasoning_content not persisted or loaded incorrectly")
            session_manager.delete_session(session_id)
            return False
    else:
        print("[FAIL] No messages loaded")
        session_manager.delete_session(session_id)
        return False


def test_reasoning_content_with_tool_calls():
    """测试带工具调用的 reasoning_content"""
    print("\n" + "=" * 60)
    print("Test 3: reasoning_content with tool calls")
    print("=" * 60)

    session = Session()

    # 模拟带工具调用和 reasoning_content 的响应
    response = LLMResponse(
        content="",
        reasoning_content="Thinking about which tool to use",
        tool_calls=[ToolCallRequest(id="call_123", name="test_tool", arguments={"param": "value"})],
        finish_reason="tool_calls",
    )

    session.add_message(
        "assistant",
        content=response.content or "",
        tool_calls=[
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in response.tool_calls
        ],
        reasoning_content=response.reasoning_content,
    )

    messages = session.get_history_message()
    last_msg = messages[-1]

    has_reasoning = "reasoning_content" in last_msg
    has_tool_calls = "tool_calls" in last_msg and len(last_msg["tool_calls"]) > 0

    if has_reasoning and has_tool_calls:
        print("[PASS] Both reasoning_content and tool_calls saved correctly")
        return True
    else:
        print(f"[FAIL] reasoning_content: {has_reasoning}, tool_calls: {has_tool_calls}")
        return False


if __name__ == "__main__":
    results = []

    results.append(test_reasoning_content_in_memory())
    results.append(test_reasoning_content_persistence())
    results.append(test_reasoning_content_with_tool_calls())

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Total: {len(results)}, Passed: {sum(results)}, Failed: {len(results) - sum(results)}")

    if all(results):
        print("\n[SUCCESS] All tests passed!")
        exit(0)
    else:
        print("\n[FAILURE] Some tests failed!")
        exit(1)
