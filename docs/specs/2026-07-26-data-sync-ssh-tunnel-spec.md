---
version: 1.1
created_at: 2026-07-26
updated_at: 2026-07-27
last_updated: 新增"Windows GSSAPI 禁用"设计决策（asyncssh.connect 传 gss_host='' 修复 PyInstaller 打包环境 win32timezone 缺失）；Functional Checklist 新增打包环境 SSH 隧道连接验证项；同步对齐 flow v1.1 反常设计 5
abstract: SSH 隧道子模块规格，定义 SSH 隧道（无域名场景下的安全传输通道）的连接管理 API、状态机、密钥存储、remote_url 拦截规则、运行模式守卫与 SyncClient 集成契约。作为 HTTP/HTTPS 之外的可选连接方式，非侵入式兼容现有同步流程。
---

# SSH 隧道同步模块 Spec

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.1 | 新增"Windows GSSAPI 禁用"设计决策（`asyncssh.connect` 传 `options=SSHClientConnectionOptions(gss_host='')`）；Functional Checklist 新增"打包环境 SSH 隧道能正常连接"验证项；同步对齐 flow v1.1 反常设计 5 |
| 1.0 | 创建 spec 初稿：定义 SSH 隧道连接管理 API、SSHTunnel 类对外接口、SyncClient SSH 集成方法、配置 Schema、状态机规则、设计决策与已知限制 |

## Overview

**业务问题**：本地家庭网络公网 IP 经常变动，导致本地 SyncClient 连不上云端 8102 端口（防火墙 CIDR 规则需要频繁更新）。同时云端 8102 默认暴露 HTTP 明文，同步 API Key 通过 `Authorization: Bearer` Header 明文传输，存在中间人抓包风险。国内服务器无备案域名，无法走 HTTPS。

**核心职责**：
- 在 LifePrism 本地客户端内置 SSH 隧道能力，作为 HTTP/HTTPS 之外的第三种连接方式
- 通过 SSH 加密的本地端口转发（local port forwarding）将本地端口映射到云端 `127.0.0.1:8102`
- 非侵入式兼容现有 HTTP/HTTPS 流程：SSH 模式作为可选项，默认关闭
- 私钥自动生成、安全存储（keyring）、公钥实时派生
- 隧道断开自动重连（指数退避），失败不阻塞 SyncClient 启动

**不做什么**：
- 不在云端部署 SSH 服务端（由用户在部署文档指导下手动配置）
- 不自动部署公钥到云端（用户手动 `echo >> authorized_keys`）
- 不提供"隧道状态实时显示"（由未来 PRD 增强）
- 不支持私钥导入、私钥轮换、passphrase 保护（见已知限制）

## Scope

### 范围内

- SSH 隧道连接管理（建立、关闭、重连、状态机）
- SSH 密钥管理（自动生成 ed25519、私钥存 keyring、公钥实时派生）
- SSH 隧道管理 API（enable / public-key / test 三个端点）
- SyncClient 与 SSH 隧道的集成（启动、关闭、remote_url 拦截、就绪检查）
- 远端 8102 端口绑定地址策略（默认 `127.0.0.1`，可通过环境变量覆盖）
- 配置 schema 字段（`sync.connection_mode`、`sync.ssh_tunnel.*`）
- 私钥存储路由（keyring storage key `ssh_tunnel_private_key`）

### 范围外

- **数据库同步核心流程**：参考 [data-sync-core-spec](./2026-07-16-data-sync-core-spec.md)
- **文件同步流程**：参考 [data-sync-files-spec](./2026-07-16-data-sync-files-spec.md)
- **云端部署流程**：参考 `docs/deployment/cloud-https-setup.md` 模式 C
- **remote_url 访问规则**：参考 [sync-remote-url-access-rules](../coding-rules/sync-remote-url-access-rules.md)
- **SSH 隧道已知限制**：参考 [ssh-tunnel-limitations](../known-limitations/ssh-tunnel-limitations.md)

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证。

