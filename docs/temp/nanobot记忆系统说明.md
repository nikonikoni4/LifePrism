# NanoBot 记忆机制详解

本文档详细说明 NanoBot 的记忆系统设计，包括聊天压缩、跨会话记忆和长期记忆三个核心机制。

## 概述

NanoBot 的记忆系统分为三个层次：

1. **聊天压缩**：解决单个 session 内 token 超限问题
2. **跨会话记忆**：将压缩的对话事实存储为中间格式
3. **长期记忆**：从跨会话记忆中提取持久化知识

```
┌─────────────────────────────────────────────────────────────┐
│                      长期记忆层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  SOUL.md    │  │  USER.md    │  │  MEMORY.md  │         │
│  │  (AI角色)   │  │  (用户偏好) │  │  (项目事实) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Dream 定时整合
                              │
┌─────────────────────────────────────────────────────────────┐
│                    跨会话记忆层                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              memory/history.jsonl                    │   │
│  │  {"cursor":1,"timestamp":"...","content":"..."}     │   │
│  │  {"cursor":2,"timestamp":"...","content":"..."}     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Token Consolidation / Auto-Compact
                              │
┌─────────────────────────────────────────────────────────────┐
│                     聊天压缩层                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              sessions/{key}.jsonl                    │   │
│  │  {"_type":"metadata","last_consolidated":5,...}     │   │
│  │  {"role":"user","content":"消息1"}                   │   │
│  │  {"role":"assistant","content":"回复1"}              │   │
│  │  ...                                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 一、聊天压缩机制

### 1.1 Token Consolidation（Token 超限压缩）

**触发条件**：当 session 的 token 数超过 `context_window_tokens` 限制时

**工作流程**：

```
1. 估算当前 session 的 token 数
2. 如果超过限制，找到需要压缩的消息范围（从 last_consolidated 到某个边界）
3. 将这些消息发送给 LLM 进行总结
4. 总结后的内容写入 history.jsonl
5. 推进 last_consolidated 游标（不删除 session 中的原消息）
```

**关键特点**：
- **不删除 session 消息**：所有消息都保留在 session JSONL 文件中
- **逻辑跳过**：通过 `last_consolidated` 游标标记哪些消息已被压缩
- **写入 history.jsonl**：压缩后的摘要存储在跨会话记忆文件中

**代码位置**：`nanobot/agent/memory.py` - `Consolidator.maybe_consolidate_by_tokens()`

### 1.2 Auto-Compact（空闲 Session 压缩）

**触发条件**：当 session 空闲时间超过 `session_ttl_minutes` 配置时

**工作流程**：

```
1. 定期检查所有 session 的更新时间
2. 找到空闲超时的 session
3. 将旧消息（保留最近 8 条）发送给 LLM 进行总结
4. 总结后的内容写入 history.jsonl
5. 删除 session 中的旧消息（只保留最近 8 条）
6. 重置 last_consolidated 游标为 0
```

**关键特点**：
- **删除 session 消息**：只保留最近 8 条消息
- **写入 history.jsonl**：压缩后的摘要存储在跨会话记忆文件中
- **摘要注入**：将摘要存入 session.metadata，下次对话时注入

**代码位置**：`nanobot/agent/autocompact.py`

### 1.3 压缩时的 Prompt 设计

**System Message**（`templates/agent/consolidator_archive.md`）：

```
Extract key facts from this conversation. Only output items matching these categories:
- User facts: personal info, preferences, stated opinions, habits
- Decisions: choices made, conclusions reached
- Solutions: working approaches discovered through trial and error
- Events: plans, deadlines, notable occurrences
- Preferences: communication style, tool preferences

