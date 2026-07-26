---
version: 1.2
created_at: 2026-07-26
updated_at: 2026-07-26
changelog:
  - v1.2 修复 issues 审查发现的问题：移除 User Story 18（隧道状态实时显示，降级为通过测试连接按钮验证）；允许前端 UI 测试（因 SyncConfigSection.test.tsx 已存在）
  - v1.1 简化 SSH 模式交互：移除"生成密钥对"按钮，改为切换模式时自动生成；移除"查看公钥"按钮，公钥始终显示；移除部署脚本方案，改为前端展示命令文本
status: ready-for-agent
---

# PRD: SSH 隧道集成（SyncClient 端）

## Problem Statement

作为本地家庭网络的 LifePrism 用户，我的家庭网络公网 IP 经常变动，导致本地 SyncClient 经常连不上云端服务器的 8102 端口（防火墙规则需要频繁手动更新 CIDR）。

同时，云端 8102 端口当前默认暴露 HTTP 明文服务，同步 API Key 通过 `Authorization: Bearer` Header 明文传输，存在中间人抓包风险（已记录在 [docs/known-limitations/cloud-security-limitations.md](../../docs/known-limitations/cloud-security-limitations.md) 限制 4）。

国内服务器没有备案域名，无法申请 Let's Encrypt 证书走 HTTPS，需要一个不依赖域名、不依赖固定 IP 的方案，让本地客户端能够安全连接到云端同步 API。

## Solution

在 LifePrism 本地客户端内置 SSH 隧道能力，作为 HTTP/HTTPS 之外的第三种连接方式。SyncClient 启动时如启用 SSH 隧道，会通过 asyncssh 建立"本地端口转发"（local port forwarding），将本地一个端口（如 8102）通过 SSH 加密通道映射到云端服务器的 `127.0.0.1:8102`。SyncClient 随后访问 `http://localhost:8102` 即可，流量全程 SSH 加密。

前端设置页"数据同步"区域增加连接方式切换（HTTP/HTTPS vs SSH），参考已有"极简/复杂模式"的 UI 风格。SSH 隧道作为可选项，默认关闭，保持对现有 HTTP/HTTPS 流程的非侵入式兼容。

云端服务器 8102 端口绑定地址从 `0.0.0.0` 改为 `127.0.0.1`，关闭公网暴露，仅在服务器本机可见。SSH 公钥由用户手动配置到云端 `~/.ssh/authorized_keys`，与 cloud_init.yaml 流程无关。

### 交互简化原则（v1.1 核心）

- **私钥自动生成**：用户切换到 SSH 模式时如 keyring 无私钥则自动生成，无需"生成密钥对"按钮
- **公钥始终展示**：进入 SSH 配置页面时实时从 keyring 私钥派生公钥并显示，无需"查看公钥"按钮
- **命令前端展示**：云端 SSH 公钥配置命令直接在前端展示（含实际公钥值），用户复制粘贴执行，无需下载部署脚本

## User Stories

### 连接方式选择

1. 作为 LifePrism 用户，我想在设置页"数据同步"区域看到连接方式选项卡（HTTP/HTTPS vs SSH），以便根据网络环境选择合适的连接方式
2. 作为 LifePrism 用户，我想默认选择 HTTP/HTTPS（与现有行为一致），以便升级后不破坏已有配置
3. 作为 LifePrism 用户，我想切换到 SSH 模式时显示 SSH 配置表单（host/port/username 等），以便输入 SSH 连接参数
4. 作为 LifePrism 用户，我想切换连接方式时自动保存配置，以便无需额外点击保存按钮
5. 作为 LifePrism 用户，我想切换回 HTTP/HTTPS 模式时 SSH 配置保留（不删除），以便下次切回 SSH 时无需重新填写

### SSH 密钥管理