### 连接方式切换

- [ ] 前端设置页"数据同步"区域显示连接方式选项卡（HTTP/HTTPS vs SSH 隧道）
- [ ] 默认选中 HTTP/HTTPS 模式（与现有行为一致，升级后不破坏已有配置）
- [ ] 切换连接方式时自动保存配置到 `sync.connection_mode`，无需额外点击保存按钮
- [ ] 切换回 HTTP/HTTPS 模式时 SSH 配置保留（不删除），下次切回 SSH 时不需重新填写
- [ ] 切换到 SSH 模式时显示 SSH 参数表单（host/port/username/local_port/remote_port）
- [ ] 切换失败时回滚 UI state 到原模式并 toast 提示错误

### SSH 密钥管理

- [ ] 切换到 SSH 模式时（且 keyring 中无私钥）自动生成 ed25519 密钥对
- [ ] 私钥自动保存到本地 keyring（Windows 凭据管理器），不出现在 config.yaml 或 storage.yaml
- [ ] 切换到 SSH 模式时如已有私钥则保留不覆盖（避免已部署到云端的公钥失效）
- [ ] 进入 SSH 配置页面时实时从 keyring 私钥派生公钥并显示
- [ ] 公钥旁有"复制公钥"按钮一键复制到剪贴板
- [ ] 前端直接展示完整的云端 SSH 公钥配置命令（含实际公钥值）
- [ ] 配置命令旁有"复制命令"按钮一键复制完整命令
- [ ] 公钥格式正确（以 `ssh-ed25519 ` 开头）

### SSH 配置保存

- [ ] 5 个 SSH 输入框（host/port/username/local_port/remote_port）失焦时自动保存到后端
- [ ] 重新进入设置页面或刷新页面后，SSH 配置能从后端正确读取并回填
- [ ] 端口输入框清空时不会传 NaN，保留原值
- [ ] 保存 SSH 配置复用 `PATCH /api/v2/settings` 接口，不新增端点

### SSH 隧道运行时

- [ ] SyncClient 启动时如启用 SSH 模式自动建立 SSH 隧道
- [ ] SSH 隧道启用时 SyncClient 自动使用 `http://localhost:{local_port}` 作为目标，不修改 `sync.remote_url` 配置
- [ ] SSH 隧道禁用时 SyncClient 走原 `sync.remote_url`（HTTP/HTTPS），向后兼容
- [ ] SSH 隧道断开后自动重连（指数退避 5s → 10s → 20s → 30s 上限）
- [ ] SSH 隧道失败时不阻塞 SyncClient 启动，其他功能（如 LLM 对话）仍可使用
- [ ] SSH 隧道失败时记录 ERROR 日志和明确原因（密钥被拒绝 / 网络不通 / 端口被占用）
- [ ] 关闭 LifePrism 时优雅关闭 SSH 隧道连接，不留孤儿进程
- [ ] SSH 隧道启用时本地监听端口被占用能给出明确错误（如"端口 8102 已被其他程序占用"）
- [ ] SSH 隧道未就绪时跳过本次同步并记录 WARNING，下次同步周期自动恢复
- [ ] Windows 打包环境（PyInstaller）下 SSH 隧道能正常连接，不因 `No module named 'win32timezone'` 失败（显式禁用 GSSAPI）

### 测试连接

- [ ] 点击"测试连接"按钮验证 SSH 隧道能否建立
- [ ] 测试连接同时验证云端 8102 端口可达（访问 `/api/sync/health`）
- [ ] 测试连接成功显示远程响应内容
- [ ] 测试连接失败显示具体原因和错误码
- [ ] 测试连接无论成功或失败都关闭连接（不留半开连接）

### 服务器端配置

- [ ] 云端 8102 端口默认绑定 `127.0.0.1`，公网无法直接访问同步 API
- [ ] 环境变量 `LIFEPRISM_API_HOST=0.0.0.0` 可覆盖默认绑定地址（用于测试或 Nginx 反代）

