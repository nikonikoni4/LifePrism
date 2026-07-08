# 部署文档

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建完整的 Linux 部署文档，说明如何在 Linux 服务器上部署 Web Demo 和 Agent Only 模式。

创建 `docs/deployment/linux-deployment-guide.md`：
- 系统要求（Ubuntu 20.04+、Python 3.10+）
- 依赖安装步骤（`pip install -e .`）
- 三种运行模式说明（Windows 桌面版、Linux Web Demo、Linux Agent Only）
- 启动命令（使用启动脚本）
- 环境变量配置说明（`LIFEPRISM_DATA_PATH`）
- 常见问题排查（端口占用、依赖缺失、日志查看）

创建 `docs/deployment/nginx-setup.md`：
- 项目暴露的信息：
  - 后端监听端口：8101
  - 需要代理的路径：`/api/*`
  - SSE 支持要求：`proxy_buffering off`
  - 前端静态文件位置：`frontend/dist/`
- 配置示例说明（不提供完整配置文件，只说明关键点）
- SSE 验证方法（如何测试流式响应是否正常）

## Acceptance criteria

- [ ] `linux-deployment-guide.md` 包含完整的部署步骤
- [ ] 文档说明三种运行模式的区别和使用场景
- [ ] 文档包含启动命令和环境变量说明
- [ ] 文档包含常见问题排查指南
- [ ] `nginx-setup.md` 说明项目需要暴露的信息
- [ ] 文档说明 SSE 支持的配置要求
- [ ] 文档提供 SSE 验证方法
- [ ] 按照文档能成功完成部署

## Blocked by

- `.scratch/linux-deployment-discussion/issues/01-monitor-platform-isolation.md`
- `.scratch/linux-deployment-discussion/issues/02-linux-web-demo-entrypoint.md`
- `.scratch/linux-deployment-discussion/issues/03-linux-agent-only-entrypoint.md`
- `.scratch/linux-deployment-discussion/issues/04-startup-scripts.md`

## User stories covered

9. 作为开发者，我想看到清晰的平台适配文档，以便理解不同运行模式的差异和限制
12. 作为运维人员，我想看到清晰的端口和依赖说明，以便配置防火墙和反向代理
