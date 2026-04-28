# LLM Channel 到 MessageBus 职责迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Channel 类的消息流转职责迁移到 MessageQueue，实现职责分离

**Architecture:** 将 Channel 的所有方法（send、_receive_loop、限流、统计）直接移动到 MessageQueue 类，Channel 保留为空类，所有调用方改为使用 bus 单例

**Tech Stack:** Python asyncio, LazySingleton

---

## File Structure

**Modified Files:**
- `lifeprism/llm/bus/queue.py` - 添加 Channel 的所有方法
- `lifeprism/llm/channel/manager.py` - 清空 Channel 类
- `lifeprism/llm/channel/__init__.py` - 移除 channel_manager 导出
- `lifeprism/llm/chat/chat_bot.py` - 改用 bus
- `lifeprism/llm/function/screenshot_analysis.py` - 改用 bus
- `lifeprism/llm/classify/classify_simple.py` - 改用 bus
- `lifeprism/llm/classify/classify_graph.py` - 改用 bus
- `lifeprism/llm/function/diary_summary.py` - 改用 bus

---

### Task 1: 迁移 Channel 方法到 MessageQueue

**Files:**
- Modify: `lifeprism/llm/bus/queue.py`

- [ ] **Step 1: 添加导入和常量**

在 `lifeprism/llm/bus/queue.py` 文件顶部添加：

```python
import asyncio
import time
from typing import Any
from collections import deque
from lifeprism.llm.bus.events import InboundMessage, OutboundMessage
from lifeprism.utils.lazy_singleton import LazySingleton
from lifeprism.utils.logger import get_logger, INFO

logger = get_logger(__name__)
logger.setLevel(INFO)

TIMEOUT_MAX = 600.0
RATE_LIMIT = 100
RATE_WINDOW = 60.0
```

- [ ] **Step 2: 添加 MessageQueue 初始化属性**

在 `MessageQueue.__init__` 方法中添加新属性：

```python
def __init__(self):
    self._inbound = None
    self._outbound = None
    self._pending: dict[str, asyncio.Future] = {}
    self.stop_receive = False
    self._receive_task: asyncio.Task | None = None
    self._rate_timestamps: deque[float] = deque()
```

- [ ] **Step 3: 添加 _ensure_receive_task 方法**

在 `MessageQueue` 类中添加：

```python
def _ensure_receive_task(self):
    """懒启动接收循环，确保在事件循环中调用"""
    if self._receive_task is None or self._receive_task.done():
        self._receive_task = asyncio.create_task(self._receive_loop())
```

- [ ] **Step 4: 添加 close 方法**

```python
async def close(self):
    """停止接收循环，释放资源"""
    if self._receive_task is None:
        return
    self._receive_task.cancel()
    try:
        await self._receive_task
    except asyncio.CancelledError:
        pass
    self._receive_task = None
```

- [ ] **Step 5: 添加 _wait_for_rate_limit 方法**

```python
async def _wait_for_rate_limit(self):
    """滑动窗口限速：确保每分钟请求数不超过 RATE_LIMIT"""
    while True:
        now = time.monotonic()
        # 清除窗口外的旧记录
        while self._rate_timestamps and now - self._rate_timestamps[0] >= RATE_WINDOW:
            self._rate_timestamps.popleft()
        if len(self._rate_timestamps) < RATE_LIMIT:
            self._rate_timestamps.append(now)
            return
        # 等到最早的请求滑出窗口
        wait = RATE_WINDOW - (now - self._rate_timestamps[0])
        logger.debug(f"[MessageQueue] 限速等待 {wait:.2f}s")
        await asyncio.sleep(wait)
```

- [ ] **Step 6: 添加 send 方法**

