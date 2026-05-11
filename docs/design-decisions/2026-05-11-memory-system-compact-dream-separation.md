---
version: 1.0
created_at: 2026-05-11
updated_at: 2026-05-11
last_updated: 创建文档初稿
abstract: 将 nanobot 记忆系统的 compact 机制与 dream 记忆提取机制分离，以适配 lifeprism 的短对话情感捕捉场景
status: decided
---

# 记忆系统 Compact 与 Dream 分离设计

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

nanobot 的记忆系统依赖 token compact 触发将内容写入 history.jsonl，这种设计不适合 lifeprism 的短对话情感捕捉场景。对于情感发泄类的短对话，可能在对话结束前既不会触发 token 超限，也不会达到空闲超时条件，导致这些重要的情感记忆永远不会被提取。

### 讨论范围

- compact 机制与记忆提取机制的职责分离
- 游标机制的设计（`last_compact_loc` 与 `last_dream_loc` 的关系）
- Dream 触发时机的设计
- Compact 内容的提取规则和使用方式
- Dream 的输入范围

### 非讨论范围

- 具体的代码实现细节
- 前端 UI 如何展示这些功能
- 数据库 schema 的具体设计
- 性能优化的具体实现

### 模糊信息的明确定义

**Q: Compact 摘要在上下文中的使用方式？**
A: 在构建 LLM 上下文时，用 compact 摘要替代 `last_compact_loc` 之前的原始消息，以减少 token 消耗。

**Q: Dream 的输入范围是否包括 compact 生成的摘要？**
A: 不包括。Dream 只处理原始的 user/assistant 消息，跳过 compact 生成的摘要消息（`compact_msg:true`），避免重复提取。

### 问题深度

这是一个**深层次的架构设计问题**，涉及到：
- 记忆系统的核心架构调整
- 从 nanobot 的"编程工作流"适配到 lifeprism 的"情感捕捉"场景
- 记忆提取的时机、范围、内容的重新设计

## 现状（当前的问题）

### nanobot 的记忆系统设计

nanobot 的记忆系统有两种触发机制：

1. **Token Consolidation**：当 session 的 token 数超过 `context_window_tokens` 限制时触发
2. **Auto-Compact**：当 session 空闲时间超过 `session_ttl_minutes`（默认 30 分钟）时触发

两种机制都会将压缩内容写入 `history.jsonl`，然后由 Dream 定期处理（默认 2 小时一次）。

### 存在的问题

#### 问题 1：短对话记忆丢失

对于情感发泄类的短对话：
- 用户发泄完情绪后立即结束对话
- 如果没超过 token 限制，Token Consolidation 不会触发
- 如果用户在 30 分钟内又开始新对话（新 session），旧 session 可能永远不会达到"空闲 30 分钟"
- **结果**：短对话的记忆可能永远不会被提取

#### 问题 2：场景不匹配

- **nanobot 的场景**：编程工作流，需要大量 token，长对话是常态
- **lifeprism 的场景**：情感捕捉，短对话是常态，需要及时捕捉情绪、思维等内心世界的想法

#### 问题 3：职责混淆

当前设计中，compact 机制同时承担两个职责：
1. **Token 管理**：压缩对话以减少 token 消耗
2. **记忆提取**：将对话内容提取为记忆事实

这两个职责的触发条件和目标不同，不应该耦合在一起。

## 可选方案

### 方案 1：缩短 Auto-Compact 时间

将 `session_ttl_minutes` 从 30 分钟改为 5-10 分钟。

**优势**：
- 实现简单，只需调整配置
- 可以更快地捕捉短对话的记忆

**劣势**：
- 治标不治本，仍然依赖空闲时间
- 如果用户频繁切换话题，仍然可能错过记忆
- 可能导致过于频繁的 compact 操作

### 方案 2：增加"对话结束时记忆提取"

在 session 被标记为结束时（用户主动结束或超时），立即触发记忆提取。

**优势**：
- 及时捕捉短对话记忆
- 不依赖 token 或空闲时间

