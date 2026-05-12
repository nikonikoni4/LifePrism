---
name: mood-summary-design
description: agent_schedule_job.py 中 update_memory 函数的心情数据获取和总结功能设计
type: feature
date: 2026-05-12
---

# 心情数据获取和总结功能设计

## 背景

在 `lifeprism/llm/function/agent_schedule_job.py` 的 `update_memory` 函数中，需要完成心情数据的获取和总结部分，作为用户记忆更新流程的一部分。

## 目标

实现心情数据的获取、格式化和客观总结，为后续的记忆更新提供结构化的心情分析数据。

## 设计方案

### 1. 架构概览

```
update_memory()
    ├── get_mood_data()          # 获取心情数据
    └── summary_moods()          # 总结心情数据
```

### 2. 数据获取层

**函数签名：**
```python
def get_mood_data(start_time: str, end_time: str) -> str
```

**职责：**
- 将时间格式从 `YYYY-MM-DD HH:MM:SS` 转换为 `YYYY-MM-DD`
- 调用 `query_user_mood(start_date, end_date)` 获取心情数据
- 返回格式化的心情数据字符串

**实现细节：**
- 使用 `datetime.strptime` 解析时间字符串
- 提取日期部分（`YYYY-MM-DD`）
- 调用现有的 `query_user_mood` 函数（已在 `lifeprismsystem.py` 中实现）
- 该函数已返回格式化字符串，无需额外处理

**数据格式示例：**
```
1. 2026-05-12 09:30:00 心情: 7分
   内容：早上工作状态不错
   影响因素: 睡眠充足, 天气晴朗

2. 2026-05-12 15:45:00 心情: 4分
   内容：下午遇到了技术难题
   影响因素: 工作压力
```

### 3. 总结层

**函数签名：**
```python
async def summary_moods(mood_data: str) -> str
```

**职责：**
- 接收心情数据字符串
- 通过 LLM 进行客观总结
- 返回总结结果

**实现细节：**
- 使用 `bus.send` 发送 `InboundMessage`，类型为 `MessageType.DREAM_TASK`
- 将心情数据作为 `content` 参数传递
- 使用专门的 `system_prompt` 指导 LLM 进行客观总结
- 处理异常情况（无数据、LLM 返回错误等）

**错误处理：**
- 如果 `mood_data` 为空或表示无数据，返回 "无心情记录"
- 如果 LLM 返回错误，记录日志并抛出 `ExternalServiceError`

### 4. System Prompt 设计

```python
MOOD_SUMMARY_SYSTEM_PROMPT = """## 任务
你需要对用户的心情记录进行客观总结。

## 数据说明
每条心情记录包含：
1. 时间：心情记录的时间
2. 心情分数：用户的心情评分（1-10分）
3. 内容：用户对心情的描述
4. 影响因素：导致该心情的因素

## 总结要求
对每条心情记录，按以下结构进行客观描述（有则写，无则跳过）：
1. 事件经过：简单描述发生了什么
2. 情绪诱因：是什么让这个情绪发生的
3. 情绪本身：用户的情绪状态是什么
4. 用户反应：面对这个情绪，用户的反应是什么

## 核心原则
1. 不要推敲或猜测
2. 仅从客观角度描述，不带任何评价
3. 如果某个组成部分数据中没有，就不写
4. 保持简洁，每条心情总结控制在 100 字以内
"""
```

### 5. 集成到 update_memory

在 `update_memory` 函数中的集成位置（第 77 行之后）：

```python
# 获取心情数据，并总结
mood_data = get_mood_data(start_time, end_time)
mood_summary_content = await summary_moods(mood_data)
```

## 技术细节

### 依赖关系

- `query_user_mood`：已存在于 `lifeprism/llm/agent/tools/lifeprismsystem.py`
- `bus.send`：已在文件中使用
- `InboundMessage`, `MessageType`：已导入
- `ExternalServiceError`：已导入

### 时间处理

- 输入格式：`YYYY-MM-DD HH:MM:SS`（如 `2026-05-12 04:00:00`）
- 转换为：`YYYY-MM-DD`（如 `2026-05-12`）
- 使用 `datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')`

### 异步处理

- `summary_moods` 必须是异步函数（使用 `async def`）
- 因为需要调用 `await bus.send()`
- 在 `update_memory` 中使用 `await summary_moods()`

## 输出示例

**输入数据：**
```
1. 2026-05-12 09:30:00 心情: 7分
   内容：早上工作状态不错，完成了两个功能模块
   影响因素: 睡眠充足, 天气晴朗

2. 2026-05-12 15:45:00 心情: 4分
   内容：下午遇到了技术难题，调试了很久
   影响因素: 工作压力
```

**期望输出：**
```
1. 早上 9:30 心情记录
   - 事件经过：用户完成了两个功能模块
   - 情绪诱因：睡眠充足和天气晴朗
   - 情绪本身：工作状态不错，心情评分 7 分
   - 用户反应：（数据中未提及）

2. 下午 15:45 心情记录
   - 事件经过：遇到技术难题，调试了很久
   - 情绪诱因：工作压力
   - 情绪本身：心情评分 4 分
   - 用户反应：（数据中未提及）
```

## 实现清单

1. ✅ 设计数据获取函数 `get_mood_data`
2. ✅ 设计总结函数 `summary_moods`
3. ✅ 编写 system prompt
4. ✅ 确定集成位置
5. ⬜ 实现 `get_mood_data` 函数
6. ⬜ 实现 `summary_moods` 函数
7. ⬜ 在 `update_memory` 中集成调用
8. ⬜ 测试功能

## 注意事项

1. **时间范围一致性**：确保 `get_mood_data` 的时间范围与 `update_memory` 的其他数据获取保持一致（date 04:00:00 ~ date+1 04:00:00）
2. **空数据处理**：如果当天没有心情记录，应返回友好提示而不是报错
3. **LLM 调用失败**：需要适当的错误处理和日志记录
4. **总结质量**：通过 system prompt 确保总结保持客观、简洁
5. **性能考虑**：单次批量总结，避免多次 LLM 调用
