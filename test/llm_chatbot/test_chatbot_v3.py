import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.getcwd()))

from lifeprism.llm.chat.chat_bot import ChatBot
from lifeprism.server.services.chatbot_service import chatbot_service
from lifeprism.server.schemas.chatbot_schemas import UpdateSessionRequest

async def test_chatbot_direct():
    print("\n--- 测试 ChatBot 直接调用 ---")
    bot = ChatBot()

    # 1. 创建新会话
    session = bot.get_or_create_session()
    session_id = session.id
    print(f"创建会话: {session_id}, 名称: {session.name}")

    # 2. 发送消息
    print("正在发送消息: '你好，谁是你的创造者？'")
    response = await bot.chat("你好，谁是你的创造者？", session_id=session_id)
    print(f"助手回复: {response.content}")

    # 3. 验证持久化
    bot2 = ChatBot()
    session_reloaded = bot2.get_session(session_id)
    print(f"重新加载会话，消息数: {len(session_reloaded.messages)}")
    assert len(session_reloaded.messages) == 2

async def test_chatbot_service():
    print("\n--- 测试 ChatbotService (业务层) ---")
    service = chatbot_service

    # 1. 获取会话列表
    sessions_resp = await service.get_sessions(page=1, page_size=10)
    print(f"当前会话总数: {sessions_resp.total}")

    # 2. 发送消息 (方式B)
    print("通过 Service 发送消息...")
    events = []
    async for event in service.send_message("测试 Service 消息", session_id=None):
        events.append(event)
        print(f"事件: {event.type}, 内容: {event.message or event.session_id}")

    new_session_id = next(e.session_id for e in events if e.type == 'session')

    # 3. 更新会话名称
    print(f"更新会话 {new_session_id} 名称为 '新测试名称'")
    await service.update_session(new_session_id, UpdateSessionRequest(name="新测试名称"))

    # 4. 验证历史记录
    history = await service.get_history(new_session_id)
    print(f"会话名称: {history.session_name}, 历史消息数: {len(history.messages)}")
    assert history.session_name == "新测试名称"

    # 5. 删除会话
    print(f"删除会话: {new_session_id}")
    await service.delete_session(new_session_id)

    final_sessions = await service.get_sessions(page=1, page_size=10)
    print(f"最终会话数: {final_sessions.total}")

if __name__ == "__main__":
    asyncio.run(test_chatbot_direct())
    asyncio.run(test_chatbot_service())