**劣势**：
- 需要明确"对话结束"的定义
- 可能增加 LLM 调用次数和成本
- 仍然没有解决职责混淆的问题

### 方案 3：Compact 与记忆分离（最终选择）

将 compact 机制与 dream 记忆提取机制完全分离：
- **Compact**：专注于 token 管理，压缩内容写入 session.jsonl
- **Dream**：专注于记忆提取，从 session 中提取记忆写入 history.jsonl

**优势**：
1. **职责清晰**：compact 专注于 token 管理，dream 专注于记忆提取
2. **触发独立**：记忆提取不依赖 token 或空闲时间，可以定期处理所有 session
3. **适配场景**：更适合 lifeprism 的情感捕捉场景
4. **灵活性高**：可以独立调整 compact 和 dream 的触发条件和处理逻辑

**劣势**：
1. **架构复杂度增加**：需要维护两个游标，两套处理逻辑
2. **可能增加 token 消耗**：如果游标独立，dream 可能需要处理更多原始消息
3. **实现成本高**：需要重构现有的记忆系统代码

## 最终决策和决策原因

### 决策：采用方案 3（Compact 与记忆分离）

### 具体设计

#### 1. 架构变化

```
原 nanobot:
  Compact → history.jsonl → Dream → MEMORY.md

新方案:
  Compact → session.jsonl (compact_msg:true)
  Dream → history.jsonl → MEMORY.md
```

#### 2. 游标机制

在 session metadata 中维护两个独立的游标：

```json
{
  "_type": "metadata",
  "key": "telegram:123",
  "last_compact_loc": 15,  // compact 处理到的位置
  "last_dream_loc": 10,    // dream 处理到的位置
  "created_at": "2026-05-11T10:00:00Z",
  "updated_at": "2026-05-11T12:00:00Z"
}
```

**游标关系**：完全独立
- Compact 处理范围：`last_compact_loc` → 当前最新消息
- Dream 处理范围：`last_dream_loc` → 当前最新消息
- 两个游标互不影响

**理由**：
- 虽然可能增加 token 消耗，但职责更清晰
- 避免复杂的游标依赖关系
- 如果后续发现 token 消耗过大，可以再调整为"last_dream_loc 跟随 last_compact_loc"

#### 3. Compact 机制

**触发条件**：保持原有的 nanobot 设计
- Token Consolidation：token 超限时触发
- Auto-Compact：session 空闲超过 `session_ttl_minutes` 时触发

**处理逻辑**：
1. 提取 `last_compact_loc` 到当前的消息
2. 完全保留最后 10 条 user 消息
3. 在此基础上提取：
   - **user fact**：用户的个人信息、偏好、习惯
   - **decision**：用户做出的决策、选择
   - **event**：发生的事件（明确写明事件发生的时间，如果有或能推敲出来；如果没有时间，说明没有提供事件时间）
   - **情绪反应**：如果有，客观记录情绪反应
   - **行为反应链条/模式**：如果有，记录行为模式
4. 将提取的内容作为一条特殊消息写入 session.jsonl：
   ```json
   {
     "role": "user",
     "content": "• 用户偏好使用 Python 3.11\n• 解决了连接超时问题\n• [2026-05-11] 用户表达了对工作的焦虑情绪",
     "compact_msg": true,
     "compact_range": [5, 15],
     "timestamp": "2026-05-11T12:00:00Z"
   }
   ```
5. 更新 `last_compact_loc` 游标

**上下文使用**：
- 在构建 LLM 上下文时，用 compact 摘要替代 `last_compact_loc` 之前的原始消息
- 这样可以大幅减少 token 消耗，同时保留关键信息

#### 4. Dream 机制

**触发条件**：
- 定时任务：每 2 小时执行一次
- 系统启动时：执行一次

**处理逻辑**：
1. 扫描所有 session，找到 `last_dream_loc` 未处理的消息
2. 对于每个 session，提取 `last_dream_loc` 到当前的消息
3. **只处理原始的 user/assistant 消息**，跳过 compact 生成的摘要消息（`compact_msg:true`）
4. 将提取的消息发送给 LLM 进行记忆提取
5. 将提取的记忆写入 `history.jsonl`：
   ```json
   {
     "cursor": 1,
     "timestamp": "2026-05-11T12:00:00Z",
     "session_key": "telegram:123",
     "content": "• 用户在工作中感到焦虑\n• 用户倾向于通过编程来缓解压力"
   }
   ```