### 安全性

- [ ] SSH 私钥仅存在本地 keyring，不出现在 config.yaml 或 storage.yaml
- [ ] 云端 agent_only 模式不会尝试加载 SSH 私钥（即使代码路径意外触发）
- [ ] SSH 隧道仅在 `run_mode == "full"` 时启用
- [ ] SSH 隧道使用 ed25519 密钥（而非 RSA）
- [ ] SSH 连接使用密钥认证（不支持密码认证）

## Technical Contract

### SSHTunnel 类

封装 asyncssh 连接和本地端口转发，提供状态机和重连能力。

<key_function>
- lifeprism/sync/ssh_tunnel.py
  - ssh_tunnel.SSHTunnel.__init__:92
  - ssh_tunnel.SSHTunnel.connect:138
  - ssh_tunnel.SSHTunnel.close:261
  - ssh_tunnel.SSHTunnel.start_keep_alive_loop:295
  - ssh_tunnel.SSHTunnel.test_connection:354
  - ssh_tunnel.SSHTunnel.is_connected:128
  - ssh_tunnel.SSHTunnel.connection_state:134
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(host, port, username, private_key, local_port, remote_host, remote_port)` | 初始化 SSH 隧道配置 | private_key 必须是 PEM 格式字符串 |
| `async connect() -> None` | 建立 SSH 连接 + 启动本地端口转发 | 状态从 disconnected/failed → connecting → connected/failed；失败抛 `ExternalServiceError`（错误码：`SSH_KEY_REJECTED` / `SSH_NETWORK_UNREACHABLE` / `SSH_LOCAL_PORT_IN_USE` / `SSH_CONNECT_FAILED` / `SSH_FORWARD_FAILED` / `SSH_KEY_INVALID`） |
| `async close() -> None` | 优雅关闭 SSH 连接和端口转发 | 幂等：多次调用不抛异常；通知 keep_alive_loop 退出 |
| `async start_keep_alive_loop() -> None` | 后台心跳保活 + 断线重连循环 | 每 30 秒检查连接状态；断开进入 reconnecting 状态，按指数退避重连；退出条件：`close()` 被调用 |
| `async test_connection() -> dict` | 一次性测试连接（建立 + 验证远程可达 + 关闭） | 成功返回 `{"status": "ok", "remote_response": {...}}`；失败返回 `{"status": "error", "error": "...", "code": "..."}`（错误码同 connect 外加 `REMOTE_UNREACHABLE`） |
| `is_connected: bool` (property) | 当前是否已连接 | state == CONNECTED |
| `connection_state: ConnectionState` (property) | 当前状态机状态 | 枚举：DISCONNECTED / CONNECTING / CONNECTED / RECONNECTING / FAILED |

### SyncClient SSH 集成方法

<key_function>
- lifeprism/sync/sync_client.py
  - sync_client.SyncClient._should_use_ssh_tunnel:254
  - sync_client.SyncClient._is_tunnel_ready:273
  - sync_client.SyncClient._ensure_tunnel_ready:281
  - sync_client.SyncClient._start_ssh_tunnel:294
  - sync_client.SyncClient._stop_ssh_tunnel:349
  - sync_client.SyncClient._read_remote_url:382
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `_should_use_ssh_tunnel() -> bool` | 三层守卫判断是否启用 SSH 隧道 | 三层守卫：(1) `run_mode == "full"` (2) `sync.connection_mode == "ssh"` (3) `ssh_tunnel_private_key` 存在 |
| `_is_tunnel_ready() -> bool` | 检查隧道是否就绪 | `_ssh_tunnel is not None and _ssh_tunnel.is_connected` |
| `async _ensure_tunnel_ready() -> bool` | 非阻塞检查隧道就绪 | 非 SSH 模式直接返回 True；SSH 模式返回 `_is_tunnel_ready()` |
| `async _start_ssh_tunnel() -> None` | 启动 SSH 隧道（含 keep-alive 后台任务） | 失败捕获所有异常，记录 ERROR，不抛出（避免阻塞 SyncClient 启动） |
| `async _stop_ssh_tunnel() -> None` | 优雅关闭 SSH 隧道 | 幂等；关闭顺序：tunnel.close → 等待 keep-alive 任务退出（5s 超时） → 清理引用 |
| `_read_remote_url() -> str` | 读取实际请求用的 remote_url（SSH 模式下走 localhost） | **统一拦截入口**；SSH 模式 + 隧道就绪 → `http://localhost:{local_port}`；SSH 模式 + 隧道未就绪 → `""`（触发上层跳过）；HTTP/HTTPS 模式 → `sync.remote_url` 配置值 |

