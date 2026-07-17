"""简化版测试：验证工具调用链功能"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lifeprism.llm.bus import InboundMessage, MessageType, bus
from lifeprism.llm.utils import llm_call_logger


async def main():
    print("=" * 60)
    print("测试：工具调用链记录功能")
    print("=" * 60)

    # 启用 logger
    llm_call_logger.enabled = True
    print("\n1. llm_call_logger 已启用")

    # 发送简单消息
    msg = InboundMessage(type=MessageType.CHAT, content="你好，今天天气怎么样？")

    print(f"\n2. 发送消息: {msg.content}")
    result = await bus.send(msg)

    print(f"\n3. 收到响应")
    if result.response:
        print(
            f"   内容预览: {result.response.content[:50]}..."
            if result.response.content
            else "   (无内容)"
        )

    # 检查 extra
    print(f"\n4. 检查 extra 字段")
    if result.extra:
        print(f"   extra 包含的键: {list(result.extra.keys())}")
        if "tool_call_chain" in result.extra:
            chain = result.extra["tool_call_chain"]
            print(f"   [成功] 找到 tool_call_chain，共 {len(chain)} 轮")
            for r in chain:
                error_count = sum(1 for tc in r["tool_calls"] if tc.get("is_error"))
                error_info = f" (含 {error_count} 个错误)" if error_count > 0 else ""
                print(f"      - 第 {r['round']} 轮: {len(r['tool_calls'])} 个工具调用{error_info}")
        else:
            print(f"   [提示] 没有 tool_call_chain（可能此消息未触发工具调用）")
    else:
        print(f"   extra 为空")

    # 记录到 logger
    print(f"\n5. 记录到 llm_call_logger")
    record_id = llm_call_logger.log_call(
        inbound_msg=msg, outbound_msg=result, prompt_module="test", prompt_name="simple_test"
    )

    if record_id:
        print(f"   [成功] 记录 ID: {record_id}")
    else:
        print(f"   [失败] 未能记录")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
