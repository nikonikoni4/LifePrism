---
issue: 02
title: SSH 隧道配置 schema + 私钥走 keyring 存储路由
triage: ready-for-agent
slice: 2
---

# SSH 隧道配置 schema + 私钥走 keyring 存储路由

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

为 SSH 隧道能力新增配置 schema 字段和私钥存储路由，作为后续所有 SSH 隧道功能的基础。

新增 6 个非敏感配置字段（写入 config.yaml）：
- `sync.connection_mode`：连接方式选择（`"http"` | `"ssh"`，默认 `"http"`）
- `sync.ssh_tunnel.host`：SSH 服务器 IP
- `sync.ssh_tunnel.port`：SSH 端口（默认 22）
- `sync.ssh_tunnel.username`：SSH 用户名
- `sync.ssh_tunnel.local_port`：本地监听端口（默认 8102）
- `sync.ssh_tunnel.remote_host`：远程目标主机（默认 `127.0.0.1`）
- `sync.ssh_tunnel.remote_port`：远程目标端口（默认 8102）

新增 1 个敏感 storage key（走 keyring/storage.yaml 路由）：
- `ssh_tunnel_private_key`：SSH 私钥（PEM 格式字符串）

复用现有 `get_storage_key()` / `set_storage_key()` 接口，遵循 [ADR 2026-07-09 密钥存储策略](../../../docs/adr/2026-07-09-key-fallback-strategy.md) v1.2。云端 agent_only 模式下 storage.yaml 不会写入此字段，天然返回 None。

本切片不实现任何隧道运行时逻辑，仅建立配置基础设施。

## Acceptance criteria

- [ ] 修改 `lifeprism/config/settings_manager.py` 新增 `sync.connection_mode` 字段（默认 `"http"`）
- [ ] 修改 `lifeprism/config/settings_manager.py` 新增 `sync.ssh_tunnel.*` 6 个字段（host/port/username/local_port/remote_host/remote_port）
- [ ] 在 `STORAGE_KEY_TO_KEYRING_USERNAME` 中注册 `ssh_tunnel_private_key` → `ssh_tunnel_private_key` 的映射
- [ ] 配置 schema 字段可通过 `get_setting("sync.ssh_tunnel.host")` 等正常读写
- [ ] 私钥可通过 `set_storage_key("ssh_tunnel_private_key", pem)` 写入 keyring（本地 full 模式）
- [ ] 私钥可通过 `get_storage_key("ssh_tunnel_private_key")` 读取（本地 full 模式）
- [ ] 云端 agent_only 模式下 `get_storage_key("ssh_tunnel_private_key")` 返回 None（字段不存在时）
- [ ] 扩展 `test/core/unit/config/test_settings_storage.py` 新增测试：
  - 本地 full 模式：写入私钥到 keyring 后可读取
  - 云端 agent_only 模式：字段不存在时返回 None
  - 私钥不出现在 config.yaml
- [ ] 遵循 [coding-rules/backend-core-rules.md](../../../docs/coding-rules/backend-core-rules.md) 的类型注解规范
- [ ] 所有现有测试通过（无回归）

## Blocked by

None - can start immediately