### SSH 隧道管理 API

提供 3 个 REST API 端点，仅 full 模式注册路由。

<key_function>
- lifeprism/server/api/ssh_tunnel_api.py
  - ssh_tunnel_api.enable_ssh_tunnel:55
  - ssh_tunnel_api.get_ssh_public_key:91
  - ssh_tunnel_api.test_ssh_tunnel:116
</key_function>

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/v2/settings/ssh-tunnel/enable` | POST | 启用 SSH 隧道模式（自动准备密钥） | 无 | `{"public_key": "ssh-ed25519 AAAA...", "is_new": bool}` |
| `/api/v2/settings/ssh-tunnel/public-key` | GET | 获取 SSH 公钥（从私钥实时派生） | 无 | `{"public_key": "ssh-ed25519 AAAA..."}` 或 `{"public_key": ""}`（无私钥） |
| `/api/v2/settings/ssh-tunnel/test` | POST | 测试 SSH 隧道连接 + 远程 8102 可达性 | `{"host": str, "port": int=22, "username": str, "local_port": int=8102, "remote_port": int=8102}` | `{"status": "ok", "remote_response": {...}}` 或 `{"status": "error", "error": str, "code": str}` |

**关键设计**：私钥不通过请求体传递，从 keyring 读取。

### 配置 Schema

#### config.yaml 字段（非敏感配置）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `sync.connection_mode` | str | `"http"` | 连接方式：`"http"`（HTTP/HTTPS） \| `"ssh"`（SSH 隧道） |
| `sync.ssh_tunnel.host` | str | `""` | SSH 服务器地址 |
| `sync.ssh_tunnel.port` | int | `22` | SSH 端口 |
| `sync.ssh_tunnel.username` | str | `""` | SSH 用户名 |
| `sync.ssh_tunnel.local_port` | int | `8102` | 本地监听端口 |
| `sync.ssh_tunnel.remote_host` | str | `"127.0.0.1"` | 远程目标主机 |
| `sync.ssh_tunnel.remote_port` | int | `8102` | 远程目标端口 |

#### storage key（敏感配置）

| storage_key | 存储位置 | 说明 |
|-------------|---------|------|
| `ssh_tunnel_private_key` | 本地 full 模式 → keyring；云端 agent_only → storage.yaml（字段不存在） | SSH 私钥 PEM 格式字符串 |

**云端天然不会写入此字段**，因为 SSH 隧道是本地客户端能力，云端不主动连接任何人，私钥在本地生成不会上传到云端，cloud_init.yaml 不涉及 SSH 私钥。

### 状态机规则

SSHTunnel 类的状态机抽象定义（具体实现路径在 flow 文档中）：

```
disconnected ──connect()──→ connecting ──成功──→ connected
                                 │                  │
                                 失败               断开
                                 ↓                  ↓
                              failed            reconnecting
                                 │                  │
                              close()          重试成功 → connected
                                                  │
                                              close() → disconnected
