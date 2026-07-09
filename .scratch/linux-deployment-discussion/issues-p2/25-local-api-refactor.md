# 本地 API 重构

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 云端与本地 API 区分

---

## What to build

从本地 `main.py` 中移除 `sync_cloud_router` 注册，明确职责分离：云端提供同步 API，本地只提供状态查询和配置生成 API。

**问题背景**：
- 当前 `main.py` 错误地注册了 `sync_cloud_router`
- 导致本地也有 `/api/sync/pull` 和 `/api/sync/push` 端点
- 这些端点在本地没有意义（本地应该是调用方，不是服务方）
- 职责混乱

**解决方案**：本地只注册状态查询和配置生成相关的 API。

**实现端到端**：

修改 `lifeprism/server/main.py`：

```python
# 注册路由
app.include_router(sync_router, prefix="/api/v2")       # ActivityWatch 同步
# app.include_router(sync_cloud_router)  # ← 删除，这是云端提供的
app.include_router(sync_status_router)   # 本地同步状态查询
app.include_router(cloud_config_router)  # 云端配置生成

# 其他路由...
app.include_router(chatbot_router)
app.include_router(goal_router)
# ...
```

**明确职责分离**：

**云端 API**（`main_agent_only.py` 提供，端口 8101）：
- `POST /api/sync/pull` - 本地调用：从云端拉取数据
- `POST /api/sync/push` - 本地调用：推送数据到云端
- `POST /api/sync/pull-files` - 本地调用：拉取文件
- `POST /api/sync/push-files` - 本地调用：推送文件
- `POST /api/sync/heartbeat` - 本地调用：发送心跳/生命周期事件

**本地 API**（`main.py` 提供）：
- `GET /api/sync/status` - 查询同步状态（上次同步时间、同步记录数）
- `POST /api/sync/trigger` - 手动触发同步
- `POST /api/sync/generate-cloud-config` - 生成云端配置文件

**本地调用云端 API**：
```python
# SyncClient 通过 httpx 调用云端
httpx.post(f"{remote_url}/api/sync/pull", ...)  # remote_url = "https://your-server:8101"
httpx.post(f"{remote_url}/api/sync/push", ...)
```

集成测试：
- 测试本地不存在 `/api/sync/pull` 端点（返回 404）
- 测试本地存在 `/api/sync/status` 端点
- 测试本地存在 `/api/sync/trigger` 端点
- 测试本地存在 `/api/sync/generate-cloud-config` 端点

---

## Acceptance criteria

- [ ] `main.py` 移除 `sync_cloud_router` 注册
- [ ] 保留 `sync_status_router` 和 `cloud_config_router` 注册
- [ ] 本地 `/api/sync/pull` 返回 404
- [ ] 本地 `/api/sync/push` 返回 404
- [ ] 本地 `/api/sync/status` 可访问
- [ ] 本地 `/api/sync/trigger` 可访问
- [ ] 本地 `/api/sync/generate-cloud-config` 可访问
- [ ] 集成测试通过：端点可用性检查
- [ ] 不影响现有业务 API

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/24-cloud-fastapi-startup.md` - 云端 FastAPI 服务启动（确保云端提供同步 API）