Priority: user corrections and preferences > solutions > decisions > events
Skip: code patterns derivable from source, git history, or anything already captured in existing memory
Output as concise bullet points, one fact per line.
```

**User Message**：格式化的消息文本

```
[2025-05-10 14:30] USER: 我想用Python写一个爬虫
[2025-05-10 14:31] ASSISTANT [tools: web_search, exec]: 好的，我来帮你...
[2025-05-10 14:35] USER: 用requests库比较好
[2025-05-10 14:36] ASSISTANT: 好的，使用requests库...
```

**设计局限**：
- 只包含需要压缩的消息，不提供之前已压缩的消息作为上下文
- 可能导致重复摘要（同样的事实被多次提取）

## 二、跨会话记忆（history.jsonl）

### 2.1 文件结构

**位置**：`workspace/memory/history.jsonl`

**格式**：JSONL（每行一个 JSON 对象）

```json
{"cursor": 1, "timestamp": "2025-05-10 14:30", "content": "• 用户偏好使用 Python 3.11\n• 解决了连接超时问题"}
{"cursor": 2, "timestamp": "2025-05-10 15:00", "content": "• 决定使用 requests 库\n• 计划实现爬虫功能"}
```

### 2.2 设计特点

**不保存 session 信息**：
- 没有 `session_id` 字段
- 一个 session 可以产生多条 history.jsonl 记录
- 所有 session 的压缩摘要混在一起

**设计意图**：
- 以对话事实为基础，而不是 session
- 让最新的聊天对话更新，不受旧消息时效性影响
- session 只是 LLM 无记忆的局限产物

**优点**：
- 最新 compact 的摘要更准确反映当前状态
- 不受旧消息时效性影响（过时的偏好、已解决的问题）

**缺点**：
- 缺乏上下文（不知道摘要来自哪个 session）
- 可能产生重复摘要

### 2.3 Cursor 机制

**写入游标**（`.cursor`）：
- 记录 history.jsonl 的最大 cursor 值
- 用于 `append_history()` 生成自增 cursor

**消费游标**（`.dream_cursor`）：
- 记录 Dream 已处理的最大 cursor 值
- 用于 `read_unprocessed_history()` 返回未处理的条目

## 三、长期记忆（Dream 机制）

### 3.1 触发条件

- **定时任务**：由 cron 定时任务调度（默认每 2 小时）
- **手动触发**：用户可以通过 `/dream` 命令手动触发

### 3.2 工作流程

```
1. 读取 history.jsonl 中未处理的条目（最多 1000 条）
2. 读取当前的 MEMORY.md、SOUL.md、USER.md
3. Phase 1（分析）：调用 LLM 分析 history 条目和现有记忆文件
4. Phase 2（编辑）：委托给 AgentRunner，使用 edit_file 工具增量编辑记忆文件
5. 更新 .dream_cursor 游标
6. 裁剪 history.jsonl（保留最近 1000 条）
```

### 3.3 记忆文件分类

**SOUL.md**（AI 角色记忆）：
- AI 的长期语音和沟通风格
- 行为模式、人格特征

**USER.md**（用户偏好记忆）：
- 用户的个人信息、偏好
- 沟通风格、工具偏好

**MEMORY.md**（项目事实记忆）：
- 项目相关的事实、决策
- 解决方案、工作进展

### 3.4 增量编辑机制

Dream 使用 `edit_file` 工具进行精确编辑，不是全量重写：

**编辑规则**（`templates/agent/dream_phase2.md`）：
```
- Edit directly — file contents provided below, no read_file needed
- Use exact text as old_text, include surrounding blank lines for unique match
- Batch changes to the same file into one edit_file call
- Surgical edits only — never rewrite entire files
- If nothing to update, stop without calling tools
```

**编辑类型**：
- `[FILE]`：添加内容到指定文件
- `[FILE-REMOVE]`：从文件中删除指定内容
- `[SKILL]`：创建新的 skill 文件

### 3.5 删除机制

**history.jsonl 裁剪**：
- `compact_history()` 裁剪 history.jsonl，只保留最近 1000 条
- 删除最旧的条目，不区分是否已处理

**潜在问题**：
- 如果 Dream 处理速度慢，可能在裁剪时删除未处理的条目

## 四、Microcompact（运行时压缩）

### 4.1 触发条件

每次 LLM 请求之前，对发送给模型的消息列表做运行时压缩。

### 4.2 压缩规则

- **目标工具**：`read_file`、`exec`、`grep`、`glob`、`web_search`、`web_fetch`、`list_dir`
- **保留最近 10 个工具结果完整**
- **超过 500 字符的旧工具结果**：替换为 `[read_file result omitted from context]` 之类的单行摘要

### 4.3 关键特点

- **纯内存操作**：不修改持久化的 session 数据
- **不触及磁盘文件**：只影响发送给 LLM 的上下文

**代码位置**：`nanobot/agent/runner.py`

## 五、文件结构总结

```
workspace/
├── sessions/
│   └── {channel}_{chat_id}.jsonl    # session 内消息（原始对话）
│       ├── {"_type":"metadata", "key":"telegram:123", "last_consolidated":5, ...}
│       ├── {"role":"user", "content":"消息1"}
│       ├── {"role":"assistant", "content":"回复1"}
│       └── ...
├── memory/
│   ├── history.jsonl                # 跨会话记忆（压缩摘要）
│   │   ├── {"cursor":1, "timestamp":"...", "content":"..."}
│   │   └── ...
│   ├── MEMORY.md                    # 长期记忆（项目事实）
│   ├── .cursor                      # Consolidator 写入游标
│   ├── .dream_cursor                # Dream 消费游标
│   └── .git/                        # 版本控制（用于记忆回溯）
├── SOUL.md                          # AI 角色记忆
└── USER.md                          # 用户偏好记忆
```

## 六、配置说明

### 6.1 Token Consolidation 配置

```json
{
  "contextWindowTokens": 128000,
  "consolidationRatio": 0.8
}
```

### 6.2 Auto-Compact 配置

```json
{
  "sessionTtlMinutes": 30
}
```

### 6.3 Dream 配置

```json
{
  "agents": {
    "defaults": {
      "dream": {
        "intervalH": 2,
        "modelOverride": null,
        "maxBatchSize": 20,
        "maxIterations": 10
      }
    }
  }
}
```

| 字段 | 含义 |
|------|------|
| `intervalH` | Dream 运行间隔（小时） |
| `modelOverride` | Dream 专用模型覆盖（null 表示使用主 agent 模型） |
| `maxBatchSize` | 每次运行处理的 history 条目数 |
| `maxIterations` | Dream 编辑阶段的工具调用预算 |

## 七、与其他 Agent 的记忆机制对比

### 7.1 Claude Code 的记忆机制

**压缩方式**：
- 将压缩后的内容写入**原 session JSONL 文件**
- 使用 **`user` role** 作为压缩消息的角色

**设计考量**：
- Claude Code 是编程 Agent，专注于代码开发任务
- 不需要提取用户 fact、decision 等内容
- 压缩的目的是为了在对话中更好地进行 coding 工作

## 八、设计哲学

### 8.1 分层记忆

不同类型的记忆使用不同的工具：
- **session.messages**：短期对话（LLM 上下文）
- **history.jsonl**：中期归档（压缩摘要）
- **SOUL.md/USER.md/MEMORY.md**：长期知识（持久化事实）

### 8.2 事实优先

以对话事实为基础，而不是 session：
- session 只是 LLM 无记忆的局限产物
- 最新的 compact 摘要更准确反映当前状态
- 不受旧消息时效性影响

### 8.3 可审计性

- Git 版本控制记录记忆文件的变更历史
- 用户可以通过 `/dream-restore` 命令回溯记忆状态
- 自动记忆是强大的，但用户始终保留检查和恢复的权利