```

| 起始状态 | 触发动作 | 目标状态 |
|---------|---------|---------|
| `DISCONNECTED` | `connect()` 成功 | `CONNECTED` |
| `DISCONNECTED` / `FAILED` | `connect()` 调用中 | `CONNECTING` |
| `CONNECTING` | 连接或转发失败 | `FAILED` |
| `CONNECTED` | 连接断开（keep-alive 检测到） | `RECONNECTING` |
| `RECONNECTING` | 重连成功 | `CONNECTED` |
| 任意状态 | `close()` | `DISCONNECTED` |

**重连策略**：
- 心跳间隔：30 秒
- 退避序列：5s → 10s → 20s → 30s（上限）
- 无最大重试次数（直到 `close()` 被调用）

### 错误码契约

SSHTunnel 通过 `ExternalServiceError` 抛出错误，错误码用于 API 层结构化返回：

| 错误码 | 触发场景 | 用户提示 |
|--------|---------|---------|
| `SSH_KEY_INVALID` | 私钥解析失败（PEM 格式错误） | SSH 私钥解析失败 |
| `SSH_KEY_REJECTED` | 服务端拒绝公钥认证（PermissionDenied） | SSH 密钥被拒绝，请检查私钥与云端 authorized_keys |
| `SSH_NETWORK_UNREACHABLE` | 网络不通（OSError / ConnectionLost） | SSH 连接网络不通 |
| `SSH_LOCAL_PORT_IN_USE` | 本地监听端口被占用（ChannelListenError） | 本地端口 {local_port} 已被其他程序占用 |
| `SSH_CONNECT_FAILED` | 其他 asyncssh 连接错误 | SSH 连接失败 |
| `SSH_FORWARD_FAILED` | 其他端口转发错误 | SSH 端口转发失败 |
| `REMOTE_UNREACHABLE` | 隧道建立但远程健康端点不可达 | 远程端点 /api/sync/health 不可达 |

### 远端 8102 端口绑定

云端 `main_agent_only.py` 的 8102 端口绑定策略：

| 配置 | 绑定地址 | 行为 |
|------|---------|------|
| 默认 | `127.0.0.1` | 仅本机访问，关闭公网暴露（配合 SSH 隧道方案） |
| 环境变量 `LIFEPRISM_API_HOST=0.0.0.0` | `0.0.0.0` | 公网可访问（用于测试或 Nginx 反代场景） |

## Design Rationale

### remote_url 拦截点选择（选项 C）

**决策**：在 `SyncClient._read_remote_url()` 方法中拦截，**不改 settings_manager、不改 API 层**。

**理由**：
- SyncClient 内部所有方法（约 20 个）通过参数传递 `remote_url`，源头都集中在 `_read_remote_url()` 一个方法
- 改一个方法即可让所有同步请求透明走 localhost
- settings_manager 保持纯净，不感知 SSH 隧道
- 前端展示和日志记录仍显示用户填写的真实地址

**`sync.remote_url` 在 SSH 模式下的语义**：

| 用途 | SSH 模式行为 |
|------|------------|
| 前端展示"云端地址" | ✅ 显示用户填的真实地址 |
| 配置完整性检查（main.py 启动检查） | ✅ 非空检查自然通过（用户仍需填写） |
| 实际 HTTP 请求 | ❌ 不使用，走 `http://localhost:8102` |
| 日志记录 | ✅ 显示真实地址（便于排查"连的是哪台服务器"） |
| "测试连接"按钮 | ✅ 测试 SSH 隧道 + 远程 8102 可达性（不用 remote_url） |

### 非侵入式设计

SSH 隧道作为可选连接方式，对现有 HTTP/HTTPS 流程零侵入：

- 所有 httpx.post/get 调用代码不变，仅在入口处条件性切换 `remote_url`
- HTTP/HTTPS 模式下 `_should_use_ssh_tunnel()` 返回 False，所有 SSH 相关代码被跳过
- 配置字段 `sync.connection_mode` 默认 `"http"`，升级后不破坏已有配置
- 云端 agent_only 模式根本不注册 SSH 隧道 API 路由