```python
async def send(self, content: str, session_id: str | None = None,
               type: str = "chat", extra: dict | None = None) -> str:
    """发送消息并等待结果
    args:
        content: 消息内容
        session_id: 会话ID
        type: 消息类型
        extra: 额外信息
    return:
        消息回复内容
    """
    self._ensure_receive_task()
    await self._wait_for_rate_limit()
    # 1. 创建消息
    msg = InboundMessage(type=type, content=content, session_id=session_id, extra=extra)
    logger.debug(f"[MessageQueue] 发送 id={msg.id} content={content!r}")

    # 2. 创建future，并入pending
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    self._pending[msg.id] = future

    # 3. 发送消息
    await self.publish_inbound(msg)

    # 4. 等待对应future回复（600s 超时，防止 agent 异常时永久挂起）
    result: OutboundMessage = await asyncio.wait_for(self._pending[msg.id], timeout=TIMEOUT_MAX)
    logger.debug(f"[MessageQueue] 收到回复: {result.response!r}")

    # 5. 异步保存统计信息 (不阻塞消息返回)
    if result.response and result.response.usage:
        try:
            from lifeprism.llm.providers.dataset_providers import llm_dataset_provider
            asyncio.create_task(asyncio.to_thread(
                llm_dataset_provider.save_usage,
                session_id=result.session_id,
                usage=result.response.usage,
                mode=msg.type
            ))
        except Exception as e:
            logger.error(f"[MessageQueue] 保存 token 使用情况失败: {e}")

    response = result.response
    if hasattr(response, 'content'):
        return response.content
    return response
```

- [ ] **Step 7: 添加 _receive_loop 方法**

```python
async def _receive_loop(self):
    while True:
        msg = await self.consume_outbound()
        future = self._pending.pop(msg.id, None) 
        if future:
            future.set_result(msg)
```

- [ ] **Step 8: 验证修改**

检查 `lifeprism/llm/bus/queue.py` 文件，确保所有方法已添加且格式正确。

---

### Task 2: 清空 Channel 类

**Files:**
- Modify: `lifeprism/llm/channel/manager.py`

- [ ] **Step 1: 替换 Channel 类为空类**

将 `lifeprism/llm/channel/manager.py` 的内容替换为：

```python
"""消息收发接口 - 已迁移到 MessageQueue"""

# TODO: 未来用于外部通道接入（微信、QQ 等）
class Channel:
    pass
```

- [ ] **Step 2: 删除 channel_manager 单例**

确认文件中已删除 `channel_manager = LazySingleton(Channel, bus=bus)` 这行。

- [ ] **Step 3: 验证修改**

检查文件内容，确保只保留空的 Channel 类和 TODO 注释。

---

### Task 3: 更新 channel/__init__.py

**Files:**
- Modify: `lifeprism/llm/channel/__init__.py`

- [ ] **Step 1: 清空导出**

将 `lifeprism/llm/channel/__init__.py` 的内容替换为：

```python
# Channel 模块已重构，消息流转功能已迁移到 bus
# 未来用于外部通道接入（微信、QQ 等）

__all__ = []
```

- [ ] **Step 2: 验证修改**

检查文件内容，确保不再导出 channel_manager。

---

### Task 4: 更新 chat_bot.py

**Files:**
- Modify: `lifeprism/llm/chat/chat_bot.py`

- [ ] **Step 1: 修改导入语句**

将第 3 行：
```python
from lifeprism.llm.channel.manager import channel_manager, Channel
```

改为：
```python
from lifeprism.llm.bus import bus
```

- [ ] **Step 2: 修改 __init__ 方法**

将第 13 行：
```python
self._channel_manager: Channel = channel_manager
```

改为：
```python
self._bus = bus
```

- [ ] **Step 3: 修改 chat 方法中的调用**

将第 24 行：
```python
response_data = await self._channel_manager.send(
```

改为：
```python
response_data = await self._bus.send(
```

- [ ] **Step 4: 验证修改**

检查文件，确保所有 channel_manager 引用已替换为 bus。

---

### Task 5: 更新 screenshot_analysis.py

**Files:**
- Modify: `lifeprism/llm/function/screenshot_analysis.py`

- [ ] **Step 1: 修改导入语句**

将第 19 行：
```python
from lifeprism.llm.channel.manager import channel_manager
```

改为：
```python
from lifeprism.llm.bus import bus
```

- [ ] **Step 2: 查找并替换所有 channel_manager.send 调用**

在文件中搜索所有 `channel_manager.send`，替换为 `bus.send`。

- [ ] **Step 3: 验证修改**

使用 grep 确认没有遗漏：
```bash
grep -n "channel_manager" lifeprism/llm/function/screenshot_analysis.py
```

预期：无输出

---

### Task 6: 更新 classify_simple.py

**Files:**
- Modify: `lifeprism/llm/classify/classify_simple.py`

- [ ] **Step 1: 修改导入语句**

