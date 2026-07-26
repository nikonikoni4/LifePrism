---
issue: 03
title: SSHTunnel 类 + 状态机 + 重连逻辑
triage: ready-for-agent
slice: 3
---

# SSHTunnel 类 + 状态机 + 重连逻辑

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

新增 `lifeprism/sync/ssh_tunnel.py` 模块，封装 asyncssh 连接和本地端口转发能力。这是 SSH 隧道的核心运行时，但本切片不集成到 SyncClient——只实现独立可测试的 SSHTunnel 类。

类设计：
- `SSHTunnel(host, port, username, private_key, local_port, remote_host, remote_port)`
- `async connect() -> None`：建立 SSH 连接 + 启动本地端口转发
- `async close() -> None`：优雅关闭连接和转发
- `async start_keep_alive_loop() -> None`：后台心跳 + 断线重连循环
- `async test_connection() -> dict`：一次性测试连接（建立 + 验证远程可达 + 关闭），返回 `{"status": "ok", "remote_response": {...}}` 或失败原因。封装"建立→验证→关闭"完整测试逻辑，供 Issue 04 的 POST /test 端点调用，避免 API 层重复组合 connect/close
- `is_connected` (property)：当前连接状态
- `connection_state` (property)：状态机枚举（disconnected / connecting / connected / reconnecting / failed）

状态机：
```
disconnected ──connect()──→ connecting ──成功──→ connected
                                 │                  │
                                 失败               断开
                                 ↓                  ↓
                              failed            reconnecting
                                 │                  │
                              close()          重试成功 → connected
                                                  │
                                              重试失败（上限）→ failed
```

重连策略：
- 心跳间隔：30 秒
- 重连退避：5s → 10s → 20s → 30s（上限）
- 重连无最大次数限制（一直重试，直到 close() 被调用）

异常处理遵循 [backend-error-handling rules](../../../docs/coding-rules/backend-error-handling.md)：捕获 asyncssh 异常转换为 `ExternalServiceError`，错误信息包含具体原因（"密钥被拒绝"/"网络不通"/"端口被占用"）。

## Acceptance criteria

- [ ] 新增 `lifeprism/sync/ssh_tunnel.py`，实现 SSHTunnel 类（含 connection_state 枚举）
- [ ] `connect()` 成功建立 SSH 连接 + 启动本地端口转发
- [ ] `connect()` 失败时状态变为 failed + 抛出 ExternalServiceError（含具体原因）
- [ ] `close()` 优雅关闭连接和转发，状态变为 disconnected
- [ ] `start_keep_alive_loop()` 后台运行心跳保活
- [ ] `test_connection()` 一次性测试：建立连接 + 验证远程 8102 可达（httpx.get /api/sync/health）+ 关闭连接，返回结果 dict
- [ ] 连接断开时自动进入 reconnecting 状态
- [ ] 重连采用指数退避（5s/10s/20s/30s 上限），不冲击服务器
- [ ] `is_connected` / `connection_state` 属性正确反映当前状态
- [ ] 错误信息透明：不同失败原因映射到不同错误消息（密钥被拒绝/网络不通/端口被占用）
- [ ] 新增 `test/core/unit/sync/test_ssh_tunnel.py` 单元测试，**mock asyncssh**（不测真实 SSH 连接）
- [ ] 测试覆盖：
  - 状态机所有转换路径（disconnected/connecting/connected/reconnecting/failed）
  - 重连退避时序（5s/10s/20s/30s）
  - 不同失败原因的错误信息
  - close() 优雅关闭
  - test_connection() 成功场景（远程 8102 可达）
  - test_connection() 失败场景（远程不可达 / 密钥被拒绝）
- [ ] 新增依赖 `asyncssh>=2.14.0` 到 `pyproject.toml`
- [ ] 遵循 [coding-rules/backend-core-rules.md](../../../docs/coding-rules/backend-core-rules.md) 和 [backend-error-handling](../../../docs/coding-rules/backend-error-handling.md) 规范
- [ ] 所有现有测试通过（无回归）

## Blocked by

- Issue 02: SSH 隧道配置 schema + 私钥走 keyring 存储路由（**软依赖/顺序依赖**：SSHTunnel 构造函数接受 `private_key` 参数，不直接读 storage key；理论上可独立实现和单元测试。保留依赖是为了切片顺序清晰，实施时可并行）
