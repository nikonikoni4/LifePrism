# 2026-07-14 数据同步与云端安全会话总结

## 会话时间

2026-07-14

## 讨论主题概览

本次会话围绕 LifePrism 云端部署的数据同步功能展开深度审计，涉及四个主要模块：

1. 数据同步链路完整性审计
2. 文件同步冲突处理方案设计（参考思源笔记）
3. 同步 API Key 安全管理
4. 云端部署安全限制梳理

---

## 一、数据同步链路完整性审计

### 发现的问题

- [Bug] [数据同步链路未打通 + 文件 LWW 空文档反向覆盖](..\history-bugs\2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md)
  - Bug 1：`SyncClient` 在 `main.py:331` 实例化后从未调用 `start_scheduled_sync(600)` 和启动时 `sync_once()`，全仓库调用次数为 0
  - Bug 2：文件 LWW 只比较 mtime，云端新部署空文档（mtime 新）会反向覆盖本地实文档（mtime 旧）
  - Spec 要求的"启动时同步"和"每 10 分钟定时同步"完全失效，仅关闭时和前端手动触发可用

### 关键结论

当前并没有做文档数据同步——不是因为"没设计"，而是**实现了但没有真正启动**（实例化后忘了调用启动方法）。

---

## 二、文件同步冲突处理方案设计

### 调研过程

调研了思源笔记（`D:\desktop\软件开发\siyuan`）的同步机制，结论：思源完全不是 LWW，而是基于 **git-like 内容寻址快照（snapshot）+ 3-way merge** 的设计。

### 与 LifePrism 的根本差异

| 维度 | LifePrism（当前） | 思源笔记 |
|------|------------------|---------|
| 同步模型 | LWW（mtime） | git-like snapshot + 3-way merge |
| 比较依据 | mtime | 内容 hash |
| 冲突处理 | 直接覆盖 | 保留双方版本，标记 Conflict |
| 加密保护 | HTTP + Bearer Token | 32 字节 AES 端到端加密 |

### 最终方案：per-file version tracking

采用简化版的思源方案——每文件独立追踪 `parent_hash` 和 `current_hash`：

- 同步前刷新 current_hash（被动扫描所有同步文件）
- 同步中按照完整决策矩阵（11 种状态组合）判定 SKIP/PUSH/PULL/CONFLICT
- 同步后一致性校验通过才推进 parent_hash
- 冲突策略：保留本地 + 备份云端到 history

### 同步白名单（待定，未写入文档）

基于 Agent 文件工具白名单（`ALLOWED_DIRS = ["user", "diary", "agent"]`）+ session：

```python
SYNC_DIRECTORIES = [
    "session/",   # 聊天会话 JSONL
    "diary/",     # 日记 MD
    "agent/",     # Agent 身份/记忆/配置
    "user/",      # 用户级数据
]
```

排除：docs/、assets/、prompts/、plan/、external_files/、workflow/、channel/wechat/account.json（改数据库）。

### 冲突分流策略（待定，未写入文档）

按文件类型分流：

- JSONL（session）：文件级 LWW
- MD（diary/agent/user）：保留本地 + 备份云端
- account.json：改数据库存储，走 LWW

### 相关文档

- Bug 记录（含思源调研附录 + per-file 完整方案）：[..\history-bugs\2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md](..\history-bugs\2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md)
- 思源源代码：`D:\desktop\软件开发\siyuan\kernel\model\repository.go`

---

## 三、同步 API Key 安全管理

### 发现的问题

- [Bug] [同步 API Key 无法重新生成 + config.yaml fallback 导致 Key 固化](..\history-bugs\2026-07-14-sync-key-regeneration-and-config-fallback.md)
  - Bug 1（前端）：生成云端配置时无确认键，用户无法选择"保留当前 Key"还是"更换 Key"
  - Bug 2（后端）：`get_sync_api_key()` 从 `config.yaml` fallback 读取 Key，导致 config.yaml 中手动写入的弱 Key 被永久固化，`secrets.token_urlsafe(32)` 永不触发
  - Bug 3（关联）：本地 config.yaml 不应出现 Key 字段，当前 config.yaml 混合了普通配置与敏感 Key

### 修复方案

| Bug | 方案 |
|-----|------|
| Bug 1 | 前端增加确认键："保留当前 Key，仅生成配置文档" vs "更换 Key 并生成配置" |
| Bug 2+3 | Key 统一存储：新建 `storage.yaml`（权限 600），通过 `run_mode` 控制读写——本地（full）仅 keyring，云端（agent_only/web_demo）才用文件 fallback |

```
读取层级：
  本地 (run_mode == "full")： keyring  → 无 fallback
  云端 (run_mode != "full")：storage.yaml → providers.yaml（仅 Provider API Key）

写入层级：
  本地：  keyring（不写文件）
  云端：  storage.yaml
```

