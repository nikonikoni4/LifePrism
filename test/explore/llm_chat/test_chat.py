"""使用 bus 进行 LLM 对话的测试"""
import asyncio
from lifeprism.llm.bus import bus
from lifeprism.llm.agent.loop import agent_loop

async def test_chat():
    """控制台对话测试"""
    print("=== LLM 对话测试 ===")
    print("输入 'quit' 退出\n")

    # 启动 agent loop
    loop_task = asyncio.create_task(agent_loop.loop())

    session_id = None
    try:
        while True:
            user_input = input("你: ").strip()
            if user_input.lower() == 'quit':
                break
            if not user_input:
                continue

            result = await bus.send(
                content=user_input,
                session_id=session_id,
                type="chat"
            )

            # 更新 session_id 用于连续对话
            if hasattr(result, 'session_id') and result.session_id:
                session_id = result.session_id

            print(f"AI: {result}\n")
    finally:
        agent_loop.stop()
        loop_task.cancel()

if __name__ == "__main__":
    asyncio.run(test_chat())