将第 15 行：
```python
from lifeprism.llm.channel.manager import channel_manager
```

改为：
```python
from lifeprism.llm.bus import bus
```

- [ ] **Step 2: 修改 _classify_batch 方法中的调用**

将第 41 行：
```python
raw = await channel_manager.send(
```

改为：
```python
raw = await bus.send(
```

- [ ] **Step 3: 验证修改**

使用 grep 确认：
```bash
grep -n "channel_manager" lifeprism/llm/classify/classify_simple.py
```

预期：无输出

---

### Task 7: 更新 classify_graph.py

**Files:**
- Modify: `lifeprism/llm/classify/classify_graph.py`

- [ ] **Step 1: 查找 channel_manager 导入**

```bash
grep -n "from lifeprism.llm.channel" lifeprism/llm/classify/classify_graph.py
```

- [ ] **Step 2: 修改导入语句**

将导入语句改为：
```python
from lifeprism.llm.bus import bus
```

- [ ] **Step 3: 替换所有 channel_manager 调用**

将所有 `channel_manager.send` 替换为 `bus.send`。

- [ ] **Step 4: 验证修改**

```bash
grep -n "channel_manager" lifeprism/llm/classify/classify_graph.py
```

预期：无输出

---

### Task 8: 更新 diary_summary.py

**Files:**
- Modify: `lifeprism/llm/function/diary_summary.py`

- [ ] **Step 1: 查找 channel_manager 导入**

```bash
grep -n "from lifeprism.llm.channel" lifeprism/llm/function/diary_summary.py
```

- [ ] **Step 2: 修改导入语句**

将导入语句改为：
```python
from lifeprism.llm.bus import bus
```

- [ ] **Step 3: 替换所有 channel_manager 调用**

将所有 `channel_manager.send` 替换为 `bus.send`。

- [ ] **Step 4: 验证修改**

```bash
grep -n "channel_manager" lifeprism/llm/function/diary_summary.py
```

预期：无输出

---

### Task 9: 全局验证

**Files:**
- All modified files

- [ ] **Step 1: 全局搜索 channel_manager 引用**

```bash
grep -r "channel_manager" lifeprism/llm/ --include="*.py"
```

预期：只在 `lifeprism/llm/channel/manager.py` 的注释中出现（如果有的话）

- [ ] **Step 2: 检查导入是否正确**

```bash
grep -r "from lifeprism.llm.channel.manager import" lifeprism/ --include="*.py"
```

预期：无输出

- [ ] **Step 3: 检查 bus 导入**

```bash
grep -r "from lifeprism.llm.bus import bus" lifeprism/llm/ --include="*.py"
```

预期：显示所有修改过的文件

---

### Task 10: 提交代码

**Files:**
- All modified files

- [ ] **Step 1: 查看修改状态**

```bash
git status
```

预期：显示所有修改的文件

- [ ] **Step 2: 添加所有修改**

```bash
git add lifeprism/llm/bus/queue.py \
        lifeprism/llm/channel/manager.py \
        lifeprism/llm/channel/__init__.py \
        lifeprism/llm/chat/chat_bot.py \
        lifeprism/llm/function/screenshot_analysis.py \
        lifeprism/llm/classify/classify_simple.py \
        lifeprism/llm/classify/classify_graph.py \
        lifeprism/llm/function/diary_summary.py
```

- [ ] **Step 3: 提交修改**

```bash
git commit -m "refactor: 将 Channel 职责迁移到 MessageQueue

- 将 Channel 的所有方法（send、_receive_loop、限流、统计）迁移到 MessageQueue
- Channel 保留为空类，未来用于外部通道接入
- 所有调用方改为使用 bus 单例

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: 验证提交**

```bash
git log -1 --stat
```

预期：显示提交信息和修改的文件列表

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ 将 Channel 的所有方法迁移到 MessageQueue (Task 1)
- ✅ Channel 保留为空类 (Task 2)
- ✅ 更新所有调用方 (Tasks 4-8)
- ✅ 全局验证 (Task 9)

**Placeholder Scan:**
- ✅ 无 TBD/TODO
- ✅ 所有代码块完整
- ✅ 所有命令具体

**Type Consistency:**
- ✅ MessageQueue.send() 签名一致
- ✅ bus 单例使用一致
- ✅ 导入语句一致
