# Linux Agent Only 启动入口

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建 Linux Agent Only 模式的启动入口，仅运行 Agent Loop 和 WeChat Channel，不启动 FastAPI 服务，实现轻量化后台运行。

创建 `lifeprism/server/main_agent_only.py`：
1. 仅包含 Agent Loop + WeChat Channel
2. 不启动 FastAPI 及所有路由
3. 不导入 Monitor 模块
4. 不启动 ScheduleService
5. 数据库初始化（`init_database`）
6. 简化版资源初始化（仅初始化必要资源）
7. 日志系统

启动命令：
```bash
python -m lifeprism.server.main_agent_only
```

预期资源占用：
- 内存：< 200MB（vs 完整版 ~500MB）
- 启动时间：< 5 秒（vs 完整版 ~15 秒）

## Acceptance criteria

- [ ] Linux 上能成功启动 Agent Only 模式
- [ ] Agent Loop 正常运行
- [ ] WeChat Channel 能正常启动和通信
- [ ] 不会启动 FastAPI 服务
- [ ] Agent 工具在无 Monitor 时正常工作（查询、记录）
- [ ] 数据库读写正常
- [ ] 资源占用符合预期（内存 < 200MB，启动时间 < 5 秒）

## Blocked by

- `.scratch/linux-deployment-discussion/issues/01-monitor-platform-isolation.md`

## User stories covered

3. 作为用户，我想将 AI Agent 部署到云服务器，以便出门在外时通过微信对话查询和记录数据，不受本地电脑开关机影响
4. 作为用户，我想通过微信查询今天的电脑使用情况，以便随时了解自己的时间分配
5. 作为用户，我想通过微信记录心情和想法，以便即使不在电脑前也能持续记录