6. 作为 LifePrism 用户，我想切换到 SSH 模式时（且 keyring 中无私钥）自动生成 ed25519 密钥对，以便无需手动操作或使用命令行 ssh-keygen
7. 作为 LifePrism 用户，我想生成的私钥自动保存到本地 keyring（Windows 凭据管理器），以便私钥不暴露在文件系统中
8. 作为 LifePrism 用户，我想切换到 SSH 模式时如已有私钥则保留不覆盖，以便避免已部署到云端的公钥失效
9. 作为 LifePrism 用户，我想进入 SSH 配置页面时实时看到当前公钥（从 keyring 私钥派生），以便随时复制部署到云端
10. 作为 LifePrism 用户，我想公钥旁有"复制公钥"按钮一键复制到剪贴板，以便快速粘贴到云端 SSH 终端
11. 作为 LifePrism 用户，我想前端直接展示完整的云端 SSH 公钥配置命令（含实际公钥值），以便复制粘贴到云端终端执行
12. 作为 LifePrism 用户，我想"配置命令"旁有"复制命令"按钮一键复制完整命令，以便避免手动选中复制出错
13. 作为 LifePrism 用户，我想点击"测试连接"按钮验证 SSH 隧道能否建立，以便在保存配置前确认参数正确
14. 作为 LifePrism 用户，我想点击"测试连接"时同时验证云端 8102 端口可达，以便确认隧道 + 远程服务都正常

### SSH 隧道运行时

15. 作为 LifePrism 用户，我想 SyncClient 启动时自动建立 SSH 隧道（如启用），以便无需手动启动额外进程
16. 作为 LifePrism 用户，我想 SSH 隧道断开后自动重连，以便网络抖动后无需手动干预
17. 作为 LifePrism 用户，我想 SSH 隧道重连采用指数退避（如 5s/10s/20s/30s 上限），以便避免服务器被频繁连接请求冲击
18. 作为 LifePrism 用户，我想 SSH 隧道失败时不阻塞 SyncClient 启动，以便其他功能（如 LLM 对话）仍可使用
19. 作为 LifePrism 用户，我想 SSH 隧道失败时记录 ERROR 日志和明确原因（如"密钥被拒绝"/"网络不通"/"端口被占用"），以便快速排查问题
20. 作为 LifePrism 用户，我想关闭 LifePrism 时优雅关闭 SSH 隧道连接，以便不留孤儿进程
21. 作为 LifePrism 用户，我想 SSH 隧道启用时本地监听端口被占用能给出明确错误（如"端口 8102 已被其他程序占用"），以便快速定位冲突
22. 作为 LifePrism 用户，我想通过"测试连接"按钮手动验证隧道当前是否可用，以便在感知到同步异常时主动排查（隧道状态实时显示由未来 PRD 增强）

### SyncClient 集成

23. 作为 LifePrism 用户，我想 SSH 隧道启用时 SyncClient 自动使用 `http://localhost:local_port` 作为目标，以便无需修改 remote_url 配置
24. 作为 LifePrism 用户，我想 SSH 隧道禁用时 SyncClient 走原 `sync.remote_url`（HTTP/HTTPS），以便向后兼容
25. 作为 LifePrism 用户，我想 SSH 隧道启用时所有 httpx 请求透明地走隧道，以便不需要改任何业务代码
26. 作为 LifePrism 用户，我想 SSH 隧道建立后等待本地端口可用再触发首次同步，以便避免同步请求因隧道未就绪而失败
27. 作为 LifePrism 用户，我想 SSH 隧道未就绪时跳过本次同步并记录 WARNING，以便下次同步周期自动恢复

### 服务器端配置

28. 作为云端服务器管理员，我想 8102 端口默认绑定 `127.0.0.1`，以便公网无法直接访问同步 API
29. 作为云端服务器管理员，我想通过环境变量 `LIFEPRISM_API_HOST` 覆盖默认绑定地址（如 `0.0.0.0`），以便在测试或特殊场景下灵活配置
30. 作为云端服务器管理员，我想关闭服务器防火墙的 8102 公网规则后，SSH 隧道仍能正常工作，以便确认 8102 完全不暴露公网

### 安全性

31. 作为 LifePrism 用户，我想 SSH 私钥只存在本地 keyring，不出现在 config.yaml 或 storage.yaml，以便符合现有 Key 存储规范（参考 [ADR 2026-07-09](../../docs/adr/2026-07-09-key-fallback-strategy.md)）
32. 作为 LifePrism 用户，我想云端 agent_only 模式不会尝试加载 SSH 私钥（即使代码路径意外触发），以便云端 keyring 不可用时也不报错
33. 作为 LifePrism 用户，我想 SSH 隧道仅在 `run_mode == "full"` 时启用，以便云端 agent_only 模式根本不调用 SSHTunnel 相关代码
34. 作为 LifePrism 用户，我想 SSH 隧道使用 ed25519 密钥（而非 RSA），以便获得更高的安全性和更短的密钥长度
35. 作为 LifePrism 用户，我想 SSH 连接禁用密码认证（仅密钥认证），以便符合 SSH 加固最佳实践

