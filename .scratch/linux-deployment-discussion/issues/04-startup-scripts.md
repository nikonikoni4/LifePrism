# 启动脚本

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建标准化的 bash 启动脚本，用于在 Linux 服务器上启动 Web Demo 和 Agent Only 模式。

创建 `scripts/deployment/start_web_demo.sh`：
- 启动 Web Demo 模式（uvicorn）
- 支持环境变量 `LIFEPRISM_DATA_PATH`
- 提供启动/停止/状态检查功能

创建 `scripts/deployment/start_agent_only.sh`：
- 启动 Agent Only 模式（python -m）
- 支持环境变量 `LIFEPRISM_DATA_PATH`
- 提供启动/停止/状态检查功能

脚本功能：
- `start`：启动服务
- `stop`：停止服务
- `status`：检查服务状态
- `restart`：重启服务

## Acceptance criteria

- [ ] `start_web_demo.sh start` 能成功启动 Web Demo
- [ ] `start_agent_only.sh start` 能成功启动 Agent Only
- [ ] `stop` 命令能正常停止服务
- [ ] `status` 命令能显示服务运行状态
- [ ] 支持通过 `LIFEPRISM_DATA_PATH` 环境变量配置数据路径
- [ ] 脚本包含必要的错误处理和日志输出
- [ ] 脚本有执行权限（chmod +x）

## Blocked by

- `.scratch/linux-deployment-discussion/issues/02-linux-web-demo-entrypoint.md`
- `.scratch/linux-deployment-discussion/issues/03-linux-agent-only-entrypoint.md`

## User stories covered

10. 作为开发者，我想通过简单的命令启动不同模式，以便快速验证功能
11. 作为运维人员，我想通过标准的启动脚本部署服务，以便自动化部署流程
13. 作为运维人员，我想使用环境变量配置数据路径，以便灵活管理服务器存储
