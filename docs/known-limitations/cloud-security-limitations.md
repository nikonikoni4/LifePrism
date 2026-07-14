---
version: 1.0
created_at: 2026-07-14
updated_at: 2026-07-14
last_updated: 初始版本，记录云端部署中的明文存储安全限制
abstract: 记录 LifePrism 云端部署中存在的已知安全限制，包括微信用户 ID（wxid）和 API Key 在云端的明文存储问题。这些限制不影响当前功能正常运行，但应在未来版本中改进。
---

# 云端部署安全限制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

---

## 限制 1：微信用户 ID（wxid）明文存储

### 影响范围

- 文件路径：`{lifeprism_data_path}/channel/wechat/account.json`
- 数据内容：`user_data` 字典的 key 为 `{wxid}@im.wechat` 格式的微信用户标识（如 `o9cq803DD87j7zPs8NXdzazpx4Yc@im.wechat`）
- 对应代码：`lifeprism/llm/channel/wechat/channel.py:74-75`（`_user_data` 字典以 wxid 为 key）

### 安全风险

wxid 是微信用户的唯一标识符。如果攻击者获取到 wxid 和对应的 `context_token`，可以伪装成合法的微信用户，向 LifePrism AI 机器人发送消息并接收回复。这在云端部署场景下尤为敏感：
- 云端 `config.yaml` 和 `account.json` 均为明文存储
- 攻击者若突破服务器获取到这些文件，即可拿到所有必要的认证凭据

### 当前缓解

- 云端部署依赖 HTTPS 传输加密（API Key 在 HTTP Header 中传输）
- 云端 `config.yaml` 使用文件权限 `600` 限制本地访问
- `account.json` 改为数据库存储后（[Bug 记录](../history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md)），泄露面从文件系统缩小到数据库

### 计划改进

- 考虑对敏感数据（wxid、context_token、API Key）进行数据库级加密或文件级加密

---

## 限制 2：API Key 明文存储

### 影响范围

- 文件路径：`{lifeprism_data_path}/cloud_init.yaml`（临时配置）、`{config_base_path}/config.yaml`（最终配置）
- 数据内容：LLM Provider API Key（如 `api_key_anthropic`、`api_key_openai`）、WeChat Bot Token、数据同步 API Key
- 对应代码：`lifeprism/config/settings_manager.py` 的 Key 读取逻辑

### 当前机制

本地 Windows 场景使用 keyring（Windows 凭据管理器）存储 Key（`api_key_{provider_name}`、`wechat_bot_token`、`sync_api_key`），安全性相对较高。

云端 Linux 场景因无桌面环境，keyring 不可用，所有 Key fallback 到 `config.yaml` 明文存储。

### 安全风险

- 攻击者获取云端 `config.yaml` 后，可直接调用所有已配置的 LLM 服务（产生费用）
- 攻击者可利用微信 Bot Token 控制微信消息收发
- 同步 API Key 泄露可读写云端同步数据

### 当前缓解

- 云端 `config.yaml` 使用文件权限 `600` 限制本地访问
- `cloud_init.yaml` 在初始化完成后立即删除（`main_agent_only.py` CLI `reinit-config` 逻辑）
- **计划改进（2026-07-14 已决策）**：Key 从 config.yaml 分离到 storage.yaml，通过 run_mode 隔离读写。详见 ADR [密钥存储策略 v1.1](../adr/2026-07-09-key-fallback-strategy.md)

---

## 限制 3：同步 API Key 无法重新生成

### 影响范围

- 本地生成逻辑：`lifeprism/config/cloud_config_generator.py:72-87`（`_resolve_sync_api_key`）
- Key 读取逻辑：`lifeprism/sync/sync_config.py:16-38`（`get_sync_api_key`）
- 前端 API：`lifeprism/server/api/cloud_config_api.py:21`（`POST /api/sync/generate-cloud-config`）

### 当前状态

`cloud_config_generator.py:85` 使用 `secrets.token_urlsafe(32)` 生成密码学安全的随机 Key，代码本身是正确的。但 `_resolve_sync_api_key` 的读取链路存在问题：
- 调用 `get_sync_api_key()`，该函数优先从 keyring 读取，若不存在则 fallback 到 `config.yaml` 的 `sync_api_key` 字段
- 一旦 `config.yaml` 中存在该字段（如开发时手动写入的测试值 `test_heartbeat_key_abc123xyz`），`_resolve_sync_api_key` 会将其当作"已有的 Key"返回，`key_is_new = False`，不会触发重新生成
- 前端点击"生成云端配置"时，没有提供"是否更换 Key"的确认选项，用户无法主动更换已泄露或不够安全的同步 API Key

