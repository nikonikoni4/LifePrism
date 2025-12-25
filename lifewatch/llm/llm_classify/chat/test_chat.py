from langchain_core.messages import HumanMessage, SystemMessage
from lifewatch.llm.llm_classify.utils.create_model import create_ChatTongyiModel
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from dataclasses import dataclass
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# 数据库路径配置
DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "chatbot.db"


@dataclass
class Context:
    user_name: str


class ChatBot:
    """
    使用 AsyncSqliteSaver 持久化存储会话的聊天机器人。
    
    使用方式：
        async with ChatBot.create() as chatbot:
            async for content in chatbot.chat("你好"):
                print(content)
    """
    
    def __init__(self, checkpointer: AsyncSqliteSaver):
        """
        私有构造函数，请使用 ChatBot.create() 工厂方法创建实例。
        """
        self.chat_model = create_ChatTongyiModel(
            enable_search=False, 
            enable_streaming=True, 
            enable_thinking=False
        )
        self.system_prompt = "You are a helpful assistant."
        self.checkpointer = checkpointer
        self.agent = create_agent(
            self.chat_model,
            checkpointer=self.checkpointer,
            system_prompt=self.system_prompt,
            context_schema=Context
        )
        self.context = Context(user_name="John")
        self.config = {"configurable": {"thread_id": "1"}}  # 默认会话ID
    
    @classmethod
    @asynccontextmanager
    async def create(cls, db_path: str | Path = DB_PATH) -> AsyncGenerator["ChatBot", None]:
        """
        异步上下文管理器工厂方法：创建 ChatBot 实例。
        
        使用方式:
            async with ChatBot.create() as chatbot:
                async for content in chatbot.chat("你好"):
                    print(content)
        
        Args:
            db_path: SQLite 数据库文件路径
            
        Yields:
            初始化完成的 ChatBot 实例
        """
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            yield cls(checkpointer)
    
    def get_new_agent(
        self,
        enable_search: bool = False,
        enable_streaming: bool = True,
        enable_thinking: bool = False
    ):
        """
        创建一个新的 agent，使用指定的模型参数。
        """
        self.chat_model = create_ChatTongyiModel(
            enable_search=enable_search,
            enable_streaming=enable_streaming,
            enable_thinking=enable_thinking
        )
        self.agent = create_agent(
            self.chat_model,
            checkpointer=self.checkpointer,
            system_prompt=self.system_prompt,
            context_schema=Context
        )
        return self.agent
    
    def set_thread_id(self, thread_id: str):
        """
        设置当前会话的 thread_id。
        
        Args:
            thread_id: 会话ID，用于区分不同的对话
        """
        self.config = {"configurable": {"thread_id": thread_id}}
    
    async def chat(self, messages: str, config: dict | None = None):
        """
        发送消息并获取流式响应。
        
        Args:
            messages: 用户输入的消息
            config: 可选的配置，默认使用 self.config
            
        Yields:
            AI 响应的内容片段
        """
        if config is None:
            config = self.config
            
        async for chunk in self.agent.astream(
            {"messages": HumanMessage(content=messages)},
            config=config,
            context=self.context,
            stream_mode="messages"
        ):
            if len(chunk) >= 1:
                message = chunk[0]
                # 只打印 AI 消息的内容
                if hasattr(message, 'content') and message.content:
                    print(message.content, end="", flush=True)
                    yield message.content


async def main():
    """
    测试函数：演示 AsyncSqliteSaver 的持久化存储功能。
    """
    print("=== 测试 AsyncSqliteSaver 会话持久化 ===\n")
    
    async with ChatBot.create() as chatbot:
        # 设置会话ID（可以用于恢复历史对话）
        chatbot.set_thread_id("test_session_1")
        
        print("开始流式输出：\n")
        async for content in chatbot.chat("简单介绍红楼梦"):
            pass  # 消息已在 chat 方法中打印
        
        print("\n")
    
    print(f"=== 流式输出结束，会话已保存到: {DB_PATH} ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
