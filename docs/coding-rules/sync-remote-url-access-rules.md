---
version: 1.0
created_at: 2026-07-26
updated_at: 2026-07-26
last_updated: 初版，配合 SSH 隧道集成（PRD: .scratch/ssh-tunnel-integration/prd.md）建立 remote_url 访问约束
abstract: 面向修改 SyncClient 和新增同步方法的开发者与 AI，规定所有需要 remote_url 的代码路径必须通过 SyncClient._read_remote_url() 获取，禁止直接调用 get_setting("sync.remote_url")，防止 SSH 隧道启用时同步请求绕过隧道导致连接失败或泄露真实服务器地址。
---

# SyncClient remote_url 访问规则

## 触发条件

遇到以下任一场景时，必须阅读并遵循本文档：

- 新增 SyncClient 的同步方法（如新的 `_pull_xxx` / `_push_xxx` 流程）
- 修改已有 SyncClient 方法的 `remote_url` 获取方式
- 在 SyncClient 之外新增需要发起 HTTP 请求到云端的代码（如工具类、辅助函数）
- 修改 `SyncClient._read_remote_url()` 方法本身
- 修改 `sync.connection_mode` 或 SSH 隧道相关配置 schema
- 在 API 层、Service 层、Repository 层新增需要读取 `sync.remote_url` 的代码

本文档配合 [`backend-core-rules.md`](./backend-core-rules.md) 和 [`backend-api-rules.md`](./backend-api-rules.md)；后者关注通用编码和 API 设计，本文档关注**remote_url 必须通过统一入口获取**的预防性约束。

## 背景

PRD `.scratch/ssh-tunnel-integration/prd.md` 引入 SSH 隧道模式作为 HTTP/HTTPS 之外的第三种连接方式。SSH 隧道启用时：

- SyncClient 实际请求目标变为 `http://localhost:{local_port}`（通过 SSH 隧道转发到云端 `127.0.0.1:8102`）
- 用户在 `sync.remote_url` 中填写的真实地址（如 `http://123.56.49.198:8102`）**仅作标识用**，不用于实际请求

拦截点选在 `SyncClient._read_remote_url()`（选项 C），原因：

- SyncClient 内部所有方法（约 20 个）通过参数传递 `remote_url`，源头都集中在 `_read_remote_url()` 一个方法
- 改一个方法即可让所有同步请求透明走 localhost
- settings_manager 保持纯净，不感知 SSH 隧道
- 前端展示和日志记录仍显示用户填写的真实地址

**关键约束**：这个设计的正确性依赖"所有实际发起 HTTP 请求的代码都通过 `_read_remote_url()` 获取 remote_url"。一旦有代码绕过此方法直接调用 `get_setting("sync.remote_url")`，SSH 隧道启用时该代码会走真实地址，导致：

1. **连接失败**：真实地址的 8102 端口已绑定 127.0.0.1，公网不可达
2. **安全风险**：泄露真实服务器 IP，攻击者可扫描 SSH 端口
3. **行为不一致**：部分同步流程走隧道，部分不走，难以排查

## 核心规则

### 规则 1：所有 remote_url 获取必须通过 `SyncClient._read_remote_url()`

在 SyncClient 内部任何方法中需要 `remote_url` 时：

```python
# ✅ 正确：通过 _read_remote_url() 获取
def my_new_sync_method(self):
    remote_url = self._read_remote_url()  # 走统一入口
    if not remote_url:
        return  # SSH 隧道未就绪或未配置 remote_url
    api_key = get_sync_api_key()
    response = httpx.post(
        url=f"{remote_url}/api/sync/my-new-endpoint",
        headers={"Authorization": f"Bearer {api_key}"},
    )

# ❌ 错误：直接调用 get_setting
def my_new_sync_method(self):
    remote_url = get_setting("sync.remote_url")  # 绕过 SSH 隧道拦截
    response = httpx.post(...)  # SSH 模式下走真实地址，连接失败
```

### 规则 2：禁止直接调用 `get_setting("sync.remote_url")` 用于发起 HTTP 请求

以下场景**严格禁止**直接读取 `sync.remote_url`：

| 场景 | 禁止原因 |
|------|---------|
| SyncClient 内部发起 HTTP 请求 | 绕过 SSH 隧道拦截 |
| 工具类、辅助函数发起 HTTP 请求到云端 | 同上 |
| Service 层直接调用云端 API | 同上 |
| Repository 层直接调用云端 API | 同上（且违反分层架构） |
| API 层直接调用云端 API | 同上 |

### 规则 3：例外清单（允许直接读取 `sync.remote_url`）

以下场景**允许**直接读取 `sync.remote_url`，因为它们不发起 HTTP 请求：

