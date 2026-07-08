# Linux Web Demo 启动入口

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建 Linux Web Demo 模式的启动入口，提供完整的 FastAPI 服务和 Agent 功能，但不包含 Monitor 模块。

创建 `lifeprism/server/main_web_demo.py`：
1. 包含 FastAPI 服务和所有 API 路由
2. 包含 Agent Loop
3. 不导入 Monitor 模块
4. 不启动 ScheduleService（因为依赖 Monitor 数据）
5. 监听 `0.0.0.0:8101`（固定端口）
6. 初始化数据库、Agent Loop、日志系统

启动命令：
```bash
uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101
```

## Acceptance criteria

- [ ] Linux 上能成功启动 Web Demo 模式
- [ ] FastAPI 服务正常响应 `/api/*` 路径
- [ ] Agent 工具可以正常使用（查询、记录）
- [ ] 不会尝试导入或启动 Monitor 模块
- [ ] 数据库初始化正常
- [ ] 日志系统正常工作

## Blocked by

- `.scratch/linux-deployment-discussion/issues/01-monitor-platform-isolation.md`

## User stories covered

1. 作为产品负责人，我想在云服务器上部署 Web Demo，以便潜在客户可以在线体验 LifePrism 的核心功能，无需下载安装
2. 作为产品负责人，我想展示 LifePrism 的完整界面和数据可视化，以便演示产品价值
6. 作为用户，我想通过浏览器访问 LifePrism，以便在任何设备上查看我的数据
