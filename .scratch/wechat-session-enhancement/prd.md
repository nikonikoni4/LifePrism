---
title: WeChat Channel Session Management Enhancement
created_at: 2026-07-05
status: ready-for-agent
type: feature
---

# WeChat Channel Session Management Enhancement

## Problem Statement

当前微信渠道的会话切换体验存在以下痛点：

1. **切换流程繁琐**：用户必须先发送 `/session-list` 查看所有 session_id，然后手动输入 `/continue <session_id>` 切换到目标会话，需要精确复制粘贴长字符串 ID
2. **会话识别困难**：列表只显示 session_id 和最后 20 个字符的消息预览，用户在微信端很难区分具体是哪个会话，尤其当有多个相似主题的会话时
3. **上下文缺失**：切换到会话后，用户看到的只是成功提示，没有任何历史对话的上下文回顾，需要重新询问才能回忆起之前聊了什么

这些问题导致用户在微信端管理多个会话时体验极差，尤其是在移动设备上操作时更加不便。

## Solution

通过引入两个 AI 工具和优化命令响应，实现智能化的会话管理：

1. **智能会话查询工具**：提供语义化的会话列表，包含每个会话的最新总结和最后用户消息，帮助用户快速识别目标会话
2. **会话历史预览工具**：当用户仍无法确定时，可查看某个会话的最近对话记录进行进一步确认
3. **AI 引导式切换**：AI 主动询问用户需求，调用工具查询，按序号展示结果，用户只需说"第几个"，AI 即可生成完整的切换指令供用户一键复制
4. **上下文回显**：切换会话后自动展示最后两轮对话，让用户快速回忆上下文
5. **新会话恢复提示**：创建新会话后提示用户如何恢复到上一个会话

## User Stories

1. 作为微信渠道用户，我想通过描述会话内容（如"上次讨论的那个数据库设计问题"）来查找会话，而不是记住 session_id，这样我可以更自然地切换会话
2. 作为微信渠道用户，我想看到每个会话的最新总结和最后一条消息，这样我可以快速识别出是哪个会话
3. 作为微信渠道用户，我想通过时间范围（如"昨天的会话"）来筛选会话列表，这样我可以缩小查找范围
4. 作为微信渠道用户，当 AI 列出多个会话时，我想看到带序号的列表（第1个、第2个...），这样我可以通过序号来指定
5. 作为微信渠道用户，当我说"第3个"时，我希望 AI 直接给我生成好的切换指令，这样我只需复制粘贴即可，不用手动拼接 session_id
6. 作为微信渠道用户，当我对会话列表中的某项仍不确定时，我想查看该会话的最近几轮对话，这样我可以进一步确认是否是我要找的
7. 作为微信渠道用户，当我切换到某个会话后，我想立即看到最后两轮对话的内容，这样我可以快速回忆起上次聊到哪里了
8. 作为微信渠道用户，当我创建新会话后，我想知道如何回到上一个会话，这样我不会丢失之前的工作
9. 作为微信渠道用户，我希望这些工具只在聊天场景下可用，不要在其他任务场景（如 DREAM_TASK）中出现，这样不会混淆工具的使用场景
10. 作为微信渠道用户，当我查看会话历史时，我希望可以指定查看的轮数（如最近 10 轮或 20 轮），这样我可以根据需要获取不同深度的上下文
11. 作为 AI 助手，当用户想切换会话但不确定是哪个时，我需要主动询问时间范围和内容关键词，这样我可以更精准地调用查询工具
12. 作为 AI 助手，当我列出会话列表后，我需要等待用户选择，而不是自动切换，这样用户可以保持对会话切换的控制权
13. 作为 AI 助手，当用户给出模糊描述（如"应该是关于前端开发的那个"）时，我需要从列表中匹配最符合的项，并生成切换指令，这样用户不需要重新描述
14. 作为系统开发者，我需要确保 chat_history.json 中每条总结都关联到 session_id，这样查询工具才能正确返回每个会话的最新总结
15. 作为系统开发者，我需要兼容旧的 chat_history.json 数据（没有 session_id 字段），这样系统升级后不会因数据格式问题而崩溃

## Implementation Decisions

### 1. 数据模型变更

**chat_history.json 增加 session_id 字段**

- 当前格式：`{"timestamp": "...", "content": "..."}`
- 新格式：`{"timestamp": "...", "content": "...", "session_id": "..."}`
- 修改位置：`ChatHistoryManager.add_content()` 方法签名增加 `session_id: str | None` 参数
- 调用点修改：`agent_schedule_job.py` 的 `process_session_message()` 函数中，调用 `history_manager.add_content()` 时传入 `session.id`
- 兼容性：查询工具需要兼容旧数据（没有 session_id 的记录跳过）