## Implementation Decisions

### 模块划分

#### 新增模块：`lifeprism/sync/ssh_tunnel.py`

`SSHTunnel` 类，封装 asyncssh 连接和本地端口转发：

- `__init__(host, port, username, private_key, local_port, remote_host, remote_port)`
- `async connect() -> None`：建立 SSH 连接 + 启动本地端口转发
- `async close() -> None`：优雅关闭连接和转发
- `async start_keep_alive_loop() -> None`：心跳 + 断线重连循环（30 秒间隔，指数退避重连）
- `async test_connection() -> dict`：一次性测试连接（建立 + 验证远程可达 + 关闭），返回 `{"status": "ok", "remote_response": {...}}` 或失败原因。供 SSH 隧道管理 API 的 POST /test 端点调用，封装"建立→验证→关闭"完整测试逻辑，避免 API 层重复组合 connect/close
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

重连策略（决策点）：
- 心跳间隔：30 秒（参考 [test_sync_startup.py](../../test/core/integration/sync/test_sync_startup.py) 的 SSH 心跳间隔约定）
- 重连退避：5s → 10s → 20s → 30s（上限）
- 重连无最大次数限制（一直重试，直到 close() 被调用）

#### 修改模块：`lifeprism/sync/sync_client.py`

在 SyncClient 启动同步流程前增加隧道编排逻辑：

- 新增方法 `async _ensure_tunnel_ready() -> bool`：如启用 SSH 隧道则等待就绪，否则直接返回 True
- 修改 `_run_sync_loop` / `sync_once` 入口：调用 `_ensure_tunnel_ready()` 判断是否继续
- `remote_url` 在启用隧道时**临时替换为** `http://localhost:{local_port}`，不改原配置
- **`_read_remote_url()` 方法注释必须明确警告**：所有需要 remote_url 的代码路径必须通过此方法获取，禁止直接调用 `get_setting("sync.remote_url")`（详见规则文档 `docs/coding-rules/sync-remote-url-access-rules.md`）

**非侵入式保证**：所有 httpx.post/get 调用代码不变，仅在入口处条件性切换 `remote_url`。

#### 新增文档：`docs/coding-rules/sync-remote-url-access-rules.md`

非代码任务（编码文档维护）。新增后端规则文档，明确约束：

- 所有需要 remote_url 的代码路径**必须**通过 `SyncClient._read_remote_url()` 获取
- **禁止**直接调用 `get_setting("sync.remote_url")`（settings_manager 层不感知 SSH 隧道）
- 例外清单：前端展示、配置完整性检查（main.py:287 启动检查）、日志记录可读原始配置值
- 新增同步方法时的检查清单（如何确认走的是 `_read_remote_url()`）
- 违反约束的后果：SSH 隧道启用时该方法会绕过隧道直接走真实地址，导致同步失败或泄露真实 IP

文档结构参考 [tombstone-prevention-rules.md](../../docs/coding-rules/tombstone-prevention-rules.md)，包含触发条件、背景、核心规则、检查清单、例外清单。

文档创建后必须在 `docs/coding-rules/index.md` 注册索引（参考已有规则的索引格式）。

##### remote_url 拦截点决策（选项 C）

**决策**：在 `SyncClient._read_remote_url()` 方法中拦截，**不改 settings_manager、不改 API 层**。

**理由**：
- SyncClient 内部所有方法（约 20 个）通过参数传递 `remote_url`，源头都集中在 `_read_remote_url()` 一个方法
- 改一个方法即可让所有同步请求透明走 localhost
- settings_manager 保持纯净，不感知 SSH 隧道
- 前端展示的"云端地址"仍是用户填写的真实地址（如 `http://123.56.49.198:8102`），日志可读性不受影响

**拦截逻辑**：

