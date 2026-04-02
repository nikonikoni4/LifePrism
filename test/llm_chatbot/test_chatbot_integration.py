import asyncio
import os
import sys

# Ensure lifeprism is in path
sys.path.append(os.getcwd())

# Must import settings first according to CLAUDE.md
from lifeprism.config.settings_manager import settings
from lifeprism.llm.agent.loop import agent_loop
from lifeprism.llm.chat.chat_bot import ChatBot
from lifeprism.llm.bus import bus

async def test_chat():
    print("Starting AgentLoop...")
    # Start agent loop in background
    loop_task = asyncio.create_task(agent_loop.loop())

    bot = ChatBot()

    try:
        print("Sending: Hello")
        # Using a timeout to avoid hanging if something is wrong
        response = await asyncio.wait_for(bot.chat("Hello"), timeout=30.0)
        print(f"Response: {response.content}")

        print("\nSending: Who are you?")
        response2 = await asyncio.wait_for(bot.chat("Who are you?"), timeout=30.0)
        print(f"Response: {response2.content}")
    except asyncio.TimeoutError:
        print("Error: Chat request timed out")
    except Exception as e:
        print(f"Error during chat: {e}")
    finally:
        print("Stopping...")
        bot.stop()
        agent_loop.stop()
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    # Set encoding to utf-8 for Windows console
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    asyncio.run(test_chat())