| 场景 | 用途 | 允许原因 |
|------|------|---------|
| 前端展示"云端地址" | UI 显示用户填的真实地址 | 不发起请求，仅展示 |
| 配置完整性检查（main.py:287 启动检查） | 验证 remote_url 非空 | 不发起请求，仅校验 |
| 日志记录（如"连的是哪台服务器"） | 排查问题时显示真实地址 | 不发起请求，仅记录 |
| `SyncClient._read_remote_url()` 内部 | 实际拦截入口 | 这是统一入口本身 |

**判断标准**：代码是否调用 `httpx.post` / `httpx.get` / `httpx.AsyncClient` 等 HTTP 客户端？

- 是 → 必须通过 `_read_remote_url()`
- 否 → 可直接读取（属于例外）

### 规则 4：新增同步方法的检查清单

编写新的同步方法时，逐项确认：

- [ ] 方法是否在 SyncClient 内部？
- [ ] 若是，是否通过 `self._read_remote_url()` 获取 remote_url？
- [ ] 若在 SyncClient 之外，是否复用 SyncClient 实例的方法？（而不是另起炉灶读 settings）
- [ ] 是否处理了 `remote_url == ""` 的情况？（SSH 隧道未就绪时返回空字符串）
- [ ] 方法签名是否接受 `remote_url: str` 参数？（与现有方法风格一致，便于参数传递）
- [ ] 是否在调用链顶层（如 `sync_once`）获取 remote_url 后通过参数传递？（避免每层都读 settings）

### 规则 5：违反约束的后果

若代码绕过 `_read_remote_url()` 直接读取 `sync.remote_url` 并发起 HTTP 请求：

| 后果 | 影响范围 |
|------|---------|
| SSH 隧道模式下连接失败 | 真实地址 8102 端口绑定 127.0.0.1，公网不可达 |
| 同步流程部分失效 | 走隧道的方法正常，绕过隧道的方法失败，行为不一致 |
| 排查困难 | 日志显示"连接超时"但无明显错误原因 |
| 安全风险 | 真实服务器 IP 暴露在请求中，可能被中间人记录 |
| 隧道状态判断失效 | SSH 隧道显示"已连接"但实际请求不走隧道 |

### 规则 6：`_read_remote_url()` 方法注释要求

`SyncClient._read_remote_url()` 方法的文档字符串必须包含以下警告：

```python
def _read_remote_url(self) -> str:
    """读取实际请求用的 remote_url（SSH 模式下走 localhost）

    ⚠ 警告：所有需要 remote_url 的代码路径必须通过此方法获取，
    禁止直接调用 get_setting("sync.remote_url")。
    SSH 隧道启用时，直接读取 settings 会绕过隧道拦截，导致连接失败。
    详见 docs/coding-rules/sync-remote-url-access-rules.md

    返回值语义：
    - HTTP/HTTPS 模式：返回 sync.remote_url 配置值
    - SSH 隧道模式 + 隧道就绪：返回 http://localhost:{local_port}
    - SSH 隧道模式 + 隧道未就绪：返回空字符串（触发上层跳过逻辑）
    """
```

## 审计参考

当前代码库中 `sync.remote_url` 的所有调用位置：

| 文件 | 行号 | 用途 | 是否合规 |
|------|------|------|---------|
| `lifeprism/config/settings_manager.py` | 91 | 默认值定义 | ✅ 配置 schema |
| `lifeprism/server/main.py` | 292 | `send_heartbeat` 启动/关闭心跳通知 | ✅ 例外（生命周期通知，非同步流程） |
| `lifeprism/server/api/sync_status_api.py` | 59 | 同步状态展示（sync_status_api） | ✅ 例外（仅展示，不发起请求） |
| `lifeprism/sync/sync_client.py` | 159 | `send_ping` 心跳检查 | ✅ 走 `_read_remote_url()` |
| `lifeprism/sync/sync_client.py` | 222 | `_run_sync_loop` 定时同步入口 | ✅ 走 `_read_remote_url()` |
| `lifeprism/sync/sync_client.py` | 383 | `_read_remote_url()` 本身 | ✅ 统一入口 |
| `lifeprism/sync/sync_client.py` | 430 | `sync_once` 主流程 | ✅ 走 `_read_remote_url()` |

审计已完成，所有发起 HTTP 请求的 SyncClient 代码路径均通过 `_read_remote_url()` 获取 remote_url。新增同步方法时仍需遵循上述规则。

## 相关文档

- [PRD: SSH 隧道集成](../../.scratch/ssh-tunnel-integration/prd.md)
- [规则: 后端核心规则](./backend-core-rules.md)
- [规则: API 设计规则](./backend-api-rules.md)
- [规则: 同步友好建表规则](./sync-friendly-table-design.md)
- [规则: 墓碑同步预防性规则](./tombstone-prevention-rules.md)
- [已知限制: 云端部署安全限制](../known-limitations/cloud-security-limitations.md)
- [ADR: 密钥存储策略](../adr/2026-07-09-key-fallback-strategy.md)