```python
def _read_remote_url(self) -> str:
    """读取实际请求用的 remote_url（SSH 模式下走 localhost）"""
    if self._should_use_ssh_tunnel():
        if not self._is_tunnel_ready():
            logger.debug("跳过本次同步：SSH 隧道未就绪")
            return ""  # 触发上层"未配置 remote_url"跳过逻辑（已有）
        local_port = settings.get("sync.ssh_tunnel.local_port") or 8102
        return f"http://localhost:{local_port}"
    return get_setting("sync.remote_url") or ""

def _should_use_ssh_tunnel(self) -> bool:
    """三层守卫判断是否启用 SSH 隧道"""
    if settings.run_mode != "full":
        return False  # 云端不启用
    if settings.get("sync.connection_mode") != "ssh":
        return False  # 未启用 SSH 模式
    if not settings.get_storage_key("ssh_tunnel_private_key"):
        return False  # 无私钥
    return True

def _is_tunnel_ready(self) -> bool:
    """检查 SSH 隧道是否就绪"""
    return self._ssh_tunnel is not None and self._ssh_tunnel.is_connected
```

**sync.remote_url 在 SSH 模式下的语义**：

| 用途 | SSH 模式行为 |
|------|------------|
| 前端展示"云端地址" | ✅ 显示用户填的真实地址 |
| 配置完整性检查（main.py:287） | ✅ 非空检查自然通过（用户仍需填写） |
| 实际 HTTP 请求 | ❌ 不使用，走 `http://localhost:8102` |
| 日志记录 | ✅ 显示真实地址（便于排查"连的是哪台服务器"） |
| "测试连接"按钮 | ✅ 测试 SSH 隧道 + 远程 8102 可达性（不用 remote_url） |

**main.py:287 启动检查保持原逻辑**：SSH 模式下用户仍需填写 `sync.remote_url`（作为标识），所以原有检查自然通过，无需改造。

#### 修改模块：`lifeprism/config/settings_manager.py`

新增配置 schema 字段（非 Key 类，进 config.yaml）：

```yaml
sync:
  connection_mode: "http"  # "http" | "ssh"，默认 "http"
  ssh_tunnel:
    enabled: false           # 与 connection_mode == "ssh" 等价，作为冗余开关
    host: ""                 # SSH 服务器 IP
    port: 22                 # SSH 端口
    username: ""             # SSH 用户名
    local_port: 8102         # 本地监听端口
    remote_host: "127.0.0.1" # 远程目标主机
    remote_port: 8102        # 远程目标端口
```

新增 storage key（Key 类，走 keyring/storage.yaml 路由）：
- `ssh_tunnel_private_key`：SSH 私钥（PEM 格式字符串）

复用现有 `get_storage_key()` / `set_storage_key()` 接口，无需新增机制。云端 storage.yaml 不会写入此字段（因为云端不生成也不使用），天然隔离。

#### 修改模块：`lifeprism/server/main_agent_only.py`

8102 端口绑定地址从硬编码 `"0.0.0.0"` 改为读取环境变量：

```python
api_host = os.environ.get("LIFEPRISM_API_HOST", "127.0.0.1")
config = uvicorn.Config(
    app,
    host=api_host,
    port=8102,
    ...
)
```

默认 `127.0.0.1`（仅本机），可通过环境变量覆盖为 `0.0.0.0` 用于测试场景。

#### 新增模块：`lifeprism/server/api/ssh_tunnel_api.py`

提供 SSH 隧道管理 API（仅 full 模式注册路由）：

- `POST /api/v2/settings/ssh-tunnel/enable`：用户切换到 SSH 模式时调用。如 keyring 中无私钥则自动生成 ed25519 密钥对（私钥存 keyring，公钥丢弃不存储）；如有私钥则保留不覆盖。返回当前公钥（从私钥派生）
- `GET /api/v2/settings/ssh-tunnel/public-key`：从 keyring 私钥实时派生公钥并返回（用于前端展示）
- `POST /api/v2/settings/ssh-tunnel/test`：测试 SSH 连接 + 隧道建立 + 远程 8102 可达性

**关键设计**：移除独立的 `generate-keypair` API，将密钥生成逻辑合并到 `enable` 接口中，用户切换模式时自动完成密钥准备。

#### 修改模块：`lifeprism/server/main.py`

在 full 模式启动时注册 `ssh_tunnel_router`，agent_only 模式不注册。

