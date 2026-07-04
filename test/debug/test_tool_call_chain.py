"""测试工具调用链记录功能"""
import asyncio
import json
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.bus import InboundMessage, MessageType, bus
from lifeprism.llm.utils import llm_call_logger


async def test_tool_call_chain():
    """测试工具调用链是否正确记录"""

    # 1. 启用 llm_call_logger
    llm_call_logger.enabled = True
    print(f"[OK] llm_call_logger 已启用")

    # 2. 发送一个需要多次工具调用的消息
    msg = InboundMessage(
        type=MessageType.CHAT,
        content="帮我查看一下今天的活动记录，然后总结一下"
    )

    print(f"\n[OK] 发送消息: {msg.content}")
    result = await bus.send(msg)

    print(f"\n[OK] 收到响应")
    print(f"  - response.content: {result.response.content[:100] if result.response and result.response.content else 'None'}...")

    # 3. 检查 extra 中是否有 tool_call_chain
    if result.extra and "tool_call_chain" in result.extra:
        tool_call_chain = result.extra["tool_call_chain"]
        print(f"\n[OK] 工具调用链已记录，共 {len(tool_call_chain)} 轮")

        for round_data in tool_call_chain:
            round_num = round_data["round"]
            tool_calls = round_data["tool_calls"]
            print(f"\n  第 {round_num} 轮:")
            for tc in tool_calls:
                error_flag = " ❌[ERROR]" if tc.get('is_error') else ""
                print(f"    - 工具: {tc['name']}{error_flag}")
                print(f"      参数: {json.dumps(tc['arguments'], ensure_ascii=False)}")
                result_preview = tc['result'][:100] if len(tc['result']) > 100 else tc['result']
                print(f"      结果: {result_preview}...")
    else:
        print(f"\n[WARN] 未找到工具调用链（可能没有工具调用）")

    # 4. 记录到 llm_call_logger
    record_id = llm_call_logger.log_call(
        inbound_msg=msg,
        outbound_msg=result,
        prompt_module="test",
        prompt_name="tool_call_chain_test",
        prompt_version="v1"
    )

    if record_id:
        print(f"\n[OK] 已记录到 llm_call_logger: {record_id}")

        # 5. 验证日志文件中是否包含 tool_call_chain
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"

        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 找到刚才的记录
            for call in data.get("calls", []):
                if call.get("id") == record_id:
                    if "tool_call_chain" in call:
                        print(f"[OK] 日志文件中包含 tool_call_chain")
                        print(f"  - 共 {len(call['tool_call_chain'])} 轮工具调用")
                    else:
                        print(f"[ERROR] 日志文件中未找到 tool_call_chain")
                    break
        else:
            print(f"[ERROR] 日志文件不存在: {log_file}")
    else:
        print(f"\n[WARN] llm_call_logger 未记录（可能未启用）")


if __name__ == "__main__":
    asyncio.run(test_tool_call_chain())
