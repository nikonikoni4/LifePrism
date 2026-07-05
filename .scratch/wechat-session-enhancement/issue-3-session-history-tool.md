# Issue 3: 会话历史预览工具

## 必读文档

在开始实现前，请阅读以下文档：

1. **PRD**: `.scratch/wechat-session-enhancement/prd.md`
   - 重点阅读：Solution 第 2 点、Implementation Decisions 第 2 节（QuerySessionHistoryTool）
2. **实现分析**: `.scratch/wechat-session-enhancement/implementation-analysis.md`
   - 重点阅读：实施顺序阶段 2、安全性约束
3. **编码规范**: `docs/coding-rules/backend-core-rules.md`
   - 重点阅读：错误处理分层、数据路径、类型注解
4. **测试规范**: `docs/coding-rules/test-rules.md`
   - 重点阅读：测试目录结构、数据来源、验证方法
5. **工具参考**: `lifeprism/llm/agent/tools/base.py` 和 `lifeprism/llm/agent/tools/lifeprismsystem.py`
   - 理解工具基类和现有工具实现模式

## Parent

无（这是独立的功能切片）

## What to build

实现会话历史预览工具 `QuerySessionHistoryTool`，允许用户查看指定 session 的最近 N 轮对话，帮助进一步确认目标会话。

完整的端到端路径包括：
- 创建工具类，继承 `Tool` 基类，实现查询逻辑
- 从指定 session.jsonl 文件读取对话历史
- 过滤出 user 和 assistant 消息
- 按时间倒序返回最近 N 条
- 在 `AgentLoop._process_msg()` 中注册工具（仅 MessageType.CHAT）
- 在 `__init__.py` 导出工具
- 编写单元测试
- 通过微信实际测试

## Acceptance criteria

- [ ] 在 `lifeprism/llm/agent/tools/session_query.py` 中添加 `QuerySessionHistoryTool` 类
- [ ] `QuerySessionHistoryTool` 继承 `Tool` 基类
- [ ] 实现 `name` 属性：返回 `"query_session_history"`
- [ ] 实现 `description` 属性：清晰说明工具用途和适用场景
- [ ] 实现 `parameters` 属性：定义参数
  - [ ] `session_id: str`（必填）
  - [ ] `limit: int`（可选，默认 10，最小 1，最大 50）
- [ ] 实现 `execute()` 方法：
  - [ ] 调用 `SessionManager.get_session_path_by_id(session_id)` 获取文件路径
  - [ ] 检查文件是否存在，不存在返回错误
  - [ ] 读取 session 文件，过滤出 `role in ["user", "assistant"]` 的消息
  - [ ] 按 timestamp 倒序，取最近 `min(limit, 50)` 条
  - [ ] 返回格式：`list[dict[str, str]]`，每项包含 `{"role": str, "content": str, "timestamp": str}`
- [ ] 所有函数有完整类型注解和文档字符串
- [ ] 错误处理：返回 `f"{ERROR}xxx"` 格式，不抛出异常
- [ ] session_id 不存在时返回错误消息
- [ ] 关键操作记录 INFO 级别日志
- [ ] 在 `lifeprism/llm/agent/loop.py` 的 `_process_msg()` 方法中注册工具
- [ ] 注册位置：`if msg.type == MessageType.CHAT:` 分支末尾（在 QuerySessionListTool 之后）
- [ ] 在 `lifeprism/llm/agent/tools/__init__.py` 导出 `QuerySessionHistoryTool`
- [ ] 在 `test/core/unit/llm/tools/test_session_query.py` 中添加测试
- [ ] 测试基本功能：返回指定数量的历史消息
- [ ] 测试 limit 参数：默认 10，最大 50
- [ ] 测试错误处理：session_id 不存在时返回错误消息
- [ ] 通过微信发送消息，验证 AI 可以调用该工具并返回结果

## Blocked by

None - 可立即开始（与 Issue 1 并行）