#### 修改模块：`frontend/apps/settings/components/SyncConfigSection.tsx`

新增"连接方式"切换 UI（参考 SettingsApp.tsx 第 870-895 行的"极简/复杂模式"切换风格）：

- 选项卡 1：HTTP/HTTPS（保留现有云端地址输入 + 生成云端配置按钮）
- 选项卡 2：SSH 隧道（新增 SSH 参数表单 + 公钥展示区 + 配置命令展示区 + 测试连接按钮）

**SSH 选项卡 UI 元素清单**：

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
| 测试连接 | 按钮 | 调 POST /test 验证隧道 + 远程可达，显示一次性结果（成功/失败 + 原因） |

**注**：隧道状态实时显示（已连接/重连中/已断开）不在本 PRD 范围（参考 Out of Scope 第 15 项），由未来 PRD 增强。

**配置命令模板**（前端动态拼接，公钥值从 GET /public-key 响应中获取）：

```bash
# 在云端服务器执行以下命令（追加 SSH 公钥）
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '<public_key>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

切换时调用 PATCH /api/v2/settings 保存 `sync.connection_mode`。如切换到 SSH 模式，先调 POST /enable 触发密钥准备（如已存在则保留），再加载公钥展示。

### 数据流向

```
[本地前端]
用户切换到 SSH 模式
   ↓ POST /api/v2/settings/ssh-tunnel/enable
[本地后端]
   ├─ 检查 keyring 是否已有 ssh_tunnel_private_key
   │   ├─ 有 → 跳过生成（保留不覆盖）
   │   └─ 无 → asyncssh.generate_private_key('ssh-ed25519')
   │          └─ settings.set_storage_key("ssh_tunnel_private_key", private_key_pem)
   ├─ 从私钥派生公钥
   └─ 返回 {"public_key": "ssh-ed25519 AAAA...", "is_new": true/false}
   ↓
[本地前端]
加载公钥展示区 + 拼接配置命令模板
   ↓
[本地前端]
用户复制配置命令（含实际公钥）
   ↓ 用户手动 SSH 登录云端
   ↓ 粘贴执行命令（追加公钥到 authorized_keys）
   ↓
[本地前端]
填写 SSH host/port/username + 点击"测试连接"
   ↓ POST /api/v2/settings/ssh-tunnel/test
[本地后端]
   ├─ 从 keyring 读私钥
   ├─ asyncssh.connect()
   ├─ forward_local_endpoint('localhost', 8102, '127.0.0.1', 8102)
   ├─ httpx.get('http://localhost:8102/api/sync/health')
   └─ 关闭测试连接 + 返回成功/失败
   ↓
[本地前端]
保存 SSH 配置（PATCH /api/v2/settings 更新 connection_mode = "ssh"）
   ↓
[LifePrism 启动]
SyncClient 启动
   ├─ 检查 sync.connection_mode == "ssh"
   ├─ 启动 SSHTunnel
   ├─ 等待本地 8102 可用
   └─ 走 http://localhost:8102 同步
```

### SSH 私钥存储路由

复用现有 [ADR 2026-07-09 密钥存储策略](../../docs/adr/2026-07-09-key-fallback-strategy.md) v1.2：

| 模式 | storage_key 读取路径 | 行为 |
|------|---------------------|------|
| 本地 full | keyring（Windows 凭据管理器） | ✅ 返回私钥 |
| 本地 web_demo（开发模式） | keyring | ✅ 返回私钥（开发用） |
| 云端 agent_only | storage.yaml | ❌ 字段不存在 → 返回 None |

云端天然不会写入 `ssh_tunnel_private_key` 字段，因为：
1. SSH 隧道是本地客户端能力，云端不主动连接任何人
2. 私钥在本地生成（前端按钮触发），不会上传到云端
3. cloud_init.yaml 不涉及 SSH 私钥（参考[讨论澄清](#)）

### run_mode 守卫（双重保险）

参考 [schedule_service.py](../../lifeprism/server/services/schedule_service.py) 和 [sync_service.py](../../lifeprism/server/services/sync_service.py) 的 run_mode 守卫模式：

```python
# SSHTunnel 启动守卫（伪代码）
def should_start_tunnel() -> bool:
    if settings.run_mode != "full":
        return False  # 云端不启动隧道
    if settings.get("sync.connection_mode") != "ssh":
        return False  # 未启用 SSH 模式
    if not settings.get_storage_key("ssh_tunnel_private_key"):
        return False  # 无私钥
    return True
