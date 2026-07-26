---
version: 1.1
created_at: 2026-07-26
updated_at: 2026-07-26
last_updated: 新增限制 8（SSH 主机密钥验证未启用 / MITM 风险），限制总数 7 → 8
abstract: 记录 LifePrism SSH 隧道连接模式（无域名场景）下的 8 项已知限制。这些限制是当前 PRD 范围下的设计选择，不影响 SSH 隧道的核心功能可用性，但用户在使用和运维时应知晓。
---

# SSH 隧道已知限制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿，记录 7 项 SSH 隧道已知限制 |
| 1.1 | 新增限制 8：SSH 主机密钥验证未启用（MITM 风险），限制总数 7 → 8 |

---

## 概述

LifePrism SSH 隧道模式（部署文档"模式 C"）为无备案域名 + 动态 IP 的本地客户端提供了无需证书的安全连接方案。完整部署流程见 [`../deployment/cloud-https-setup.md`](../deployment/cloud-https-setup.md) "模式 C 配置"章节。

本文档记录该方案当前 PRD 范围下的 8 项已知限制。这些限制源自 [`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md) 的 Out of Scope 决策，是当前阶段有意接受的设计选择。

---

## 限制 1：本地需要保持 SSH 隧道进程

### 问题描述

SSH 隧道是本地 SyncClient 启动时通过 asyncssh 建立的"本地端口转发"会话，依赖 LifePrism 进程持续运行。LifePrism 关闭后 SSH 隧道也随之关闭，云端 8102 端口在隧道关闭期间不可达。

### 影响范围 + 严重程度

- **影响范围**：模式 C 下所有同步流量
- **严重程度**：中（LifePrism 关闭期间无同步需求，但用户可能误以为隧道独立运行）

### 当前假设

- 系统假设"LifePrism 进程在运行 = SSH 隧道在运行"
- LifePrism 内置自动管理隧道生命周期，不依赖 autossh 等外部进程

### 触发条件

- 用户关闭 LifePrism 客户端
- LifePrism 进程崩溃后未自动重启（如 systemd 未配置 Restart=on-failure）

### 临时方案或计划改进

- **当前方案**：LifePrism 启动时自动建立隧道，关闭时优雅关闭隧道，无需用户干预
- **未来增强**：如需独立隧道进程，可手动使用 `ssh -L 8102:127.0.0.1:8102 user@host -N` 在外部终端启动，绕过 LifePrism 管理（不在本 PRD 范围）

### 相关文档

- 部署文档：[`../deployment/cloud-https-setup.md`](../deployment/cloud-https-setup.md) C.5 节"SSH 隧道运行时行为"

---

## 限制 2：SSH 服务必须可用

### 问题描述

SSH 隧道依赖云端服务器的 SSH 服务（默认 22 端口）持续可用。任何导致 SSH 服务故障的因素都会中断同步。

### 影响范围 + 严重程度

- **影响范围**：模式 C 下所有同步流量
- **严重程度**：高（SSH 服务故障 = 同步完全中断）

### 当前假设

- 云端 SSH 服务（sshd）持续运行且配置正确
- 云端 22 端口公网可达
- 网络中间链路无持续阻断

### 触发条件

- 云端 sshd 进程崩溃或被 kill
- sshd_config 配置错误（如误改 `PermitRootLogin`、`PasswordAuthentication` 后未重启 sshd）
- 云服务商安全组临时关闭 22 端口
- 服务器主机宕机或重启后 SSH 服务未自启

### 临时方案或计划改进

- **当前方案**：LifePrism SyncClient 检测到隧道断开后自动重连（指数退避 5s → 10s → 20s → 30s 上限），不阻塞其他功能；同步失败时记录 ERROR 日志，用户可通过同步日志感知异常
- **运维建议**：建议在云端启用 `systemctl enable sshd` 确保 SSH 服务开机自启；配置 fail2ban 防止暴力破解导致 sshd 被频繁连接冲击
- **未来增强**：未来 PRD 可能新增 `GET /api/v2/settings/ssh-tunnel/status` 端点 + 前端轮询实时显示隧道状态（不在本 PRD 范围）

### 相关文档

- 部署文档：[`../deployment/cloud-https-setup.md`](../deployment/cloud-https-setup.md) C.2.3 节"SSH 服务加固建议"
- 已知限制：[`./cloud-security-limitations.md`](./cloud-security-limitations.md)

---

## 限制 3：私钥丢失后无法恢复

### 问题描述

SSH 私钥保存在本地 keyring（Windows 凭据管理器），不参与云端同步，也无备份机制。一旦 keyring 数据丢失（如系统重装、用户账户删除、keyring 损坏），私钥无法恢复。

### 影响范围 + 严重程度

- **影响范围**：模式 C 下同步功能
- **严重程度**：中（私钥丢失后需重新配置，但不影响云端数据）

### 当前假设

- 系统假设"本地 keyring 数据持久可靠"
- keyring 是 Windows 系统级凭据存储，正常使用不会丢失

### 触发条件

- 用户重装 Windows 系统
- 用户删除 Windows 账户或重置凭据管理器
- keyring 后端损坏（极少见）

### 临时方案或计划改进

- **当前方案**：私钥丢失后无法恢复，需按以下步骤重新配置：
  1. 在 LifePrism 设置页清空 `ssh_tunnel_private_key`（或重置 settings）
  2. 切换到 SSH 模式时系统自动生成新的 ed25519 密钥对
  3. 复制新公钥到云端 `~/.ssh/authorized_keys`（建议同时删除旧的失效公钥条目）
  4. 点击"测试连接"验证新密钥对工作正常
- **未来增强**：私钥导入功能（参考 Out of Scope 第 12 项）由未来 PRD 评估

### 相关文档

- ADR 密钥存储策略：[`../adr/2026-07-09-key-fallback-strategy.md`](../adr/2026-07-09-key-fallback-strategy.md)
- 部署文档：[`../deployment/cloud-https-setup.md`](../deployment/cloud-https-setup.md) C.3 节"本地配置流程"

---

## 限制 4：不支持私钥导入

### 问题描述

LifePrism 仅支持在前端切换到 SSH 模式时自动生成 ed25519 密钥对，不支持导入用户已有的 SSH 私钥。

### 影响范围 + 严重程度

- **影响范围**：已有 SSH 密钥对的用户
- **严重程度**：低（多数用户没有现成的 SSH 密钥对，自动生成已满足需求）

### 当前假设

- 系统假设"用户没有现成 SSH 密钥对"或"用户愿意使用 LifePrism 生成的独立密钥对"
- 自动生成的密钥对与用户其他用途的密钥隔离，安全性更好

### 触发条件

- 用户已有 SSH 密钥对（如 `~/.ssh/id_ed25519`）希望复用
- 用户在企业环境中使用 CA 签发的 SSH 证书

### 临时方案或计划改进

- **当前方案**：使用 LifePrism 自动生成的密钥对，不复用已有私钥
- **临时变通**：高级用户可手动将已有私钥 PEM 内容写入 keyring 的 `ssh_tunnel_private_key` 字段（需通过命令行工具或开发模式操作，不在前端 UI 支持）
- **未来增强**：私钥导入 UI 由未来 PRD 评估（参考 Out of Scope 第 12 项），需考虑格式兼容（OpenSSH/PuTTY/PEM）、密钥类型兼容（ed25519/RSA/ECDSA）、passphrase 支持等

### 相关文档

- PRD Out of Scope 第 12 项：[`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md)