### run_mode 守卫（三层防护）

参考 `schedule_service.py` 和 `sync_service.py` 的 run_mode 守卫模式：

1. **run_mode 守卫**：云端根本不执行 SSH 隧道代码（`settings.run_mode != "full"` 直接返回）
2. **connection_mode 守卫**：未启用 SSH 模式不启动（`sync.connection_mode != "ssh"` 直接返回）
3. **私钥存在性守卫**：无私钥不启动（`ssh_tunnel_private_key` 不存在直接返回）

### 密钥存储路由

复用 [ADR 2026-07-09 密钥存储策略](../adr/2026-07-09-key-fallback-strategy.md) v1.2：

| 模式 | storage_key 读取路径 | 行为 |
|------|---------------------|------|
| 本地 full | keyring（Windows 凭据管理器） | ✅ 返回私钥 |
| 本地 web_demo（开发模式） | keyring | ✅ 返回私钥（开发用） |
| 云端 agent_only | storage.yaml | ❌ 字段不存在 → 返回 None |

### asyncssh 库选择理由

- 异步原生（与 LifePrism asyncio 架构一致）
- 成熟稳定（PyPI 上活跃维护）
- 支持 ed25519 密钥
- 支持本地端口转发

### Windows GSSAPI 禁用（v1.1 新增）

**背景**：PyInstaller 打包环境未收集 `win32timezone`（pywin32 子模块），asyncssh 在 Windows 上默认初始化 GSSClient 会触发 `sspi → win32timezone` 导入链，抛 `ModuleNotFoundError`。asyncssh `connection.py:3317` 的 try/except 只捕获 `GSSError` 不捕获 `ModuleNotFoundError`，异常直接冒泡使 SSH 隧道连接失败。

**决策**：在 `SSHTunnel.connect()` 中显式传 `options=asyncssh.SSHClientConnectionOptions(gss_host='')`，利用 asyncssh `connection.py:3314` 的 `if gss_host:` 短路判断（空字符串为 falsy）跳过 GSSClient 实例化。

**为何不通过 `lifeprism.spec` hiddenimports 收集 pywin32 子模块**：
- `win32timezone` 可能只是冰山一角，`sspi.ClientAuth()` 内部可能还触发其他 pywin32 子模块导入（如 `win32security`、`win32cred`），需穷举所有子模块
- pywin32 升级或 asyncssh 升级可能引入新子模块依赖，维护成本高
- 项目用密钥认证，GSSAPI 是不需要的功能，禁用比打包完整依赖更符合最小依赖原则

**为何不在 `lifeprism.spec` 添加 asyncssh 到 hiddenimports**：asyncssh 是纯 Python 包，PyInstaller 静态分析理论上能自动发现。实际打包产物中 asyncssh 模块已正确包含（通过 PYZ 归档嵌入 exe），问题不在 asyncssh 本身而在其运行时调用的 pywin32 子模块。

**影响**：仅禁用 GSSAPI 认证（项目不使用），不影响密钥认证、kex_algs、known_hosts 验证、重连逻辑。

**相关位置**：
- `lifeprism/sync/ssh_tunnel.py:179`（`asyncssh.connect` 调用）
- `test/core/unit/sync/test_ssh_tunnel.py::test_connect_disables_gssapi`（回归测试）
- `docs/flows/2026-07-26-ssh-tunnel-flow.md` 反常设计 5
- `docs/history-bugs/2026-07-27-packaged-win32timezone-gssapi.md`（bug 历史记录）

### 已知限制

完整列表参考 [SSH 隧道已知限制](../known-limitations/ssh-tunnel-limitations.md)，核心 8 项：