```

三层防护：
1. run_mode 守卫：云端根本不执行 SSH 隧道代码
2. connection_mode 守卫：未启用 SSH 模式不启动
3. 私钥存在性守卫：无私钥不启动

### 服务器端配置变更

8102 端口默认从 `0.0.0.0` 改为 `127.0.0.1`：

- 修改 [main_agent_only.py:320](../../lifeprism/server/main_agent_only.py#L320) `host="0.0.0.0"` → `host=os.environ.get("LIFEPRISM_API_HOST", "127.0.0.1")`
- 部署文档需更新：[cloud-https-setup.md](../../docs/deployment/cloud-https-setup.md) 移除"模式 B（uvicorn 直连）"章节，或标注为"不推荐，仅测试用"

### 异常处理

参考 [backend-error-handling rules](../../docs/coding-rules/backend-error-handling.md)：

- SSHTunnel 是中间层，捕获 asyncssh 异常转换为 `ExternalServiceError`
- API 层不 try/except，让异常冒泡到全局处理器
- 重连失败不抛出，记录 WARNING 后等待下次重试

### 依赖

新增 Python 依赖：`asyncssh>=2.14.0`（添加到 pyproject.toml）

asyncssh 选择理由：
- 异步原生（与 LifePrism asyncio 架构一致）
- 成熟稳定（PyPI 上活跃维护）
- 支持 ed25519 密钥
- 支持本地端口转发

## Testing Decisions

### 测试策略总览

**最高 seam 原则**：所有 SSH 隧道行为在 SSHTunnel 类层面验证完毕，SyncClient 层只验证"是否调用了 SSHTunnel"。

### 测试 seam

#### Seam 1（新建，单元测试）：`test/core/unit/sync/test_ssh_tunnel.py`

测试 SSHTunnel 类的外部可观察行为，**mock asyncssh**（不测真实 SSH 连接）。

测试覆盖：
- 状态机：disconnected → connecting → connected → reconnecting → failed
- `connect()` 成功建立连接 + 启动端口转发
- `connect()` 失败时状态变为 failed + 抛出 ExternalServiceError
- `close()` 优雅关闭连接和转发
- `start_keep_alive_loop()` 心跳保持
- 重连逻辑：断开后自动重试，指数退避（5s/10s/20s/30s）
- `is_connected` / `connection_state` 属性正确性
- 错误信息透明度：不同失败原因（密钥被拒绝/网络不通/端口被占用）映射到不同错误消息

Mock 策略：
- `unittest.mock.patch('asyncssh.connect')`
- `unittest.mock.patch('asyncssh.connect_forward_local')` 或等价 API
- AsyncMock 用于异步方法

参考现有测试：
- [test_sync_service_run_mode.py](../../test/core/unit/services/test_sync_service_run_mode.py)：run_mode 守卫测试模式
- [test_settings_storage.py](../../test/core/unit/config/test_settings_storage.py)：keyring 路由测试模式

#### Seam 2（扩展，集成测试）：`test/core/integration/sync/test_sync_startup.py`

扩展 SyncClient 启动测试，新增 SSH 隧道编排场景。

测试覆盖：
- `connection_mode == "ssh"` + 隧道连接成功 → sync_once 正常执行
- `connection_mode == "ssh"` + 隧道连接失败 → sync_once 跳过 + 记录 ERROR
- `connection_mode == "http"` → 不启动隧道 + 走原 remote_url
- `run_mode != "full"` → 不启动隧道（云端守卫）
- 隧道未就绪时 sync_once 跳过 + 记录 WARNING
- 隧道就绪后 remote_url 临时替换为 `http://localhost:8102`

Mock 策略：
- Mock SSHTunnel 类（不真实启动 asyncssh）
- Mock settings.run_mode 和 sync.connection_mode

#### Seam 3（扩展，单元测试）：`test/core/unit/config/test_settings_storage.py`

扩展 storage 路由测试，新增 `ssh_tunnel_private_key` 字段。