---

## 限制 5：密钥保留不覆盖

### 问题描述

用户切换到 SSH 模式时，如 keyring 中已存在 `ssh_tunnel_private_key`，LifePrism 保留原私钥不覆盖。这是有意设计（避免已部署到云端的公钥失效），但在多端切换场景下可能导致前端展示的公钥与云端 `authorized_keys` 中的公钥不一致。

### 影响范围 + 严重程度

- **影响范围**：多端切换 keyring 的用户（如在不同 Windows 账户或不同电脑间切换）
- **严重程度**：中（如不一致，SSH 连接会被拒绝，但可通过"测试连接"快速发现）

### 当前假设

- 系统假设"单台本地客户端使用同一个 keyring"
- 单端使用场景下，私钥一旦生成并部署公钥后无需再变

### 触发条件

- 用户在多台本地电脑间切换 keyring（如 PC1 生成密钥 → 部署公钥 → 在 PC2 切换 SSH 模式 → PC2 生成新密钥但云端 `authorized_keys` 仍只有 PC1 的公钥）
- 用户重置 settings 后未重新生成密钥就切换 SSH 模式
- 用户手动修改 keyring 中的 `ssh_tunnel_private_key` 字段

### 临时方案或计划改进

- **当前方案**：用户切换到 SSH 模式后，前端始终从 keyring 私钥实时派生公钥并展示，用户可对比公钥与云端 `authorized_keys` 是否一致；通过"测试连接"按钮验证一致性
- **故障排查**：如"测试连接"返回"密钥被拒绝"，按以下步骤排查：
  1. 复制前端展示的当前公钥
  2. SSH 登录云端检查 `~/.ssh/authorized_keys`
  3. 如公钥不在列表中，追加新公钥（不要删除旧公钥，避免影响其他设备）
  4. 重新点击"测试连接"
- **未来增强**：无私钥轮换 UI（参考限制 6）的根因相同，由未来 PRD 评估

### 相关文档

