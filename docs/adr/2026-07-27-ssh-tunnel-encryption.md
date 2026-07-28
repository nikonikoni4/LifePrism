---
version: 1.0
created_at: 2026-07-27
updated_at: 2026-07-27
last_updated: 创建初稿，记录在 HTTPS+域名+备案流程不可接受时选择 SSH 隧道加密的决策
abstract: 在家庭网络 IP 变动 + 国内服务器 ICP 备案复杂的场景下，新增 SSH 隧道作为云端同步的加密通道选项，与已有的 HTTP/HTTPS 模式并存，降低加密门槛
status: decided
---

# SSH 隧道作为云端同步加密通道

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

家庭网络 IP 地址经常变动，云端服务器防火墙严格限制 IP 时需要频繁修改规则。若直接放开 IP 端口使用 HTTP 明文传输，API Key 和同步数据会暴露在公网；使用 HTTPS 加密需要 Let's Encrypt 证书，证书需要绑定域名，而国内服务器绑定域名需要 ICP 备案——整个 HTTPS+域名+备案流程特别复杂，用户判断不可接受。需要一个在不备案、不绑定域名的前提下实现加密传输的方案。

### 讨论范围

- lifeprism 云端同步通道的加密方式选型
- HTTP / HTTPS / SSH 三种模式的并存关系
- SSH 隧道模式的外部环境前提与配置流程

### 非讨论范围

- SSH 隧道的内部实现细节（状态机、重连机制）→ 属于 spec `2026-07-26-data-sync-ssh-tunnel-spec.md`
- SSH 隧道数据流→ 属于 flow `2026-07-26-ssh-tunnel-flow.md`
- 删除同步、全局任务状态等独立决策→ 各有独立 ADR

### 模糊信息的明确定义

- "加密门槛"：指实现传输加密所需的外部依赖数量、配置步骤数、持续维护成本的综合难度
- "外部环境限制"：指服务器所在国家法规（ICP 备案）、家庭网络特性（IP 变动）等非代码层面的约束

### 问题深度

这是涉及产品部署形态与运维方式的长期决策，非浅层方案选择。决策一旦落地，前端配置 UI、SyncClient 启动流程、打包依赖（asyncssh + pywin32 GSSAPI 处理）都围绕此决策展开。

## 现状

- lifeprism 已支持 HTTP + API Key 模式（基础方案，明文传输，仅适合内网测试）
- lifeprism 已支持 HTTPS 模式（代码层支持，但需要用户自行配置证书）
- 云端服务器部署在国内云厂商，ICP 备案流程复杂
- 家庭网络 IP 由 ISP 动态分配，频繁变动
- 用户使用 xftp 等工具对 SSH 协议有一定熟悉度
- 用户对 VPN、内网穿透工具（frp、Tailscale、ZeroTier）不熟悉

## 决策前提

- 前提 1：家庭网络 IP 地址经常变动（事实，ISP 动态分配）
- 前提 2：云端防火墙严格限制 IP，IP 变动需要手动修改规则（事实，运维痛点）
- 前提 3：放开 IP 端口使用 HTTP 明文传输存在安全风险（事实，API Key 和同步数据会暴露）
- 前提 4：HTTPS 加密需要 Let's Encrypt 证书（事实，业界标准）
- 前提 5：证书需要绑定域名（事实，Let's Encrypt 要求域名验证）
- 前提 6：国内服务器绑定域名需要 ICP 备案（事实，法规要求）
- 前提 7：HTTPS+域名+备案流程特别复杂，用户判断不可接受（用户判断）
- 前提 8：lifeprism 已支持 HTTP/HTTPS 两种模式，SSH 是新增的可选项（事实，代码已实现并存）
- 前提 9：用户对 VPN、内网穿透等替代方案不熟悉，对 SSH 稍熟悉（因 xftp 等工具使用经验）（用户判断）

## 可选方案

### 方案 A：HTTPS + 域名 + ICP 备案

走标准 HTTPS 加密路径：购买域名 → ICP 备案 → 配置 DNS → Let's Encrypt 签发证书 → 部署 HTTPS。

**优势**

- 业界标准方案，最规范的加密方式
- 支持浏览器直接访问（未来若做网页端可直接复用）
- 证书自动续期机制成熟（certbot）

**劣势**

- ICP 备案流程复杂，需要提供主体材料、等待审核（数周）
- 需要购买并维护域名
- 国内服务器备案要求严格，可能因材料问题被驳回

### 方案 B：HTTP + API Key（已有基础方案）

继续使用已有的 HTTP 模式，依赖 API Key 认证保护接口，不加密传输内容。

**优势**

- 零外部依赖，开箱即用
- 内网测试环境最方便

**劣势**

- API Key 在 HTTP 头中明文传输，可被中间人嗅探
- 同步数据（含可能的敏感对话内容）明文传输
- 公网部署存在严重安全风险

### 方案 C：SSH 隧道加密（新增方案）