### 2. 工具实现

**创建 `lifeprism/llm/agent/tools/session_query.py`**

包含两个工具类：

**QuerySessionListTool**
- 工具名：`query_session_list`
- 参数：
  - `date_filter: str | None`（可选，格式 "YYYY-MM-DD"，筛选指定日期的会话）
- 返回：`dict[str, dict[str, str]]`，格式为 `{"session_id": {"last_summary": str, "last_user_message": str}}`
- 实现逻辑：
  1. 从 `settings.session_path` 遍历所有 `.jsonl` 文件
  2. 读取 metadata 获取 `updated_at` 时间戳，应用日期过滤
  3. 读取 session 文件，获取最后一条 `role=="user"` 的消息作为 `last_user_message`
  4. 从 `ChatHistoryManager` 加载 `chat_history.json`，按 `session_id` 分组，取每个 session 的最新一条（timestamp 最大）作为 `last_summary`
  5. 兼容旧数据：如果某条历史记录没有 `session_id`，跳过该记录
  6. 返回 dict

**QuerySessionHistoryTool**
- 工具名：`query_session_history`
- 参数：
  - `session_id: str`（必填）
  - `limit: int = 10`（默认 10，最大 50）
- 返回：`list[dict[str, str]]`，每项包含 `{"role": str, "content": str, "timestamp": str}`
- 实现逻辑：
  1. 调用 `SessionManager.get_session_path_by_id(session_id)` 获取文件路径
  2. 检查文件是否存在，不存在返回错误
  3. 读取 session 文件，过滤出 `role in ["user", "assistant"]` 的消息
  4. 按 timestamp 倒序，取最近 `min(limit, 50)` 条
  5. 返回 list

### 3. 工具注册

**修改 `lifeprism/llm/agent/loop.py` 的 `_process_msg()` 方法**

- 在 `if msg.type == MessageType.CHAT:` 分支中注册两个新工具
- 注册位置：在现有工具注册语句之后
- 代码示例：
  ```python
  if msg.type == MessageType.CHAT:
      # ... 现有工具注册 ...
      self._tool_registry.register(QuerySessionListTool())
      self._tool_registry.register(QuerySessionHistoryTool())
      tools: list[dict[str, Any]] = self._tool_registry.get_definitions()
  ```

### 4. 工具导出

**修改 `lifeprism/llm/agent/tools/__init__.py`**

- 导入并导出 `QuerySessionListTool` 和 `QuerySessionHistoryTool`

### 5. 提示词说明

**更新 `templates/agent/chat/tool.md`**

在"控制指令"部分之前，新增"会话切换辅助"章节：

内容要点：
- 说明两个工具的用途和适用场景
- 定义 AI 的引导流程：先询问时间范围和内容关键词 → 调用 `query_session_list` → 按序号列出结果 → 等待用户选择
- 列出结果时的格式要求：必须有明确序号（第1个、第2个...），每项显示 session_id、最新总结和最后消息
- 用户选择后的响应模板：识别用户说的"第X个"或模糊描述 → 回复"请复制下面的指令发送\n/continue <session_id>"
- 如果用户仍不确定，引导使用 `query_session_history` 工具查看具体对话

### 6. 命令响应增强

**修改 `lifeprism/llm/agent/loop.py` 的 `_process_cmd()` 方法**

**`/continue <session_id>` 命令**：
- 当前逻辑：验证 session_id 存在性，返回成功提示
- 新增逻辑：
  1. 加载 session 对象
  2. 从 `session.messages` 中提取最后两轮对话（最后一条 `role=="user"` 和最后一条 `role=="assistant"`）
  3. 构造响应文本：
     ```
     [SUCCESS] 继续会话 <session_id>
     
     最后两轮对话：
     user:
     <user_content>
     
     A:
     <assistant_content>
     ```
  4. 如果 session 消息少于两轮，显示现有内容
  5. 返回 OutboundMessage

**`/new` 命令**：
- 当前逻辑：创建新 session，返回成功提示
- 新增逻辑：
  1. 创建新 session 前，获取当前使用的 `old_session_id`（从 `msg.session_id` 获取）
  2. 构造响应文本：
     ```
     [SUCCESS] 新建会话 <new_session_id> --- 可以开始新的聊天了！
     
     可以通过使用以下指令恢复上一个会话：
     /continue <old_session_id>
     ```
  3. 如果 `old_session_id` 为 None（首次创建会话），不显示恢复提示
  4. 返回 OutboundMessage

