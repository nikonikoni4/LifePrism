"""
LangGraph 上下文管理演示脚本

这个脚本演示了如何用自定义 Graph 实现类似 Agent 的上下文管理功能。
核心原理：
1. State 中的 messages 字段使用 operator.add，实现消息累加
2. checkpointer 自动保存和恢复整个 State
3. 每次调用时，通过 thread_id 区分不同会话
"""

from typing import Annotated
from typing_extensions import TypedDict
import operator
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# 导入你的模型创建函数
from lifewatch.llm.llm_classify.utils import create_ChatTongyiModel


# ============================================
# 第一步：定义 State（类似 Agent 内部的状态）
# ============================================
class ChatState(TypedDict):
    """
    对话状态
    
    messages 使用 Annotated[list, operator.add] 的作用：
    - 每次节点返回 {"messages": [new_msg]} 时
    - 新消息会 **追加** 到现有列表，而不是覆盖
    - 这就是上下文累积的核心原理！
    """
    messages: Annotated[list[BaseMessage], operator.add]


# ============================================
# 第二步：定义节点（处理逻辑）
# ============================================
class SimpleChatGraph:
    """
    简单的聊天 Graph，复现 Agent 的上下文管理功能
    """
    
    def __init__(self, checkpointer=None):
        self.checkpointer = checkpointer or InMemorySaver()
        self.llm = create_ChatTongyiModel(
            enable_search=False,
            enable_thinking=False,
            enable_streaming=False,
            temperature=0.7
        )
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """构建 Graph"""
        graph = StateGraph(ChatState)
        
        # 添加节点
        graph.add_node("chat", self._chat_node)
        
        # 添加边
        graph.add_edge(START, "chat")
        graph.add_edge("chat", END)
        
        # 编译时传入 checkpointer！这是关键
        return graph.compile(checkpointer=self.checkpointer)
    
    async def _chat_node(self, state: ChatState) -> dict:
        """
        聊天节点
        
        关键点：
        1. state["messages"] 包含了所有历史消息（由 checkpointer 自动恢复）
        2. 我们把整个历史传给 LLM
        3. 返回新消息，会自动追加到 messages 列表
        """
        # 打印当前的消息历史（调试用）
        print("\n" + "="*50)
        print("📜 当前消息历史：")
        for i, msg in enumerate(state["messages"]):
            role = "👤 用户" if isinstance(msg, HumanMessage) else "🤖 AI"
            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"  {i+1}. {role}: {content}")
        print("="*50)
        
        # 调用 LLM，传入完整的消息历史
        response = await self.llm.ainvoke(state["messages"])
        print("返回到类型",type(response))
        # 返回新的 AI 消息，会自动追加到 messages
        return {"messages": [response]}
    
    async def chat(self, user_input: str, thread_id: str) -> str:
        """
        发送消息并获取回复
        
        Args:
            user_input: 用户输入
            thread_id: 会话ID，相同的 thread_id 会共享上下文
        
        Returns:
            AI 的回复内容
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        # 调用 Graph
        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config
        )
        
        # 返回最后一条消息（AI 的回复）
        return result["messages"][-1].content


# ============================================
# 第三步：演示多轮对话
# ============================================
async def demo_memory_mode():
    """
    演示：内存模式（程序结束后会话丢失）
    """
    print("\n" + "🔷"*30)
    print("演示 1：内存模式 (InMemorySaver)")
    print("🔷"*30)
    
    # 使用内存存储
    checkpointer = InMemorySaver()
    chat = SimpleChatGraph(checkpointer=checkpointer)
    
    # 第一轮对话
    print("\n📤 用户: 你好，我叫小明")
    response = await chat.chat("你好，我叫小明", thread_id="session_1")
    print(f"📥 AI: {response}")
    
    # 第二轮对话 - 测试是否记住了名字
    print("\n📤 用户: 你还记得我叫什么吗？")
    response = await chat.chat("你还记得我叫什么吗？", thread_id="session_1")
    print(f"📥 AI: {response}")
    
    # 第三轮对话 - 继续测试上下文
    print("\n📤 用户: 帮我总结一下我们刚才聊了什么")
    response = await chat.chat("帮我总结一下我们刚才聊了什么", thread_id="session_1")
    print(f"📥 AI: {response}")
    
    print("\n" + "-"*50)
    print("✅ 可以看到，AI 记住了之前的对话内容！")
    print("   这是因为 messages 列表在每轮对话中不断累积")
    print("-"*50)


async def demo_different_threads():
    """
    演示：不同 thread_id 有独立的上下文
    """
    print("\n" + "🔶"*30)
    print("演示 2：不同 thread_id 的隔离性")
    print("🔶"*30)
    
    checkpointer = InMemorySaver()
    chat = SimpleChatGraph(checkpointer=checkpointer)
    
    # 会话 A
    print("\n--- 会话 A (thread_id='user_A') ---")
    print("📤 用户A: 我喜欢吃苹果")
    response = await chat.chat("我喜欢吃苹果", thread_id="user_A")
    print(f"📥 AI: {response}")
    
    # 会话 B - 不同的 thread_id
    print("\n--- 会话 B (thread_id='user_B') ---")
    print("📤 用户B: 我喜欢什么水果？")
    response = await chat.chat("我喜欢什么水果？", thread_id="user_B")
    print(f"📥 AI: {response}")
    
    # 回到会话 A
    print("\n--- 回到会话 A (thread_id='user_A') ---")
    print("📤 用户A: 我喜欢什么水果？")
    response = await chat.chat("我喜欢什么水果？", thread_id="user_A")
    print(f"📥 AI: {response}")
    
    print("\n" + "-"*50)
    print("✅ 用户B 的会话不知道用户A 说过什么")
    print("   但用户A 的会话能记住自己说过的话")
    print("   这就是 thread_id 的隔离作用！")
    print("-"*50)


async def demo_sqlite_persistence():
    """
    演示：SQLite 持久化存储
    """
    print("\n" + "🔷"*30)
    print("演示 3：SQLite 持久化存储")
    print("🔷"*30)
    
    db_path = "demo_chat_history.db"
    
    # 第一次运行：创建会话
    print("\n--- 第一次运行 ---")
    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        chat = SimpleChatGraph(checkpointer=checkpointer)
        
        print("📤 用户: 请记住这个数字：42")
        response = await chat.chat("请记住这个数字：42", thread_id="persistent_session")
        print(f"📥 AI: {response}")
    
    # 模拟"程序重启"后，重新连接
    print("\n--- 模拟程序重启，重新连接数据库 ---")
    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        chat = SimpleChatGraph(checkpointer=checkpointer)
        
        print("📤 用户: 我让你记住的数字是多少？")
        response = await chat.chat("我让你记住的数字是多少？", thread_id="persistent_session")
        print(f"📥 AI: {response}")
    
    print("\n" + "-"*50)
    print("✅ 即使'重启'后，AI 仍然记得之前的对话")
    print("   因为 State 被保存到了 SQLite 数据库")
    print("-"*50)
    
    # 清理演示文件
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🧹 已清理演示数据库: {db_path}")


# ============================================
# 主函数
# ============================================
async def main():
    print("="*60)
    print("LangGraph 上下文管理原理演示")
    print("="*60)
    print("""
核心原理总结：
┌─────────────────────────────────────────────────────────┐
│ 1. State 定义：                                          │
│    messages: Annotated[list[Message], operator.add]     │
│    → operator.add 让新消息追加而不是覆盖                  │
│                                                         │
│ 2. Graph 编译：                                          │
│    graph.compile(checkpointer=checkpointer)             │
│    → checkpointer 自动保存/恢复整个 State                │
│                                                         │
│ 3. 调用时指定 thread_id：                                │
│    config={"configurable": {"thread_id": "xxx"}}        │
│    → 相同 thread_id 共享上下文，不同 thread_id 隔离      │
└─────────────────────────────────────────────────────────┘
    """)
    
    # 运行演示
    await demo_memory_mode()
    # await demo_different_threads()
    # await demo_sqlite_persistence()
    
    print("\n" + "="*60)
    print("演示完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
