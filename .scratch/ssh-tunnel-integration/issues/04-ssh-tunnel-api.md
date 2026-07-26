---
issue: 04
title: SSH 隧道管理 API（enable 自动生成密钥 + public-key + test）
triage: ready-for-agent
slice: 4
---

# SSH 隧道管理 API（enable 自动生成密钥 + public-key + test）

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

新增 `lifeprism/server/api/ssh_tunnel_api.py` 模块，提供 SSH 隧道管理的 3 个 API 端点（仅 full 模式注册路由，agent_only 模式不暴露）。

三个端点：

**1. POST /api/v2/settings/ssh-tunnel/enable**
- 用户切换到 SSH 模式时调用
- 检查 keyring 是否已有 `ssh_tunnel_private_key`
  - 有 → 保留不覆盖（避免已部署到云端的公钥失效）
  - 无 → 调用 `asyncssh.generate_private_key('ssh-ed25519')` 生成密钥对，私钥存 keyring
- 从私钥派生公钥（不存储，每次实时派生）
- 返回 `{"public_key": "ssh-ed25519 AAAA...", "is_new": true/false}`

**2. GET /api/v2/settings/ssh-tunnel/public-key**
- 从 keyring 私钥实时派生公钥
- keyring 无私钥时返回 `{"public_key": ""}`（不抛错）
- 用于前端进入 SSH 配置页面时加载展示

**3. POST /api/v2/settings/ssh-tunnel/test**
- 接收 SSH 连接参数（host/port/username/local_port/remote_port）
- 调用 `SSHTunnel.test_connection()`（Issue 03 实现）
- 返回 `{"status": "ok", "remote_response": {...}}` 或失败原因

## Acceptance criteria

- [ ] 新增 `lifeprism/server/api/ssh_tunnel_api.py`，实现 3 个端点
- [ ] 修改 `lifeprism/server/main.py` 在 full 模式启动时注册 `ssh_tunnel_router`
- [ ] agent_only 模式不注册此路由（run_mode 守卫）
- [ ] POST /enable：
  - keyring 无私钥时自动生成 ed25519 密钥对 + 返回公钥 + is_new=true
  - keyring 已有私钥时保留不覆盖 + 返回派生公钥 + is_new=false
  - 返回的公钥格式正确（以 `ssh-ed25519 ` 开头）
- [ ] GET /public-key：
  - keyring 有私钥时返回派生公钥
  - keyring 无私钥时返回空字符串（不抛错）
- [ ] POST /test：
  - 调用 `SSHTunnel.test_connection()`（Issue 03 实现的"建立→验证→关闭"一次性测试方法）
  - 返回测试结果或失败原因（如"密钥被拒绝"/"远程 8102 不可达"）
  - 不留孤儿进程（test_connection 内部关闭连接）
- [ ] 新增 `test/core/integration/api/test_ssh_tunnel_api.py` 测试：
  - POST /enable 三个场景（无私钥生成/有私钥保留/公钥格式正确）
  - GET /public-key 两个场景（有私钥/无私钥）
  - POST /test（mock SSHTunnel.test_connection）
  - 路由仅在 full 模式注册（agent_only 模式不暴露）
- [ ] 遵循 [backend-api-rules](../../../docs/coding-rules/backend-api-rules.md) 和 [backend-error-handling](../../../docs/coding-rules/backend-error-handling.md) 规范
- [ ] 所有现有测试通过（无回归）

## Blocked by

- Issue 02: SSH 隧道配置 schema（需 storage key 路由）
- Issue 03: SSHTunnel 类（test 端点需调用 SSHTunnel）