在本地与云端之间建立 SSH 隧道，sync_client 通过 `localhost:{local_port}` 访问云端服务，SSH 协议负责加密传输。

**优势**

- 不需要域名、不需要 ICP 备案
- 加密传输由 SSH 协议保证（成熟稳定）
- 用户对 SSH 有一定熟悉度（xftp 等工具）
- 与已有 HTTP/HTTPS 模式并存，非侵入式集成
- 防火墙只需开放 SSH 端口（22），可绑定 127.0.0.1 限制来源

**劣势**

- 仅支持单客户端连接（一个隧道对应一个本地端口）
- 隧道断开时同步会跳过（已通过 `_ensure_tunnel_ready` + 重连机制处理）
- 不支持浏览器直接访问（仅用于 sync_client ↔ 云端后端 HTTP 通信）
- 打包环境需要处理 asyncssh GSSAPI 依赖问题（已通过 `gss_host=''` 修复）
- 需要用户手动配置云端 `~/.ssh/authorized_keys`

### 方案 D：VPN / 内网穿透工具

使用 WireGuard、frp、Tailscale、ZeroTier 等工具组建虚拟网络。

**优势**

- 传输层加密，对应用透明
- 部分工具（Tailscale、ZeroTier）零配置

**劣势**

- 用户不熟悉，学习成本高（用户判断）
- 需要额外维护一套网络基础设施
- 部分工具在国内网络环境下不稳定

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 7 成立（HTTPS+备案不可接受） + 前提 9 成立（不熟悉 VPN） | 方案 C（SSH 隧道） | 当前选择 |
| 未来完成 ICP 备案 + 拥有域名 | 方案 A（HTTPS+域名） | 备选触发条件 1 |
| 仅内网测试环境，无公网部署需求 | 方案 B（HTTP+API Key） | 备选触发条件 2 |
| 用户熟悉 VPN 工具且愿意维护 | 方案 D（VPN/内网穿透） | 备选触发条件 3 |

决策规则：三种方案（A/B/C）都可选，SSH 是在"降低加密门槛"前提下比较方便的方式。选择哪种方案取决于外部环境限制——备案完成选 A，内网测试选 B，需要加密但无域名选 C。

## 最终决策

当前成立的前提：前提 1-9 全部成立（家庭 IP 变动 + 备案复杂 + 用户熟悉 SSH）。

因此选择 **方案 C：SSH 隧道加密**。

前提失效时的切换路径：
- 若未来完成 ICP 备案并拥有域名 → 切换到方案 A（HTTPS+域名）
- 若仅在内网测试 → 切换到方案 B（HTTP+API Key）
- 若用户熟悉 VPN 工具且愿意维护 → 可考虑方案 D

## 决策原因

- 原因 1：HTTPS+域名+备案流程的复杂度与"同步加密"这一需求的价值不匹配，用户判断备案成本不可接受
- 原因 2：SSH 协议本身是成熟的加密传输方案，且用户因 xftp 等工具有一定熟悉度，学习成本低于 VPN 类方案
- 原因 3：SSH 隧道模式与已有 HTTP/HTTPS 模式并存，非侵入式集成，不影响现有功能
- 原因 4：方案 B 的明文传输风险在公网部署中不可接受，必须有加密方案兜底

## 后续影响

- **代码结构**：新增 `lifeprism/sync/ssh_tunnel.py`、`lifeprism/server/api/ssh_tunnel_api.py`；SyncClient 新增 `_ssh_tunnel` 实例和 `_read_remote_url` 拦截层
- **配置 Schema**：新增 `sync.connection_mode`（http/ssh）、`sync.ssh_tunnel.*` 配置项
- **前端 UI**：设置页新增 SSH 标签页，支持生成密钥、测试连接、复制公钥
- **打包依赖**：新增 asyncssh 依赖；打包环境需要处理 GSSAPI 禁用（`gss_host=''`，详见 [2026-07-27-packaged-win32timezone-gssapi](../history-bugs/2026-07-27-packaged-win32timezone-gssapi.md)）
- **外部配置**：用户需要手动在云端 `~/.ssh/authorized_keys` 追加公钥
- **未来限制**：若需要浏览器直接访问云端网页端，SSH 模式无法满足，需切换到 HTTPS
- **测试**：SSH 隧道单元测试覆盖连接、重连、状态机；打包环境端到端验证已通过

## 相关文档

- Spec：[2026-07-26-data-sync-ssh-tunnel-spec.md](../specs/2026-07-26-data-sync-ssh-tunnel-spec.md)
- Flow：[2026-07-26-ssh-tunnel-flow.md](../flows/2026-07-26-ssh-tunnel-flow.md)
- PRD：`.scratch/ssh-tunnel-integration/prd.md`
- Bug 历史：[2026-07-27-packaged-win32timezone-gssapi.md](../history-bugs/2026-07-27-packaged-win32timezone-gssapi.md)
