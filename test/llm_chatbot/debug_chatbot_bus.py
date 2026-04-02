import asyncio
import sys
import os
import uuid

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.getcwd()))

from lifeprism.llm.chat.chat_bot import ChatBot
from lifeprism.llm.bus import bus, OutboundMessage, InboundMessage
from lifeprism.llm.providers.base import LLMResponse

async def mock_agent_loop():
    """模拟 AgentLoop 消耗 InboundMessage 并发布 OutboundMessage"""
    print("[MockAgent] 启动...")
    while True:
        try:
            msg = await bus.consume_inbound()
            print(f"[MockAgent] 收到消息: {msg.content}, id={msg.id}")

            # 检查是否包含 history
            history = msg.extra.get('history', [])
            print(f"[MockAgent] 携带历史消息数: {len(history)}")

            # 模拟 LLM 响应
            response = LLMResponse(content=f"回复: {msg.content} (已处理历史)")
            out_msg = OutboundMessage(id=msg.id, response=response)

            await bus.publish_outbound(out_msg)
            print(f"[MockAgent] 已发布回复: {msg.id}")
        except Exception as e:
            print(f"[MockAgent] 错误: {e}")
            break

async def test_integration():
    print("\n--- 集成测试: ChatBot + Bus + MockAgent ---")

    # 1. 启动 Mock Agent
    agent_task = asyncio.create_task(mock_agent_loop())

    try:
        bot = ChatBot()

        # 2. 创建会话
        session = bot.get_or_create_session()
        session_id = session.id
        print(f"[Test] 会话 ID: {session_id}")

        # 3. 发送第一条消息
        print("[Test] 发送第一条消息...")
        res1 = await bot.chat("第一条消息", session_id=session_id)
        print(f"[Test] 收到回复 1: {res1.content}")

        # 4. 发送第二条消息（验证历史记录自动带入）
        print("\n[Test] 发送第二条消息...")
        res2 = await bot.chat("第二条消息", session_id=session_id)
        print(f"[Test] 收到回复 2: {res2.content}")

        # 5. 检查 Session 状态
        session_final = bot.get_session(session_id)
        print(f"\n[Test] 最终 Session 消息数: {len(session_final.messages)}")
        for m in session_final.messages:
            print(f"  - {m['role']}: {m['content']}")

        assert len(session_final.messages) == 4 # 2 user + 2 assistant
        print("\n[Test] 测试成功！")

    finally:
        agent_task.cancel()
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(test_integration())