测试覆盖：
- 本地 full 模式：set_storage_key("ssh_tunnel_private_key", ...) 写入 keyring
- 云端 agent_only 模式：get_storage_key("ssh_tunnel_private_key") 返回 None（字段不存在）
- 私钥不在 config.yaml 中（仅 storage 路由）

#### Seam 4（扩展，集成测试）：`test/core/integration/test_agent_only_mode.py`

验证 8102 端口默认绑定 `127.0.0.1`。

测试覆盖：
- 默认配置：host 为 127.0.0.1
- 环境变量 LIFEPRISM_API_HOST=0.0.0.0：host 覆盖为 0.0.0.0

#### Seam 5（新建，API 测试）：`test/core/integration/api/test_ssh_tunnel_api.py`

测试 SSH 隧道管理 API（仅 full 模式注册）。

测试覆盖：
- POST /enable：
  - keyring 无私钥时自动生成 ed25519 密钥对 + 返回公钥 + is_new=true
  - keyring 已有私钥时保留不覆盖 + 返回派生公钥 + is_new=false
  - 返回的公钥格式正确（以 `ssh-ed25519 ` 开头）
- GET /public-key：
  - keyring 有私钥时返回派生公钥
  - keyring 无私钥时返回空字符串（不抛错）
- POST /test：mock SSHTunnel.test_connection，验证请求/响应契约
- 路由仅在 full 模式注册（agent_only 模式不暴露）

### 测试质量标准

**只测外部行为，不测实现细节**：
- ✅ 测 `tunnel.is_connected == True`（外部可观察）
- ❌ 不测 `tunnel._connection._transport.active`（内部实现）
- ✅ 测"调用 connect() 后再调用 close() 状态变为 disconnected"
- ❌ 不测"connect() 内部调用了 asyncssh.connect() 多少次"

**测试名称表达意图**：
- ✅ `test_connect_failure_sets_state_to_failed`
- ❌ `test_state_machine_transition_1`

### 不做的测试

- ❌ 不测真实 SSH 连接（外部依赖，CI 不稳定，需要测试服务器）
- ❌ 不测 httpx 实际请求（已被 test_sync_client.py 覆盖）
- ❌ 不测 asyncssh 库本身（信任第三方库）

### 前端 UI 测试策略

允许扩展 `frontend/apps/settings/components/SyncConfigSection.test.tsx` 新增 UI 测试（该文件已存在，遵循现有测试风格）。测试覆盖：
- 连接方式切换交互
- SSH 选项卡 UI 元素渲染
- API 调用契约（mock fetch）
- 复制按钮剪贴板操作

不测的 UI 部分：
- 视觉样式（颜色、布局）
- 浏览器兼容性
- 真实 API 联调（手动验证）

## Out of Scope

1. **云端 SSH 服务端配置**：安装 fail2ban、禁用密码登录、修改 sshd_config 等服务器加固由用户在部署文档指导下手动完成，不在 LifePrism 代码内自动化
2. **SSH 公钥自动部署到云端**：用户手动 SSH 登录云端追加到 `~/.ssh/authorized_keys`，不在 cloud_init.yaml 中传递（已与用户确认）
3. **SSH 部署脚本下载**：不提供 `setup_ssh.sh` 下载按钮，改为前端展示配置命令文本让用户复制粘贴执行（简化 UI，避免脚本维护）
4. **"生成 SSH 密钥对"独立按钮**：不提供独立按钮，密钥生成逻辑内嵌到"切换到 SSH 模式"动作中（如 keyring 无私钥则自动生成）
5. **"查看公钥"独立按钮**：不提供独立按钮，公钥始终展示在 SSH 配置页面（从 keyring 私钥实时派生）
6. **Nginx 反向代理部署**：本 PRD 仅解决"无域名场景下的安全连接"，Nginx + Let's Encrypt 方案在 [cloud-https-setup.md](../../docs/deployment/cloud-https-setup.md) 单独维护，两者可共存
7. **多端同时连接**：本 PRD 假设单台本地客户端连接云端，多端场景（如手机+电脑同时同步）每台独立建立 SSH 隧道，不共享隧道
8. **SSH 证书认证（CA 签发）**：仅支持用户级密钥对，不引入企业级 SSH CA 体系
9. **Tailscale/ZeroTier/WireGuard 集成**：其他虚拟内网方案不在本 PRD 范围
10. **HTTP/HTTPS 模式改造**：现有 HTTP/HTTPS 流程零改动，仅作为可选连接方式之一保留
11. **私钥密码保护（passphrase）**：ed25519 密钥不设 passphrase（自动化重连需要），如需 passphrase 保护由未来 PRD 增强
12. **私钥导入功能**：仅支持前端生成密钥对，不支持导入已有私钥（避免格式兼容问题）
13. **私钥轮换 UI**：不提供"重新生成密钥对"按钮，避免已部署到云端的公钥失效；如需轮换通过重置 settings 或命令行操作
14. **服务器 8102 绑定地址自动改 127.0.0.1**：用户需手动修改 main_agent_only.py 或通过环境变量配置，PRD 仅提供默认值变更
15. **隧道状态实时显示**：不提供 `GET /status` 端点和前端实时状态轮询；用户通过"测试连接"按钮手动验证隧道当前是否可用；同步失败时通过同步日志感知异常；实时状态显示由未来 PRD 增强

