import asyncio
import sys
from lifeprism.llm.agent.loop import agent_loop
from lifeprism.llm.chat.chat_bot import ChatBot

# 设置标准输出编码为 utf-8，避免 Windows 上的编码错误
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test_chatbot():
    # 1. 启动 AgentLoop
    loop_task = asyncio.create_task(agent_loop.loop())
    print("[Test] AgentLoop started.")

    # 2. 初始化 ChatBot
    bot = ChatBot()

    try:
        # 3. 发送消息
        print("[Test] Sending message: '你好'")
        response = await bot.chat("你好")
        # 使用 repr 打印以避免复杂的字符编码问题
        print(f"[Test] Received response: {repr(response)}")

        # 4. 再次发送消息（测试多轮/并发安全性）
        print("\n[Test] Sending message: '你是谁？'")
        response2 = await bot.chat("你是谁？")
        print(f"[Test] Received response: {repr(response2)}")

    finally:
        # 5. 清理
        print("\n[Test] Cleaning up...")
        # 注意：ChatBot 类中如果没实现 close，则不调用
        if hasattr(bot, 'close'):
            await bot.close()

        agent_loop.stop()
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        print("[Test] Done.")

if __name__ == "__main__":
    asyncio.run(test_chatbot())
