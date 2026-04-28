# LLM 模块 Channel 到 MessageBus 职责迁移 - 设计文档

## 背景

当前 `lifeprism.llm.channel.manager.Channel` 类承担了消息总线的职责，包括：
- 请求-响应模式管理（_pending Future 字典）
- 限流控制（滑动窗口）
- 接收循环（_receive_loop）
- 发送消息封装（send 方法）

但从语义上看，Channel 应该是"对外通道"（微信、QQ 等外部平台接入），而不是内部消息总线。这导致职责混乱。

## 目标

将消息流转职责从 Channel 迁移到 MessageQueue，实现职责分离：
- **MessageQueue**：负责所有内部消息流转逻辑
- **Channel**：保留为空类，未来用于外部通道接入

## 设计方案

### 方案选择

**方案 1：直接迁移（已选择）**
- 将 Channel 的所有方法直接移动到 MessageQueue
- Channel 类保留为空类（添加 TODO 注释）
- 所有调用方改为 `bus.send()`

优点：
- 最简单直接，改动最小
- 职责清晰：MessageQueue 负责所有消息流转
- 代码集中在一个文件，易于维护

### 架构设计

#### 模块职责

**MessageQueue（bus/queue.py）**
- 管理 inbound/outbound 双向队列
- 实现请求-响应模式（_pending Future 管理）
- 提供 send() 方法（封装消息发送+等待响应）
- 实现接收循环（_receive_loop）
- 限流控制（滑动窗口）
- 统计信息保存（token usage）

**Channel（channel/manager.py）**
- 保留为空类，添加 TODO 注释说明未来用途
- 不再导出 channel_manager 单例

**调用方**
- 从 `from lifeprism.llm.channel.manager import channel_manager` 改为 `from lifeprism.llm.bus import bus`
- 从 `channel_manager.send()` 改为 `bus.send()`

#### 数据流

```
调用方 (chat_bot, screenshot_analysis, etc.)
    ↓
bus.send(content, session_id, type, extra)
    ↓
限流检查 (_wait_for_rate_limit)
    ↓
创建 InboundMessage + Future
    ↓
publish_inbound(msg) → inbound 队列
    ↓
AgentLoop.consume_inbound() 处理
    ↓
AgentLoop.publish_outbound(response) → outbound 队列
    ↓
_receive_loop 匹配 ID 并完成 Future
    ↓
返回响应给调用方
```

### 实现细节

#### MessageQueue 新增方法

1. **send(content, session_id, type, extra) -> str**
   - 限流检查
   - 创建 InboundMessage
   - 创建并注册 Future
   - 发布消息到 inbound 队列
   - 等待 Future 完成（超时 600 秒）
   - 异步保存 token 统计
   - 返回响应内容

2. **_receive_loop()**
   - 无限循环从 outbound 队列取消息
   - 根据消息 ID 匹配 _pending 中的 Future
   - 调用 future.set_result() 完成响应

3. **_wait_for_rate_limit()**
   - 滑动窗口限流（100 次/分钟）
   - 清除窗口外的旧记录
   - 超限时等待最早请求滑出窗口

4. **_ensure_receive_task()**
   - 懒启动接收循环
   - 确保在事件循环中调用

5. **close()**
   - 取消接收循环任务
   - 释放资源

#### Channel 类变更

```python
# TODO: 未来用于外部通道接入（微信、QQ 等）
class Channel:
    pass
```

#### 调用方变更

需要修改的文件：
- `lifeprism/llm/chat/chat_bot.py`
- `lifeprism/llm/function/screenshot_analysis.py`
- `lifeprism/llm/classify/classify_simple.py`
- `lifeprism/llm/classify/classify_graph.py`
- `lifeprism/llm/function/diary_summary.py`

变更内容：
```python
# 变更前
from lifeprism.llm.channel.manager import channel_manager
result = await channel_manager.send(...)

# 变更后
from lifeprism.llm.bus import bus
result = await bus.send(...)
```

### 测试验证

1. **功能测试**
   - 所有调用方正常工作
   - 请求-响应匹配正确（并发场景）
   - 超时机制正常

2. **性能测试**
   - 限流机制正常（100 次/分钟）
   - 并发请求不串消息

3. **资源管理**
   - 接收循环懒启动
   - close() 正常释放资源

## 风险与缓解

**风险 1：并发场景下消息串号**
- 缓解：保持原有 Future 匹配逻辑不变
- 验证：并发测试

**风险 2：调用方遗漏修改**
- 缓解：通过 Grep 搜索所有 channel_manager 引用
- 验证：运行现有测试

**风险 3：接收循环启动时机**
- 缓解：保持懒启动逻辑不变
- 验证：首次调用 send() 时自动启动

## 实施步骤

1. 修改 `bus/queue.py`：将 Channel 的所有方法迁移到 MessageQueue
2. 修改 `channel/manager.py`：保留 Channel 为空类
3. 修改所有调用方：从 channel_manager 改为 bus
4. 运行测试验证
5. 提交代码

## 后续工作

- 实现外部通道接入（微信、QQ 等）
- 优化限流策略（可配置化）
- 增强错误处理和日志
