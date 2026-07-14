---
version: 1.1
created_at: 2026-07-09
updated_at: 2026-07-14
last_updated: v1.1——Key 从 config.yaml 分离到 storage.yaml，通过 run_mode 隔离本地/云端读写路径
abstract: 密钥存储从"keyring + config.yaml fallback"演进为"keyring（本地）+ storage.yaml（云端）"分离架构。核心原因：config.yaml fallback 导致弱 Key 永久固化，且混合了普通配置与敏感凭据。新增 storage.yaml（权限 600）专用于 Key 存储，命名避开 "keys.yaml" 以降低文件直接暴露时的敏感度。通过 run_mode 控制读写路径：本地（full）只用 keyring，云端（agent_only/web_demo）用 storage.yaml。
status: decided
---

# 密钥存储策略：keyring + config.yaml Fallback vs 环境变量

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.1 | Key 从 config.yaml 分离到 storage.yaml，通过 run_mode 隔离本地/云端读写路径。新增演进历史节，记录 v1.0 的 config.yaml fallback 带来的 Key 固化 bug |
| 1.0 | 创建文档初稿，决策 keyring + config.yaml fallback |

## 问题界定

### 问题简述

LifeWatch-AI 需要在 Windows 本地和 Linux 云端两种环境读取密钥（LLM API Key、微信 Token、同步 API Key）。本地有 keyring（Windows 凭据管理器），云端无桌面环境 keyring 不可用。需要决定云端密钥的存储方式。

### 讨论范围

- 3 种密钥的存储方式：LLM Provider API Key、微信 Token、同步 API Key
- 本地 vs 云端的密钥读取差异
- keyring fallback 到哪种文件格式：config.yaml vs .env

### 非讨论范围

- 密钥的生成逻辑（已在 Issue #07 的 CloudConfigGenerator 中实现）
- 密钥的传输安全（HTTPS，已在 PRD §5 中决定）
- 文件权限（已在 Code Review Issue #14 中修复为 600）

### 模糊信息的明确定义

- `keyring`：操作系统级别的密钥管理服务。Windows 使用"凭据管理器"，Linux 有 Secret Service API（但需要桌面环境 D-Bus）。云端 Linux 服务器通常无桌面环境，keyring 不可用。
- `.env` 文件：12-factor app 推荐的环境变量文件格式，需配合 `python-dotenv` 库在启动时加载到 `os.environ`。
- `config.yaml`：项目已有的配置文件，由 `settings_manager` 统一加载，已包含 llm、sync 等配置。

### 问题深度

涉及跨平台密钥管理的架构决策。选择影响所有密钥的读取路径，且后续所有新增密钥类型都要遵循同一策略。

## 现状

- 本地 Windows：所有密钥存储在 keyring 中，`provider_manager.get_api_key()` 和 `WechatAuth._load_token_from_keyring()` 直接调用 `keyring.get_password()`
- 云端 Linux：无 keyring，密钥需要从文件读取
- `config.yaml` 已被 `settings_manager` 加载，已有 `get_setting()` / `set_setting()` 接口
- `providers.yaml` 已被 `provider_manager` 加载，已有 provider 列表配置

## 可选方案

### 方案 A：keyring + config.yaml Fallback（已实现）

密钥读取时优先 keyring，失败后 fallback 到 config.yaml / providers.yaml。

**优势**

- config.yaml 已被 settings_manager 加载，零新增依赖
- 所有配置集中在一个文件，读取方便
- fallback 逻辑在数据返回层，其他代码零感知云端/本地差异
- 密钥和其他配置项在同一个文件中，部署时只需复制一个文件

**劣势**

- 密钥和普通配置混在一起，不够"标准化"（12-factor app 推荐密钥用环境变量）
- 如果 config.yaml 被误提交到 git，密钥会泄露（需靠 .gitignore + 文件权限 600 防护）

### 方案 B：keyring + .env Fallback

密钥读取时优先 keyring，失败后 fallback 到 `.env` 文件，通过 `python-dotenv` 加载到 `os.environ`。

**优势**

