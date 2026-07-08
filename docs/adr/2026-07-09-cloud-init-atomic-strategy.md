---
version: 1.0
created_at: 2026-07-09
updated_at: 2026-07-09
last_updated: 2026-07-09
abstract: cloud_init.yaml 初始化采用验证失败不删除策略，否决"失败即删除"和"失败即忽略"。核心原因：保留文件方便用户修复后重试，避免密钥丢失。
status: decided
---

# cloud_init.yaml 原子初始化策略

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

云端启动时读取 `cloud_init.yaml` 初始化配置。如果配置验证失败（缺少必需字段），需要决定是否删除该文件。

### 讨论范围

- 验证失败时的文件处理策略
- 初始化的原子性保证（config.yaml 和 providers.yaml 都写入成功才删除 cloud_init.yaml）
- monitor_type 强制覆盖逻辑

### 非讨论范围

- 密钥存储方式（已在 `2026-07-09-key-fallback-strategy.md` 中决定）
- 配置生成逻辑（已在 Issue #07 的 CloudConfigGenerator 中实现）

### 问题深度

涉及初始化失败后的恢复策略。错误的选择会导致密钥丢失（需要重新生成）或无限重试（每次启动都失败）。

## 现状

- `cloud_init.yaml` 包含所有密钥（LLM API Key、微信 Token、同步 API Key），由本地 CloudConfigGenerator 生成
- 用户需要手动将 `cloud_init.yaml` 复制到云端服务器
- CloudInitializer 读取后写入 `config.yaml` 和 `providers.yaml`
- 密钥一旦生成不可恢复（keyring 中的密钥在本地，云端无法重新读取）

## 可选方案

### 方案 A：验证失败不删除（已实现）

验证失败时抛出 ConfigError 并保留 `cloud_init.yaml`，用户修复后重试。

**优势**

- 密钥不丢失，用户修复配置后可以重新初始化
- 错误信息清晰，方便用户定位问题
- 只有 config.yaml 和 providers.yaml 都写入成功才删除

**劣势**

- 如果用户不修复，每次启动都会失败（但会给出明确错误信息）
- 文件残留需要用户手动处理

### 方案 B：失败即删除

验证失败时删除 `cloud_init.yaml`，用户需要重新生成。

**优势**

- 不会有残留文件

**劣势**

- 密钥丢失：密钥在本地 keyring 中，但用户可能已经关闭本地程序
- 用户需要重新在本地生成配置并复制到云端，流程繁琐
- 验证失败的原因可能很简单（拼写错误），删除文件是小题大做

### 方案 C：失败即忽略

验证失败时忽略错误，继续启动（使用已有的 config.yaml）。

**优势**

- 不阻塞启动

**劣势**

- 用户可能不知道配置初始化失败
- 密钥未写入 config.yaml，后续同步会失败（原因不明）
- 掩盖问题，不利于排查

## 最终决策

选择 **方案 A：验证失败不删除**。

## 决策原因

- 原因 1：密钥不可恢复。`cloud_init.yaml` 中的密钥由本地 keyring 生成，如果删除文件且本地程序已关闭，用户需要重新生成密钥并重新配置所有 Key，流程繁琐。保留文件让用户修复后重试是最安全的方案。
- 原因 2：原子性保证。只有 config.yaml 和 providers.yaml 都写入成功才删除 cloud_init.yaml。如果 config.yaml 写入成功但 providers.yaml 写入失败，cloud_init.yaml 仍然保留，下次启动可以重新初始化（覆盖已写入的 config.yaml）。
- 原因 3：错误信息透明。验证失败时抛出 ConfigError 并记录详细错误信息（缺少哪些字段），用户可以按提示修复 cloud_init.yaml 后重试。

## monitor_type 强制覆盖

CloudConfigGenerator 生成 `cloud_init.yaml` 时强制设置 `monitor_type: none`，CloudInitializer 初始化时和启动时都会校验 `monitor_type` 必须为 `none`。如果不是，自动修正并记录 WARNING。

这是为了确保云端禁用 Monitor 模块（Monitor 依赖 Windows API，在 Linux 上无法运行），与 `2026-07-08-linux-deployment-multiple-entrypoints.md` ADR 中的多入口架构一致。

## 后续影响

- 验证失败时启动会阻塞，用户需要 SSH 到云端修复 `cloud_init.yaml` 后重启服务
- 未来可以考虑增加 `--force-init` CLI 参数，跳过验证强制初始化（但当前不需要）
- `cloud_init.yaml` 在成功初始化后被删除，不会残留