## Further Notes

### 安全收益

启用 SSH 隧道后：
1. **8102 端口公网完全不可见**（绑定 127.0.0.1），nmap 扫描无法发现
2. **API Key 通过 SSH 加密传输**，中间人无法抓包
3. **本地 IP 变动无影响**（SSH 是出站连接）
4. **API Key 泄露风险大幅降低**（即使泄露，攻击者也无法从公网访问 8102）

### 与 ADR 2026-07-14 决策的关系

[ADR 2026-07-14 同步端口 8102 必须走 HTTPS](../../docs/known-limitations/cloud-security-limitations.md) 的决策要求 HTTPS 加密传输。SSH 隧道方案是 HTTPS 的替代实现——SSH 加密同样满足"传输加密"的根本要求，且无需域名和证书。

部署文档需更新：[cloud-https-setup.md](../../docs/deployment/cloud-https-setup.md) 增加"模式 C：SSH 隧道（无域名场景）"章节，与模式 A（Nginx）和模式 B（uvicorn 直连）并列。

### 兼容性矩阵

| 场景 | 当前方案 | 本 PRD 后 |
|------|---------|----------|
| 本地有备案域名 | Nginx + HTTPS | ✅ 仍可用（HTTP/HTTPS 模式） |
| 本地无域名 + 固定 IP | uvicorn HTTPS + CIDR | ✅ 仍可用（HTTP/HTTPS 模式） |
| 本地无域名 + 动态 IP | ❌ 无法安全连接 | ✅ SSH 隧道（新增） |
| 本地无域名 + 频繁断网 | ❌ 无法自动恢复 | ✅ SSH 隧道 + autossh 重连 |

### 已知限制（待记录到 docs/known-limitations/）

1. **本地需要保持 SSH 隧道进程**：LifePrism 内置自动管理，但 LifePrism 关闭后隧道也关闭
2. **SSH 服务必须可用**：服务器 SSH 服务故障会导致同步中断
3. **私钥丢失后无法恢复**：keyring 中私钥删除后需要重新生成密钥对并配置云端 authorized_keys
4. **不支持私钥导入**：仅支持前端生成密钥对，已有私钥用户需手动配置（参考外部脚本方案）
5. **密钥保留不覆盖**：切换到 SSH 模式时如 keyring 已有私钥则保留，可能导致前端展示的公钥与云端 authorized_keys 中的公钥不一致（如用户在多台本地机器间切换 keyring）；需通过"测试连接"验证一致性
6. **无私钥轮换 UI**：不提供"重新生成密钥对"按钮，如需轮换需通过重置 settings 或命令行操作后重新配置云端 authorized_keys
7. **隧道状态非实时显示**：前端不实时显示隧道状态（已连接/重连中/已断开），需通过"测试连接"按钮手动验证；隧道断开时仅通过同步失败日志感知

### 后续可能的增强（不在本 PRD 范围）

- 私钥导入功能（支持已有密钥对）
- 多服务器配置（一个本地连接多个云端）
- SSH 证书认证（CA 签发，企业级）
- 隧道流量监控和统计
- 自动化服务器 SSH 加固（cloud_init.yaml 扩展）
- 隧道状态实时显示（新增 GET /status 端点 + 前端轮询，独立 PRD）