- 符合 12-factor app 实践，密钥和配置分离
- .env 是业界标准做法，新人容易理解
- `os.environ.get()` 是标准库，不需要自定义读取逻辑

**劣势**

- .env 本质也是文件，和 config.yaml 一样需要文件权限保护，安全性无实质差异
- 需引入 `python-dotenv` 依赖
- .env 是扁平的 key=value 格式，不支持嵌套结构（多个 LLM Provider 的 Key 需要扁平化命名如 `API_KEY_ANTHROPIC`、`API_KEY_OPENAI`）
- 需要额外的加载逻辑（启动时调用 `dotenv.load_dotenv()`），而 config.yaml 已在 settings_manager 中加载
- 部署时需要管理两个文件（config.yaml + .env），而非一个

### 方案 C：纯环境变量（systemd Environment=）

云端通过 systemd 服务的 `Environment=` 指令注入环境变量。

**优势**

- 密钥不出现在文件系统中
- 符合 Linux 服务部署实践

**劣势**

- 多个密钥管理不便（每个 Key 一行 Environment= 指令）
- 修改密钥需要编辑 systemd unit 文件并 `systemctl daemon-reload`
- 本地 Windows 无 systemd，仍需另一套方案（keyring），导致两套逻辑
- 不如 config.yaml 直观，排查问题时需要 `systemctl show` 或 `printenv`

## 最终决策

选择 **方案 A：keyring + config.yaml Fallback**。

## 决策原因

- 原因 1：.env 本质也是文件。用户指出".env 还是写入文件，和直接写在配置里有什么区别"。技术上看，.env 和 config.yaml 都需要文件权限保护，安全性无实质差异。区别仅在于格式（扁平 vs 嵌套）和加载方式（python-dotenv vs settings_manager），而 config.yaml 的加载已经在项目中实现。
- 原因 2：简单优先。用户判断"全部写在一个文件里到时候读取方便"。config.yaml 已被 settings_manager 加载，新增密钥只需在对应位置读取，无需引入新依赖或加载逻辑。.env 方案需要额外引入 python-dotenv、编写加载代码、管理扁平化命名约定，收益不明显。
- 原因 3：providers.yaml 已有 provider 列表结构。LLM API Key 天然属于 provider 的属性，写入 providers.yaml 的对应 provider 条目下（新增 `api_key` 字段）比扁平化到 .env 更自然。
- 原因 4：部署便捷。云端只需复制一个 cloud_init.yaml 文件，CloudInitializer 自动拆分写入 config.yaml 和 providers.yaml。如果用 .env，部署时需要多管理一个文件。

## 演进历史

| 版本 | 方案 | 解决的问题 | 引入的新问题 |
| ---- | ---- | ---------- | ------------ |
| v1.0 | keyring + config.yaml fallback | 云端 keyring 不可用时 Key 无处存放 | config.yaml fallback 被 `cloud_config_generator._resolve_sync_api_key()` 复用，导致 config.yaml 中手动写入的弱 Key 被永久固化为同步 API Key（`secrets.token_urlsafe(32)` 永不触发）。详见 Bug 记录 [2026-07-14-sync-key-regeneration-and-config-fallback](../history-bugs/2026-07-14-sync-key-regeneration-and-config-fallback.md) Bug 2 |
| v1.1 | keyring（本地）+ storage.yaml（云端）分离 | 根除 config.yaml fallback 导致的 Key 固化污染 | 新增 storage.yaml 文件需在部署流程中管理；需通过 run_mode 控制读写路径 |

## v1.1 修订：Key 分离到 storage.yaml

### 问题发现

v1.0 的 `get_sync_api_key()` 在 `cloud_config_generator._resolve_sync_api_key()` 和 `sync_cloud_api.verify_sync_api_key()` 两个场景复用，但这两个场景对"fallback 到 config.yaml"的需求完全相反：

- **验证场景**（verify_sync_api_key）：fallback 到 config.yaml 是**合理的**——云端部署时 keyring 不可用，必须从文件验证
- **生成场景**（_resolve_sync_api_key）：fallback 到 config.yaml 是**不该发生的**——生成新配置时，config.yaml 的值不应被当作"现有的 Key"。一旦 config.yaml 中存在该字段（如开发时手动写入的 `test_heartbeat_key_abc123xyz`），会被永久固化为同步 API Key

