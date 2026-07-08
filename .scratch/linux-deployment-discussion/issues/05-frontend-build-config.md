# 前端构建配置

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

验证前端能正确构建为静态文件，并更新文档说明如何构建用于 Web Demo 部署。

验证前端构建流程：
1. 检查 `frontend` submodule 的构建配置
2. 验证 `npm run build` 能生成 `dist/` 目录
3. 验证构建产物包含完整的静态资源（HTML、CSS、JS、assets）
4. 验证构建产物可以被 Nginx 直接托管

更新 `frontend/README.md`（或创建 `frontend/DEPLOYMENT.md`）：
- 说明如何构建静态文件
- 说明构建产物的位置
- 说明部署时需要注意的事项（API 代理配置等）

## Acceptance criteria

- [ ] `cd frontend && npm run build` 能成功生成 `dist/` 目录
- [ ] `dist/` 目录包含完整的静态文件（HTML、CSS、JS、assets）
- [ ] 构建产物可以在 Nginx 中正常托管
- [ ] 文档说明清晰，包含构建命令和部署说明
- [ ] 文档说明前端需要配置后端 API 地址的方式（如果需要）

## Blocked by

None - can start immediately

## User stories covered

1. 作为产品负责人，我想在云服务器上部署 Web Demo，以便潜在客户可以在线体验 LifePrism 的核心功能，无需下载安装
2. 作为产品负责人，我想展示 LifePrism 的完整界面和数据可视化，以便演示产品价值
