---
issue: 05
title: SyncClient SSH 隧道编排 + _read_remote_url() 拦截
triage: ready-for-agent
slice: 5
---

# SyncClient SSH 隧道编排 + _read_remote_url() 拦截

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

将 SSH 隧道集成到 SyncClient 启动流程，实现非侵入式 remote_url 拦截。本切片是 SSH 隧道能力与同步主流程的集成层。

**集成逻辑**：
- SyncClient 启动时检查 `sync.connection_mode == "ssh"`
- 如启用 SSH 模式，启动 SSHTunnel 后台任务（含心跳保活和重连）
- 等待本地监听端口可用后触发首次同步
- 隧道未就绪时跳过本次同步并记录 WARNING
- SyncClient 关闭时优雅关闭 SSH 隧道

**remote_url 拦截**（核心设计，参考 [sync-remote-url-access-rules.md](../../../docs/coding-rules/sync-remote-url-access-rules.md)）：
- 在 `SyncClient._read_remote_url()` 方法中拦截
- SSH 模式 + 隧道就绪 → 返回 `http://localhost:{local_port}`
- SSH 模式 + 隧道未就绪 → 返回空字符串（触发上层跳过逻辑）
- HTTP 模式 → 返回原 `sync.remote_url`
- **`_read_remote_url()` 方法注释必须明确警告**：所有需要 remote_url 的代码路径必须通过此方法获取，禁止直接调用 `get_setting("sync.remote_url")`

**三层守卫**（参考已有 run_mode 守卫模式）：
1. run_mode 守卫：云端 agent_only 模式根本不启动隧道
2. connection_mode 守卫：未启用 SSH 模式不启动
3. 私钥存在性守卫：无私钥不启动

## Acceptance criteria

- [ ] 修改 `lifeprism/sync/sync_client.py` 新增方法：
  - `async _ensure_tunnel_ready() -> bool`：如启用 SSH 隧道则等待就绪，否则返回 True
  - `_should_use_ssh_tunnel() -> bool`：三层守卫判断
  - `_is_tunnel_ready() -> bool`：检查 SSHTunnel 实例状态
  - `async _start_ssh_tunnel() -> None`：启动 SSHTunnel 后台任务
  - `async _stop_ssh_tunnel() -> None`：优雅关闭 SSHTunnel
- [ ] 修改 `_read_remote_url()` 方法实现 SSH 模式拦截逻辑
- [ ] `_read_remote_url()` 方法 docstring 包含明确警告（参考 [sync-remote-url-access-rules.md 规则 6](../../../docs/coding-rules/sync-remote-url-access-rules.md)）：
  - 警告所有代码路径必须通过此方法获取 remote_url
  - 说明 SSH 隧道启用时直接读 settings 会绕过隧道
  - 说明返回值语义（HTTP 模式/SSH 模式就绪/SSH 模式未就绪）
- [ ] 修改 SyncClient 启动流程，如启用 SSH 模式则启动 SSHTunnel
- [ ] 修改 SyncClient 关闭流程，优雅关闭 SSHTunnel
- [ ] 隧道未就绪时 sync_once 跳过 + 记录 WARNING 日志
- [ ] 隧道失败时不阻塞 SyncClient 启动（其他功能如 LLM 对话仍可用）
- [ ] SSH 模式下所有 httpx 请求透明走 localhost（通过参数传递 remote_url）
- [ ] HTTP 模式行为完全不变（向后兼容）
- [ ] 扩展 `test/core/integration/sync/test_sync_startup.py` 新增测试：
  - connection_mode == "ssh" + 隧道连接成功 → sync_once 正常执行 + remote_url 为 localhost
  - connection_mode == "ssh" + 隧道连接失败 → sync_once 跳过 + 记录 ERROR
  - connection_mode == "http" → 不启动隧道 + 走原 remote_url
  - run_mode != "full" → 不启动隧道（云端守卫）
  - 隧道未就绪时 sync_once 跳过 + 记录 WARNING
- [ ] 审计 sync_client.py 中所有 `get_setting("sync.remote_url")` 调用位置，确认通过 `_read_remote_url()`（参考 [sync-remote-url-access-rules.md 审计表](../../../docs/coding-rules/sync-remote-url-access-rules.md)）
- [ ] 遵循 [coding-rules/backend-core-rules.md](../../../docs/coding-rules/backend-core-rules.md) 和 [sync-remote-url-access-rules.md](../../../docs/coding-rules/sync-remote-url-access-rules.md) 规则
- [ ] 所有现有测试通过（无回归）

## Blocked by

- Issue 02: SSH 隧道配置 schema（需读 sync.connection_mode 和 ssh_tunnel_private_key）
- Issue 03: SSHTunnel 类（需调用 SSHTunnel 启动/关闭）
- Issue 04: SSH 隧道管理 API（**软依赖/顺序依赖**：enable 接口是前端切换模式时调用，SyncClient 启动时直接读 storage key 即可，不严格需要 API 端点。保留依赖是为了端到端可验证，实施时可并行）
