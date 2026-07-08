# 测试 - Agent Only 功能

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建集成测试，验证 Agent Only 模式下的核心功能是否正常工作。

创建 `test/integration/test_agent_only_mode.py`，包含以下测试用例：

1. `test_agent_loop_starts_without_fastapi`
   - 验证 Agent Loop 能独立启动，不依赖 FastAPI
   - Mock Agent Loop 的启动逻辑

2. `test_wechat_channel_starts_in_agent_mode`
   - 验证 WeChat Channel 能在 Agent Only 模式下启动
   - Mock WeChat Channel 的网络请求

3. `test_agent_tools_work_without_monitor`
   - 验证 Agent 工具在无 Monitor 时正常工作
   - Mock LLM 调用
   - 验证查询和记录工具能正常执行

4. `test_database_accessible_in_agent_mode`
   - 验证数据库读写正常
   - 使用临时数据库文件
   - 验证基本的 CRUD 操作

使用 Mock 策略：
- Mock WeChat Channel 的网络请求
- Mock LLM 调用
- 使用临时数据库文件

## Acceptance criteria

- [ ] 所有测试用例实现完整
- [ ] 测试能验证 Agent Only 模式的独立性（不依赖 FastAPI）
- [ ] 测试能验证 Agent 工具在无 Monitor 时正常工作
- [ ] 测试能验证数据库访问正常
- [ ] 使用 Mock 隔离外部依赖
- [ ] 测试独立运行，不依赖其他测试状态

## Blocked by

- `.scratch/linux-deployment-discussion/issues/03-linux-agent-only-entrypoint.md`

## User stories covered

3. 作为用户，我想将 AI Agent 部署到云服务器，以便出门在外时通过微信对话查询和记录数据，不受本地电脑开关机影响
4. 作为用户，我想通过微信查询今天的电脑使用情况，以便随时了解自己的时间分配
5. 作为用户，我想通过微信记录心情和想法，以便即使不在电脑前也能持续记录
