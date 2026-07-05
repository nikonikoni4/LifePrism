# Issue 2: 会话列表查询工具

## 必读文档

在开始实现前，请阅读以下文档：

1. **PRD**: `.scratch/wechat-session-enhancement/prd.md`
   - 重点阅读：Solution 第 1 点、Implementation Decisions 第 2 节（QuerySessionListTool）
2. **实现分析**: `.scratch/wechat-session-enhancement/implementation-analysis.md`
   - 重点阅读：实施顺序阶段 2、安全性约束、性能考虑
3. **编码规范**: `docs/coding-rules/backend-core-rules.md`
   - 重点阅读：错误处理分层、数据路径、类型注解
4. **测试规范**: `docs/coding-rules/test-rules.md`
   - 重点阅读：测试目录结构、数据来源、验证方法
5. **工具参考**: `lifeprism/llm/agent/tools/base.py` 和 `lifeprism/llm/agent/tools/lifeprismsystem.py`
   - 理解工具基类和现有工具实现模式

## Parent

无（这是独立的功能切片）

## What to build

实现智能会话列表查询工具 `QuerySessionListTool`，允许用户通过日期筛选会话，并获取每个会话的最新总结和最后用户消息。

完整的端到端路径包括：
- 创建工具类，继承 `Tool` 基类，实现查询逻辑
- 从所有 session.jsonl 文件读取会话信息
- 从 chat_history.json 聚合每个 session 的最新总结
- 在 `AgentLoop._process_msg()` 中注册工具（仅 MessageType.CHAT）
- 在 `__init__.py` 导出工具
- 编写单元测试，覆盖基本功能、日期过滤、兼容性
- 通过微信实际测试，验证 AI 可以调用该工具

## Acceptance criteria

- [ ] 创建 `lifeprism/llm/agent/tools/session_query.py` 文件
- [ ] `QuerySessionListTool` 继承 `Tool` 基类
- [ ] 实现 `name` 属性：返回 `"query_session_list"`
- [ ] 实现 `description` 属性：清晰说明工具用途和适用场景
- [ ] 实现 `parameters` 属性：定义 `date_filter: str | None` 参数（格式 "YYYY-MM-DD"）
- [ ] 实现 `execute()` 方法：
  - [ ] 从 `settings.session_path` 遍历所有 `.jsonl` 文件
  - [ ] 读取 session metadata，应用日期过滤
  - [ ] 获取最后一条 user 消息作为 `last_user_message`
  - [ ] 从 `ChatHistoryManager` 加载 `chat_history.json`
  - [ ] 按 session_id 分组，取最新的 summary 作为 `last_summary`
  - [ ] 兼容旧数据：跳过没有 session_id 的记录
  - [ ] 返回格式：`{"session_id": {"last_summary": str, "last_user_message": str}}`
- [ ] 所有函数有完整类型注解和文档字符串
- [ ] 错误处理：返回 `f"{ERROR}xxx"` 格式，不抛出异常
- [ ] 文件操作有 try-except，单个文件错误不影响整体查询
- [ ] 关键操作记录 INFO 级别日志
- [ ] 在 `lifeprism/llm/agent/loop.py` 的 `_process_msg()` 方法中注册工具
- [ ] 注册位置：`if msg.type == MessageType.CHAT:` 分支末尾
- [ ] 在 `lifeprism/llm/agent/tools/__init__.py` 导出 `QuerySessionListTool`
- [ ] 创建 `test/core/unit/llm/tools/test_session_query.py`，标记 `@pytest.mark.core`
- [ ] 测试基本功能：返回格式正确，包含 last_summary 和 last_user_message
- [ ] 测试日期过滤：只返回指定日期的 session
- [ ] 测试兼容性：chat_history.json 中没有 session_id 的记录不影响查询
- [ ] 测试空结果：没有符合条件的 session 时返回空 dict
- [ ] 通过微信发送消息，验证 AI 可以调用该工具并返回结果

## Blocked by

Issue 1 - 数据层增强必须完成，确保 chat_history.json 包含 session_id