### 相关文档

- Bug 记录：[..\history-bugs\2026-07-14-sync-key-regeneration-and-config-fallback.md](..\history-bugs\2026-07-14-sync-key-regeneration-and-config-fallback.md)

---

## 四、云端部署安全限制梳理

### 已记录到已知限制

- [已知限制] [云端部署安全限制](..\known-limitations\cloud-security-limitations.md)

总结 4 项：

| # | 限制 | 严重程度 | 计划改进 |
|---|------|---------|---------|
| 1 | wxid 明文存储，攻击者可伪装 AI 机器人 | 中 | 数据库/文件级加密 |
| 2 | API Key 明文存储，攻击者滥用 LLM 服务 | 高 | storage.yaml + run_mode 隔离 |
| 3 | 同步 API Key 无法重新生成 | 中 | 前端确认键 + 移除 config fallback |
| 4 | 同步传输未启用 HTTPS，Bearer Token 明文 | 高 | Let's Encrypt + Nginx 反向代理 |

### 传输层确认

- 云端认证是用 Key 的（`verify_sync_api_key` + `secrets.compare_digest` 常量时间比较），所有 5 个同步端点都绑定了认证依赖
- **但当前部署是 `http://` 而非 `https://`**，Authorization Header 的 Bearer Token 明文传输，中间人可直接拦截
- HTTPS（TLS）加密整个 HTTP 报文，包括 Header。理论上 Bearer Token 不会被拦截。但当前未配置

### 相关文档

- 已知限制：[..\known-limitations\cloud-security-limitations.md](..\known-limitations\cloud-security-limitations.md)
- Bug 记录：[..\history-bugs\2026-07-14-sync-key-regeneration-and-config-fallback.md](..\history-bugs\2026-07-14-sync-key-regeneration-and-config-fallback.md)

---

## 五、本次会话涉及的专业概念（计算机网络相关）

以下概念在讨论中涉及，用户后续需要确认：

| 概念 | 在本次讨论中的角色 |
|------|-------------------|
| HTTPS / TLS | 加密整个 HTTP 报文（包括 Authorization Header），防止中间人拦截 Bearer Token |
| Bearer Token | HTTP Header 格式：`Authorization: Bearer xxx`，作为 API 认证凭据 |
| LWW（Last-Write-Wins） | 同步冲突解决策略——只比较时间戳，更新的一方获胜。LifePrism 当前使用 |
| 3-way merge | 三方合并——引入共同祖先 Base，能区分"仅一方改"和"双方都改" |
| content hash（SHA-256） | 基于文件内容计算哈希值，用于判断文件是否被修改（比 mtime 可靠） |
| per-file version tracking | 每文件独立追踪 parent_hash 和 current_hash，简化版 3-way merge |
| keyring | 操作系统凭据管理器（Windows 凭据管理器），本地安全存储 Key |
| constants-time compare (`secrets.compare_digest`) | 防时序攻击的字符串比较方法 |
| run_mode | LifePrism 的运行时配置（full / web_demo / agent_only），仅内存不持久化 |

---

## 六、本次会话产生的文档清单

| 文件夹 | 文件 | 内容 |
|--------|------|------|
| `docs/history-bugs/` | `2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md` | Bug 1（链路断开）+ Bug 2（LWW 空文档覆盖）+ 思源调研附录 + per-file 完整方案 |
| `docs/history-bugs/` | `2026-07-14-sync-key-regeneration-and-config-fallback.md` | Bug 1（前端无确认键）+ Bug 2（config fallback 污染）+ Bug 3（Key 统一存储方案） |
| `docs/history-bugs/` | `index.md` | 新增两条 bug 索引 |
| `docs/known-limitations/` | `cloud-security-limitations.md` | 4 项云端安全限制（wxid / API Key / sync Key 重生成 / HTTPS） |
| `docs/known-limitations/` | `index.md` | 新增云端安全限制索引 |
| `docs/temp/` | `2026-07-14-sync-and-security-session-summary.md` | 本文件（会话总结） |

---

## 七、待决定的开放话题

1. **chat_history.json**：是否从 user/ 白名单排除？（当前倾向排除，但未最终确定）
2. **plan/ 同步**：已决定排除，但前提是"Agent 不需要读取计划，Agent 不会修改计划"。需写明确认
3. **微信多用户支持**：当前设计支持但未实际使用，是否限单用户？（讨论中）
4. **冲突解决的具体实现**：按文件类型分流（JSONL LWW / MD 保留本地备份云端），待最终确认
5. **决策文档**：计划写入 ADR（per-file version tracking / 白名单对齐 / 冲突分流 / account.json 改数据库），等待用户启动 write-decisions
