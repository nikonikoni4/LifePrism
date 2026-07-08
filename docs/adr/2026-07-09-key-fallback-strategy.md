---
version: 1.0
created_at: 2026-07-09
updated_at: 2026-07-09
last_updated: 2026-07-09
abstract: 密钥存储采用 keyring 优先 + config.yaml fallback 策略，否决 .env 环境变量方案。核心原因：.env 本质也是文件，而 config.yaml 已被 settings_manager 加载，无需引入额外依赖和加载逻辑。
status: decided
---

# 密钥存储策略：keyring + config.yaml Fallback vs 环境变量

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

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

## 后续影响

- 所有新增密钥类型都应遵循 keyring 优先 + config.yaml fallback 模式
- config.yaml 和 providers.yaml 的文件权限必须为 600（已在 Code Review 中修复）
- .gitignore 必须排除 config.yaml 和 providers.yaml（项目已有此配置）
- 如果未来云端迁移到容器化部署（Docker/K8s），可能需要重新评估是否改用环境变量（容器场景下环境变量注入更方便）
