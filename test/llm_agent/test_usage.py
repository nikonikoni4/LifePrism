"""直接运行此文件以测试 LLM usage 返回的结构"""
import asyncio
import sys
import os

# 将项目根目录添加到 pythonpath，确保能导入 lifeprism
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from lifeprism.llm.bus.queue import bus
from lifeprism.llm.channel.manager import Channel
from lifeprism.llm.agent.loop import AgentLoop
import pytest

def _drain_queue(q: asyncio.Queue):
    """清空 asyncio.Queue"""
    while not q.empty():
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            break

@pytest.mark.asyncio
async def test_usage_logic():
    """直接运行的测试函数"""
    print("--- 启动 AgentLoop ---")
    loop = AgentLoop(bus)
    agent_task = asyncio.create_task(loop.loop())

    print("--- 初始化 Channel ---")
    channel = Channel(bus)

    try:
        print("--- 发送消息中... ---")
        reply = await channel.send("Hello, how are you?")

        # 在 Windows 环境下，彻底避免 print 到 GBK 控制台的编码问题
        try:
            content_str = reply.content.encode('gbk', errors='replace').decode('gbk')
            print(f"\n[LLM Response Content]: {content_str}")
        except Exception:
            print(f"\n[LLM Response Content]: {repr(reply.content)}")

        print(f"[LLM Usage Data]: {reply.usage}")

        if reply.usage:
            print("\n详细 Token 消耗:")
            print(f"  - prompt_tokens (输入): {reply.usage.get('prompt_tokens', 'N/A')}")
            print(f"  - completion_tokens (输出): {reply.usage.get('completion_tokens', 'N/A')}")
            print(f"  - total_tokens (总计): {reply.usage.get('total_tokens', 'N/A')}")
        else:
            print("\n[警告] 未获取到 usage 数据")

    except Exception as e:
        print(f"\n[错误]: {e}")
    finally:
        print("\n--- 正在关闭... ---")
        await channel.close()
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        _drain_queue(bus.inbound)
        _drain_queue(bus.outbound)
        print("--- 测试完成 ---")

if __name__ == "__main__":
    # 设置 Windows 下的事件循环策略（如果需要）
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_usage_test())
