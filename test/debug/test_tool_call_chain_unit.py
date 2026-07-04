"""单元测试：验证 tool_call_chain 数据结构"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_outbound_message_structure():
    """测试 OutboundMessage 是否支持 tool_call_chain"""
    from lifeprism.llm.bus import OutboundMessage
    from lifeprism.llm.providers import LLMResponse

    # 模拟工具调用链
    tool_call_chain = [
        {
            "round": 1,
            "tool_calls": [
                {
                    "id": "call_123",
                    "name": "query_activity",
                    "arguments": {"date": "2026-06-30"},
                    "result": "查询成功",
                    "is_error": False
                },
                {
                    "id": "call_789",
                    "name": "bad_tool",
                    "arguments": {"param": "bad"},
                    "result": "ERROR工具调用失败",
                    "is_error": True
                }
            ]
        },
        {
            "round": 2,
            "tool_calls": [
                {
                    "id": "call_456",
                    "name": "summarize",
                    "arguments": {"content": "..."},
                    "result": "总结完成",
                    "is_error": False
                }
            ]
        }
    ]

    # 创建 OutboundMessage
    msg = OutboundMessage(
        id="test_id",
        response=LLMResponse(content="测试响应"),
        session_id="test_session",
        extra={"tool_call_chain": tool_call_chain}
    )

    print("=" * 60)
    print("测试：OutboundMessage 数据结构")
    print("=" * 60)

    # 验证结构
    assert msg.extra is not None, "extra 不应为 None"
    assert "tool_call_chain" in msg.extra, "extra 应包含 tool_call_chain"
    assert len(msg.extra["tool_call_chain"]) == 2, "应有 2 轮工具调用"

    print("\n[成功] OutboundMessage 结构正确")
    print(f"  - extra 包含键: {list(msg.extra.keys())}")
    print(f"  - tool_call_chain 长度: {len(msg.extra['tool_call_chain'])}")

    # 验证每轮数据
    for i, round_data in enumerate(msg.extra["tool_call_chain"], 1):
        assert "round" in round_data, f"第 {i} 轮缺少 round 字段"
        assert "tool_calls" in round_data, f"第 {i} 轮缺少 tool_calls 字段"
        for tc in round_data["tool_calls"]:
            assert "is_error" in tc, f"工具调用 {tc.get('name')} 缺少 is_error 字段"
            assert isinstance(tc["is_error"], bool), f"is_error 应为布尔类型"
        print(f"  - 第 {round_data['round']} 轮: {len(round_data['tool_calls'])} 个工具调用")

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


def test_llm_call_logger_structure():
    """测试 llm_call_logger 是否能正确保存 tool_call_chain"""
    from lifeprism.llm.bus import InboundMessage, OutboundMessage, MessageType
    from lifeprism.llm.providers import LLMResponse
    from lifeprism.llm.utils import llm_call_logger
    import json
    from datetime import datetime

    print("\n" + "=" * 60)
    print("测试：llm_call_logger 记录结构")
    print("=" * 60)

    # 启用 logger
    llm_call_logger.enabled = True

    # 模拟数据
    tool_call_chain = [
        {
            "round": 1,
            "tool_calls": [
                {
                    "id": "call_789",
                    "name": "test_tool",
                    "arguments": {"param": "value"},
                    "result": "测试结果",
                    "is_error": False
                }
            ]
        }
    ]

    inbound = InboundMessage(
        type=MessageType.CHAT,
        content="测试消息"
    )

    outbound = OutboundMessage(
        id="test_id",
        response=LLMResponse(content="测试响应", usage={"input_tokens": 10, "output_tokens": 20}),
        session_id="test_session",
        extra={"tool_call_chain": tool_call_chain}
    )

    # 记录
    record_id = llm_call_logger.log_call(
        inbound_msg=inbound,
        outbound_msg=outbound,
        prompt_module="test",
        prompt_name="structure_test"
    )

    assert record_id is not None, "应成功记录"
    print(f"\n[成功] 记录 ID: {record_id}")

    # 验证日志文件
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"

    assert log_file.exists(), f"日志文件不存在: {log_file}"
    print(f"[成功] 日志文件存在: {log_file}")

    with open(log_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 找到记录
    record = None
    for call in data.get("calls", []):
        if call.get("id") == record_id:
            record = call
            break

    assert record is not None, f"未找到记录 {record_id}"
    assert "tool_call_chain" in record, "记录中缺少 tool_call_chain"
    assert len(record["tool_call_chain"]) == 1, "tool_call_chain 长度不正确"

    print(f"[成功] 日志文件包含 tool_call_chain")
    print(f"  - 共 {len(record['tool_call_chain'])} 轮")

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_outbound_message_structure()
    test_llm_call_logger_structure()
