# AsyncSqliteSaver 会话持久化集成指南

**日期**: 2025-12-25  
**作者**: AI Assistant

---

## 📋 概述

本文档记录了在 LifeWatch-AI 项目中集成 `AsyncSqliteSaver` 实现聊天会话持久化存储时遇到的问题及其解决方案。

---

## 🎯 目标

将 `ChatBot` 类的会话存储从 `InMemorySaver`（内存存储，重启丢失）改为 `AsyncSqliteSaver`（SQLite 持久化存储）。

---

## ❌ 遇到的问题

### 问题 1：`is_alive` 属性错误

**错误信息**：
```
AttributeError: 'Connection' object has no attribute 'is_alive'
```

**发生位置**：
```
File "langgraph\checkpoint\sqlite\aio.py", line 284, in setup
    if not self.conn.is_alive():
```

**原因分析**：

这是 `aiosqlite` 库的 **破坏性变更** 导致的兼容性问题：

| aiosqlite 版本 | Connection 类继承 | 是否有 `is_alive` |
|---------------|------------------|------------------|
| < 0.22.0 | 继承自 `Thread` | ✅ 有 |
| >= 0.22.0 | 不再继承 `Thread` | ❌ 没有 |

`langgraph-checkpoint-sqlite` 3.0.1 的源代码中仍然调用了 `self.conn.is_alive()`，与 `aiosqlite` 0.22.x 不兼容。

**解决方案**：

降级 `aiosqlite` 到兼容版本：
```bash
pip install aiosqlite==0.21.0
```

---

### 问题 2：上下文管理器使用方式

**错误尝试**：
```python
# ❌ 错误：直接调用 from_conn_string 然后手动 setup
checkpointer = AsyncSqliteSaver.from_conn_string(str(db_path))
await checkpointer.setup()  # 这会触发 is_alive 错误
```

**正确用法**：

`AsyncSqliteSaver` **必须** 使用 `async with` 上下文管理器：
```python
# ✅ 正确
async with AsyncSqliteSaver.from_conn_string("chatbot.db") as checkpointer:
    # 在这里使用 checkpointer
    agent = create_agent(model, checkpointer=checkpointer, ...)
```

**原因**：
- 上下文管理器会正确初始化数据库连接
- 退出时会自动关闭连接，避免程序挂起

---

## ✅ 最终解决方案

### 代码结构

使用 `@asynccontextmanager` 包装工厂方法：

```python
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

class ChatBot:
    def __init__(self, checkpointer):
        self.checkpointer = checkpointer
        self.agent = create_agent(self.chat_model, checkpointer=self.checkpointer, ...)
    
    @classmethod
    @asynccontextmanager
    async def create_with_persistence(cls, db_path="chatbot.db"):
        """使用 SQLite 持久化存储的工厂方法"""
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            yield cls(checkpointer)
```

### 使用方式

```python
# 持久化模式
async with ChatBot.create_with_persistence() as chatbot:
    chatbot.set_thread_id("user_session_123")
    async for content in chatbot.chat("你好"):
        print(content)

# 内存模式（可选保留）
chatbot = ChatBot()  # 使用默认的 InMemorySaver
```

---

## 📦 依赖版本

| 包名 | 测试通过版本 | 备注 |
|-----|-------------|------|
| langgraph | 1.0.4 | |
| langgraph-checkpoint-sqlite | 3.0.1 | |
| aiosqlite | **0.21.0** | ⚠️ 不要使用 0.22.x |

### 安装命令

```bash
pip install langgraph langgraph-checkpoint-sqlite aiosqlite==0.21.0
```

---

## 📁 数据存储

- **数据库文件**：`chatbot.db`（项目根目录）
- **表结构**：
  - `checkpoints` - 存储会话检查点
  - `writes` - 存储写入记录

---

## 🧪 验证持久化

可以通过以下方式验证会话是否正确持久化：

1. **第一次对话**：
   ```python
   async with ChatBot.create_with_persistence() as chatbot:
       chatbot.set_thread_id("test_1")
       await chatbot.chat("介绍一下红楼梦")
   ```

2. **重启程序后，使用相同 thread_id**：
   ```python
   async with ChatBot.create_with_persistence() as chatbot:
       chatbot.set_thread_id("test_1")
       await chatbot.chat("作者是谁？")  # 应该能回答"曹雪芹"
   ```

如果模型能正确回答后续问题（基于之前的上下文），说明持久化成功。

---

## 📚 参考资料

- [LangGraph Checkpointing 文档](https://docs.langchain.com/oss/python/langgraph/persistence)
- [AsyncSqliteSaver API 参考](https://reference.langchain.com/python/langgraph/checkpoints/#langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver)
- [aiosqlite 0.22.0 Breaking Change (GitHub Issue)](https://github.com/langchain-ai/langgraph/issues)

---

## 📝 经验总结

1. **版本兼容性很重要**：异步库的 Breaking Change 可能导致难以排查的错误
2. **遵循官方示例**：`AsyncSqliteSaver` 必须使用 `async with` 上下文管理器
3. **测试持久化**：通过多轮对话验证历史记录是否正确保存和恢复