### 安全风险

- 弱 Key 一旦写入 config.yaml，会被永久固化为同步 API Key，除非用户手动删除 keyring 和 config.yaml 中的对应值
- 同步 API Key 是数据同步的唯一认证凭据，泄露后攻击者可读写云端同步数据

### 计划改进

- 前端增加确认键：生成云端配置时提示用户选择"保留当前 Key"还是"更换 Key"（[Bug 记录](../history-bugs/2026-07-14-sync-key-regeneration-and-config-fallback.md)）
- `get_sync_api_key` 不应从 `config.yaml` fallback 读取同步 API Key —— 已在 [密钥存储策略 ADR v1.1](../adr/2026-07-09-key-fallback-strategy.md) 中决策：本地只用 keyring，云端用 storage.yaml

---

## 限制 4：同步数据传输未启用 HTTPS

### 影响范围

- 本地配置：`sync.remote_url` 当前为 `http://` 而非 `https://`
- 实际部署：云端 port 8102 直接暴露 HTTP 服务，未配置 TLS 证书和 Nginx 反向代理
- 对应代码：`lifeprism/server/main_agent_only.py:313`（uvicorn 直接监听 HTTP）

### 安全风险

同步 API Key 通过 `Authorization: Bearer {key}` HTTP Header 传输。当前使用 HTTP 明文传输，任何能在网络路径上抓包的中间人都可以直接读取 Bearer Token，进而伪装为合法本地客户端读写云端同步数据。

PRD（`linux-deployment-prd.md:526`）明确要求"HTTPS 加密传输（必须）"，但当前部署未配置。

### 当前缓解

- **已决策（2026-07-14）**：同步端口 8102 必须走 HTTPS，作为默认配置。Nginx 在 443 端口终止 TLS，将 `/api/sync/` 转发到 uvicorn 8102。详见 [Nginx 配置指南](../deployment/nginx-setup.md) v1.1
- 本地 SyncClient 的 `sync.remote_url` 设为 `https://your-domain.com`（不带端口号，443 是默认 HTTPS 端口）

### 计划改进

- 服务器端：安装 Nginx + Let's Encrypt 证书，配置 `/api/sync/` → `http://127.0.0.1:8102` 反向代理（nginx-setup.md 已包含完整配置）
- 本地：`sync.remote_url` 前缀改为 `https://`

---

## 相关文档

- Bug 记录：[2026-07-14 数据同步链路未打通 + 文件 LWW 空文档反向覆盖](../history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md)
- Bug 记录：[2026-07-14 sync API Key 重生成 + config fallback](../history-bugs/2026-07-14-sync-key-regeneration-and-config-fallback.md)
- 思源笔记调研（附录在 Bug 记录中）：加密密钥隔离机制
- 同步配置生成：`.scratch/linux-deployment-discussion/linux-deployment-prd.md`（P2 第 6 节：配置管理）

---

## 限制 5：keyring 包在 Linux headless 环境可能不可用

### 影响范围

- 当前所有 Key（sync_api_key、wechat_token、Provider API Key）的读取链路都以 `import keyring` 为第一优先级
- 涉及文件：`sync_config.py:6`、`wechat/auth.py:12`、`provider_manager.py:17`、`settings_manager.py:16`
- 即使云端已设计"keyring 读不到 → fallback 到文件"的逻辑（如 `sync_config.py:24-37` 的 try/except），但 **`import keyring` 本身是顶层导入**，如果 Linux headless 环境中 keyring 包无法安装或安装后 import 失败，整个模块都无法加载

### 当前状态

`pyproject.toml` 中 keyring 是顶层依赖（第 17 行），所有平台统一安装。但 keyring 在 Linux headless 环境中依赖 `secretstorage` 后端，该后端需要 D-Bus 和 `gnome-keyring`/`kwallet` 等系统组件，headless 服务器可能不具备。

### 安全风险

- 云端部署若 keyring 无法安装，所有 Key 读取逻辑垮掉，需要全部 fall