6. 更新 `last_dream_loc` 游标

**为什么跳过 compact 消息**：
- Compact 已经提取了 user fact、decision、event、情绪反应等内容
- Dream 再处理这些内容可能导致重复提取
- Dream 应该专注于从原始对话中提取更深层次的模式和洞察

#### 5. 数据流示例

```
时间线：
T1: user消息1, assistant消息1
T2: user消息2, assistant消息2
T3: user消息3, assistant消息3
... (继续对话)
T10: token超限，触发compact
    → 生成compact消息（msg[10]），last_compact_loc=10
T11: user消息11, assistant消息11
T12: 2小时后，触发dream
    → 处理msg[0]~msg[11]（跳过msg[10]的compact消息）
    → 写入history.jsonl
    → last_dream_loc=11
T13: user消息12, assistant消息12
T14: 空闲超时，触发compact
    → 生成compact消息（msg[14]），last_compact_loc=14
T15: 2小时后，触发dream
    → 处理msg[12]~msg[14]（跳过msg[14]的compact消息）
    → 写入history.jsonl
    → last_dream_loc=14
```

### 决策原因

#### 1. 解决短对话记忆丢失问题

通过定期的 Dream 任务（2 小时 + 系统启动时），可以确保所有 session 的记忆都会被提取，不依赖 token 超限或空闲超时。

#### 2. 职责清晰

- **Compact**：专注于 token 管理，减少单次对话的上下文长度
- **Dream**：专注于记忆提取，捕捉用户的情感、思维、行为模式

两个机制各司其职，互不干扰。

#### 3. 适配 lifeprism 场景

- 短对话的情感记忆可以通过定期 Dream 任务及时捕捉
- 不需要等待 token 超限或空闲超时
- 更符合情感捕捉的需求

#### 4. 灵活性和可扩展性

- 可以独立调整 compact 和 dream 的触发条件
- 可以独立优化 compact 和 dream 的提取规则
- 如果后续发现 token 消耗过大，可以调整游标关系

#### 5. 保留 nanobot 的优秀设计

- 保留了 compact 机制的 token 管理功能
- 保留了 Dream 机制的长期记忆提取功能
- 只是将两者的触发条件和数据流分离

### 潜在风险和缓解措施

#### 风险 1：Token 消耗增加

由于游标独立，Dream 可能需要处理更多原始消息，增加 token 消耗。

**缓解措施**：
- 监控 Dream 任务的 token 消耗
- 如果发现消耗过大，可以调整为"last_dream_loc 跟随 last_compact_loc"
- 或者增加 Dream 的批处理逻辑，限制每次处理的消息数量

#### 风险 2：实现复杂度增加

需要重构现有的记忆系统代码，增加开发和测试成本。

**缓解措施**：
- 分阶段实现，先实现核心功能，再优化细节
- 编写充分的单元测试和集成测试
- 参考 nanobot 的实现，复用成熟的代码逻辑

#### 风险 3：Dream 任务的性能问题

如果 session 数量很多，Dream 任务可能需要处理大量消息，导致性能问题。

**缓解措施**：
- 增加批处理逻辑，每次只处理一定数量的 session
- 增加优先级机制，优先处理最近活跃的 session
- 监控 Dream 任务的执行时间，及时优化

## 后续工作

1. 修改 session metadata 结构，增加 `last_dream_loc` 字段
2. 修改 compact 逻辑，将结果写入 session.jsonl 而非 history.jsonl
3. 新增 dream 任务，从 session 中提取记忆到 history.jsonl
4. 增加 dream 的定时调度（2 小时 + 启动时）
5. 调整 compact 的 prompt，增加情绪/行为模式提取
6. 编写单元测试和集成测试
7. 监控 token 消耗和性能指标，根据实际情况调整设计