1. 本地需要保持 SSH 隧道进程（LifePrism 关闭后隧道也关闭）
2. SSH 服务必须可用（sshd 故障会导致同步中断）
3. 私钥丢失后无法恢复（需重新生成密钥对并重新配置云端）
4. 不支持私钥导入（仅前端生成）
5. 密钥保留不覆盖（多端切换场景需通过"测试连接"验证一致性）
6. 无私钥轮换 UI（需通过重置 settings 或命令行操作）
7. 隧道状态非实时显示（仅通过"测试连接"按钮验证）
8. SSH 主机密钥验证未启用（`known_hosts=None`，存在 MITM 风险，需确保部署环境网络可信）

**相关 ADR**：
- [ADR 2026-07-09 密钥存储策略](../adr/2026-07-09-key-fallback-strategy.md)

## Interaction / UX Notes

### 前端 UI 结构

设置页"数据同步"区域增加连接方式切换（参考 SettingsApp.tsx 的"极简/复杂模式"切换风格）：

- **选项卡 1：HTTP/HTTPS**：保留现有云端地址输入 + 生成云端配置按钮
- **选项卡 2：SSH 隧道**：新增 SSH 参数表单 + 公钥展示区 + 配置命令展示区 + 测试连接按钮 + 生成云端配置按钮

### SSH 选项卡 UI 元素

| 元素 | 类型 | 说明 |
|------|------|------|
| SSH 主机 | 输入框 | 服务器 IP |
| SSH 端口 | 输入框 | 默认 22 |
| SSH 用户名 | 输入框 | 如 "lifeprism" |
| 本地监听端口 | 输入框 | 默认 8102 |
| 远程目标端口 | 输入框 | 默认 8102 |
| 公钥展示区 | 只读文本框 | 进入页面时调 GET /public-key 加载 |
| 复制公钥 | 按钮 | 一键复制公钥到剪贴板 |
| 配置命令展示区 | 只读文本框 | 模板含实际公钥值，前端动态拼接 |
| 复制命令 | 按钮 | 一键复制完整命令到剪贴板 |
| 测试连接 | 按钮 | 调 POST /test 验证隧道 + 远程可达 |
| 生成云端配置 | 按钮 | 复用 HTTP 模式逻辑，SSH 模式下同样需要 cloud_init.yaml |

### 配置命令模板

前端动态拼接，公钥值从 GET /public-key 响应中获取：

```bash
# 在云端服务器执行以下命令（追加 SSH 公钥）
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '<public_key>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 交互简化原则

- **私钥自动生成**：用户切换到 SSH 模式时如 keyring 无私钥则自动生成，无需"生成密钥对"按钮
- **公钥始终展示**：进入 SSH 配置页面时实时从 keyring 私钥派生公钥并显示，无需"查看公钥"按钮
- **命令前端展示**：云端 SSH 公钥配置命令直接在前端展示（含实际公钥值），用户复制粘贴执行，无需下载部署脚本
- **失焦自动保存**：5 个 SSH 输入框失焦时自动保存到后端，无需额外点击保存按钮

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **数据库同步核心流程**：[data-sync-core-spec](./2026-07-16-data-sync-core-spec.md) - 29 张静态表增量同步、动态表双向建表、墓碑同步、心跳管理
- **文件同步流程**：[data-sync-files-spec](./2026-07-16-data-sync-files-spec.md) - 文件双向同步、三阶段 API 协议、冲突解决
- **数据同步总览**：[data-sync-overview](./2026-07-16-data-sync-overview.md) - 子模块划分和依赖关系
- **remote_url 访问规则**：[sync-remote-url-access-rules](../coding-rules/sync-remote-url-access-rules.md) - 编码约束（禁止绕过 `_read_remote_url()`）
- **SSH 隧道已知限制**：[ssh-tunnel-limitations](../known-limitations/ssh-tunnel-limitations.md) - 8 项已知限制和后续增强计划
- **云端部署流程**：`docs/deployment/cloud-https-setup.md` 模式 C - 完整部署步骤
- **密钥存储策略 ADR**：[2026-07-09-key-fallback-strategy](../adr/2026-07-09-key-fallback-strategy.md) - storage key 路由机制