### 解决方案

将所有 Key 从 `config.yaml` 中分离，统一到专用文件 `storage.yaml`。通过 `run_mode` 控制读写行为。

### storage.yaml 命名理由

候选名 `keys.yaml` / `secrets.yaml` 被否决——从文件名一眼就能看出存放的是密钥，文件暴露时等于直接宣示"这里是所有凭据"。选择 **`storage.yaml`**：

- 看起来像普通存储配置文件，不直接暗示"密钥"
- 权限 `600` 作为第一道防线，文件名不暴露内容性质作为第二道防线（深度防御）
- 与已有 `providers.yaml`（Provider 配置）、`config.yaml`（应用配置）形成命名一致性（都是 `*.yaml`）

| 候选名 | 问题 |
|--------|------|
| `keys.yaml` | 直接宣示"这是密钥文件"，暴露时攻击者第一眼就看到关键目标 |
| `secrets.yaml` | 同上，一眼就知道内容敏感 |
| `storage.yaml` | 中性命名，降低识别度 ✅ |

### 文件结构

```yaml
# storage.yaml（仅 Key，文件权限 600）
sync_api_key: "N7kX..."
wechat_token: "wx_token_..."
providers:
  anthropic: "sk-ant-..."
  deepseek: "sk-ds-..."
```

位置：`{config_base_path}/storage.yaml`

### 读取层级

```
本地 (run_mode == "full")：
  sync_api_key       → keyring（没有就 None，不读任何文件）
  wechat_token        → keyring（没有就 None，不读任何文件）
  Provider API Key    → keyring（没有就 None，不读任何文件）

云端 (run_mode == "agent_only" | "web_demo")：
  sync_api_key       → storage.yaml
  wechat_token        → storage.yaml
  Provider API Key    → storage.yaml → providers.yaml（兜底）
```

### 写入层级

```
本地 (run_mode == "full")：
  所有 Key → 写入 keyring（不写任何文件）

云端 (run_mode == "agent_only" | "web_demo")：
  所有 Key → 写入 storage.yaml（keyring 不可用，不尝试写入）
```

### 涉及改动

| 文件 | 改动 |
|------|------|
| 新增 `storage.yaml` | `{config_base_path}/storage.yaml`，权限 600 |
| `sync_config.py:get_sync_api_key()` | `run_mode == "full"` → 只读 keyring；云端 → 读 storage.yaml |
| `wechat/auth.py:_load_token_from_keyring()` | 同上 |
| `provider_manager.py:get_api_key()` | 同上，云端再加一层 providers.yaml 兜底 |
| `cloud_config_generator.py` | cloud_init.yaml 输出 storage 段 |
| `cloud_initializer.py` | 初始化时 Key 写入 storage.yaml 而非 config.yaml |
| `config.yaml` | 移除 sync_api_key、wechat_token 字段（从 DEFAULTS 和现有文件中清理）|

**`providers.yaml` 不动**，它已有自己的结构和 fallback 层级。

## 后续影响

- 所有新增密钥类型都应遵循 `keyring（本地） + storage.yaml（云端）` 分离模式
- storage.yaml 和 providers.yaml 的文件权限必须为 600
- config.yaml 不再包含任何 Key 字段（sync_api_key、wechat_token 等已移除）
- .gitignore 必须排除 storage.yaml
- 部署流程中 cloud_init.yaml 的 storage 段由 CloudInitializer 写入 storage.yaml
- keyring 在 Linux headless 环境不可用，需配合 keyring 懒加载方案（见 Bug 记录 [2026-07-14-sync-key-regeneration-and-config-fallback](../history-bugs/2026-07-14-sync-key-regeneration-and-config-fallback.md) Bug 4）
- 如果未来云端迁移到容器化部署（Docker/K8s），可能需要重新评估是否改用环境变量（容器场景下环境变量注入更方便），但 storage.yaml 的中性命名策略在容器场景中同样适用（挂载为 volume 时文件名不暴露内容性质）
