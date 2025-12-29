"""
V1 版本聊天机器人,带记忆功能
"""

from langchain_core.messages import HumanMessage, SystemMessage
from lifewatch.llm.llm_classify.utils.create_model import create_ChatTongyiModel
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from dataclasses import dataclass
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Union, AsyncGenerator, Dict, Any
from lifewatch.config.database import CHAT_HISTORY_DB

# 暂定
@dataclass
class Context:
    user_name: str


class ChatBot:
    """
    聊天机器人类，支持内存存储和 SQLite 持久化存储两种模式。
    
    使用方式：
    1. 内存模式（不保存会话）: 
        chatbot = ChatBot()
        async for content in chatbot.chat("你好"):
            print(content)
    
    2. 持久化模式: 
        async with ChatBot.create_with_persistence() as chatbot:
            async for content in chatbot.chat("你好"):
                print(content)
    """
    
    def __init__(
        self,
        checkpointer: Optional[Union[InMemorySaver, AsyncSqliteSaver]] = None,
        enable_search=False,
        enable_streaming=True,
        enable_thinking=False
    ):
        """
        初始化 ChatBot。
        
        Args:
            checkpointer: 检查点保存器，None 时使用 InMemorySaver
        """
        self.chat_model = create_ChatTongyiModel(
            enable_search=enable_search,
            enable_streaming=enable_streaming,
            enable_thinking=enable_thinking
        )
        self.system_prompt = "You are a helpful assistant."
        self.checkpointer = checkpointer or InMemorySaver()
        self._is_persistent = isinstance(self.checkpointer, AsyncSqliteSaver)
        
        self.agent = create_agent(
            self.chat_model,
            checkpointer=self.checkpointer,
            system_prompt=self.system_prompt,
            context_schema=Context
        )
        self.context = Context(user_name="John")
        self.config: Optional[dict] = None  # 需要通过 set_thread_id() 或 chat(config=...) 设置
        # Token 使用统计
        self.tokens_usage: Dict[str, Any] = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'search_count': 0
        }
    
    @classmethod
    @asynccontextmanager
    async def create_with_persistence(
        cls,
        db_path: Union[str, Path] = CHAT_HISTORY_DB
    ) -> AsyncGenerator["ChatBot", None]:
        """
        异步上下文管理器工厂方法：创建使用 AsyncSqliteSaver 持久化的 ChatBot 实例。
        
        使用方式:
            async with ChatBot.create_with_persistence() as chatbot:
                async for content in chatbot.chat("你好"):
                    print(content)
        
        Args:
            db_path: SQLite 数据库文件路径
            
        Yields:
            使用 AsyncSqliteSaver 的 ChatBot 实例
        """
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            yield cls(checkpointer)
    
    def get_new_agent(
        self,
        enable_search: bool = False,
        enable_streaming: bool = True,
        enable_thinking: bool = False,
        
    ):
        """
        创建一个新的 agent，使用指定的模型参数。
        
        Args:
            enable_search: 启用搜索功能
            enable_streaming: 启用流式输出
            enable_thinking: 启用思考模式
            
        Returns:
            新的 agent 实例
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
    
    async def chat(self, messages: str, config: Optional[dict] = None):
        """
        发送消息并获取流式响应。
        
        Args:
            messages: 用户输入的消息
            config: 可选的配置，默认使用 self.config
            
        Yields:
            AI 响应的内容片段
            
        Note:
            调用结束后，可通过 self.tokens_usage 获取本次对话的 token 使用情况
        """
        if config is None:
            config = self.config
        
        if config is None:
            raise ValueError(
                "会话配置未设置。请先调用 set_thread_id(thread_id) 设置会话ID，"
                "或在 chat() 调用时传入 config 参数。"
            )
        
        # 重置 token 统计
        self.tokens_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'search_count': 0
        }
        
        # 用于估算的变量
        output_content = ""
        last_message = None
            
        async for chunk in self.agent.astream(
            {"messages": HumanMessage(content=messages)},
            config=config,
            context=self.context,
            stream_mode="messages"
        ):
            if len(chunk) >= 1:
                message = chunk[0]
                last_message = message  # 保存最后一个消息用于解析 token
                if hasattr(message, 'content') and message.content:
                    output_content += message.content
                    print(message.content, end="", flush=True)
                    yield message.content
        
        # 解析或估算 token 使用量
        self._update_token_usage(last_message, messages, output_content)
    
    def _update_token_usage(
        self, 
        last_message: Any, 
        input_text: str, 
        output_text: str
    ):
        """
        更新 token 使用统计
        
        流式模式下 AIMessageChunk 的结构:
        - content: 内容片段
        - response_metadata: {} (流式模式下为空)
        - usage_metadata: None 或 {'input_tokens': x, 'output_tokens': y, 'total_tokens': z}
        - chunk_position: 'first'/'middle'/'last'
        
        Args:
            last_message: 最后一个响应消息（AIMessageChunk）
            input_text: 输入文本，用于估算
            output_text: 输出文本，用于估算
        """
        # 尝试从 usage_metadata 解析（部分模型在最后一个 chunk 会包含）
        if last_message is not None:
            try:
                # 方式1: 检查 usage_metadata 属性
                usage_meta = getattr(last_message, 'usage_metadata', None)
                if usage_meta is not None and isinstance(usage_meta, dict):
                    if usage_meta.get('total_tokens', 0) > 0:
                        self.tokens_usage = {
                            'input_tokens': usage_meta.get('input_tokens', 0),
                            'output_tokens': usage_meta.get('output_tokens', 0),
                            'total_tokens': usage_meta.get('total_tokens', 0),
                            'search_count': 0
                        }
                        return
                
                # 方式2: 检查 response_metadata (非流式调用时)
                response_meta = getattr(last_message, 'response_metadata', {})
                if response_meta:
                    token_usage = response_meta.get('token_usage', {})
                    if token_usage.get('total_tokens', 0) > 0:
                        self.tokens_usage = {
                            'input_tokens': token_usage.get('input_tokens', 0),
                            'output_tokens': token_usage.get('output_tokens', 0),
                            'total_tokens': token_usage.get('total_tokens', 0),
                            'search_count': token_usage.get('plugins', {}).get('search', {}).get('count', 0)
                        }
                        return
            except Exception:
                pass  # 解析失败，使用估算
        
        # 估算 token 使用量
        # 中文约 2 tokens/字，英文约 0.75 tokens/词
        # 这里使用粗略估算：平均 1.5 tokens/字符
        self.tokens_usage = {
            'input_tokens': int(len(input_text) * 1.5),
            'output_tokens': int(len(output_text) * 1.5),
            'total_tokens': int((len(input_text) + len(output_text)) * 1.5),
            'search_count': 0
        }


if __name__ == "__main__":
    async def main():
        """测试 chat() 方法的 tokens_usage 获取"""
        async with ChatBot.create_with_persistence() as chatbot:
            chatbot.set_thread_id("test_tokens_usage")
            
            print("=" * 60)
            print("测试：通过 chat() 方法验证 tokens_usage 获取")
            print("=" * 60)
            print()
            
            print("AI 回复：", end="")
            async for chunk in chatbot.chat("你好，介绍一下你自己"):
                pass  # chat() 内部已经 print 了
            
            print("\n")
            print("=" * 60)
            print("tokens_usage 结果：")
            print("=" * 60)
            print(f"  input_tokens:  {chatbot.tokens_usage['input_tokens']}")
            print(f"  output_tokens: {chatbot.tokens_usage['output_tokens']}")
            print(f"  total_tokens:  {chatbot.tokens_usage['total_tokens']}")
            print(f"  search_count:  {chatbot.tokens_usage['search_count']}")
            print("=" * 60)

    import asyncio
    asyncio.run(main())