- PRD User Story 8：[`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md)
- PRD 已知限制第 5 项

---

## 限制 6：无私钥轮换 UI

### 问题描述

LifePrism 不提供"重新生成密钥对"按钮，用户无法通过前端 UI 主动轮换 SSH 私钥。如需轮换需通过重置 settings 或命令行操作后重新配置云端 `authorized_keys`。

### 影响范围 + 严重程度

- **影响范围**：需要轮换密钥的用户（如怀疑私钥泄露）
- **严重程度**：低（多数用户无需轮换密钥；轮换需求场景极少）

### 当前假设

- 系统假设"密钥一旦生成并部署后长期有效"
- 私钥保存在本地 keyring，泄露风险较低

### 触发条件

- 用户怀疑私钥泄露（如电脑被入侵）
- 用户希望定期轮换密钥以提升安全性
- 用户希望在多台设备间切换主密钥

### 临时方案或计划改进

- **当前方案**：如需轮换密钥，按以下步骤手动操作：
  1. 清空 keyring 中的 `ssh_tunnel_private_key` 字段（通过命令行工具或开发模式）
  2. 在前端切换出 SSH 模式再切回（或重启 LifePrism），系统检测到无私钥后自动生成新密钥对
  3. 复制新公钥到云端 `~/.ssh/authorized_keys`
  4. 删除云端 `authorized_keys` 中的旧公钥条目（避免被旧私钥持有者利用）
  5. 点击"测试连接"验证新密钥对工作正常
- **未来增强**：私钥轮换 UI（含"重新生成密钥对"按钮 + 旧公钥清理提示）由未来 PRD 评估（参考 Out of Scope 第 13 项）

### 相关文档

- PRD Out of Scope 第 13 项：[`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md)

---

## 限制 7：隧道状态非实时显示

### 问题描述

前端不实时显示 SSH 隧道状态（已连接 / 重连中 / 已断开），用户需通过"测试连接"按钮手动验证隧道当前是否可用。隧道断开时仅通过同步失败日志感知异常。

### 影响范围 + 严重程度

- **影响范围**：用户体验（运维感知速度）
- **严重程度**：低（功能不影响，仅是状态感知不实时）

### 当前假设

- 系统假设"用户能通过同步日志感知隧道异常"或"用户主动点击测试连接验证状态"
- 隧道断开后 SyncClient 自动重连，多数场景下用户无需干预

### 触发条件

- 网络抖动导致 SSH 隧道短暂断开（自动重连中）
- 云端 SSH 服务故障导致隧道长时间断开
- 本地端口被占用导致隧道无法建立

### 临时方案或计划改进

- **当前方案**：
  - 用户感知隧道异常的途径：(a) 同步日志中出现"SSH 隧道未就绪"或类似 WARNING/ERROR；(b) 主动点击前端"测试连接"按钮，后端会建立临时连接验证隧道 + 远程 8102 可达性
  - 隧道断开后 SyncClient 自动重连（指数退避 5s → 10s → 20s → 30s 上限），重连无最大次数限制
- **未来增强**：未来 PRD 可新增 `GET /api/v2/settings/ssh-tunnel/status` 端点 + 前端轮询实时显示隧道状态（参考 Out of Scope 第 15 项）。需要权衡：(a) 轮询频率对性能的影响；(b) 状态枚举的设计（disconnected / connecting / connected / reconnecting / failed）；(c) 失败原因的展示

### 相关文档

- PRD Out of Scope 第 15 项：[`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md)
- PRD User Story 22：通过"测试连接"按钮手动验证隧道当前是否可用

---

## 限制 8：SSH 主机密钥验证未启用（MITM 风险）

### 问题描述

`SSHTunnel.connect()` 使用 `known_hosts=None` 禁用了 SSH 主机密钥验证，攻击者可在客户端和云端之间劫持连接进行中间人攻击（MITM）。代码注释已承认此问题（`ssh_tunnel.py:172`）但未记录到已知限制文档中。

### 影响范围 + 严重程度

- **影响范围**：安全性（模式 C 下所有 SSH 隧道连接）
- **严重程度**：中（取决于部署环境网络可信度）

### 当前假设

- 部署环境网络可信（如家庭网络或 VPS 直连），攻击者无法劫持 SSH 连接
- 客户端到云端的网络路径不被恶意第三方控制

### 触发条件

- 攻击者位于客户端和云端之间的网络路径上，能够修改 DNS 或路由
- 部署在不可信网络环境（如公共 WiFi、被劫持的运营商网络）

### 临时方案或计划改进

- **当前方案**：确保部署环境网络可信（如家庭网络或 VPS 直连），避免在不可信网络环境下使用 SSH 隧道模式；未来版本将支持 known_hosts 配置
- **未来增强**：添加 `sync.ssh_tunnel.known_hosts_path` 配置项，允许用户指定 known_hosts 文件路径，启用主机密钥验证

### 相关文档

- 代码实现：[`../../lifeprism/sync/ssh_tunnel.py`](../../lifeprism/sync/ssh_tunnel.py):172

---

## 相关文档

- 部署文档：[`../deployment/cloud-https-setup.md`](../deployment/cloud-https-setup.md) "模式 C 配置：SSH 隧道（无域名场景）"
- 云端安全限制：[`./cloud-security-limitations.md`](./cloud-security-limitations.md) 限制 4 替代方案
- 密钥存储策略 ADR：[`../adr/2026-07-09-key-fallback-strategy.md`](../adr/2026-07-09-key-fallback-strategy.md)
- SSH 隧道集成 PRD：[`../../.scratch/ssh-tunnel-integration/prd.md`](../../.scratch/ssh-tunnel-integration/prd.md)
- 编码规则（remote_url 拦截）：[`../coding-rules/sync-remote-url-access-rules.md`](../coding-rules/sync-remote-url-access-rules.md)
