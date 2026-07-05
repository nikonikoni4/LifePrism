# Issue 1: 数据层增强 - chat_history.json 支持 session_id

## 必读文档

在开始实现前，请阅读以下文档：

1. **PRD**: `.scratch/wechat-session-enhancement/prd.md`
   - 重点阅读：Problem Statement、Solution、Implementation Decisions 第 1 节
2. **实现分析**: `.scratch/wechat-session-enhancement/implementation-analysis.md`
   - 重点阅读：实施顺序阶段 1、约束确认第 2.1 节
3. **编码规范**: `docs/coding-rules/backend-core-rules.md`
   - 重点阅读：类型注解、文档字符串、日志记录规范

## Parent

无（这是独立的基础功能）

## What to build

为 `chat_history.json` 增加 `session_id` 字段支持，确保新生成的会话总结能关联到具体的 session。这是后续会话查询功能的数据基础。

完整的端到端路径包括：
- 修改 `ChatHistoryManager.add_content()` 方法签名，增加可选的 `session_id` 参数
- 修改定时任务 `process_session_message()` 中的调用点，传入 `session.id`
- 确保向后兼容：不传 `session_id` 时，行为与旧版本一致
- 验证新生成的 `chat_history.json` 包含 `session_id` 字段

## Acceptance criteria

- [ ] `ChatHistoryManager.add_content()` 方法签名包含 `session_id: str | None = None` 参数
- [ ] 方法有完整的类型注解和 Google 风格文档字符串
- [ ] `save_history()` 方法在写入时包含 `session_id` 字段（如果提供）
- [ ] `agent_schedule_job.py` 中的 `process_session_message()` 调用 `add_content()` 时传入 `session.id`
- [ ] 使用 grep 搜索所有 `add_content` 调用点，确认没有遗漏
- [ ] 向后兼容：不传 `session_id` 时，不写入该字段
- [ ] 运行定时任务后，新生成的 `chat_history.json` 包含 `session_id` 字段
- [ ] 关键操作记录 INFO 级别日志

## Blocked by

None - 可立即开始