### 7. 模块边界

- **工具层**（`tools/session_query.py`）：负责数据查询和聚合，返回结构化数据
- **AgentLoop**（`agent/loop.py`）：负责工具注册和命令处理逻辑
- **SessionManager**（`session/manager.py`）：提供 session 文件读取接口，不修改现有逻辑
- **ChatHistoryManager**（`session/manager.py`）：修改 `add_content()` 签名，增加 `session_id` 参数
- **提示词模板**（`templates/agent/chat/tool.md`）：定义 AI 的行为规范和响应模板

## Testing Decisions

### 测试原则

- 只测试外部行为（工具输入输出、命令响应格式），不测试实现细节（如内部数据结构）
- 使用真实的文件系统（临时目录），不 mock SessionManager 或 ChatHistoryManager
- 每个测试用例创建独立的临时数据环境，测试后清理

### 测试模块

**1. `test/core/unit/llm/tools/test_session_query.py`**

测试内容：
- `QuerySessionListTool` 基本功能：返回格式正确、包含 last_summary 和 last_user_message
- 日期过滤功能：只返回指定日期的 session
- 兼容旧数据：chat_history.json 中没有 session_id 的记录不影响查询
- 空结果处理：没有符合条件的 session 时返回空 dict
- `QuerySessionHistoryTool` 基本功能：返回指定数量的历史消息
- limit 参数验证：默认 10，最大 50
- session_id 不存在时返回错误消息

**2. `test/core/unit/llm/agent/test_loop_cmd.py`（或扩展现有测试文件）**

测试内容：
- `/continue` 命令增强：响应包含最后两轮对话
- `/new` 命令增强：响应包含恢复上一个会话的提示
- 边界情况：session 消息少于两轮时的处理

### 测试先例

参考现有测试：
- Session 相关测试：`test/core/unit/llm/chat_history/test_chat_history.py`
- 工具测试模式：`test/core/unit/llm/tools/` 下的其他工具测试
- AgentLoop 命令测试：查找现有的 `/new`、`/continue` 相关测试（如果存在）

## Out of Scope

以下功能不在本 PRD 范围内：

1. **前端界面**：不涉及前端的会话管理 UI，所有交互通过微信渠道的文本命令完成
2. **其他渠道支持**：工具和命令增强只针对微信渠道，其他渠道（如未来可能的 Telegram、Slack）不在此次实现范围内
3. **会话删除/重命名**：不涉及会话的删除、重命名等管理功能
4. **会话分组/标签**：不引入会话分组、标签等组织功能
5. **自动会话切换**：AI 不会自动切换会话，必须由用户明确选择并发送命令
6. **多会话合并**：不涉及将多个会话合并为一个的功能
7. **会话导出**：不涉及将会话导出为文件的功能
8. **实时会话同步**：不涉及跨设备的会话同步功能

## Further Notes

### 数据一致性

- `chat_history.json` 的 `session_id` 字段是在 `process_session_message()` 定时任务中添加的，该任务每 2 小时运行一次
- 因此，新创建的 session 在前 2 小时内可能没有对应的 summary 记录，`query_session_list` 工具会返回该 session 的 `last_summary` 为空字符串或 None
- 这是预期行为，不需要特殊处理

### 提示词工程

- `templates/agent/chat/tool.md` 的更新需要明确 AI 的行为边界：
  - **必须按序号列出**：确保用户可以通过"第几个"来选择
  - **等待用户确认**：列出结果后不自动切换，等待用户选择
  - **生成可复制指令**：用户选择后，回复格式必须是"请复制下面的指令发送\n/continue <session_id>"
- 这些规则应通过实际使用来验证和迭代，初版可能需要根据用户反馈调整提示词

### 性能考虑

- `query_session_list` 工具需要遍历所有 session 文件和 chat_history.json，当 session 数量较多（如 100+）时可能有性能问题
- 初版实现可以不考虑性能优化，如果后续发现问题，可以考虑：
  - 缓存 session metadata
  - 限制返回结果数量（如最多 20 个）
  - 增加分页支持

### 未来扩展

- 如果用户反馈良好，可以考虑将这些工具扩展到其他渠道（如桌面 UI）
- 可以考虑增加会话搜索功能（基于全文检索）
- 可以考虑增加会话推荐功能（基于用户当前输入的内容）
