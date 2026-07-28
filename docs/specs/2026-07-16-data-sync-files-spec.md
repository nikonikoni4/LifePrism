---
version: 2.0
created_at: 2026-07-16
updated_at: 2026-07-16
last_updated: 从 v1.0（2026-07-11-data-sync-spec.md）拆分重构；三阶段 API 协议（check/fetch/push/verify/commit）替代原简单 pull/push；新增 per-file version tracking、AI 冲突合并、白名单对齐、file_sync_state 表、hash 规范化策略
abstract: 文件双向同步规格，定义 per-file version tracking（parent_hash + current_hash + 11 状态决策矩阵）、三阶段 API 协议（check → fetch/push → verify/commit）、按文件类型分流冲突解决（MD 由 AI 合并、JSONL 走 LWW）、同步白名单（对齐 Agent 工具白名单）和认证安全的技术契约
status: draft
module: sync
---

# 数据同步模块规格 — 文件同步

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 2.0 | 从原 `2026-07-11-data-sync-spec.md` 拆分独立 spec；三阶段 API 协议 + per-file version tracking |
| 1.0 | 创建 spec 初稿（原 data-sync-spec 的文件同步章节） |

## Overview

**业务问题**：文件同步需要考虑"空文档覆盖"（云端新部署空文档 mtime 更新 → 错误覆盖本地有内容文档）、"云端缺少文件"（重装后已同步文件无法重新推送到云端）、"双向修改冲突"（本地和云端都修改了同一文件）等场景。纯 mtime LWW 无法正确区分这些场景。

**核心职责**：
- **per-file version tracking**：每文件独立追踪 `parent_hash` 和 `current_hash`，通过 11 状态决策矩阵精确判定变更方向
- **三阶段 API 协议**：check（轻量快照交换）→ fetch/push（内容传输）→ verify/commit（一致性校验）
- **冲突分流**：MD 文件由 AI 驱动合并（CONFLICT_RESOLVE 消息类型），JSONL 走文件级 LWW
- **同步白名单**：对齐 Agent 工具白名单（ALLOWED_DIRS + session），明确排除 chat_history.json 和已弃用目录

## Scope

### 范围内

- per-file version tracking（parent_hash + current_hash）
- 11 状态决策矩阵（PUSH / PULL / CONFLICT / SKIP）
- 三阶段 API 端点：check / fetch / push-files / verify / commit
- 冲突按文件类型分流（.md → AI 合并、.jsonl → LWW）
- CONFLICT_RESOLVE 消息类型（InboundMessage → AgentLoop → AI 合并 → write_file）
- 冲突备份（sync_conflict/{timestamp}/ 目录）
- hash 规范化策略（统一行尾符 + 去行尾空白 + SHA-256）
- file_sync_state 表（对称维护于本地和云端）
- 文件存在性显式查询（all_paths）
- gzip 压缩 + base64 编码传输

### 范围外

- 数据库同步（30 张静态表 + 动态表）→ [`data-sync-core-spec`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-core-spec.md)
- 心跳与消息路由 → 同上
- 云端配置初始化 → 同上
- 行级 diff 自动合并

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 同步白名单

- [ ] 同步目录仅 4 个：session/、diary/、agent/、user/
- [ ] chat_history.json 被明确排除
- [ ] account.json 已改为数据库存储（wechat_account_state 表），不在文件白名单
- [ ] docs/、assets/、prompts/、plan/、external_files/、workflow/ 不在白名单

### 三阶段协议 — Phase 1: Check

- [ ] `/api/sync/pull-files/check` 返回 mtime > last_sync_time 的变更文件（path + parent_hash + current_hash）
- [ ] check 响应包含 `all_paths`（云端所有非黑名单文件路径清单）用于存在性判断
- [ ] 本地扫描 SYNC_DIRECTORIES 刷新所有文件 current_hash，新文件 parent=NULL

### 三阶段协议 — Phase 2a: 11 状态矩阵

- [ ] 本地 parent=NULL + 云端不存在的文件 → PUSH（本地新建）
- [ ] 本地不存在的文件 + 云端 parent=NULL → PULL（云端新建）
- [ ] 双方都新建同路径文件 → CONFLICT
- [ ] 本地从未同步 + 云端有历史 → PULL
- [ ] 云端从未同步 + 本地有历史 → PUSH
- [ ] 双方都没改 → SKIP
- [ ] 仅本地改 → PUSH
- [ ] 仅云端改 → PULL
- [ ] 双方都改且内容不同 → CONFLICT
- [ ] parent 不一致 → CONFLICT（兜底）

### 三阶段协议 — Phase 2b: Fetch

- [ ] `/api/sync/pull-files/fetch` 按路径返回文件内容 + hash
- [ ] 仅拉取 PULL 和 CONFLICT 文件
- [ ] 本地写入文件后立即计算 current_hash 并更新 file_sync_state

### 三阶段协议 — Phase 2c: Push

- [ ] `/api/sync/push-files` 推送文件内容 + hash
- [ ] 云端写入后立即计算 current_hash 并更新 file_sync_state
- [ ] 传输使用 gzip + base64

### 三阶段协议 — Phase 3: Verify + Commit

- [ ] `/api/sync/pull-files/verify` 云端实时计算 hash 返回
- [ ] 本地比对双方 current_hash 一致
- [ ] `/api/sync/pull-files/commit` 确认同步完成，云端推进 parent_hash = current_hash

### 冲突解决

- [ ] .md 文件冲突 → AI 驱动合并（CONFLICT_RESOLVE 消息类型）
- [ ] .jsonl 文件冲突 → 文件级 LWW（保留本地版本 PUSH 覆盖）
- [ ] 云端版本备份到 sync_conflict/{timestamp}/ 目录
- [ ] AI 合并完成后更新 file_sync_state: parent_hash = new_hash

### hash 规范化

- [ ] 所有 hash 计算前统一行尾符（\r\n → \n，孤立 \r → \n）
- [ ] 去除每行行尾空白，保留词语间空格
- [ ] 使用 SHA-256 算法

## Technical Contract

### file_sync_state 表

用于本地和云端对称维护文件同步状态。

```sql
CREATE TABLE file_sync_state (
    file_path    TEXT PRIMARY KEY,
    parent_hash  TEXT,     -- 上次同步成功时的内容 hash
    current_hash TEXT,     -- 当前内容 hash
    updated_at   TEXT NOT NULL
);
```

- **不加入 SYNC_TABLES**：file_sync_state 是同步元数据，通过 pull-files/push-files API 扩展字段传递，不走数据库同步链路
- **parent_hash 更新时机**：Phase 3 commit 成功 → parent_hash = current_hash
- **current_hash 更新时机**：同步开始扫描时 + 每次写入文件后立即可计算

### 同步白名单

```python
SYNC_DIRECTORIES = [
    "session/",   # 聊天会话 JSONL（Agent 会话层写入）
    "diary/",     # 日记 MD（Agent write_file/edit_file）
    "agent/",     # Agent 身份/记忆/chat 配置（Agent write_file/edit_file）
    "user/",      # 用户级数据（Agent write_file/edit_file）
]
```

**排除项**：

| 排除 | 理由 |
|------|------|
| `user/chat_history.json` | 由 dreaming task 写入，云端 agent_only 无 dreaming，不会变更 |
| `channel/wechat/account.json` | 已改为 wechat_account_state 数据库表（见 core-spec） |
| `docs/`、`assets/`、`prompts/`、`plan/`、`external_files/`、`workflow/` | 不在 Agent 工具白名单，Agent 不可操作 |

### hash 规范化策略

```python
def compute_file_hash(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

**规则**：统一行尾符 + 去每行行尾空白 + SHA-256。保留词语间空格避免内容碰撞。源文件不受影响，仅 hash 计算时规范化。

### API 端点

| 端点 | 方法 | Request | Response |
|------|------|---------|----------|
| `/api/sync/pull-files/check` | POST | `{last_sync_time, directories}` | `{files: [{path, parent_hash, current_hash}], all_paths: [...], sync_time}` |
| `/api/sync/pull-files/fetch` | POST | `{paths: [...]}` | `{files: [{path, content, parent_hash, current_hash}]}` |
| `/api/sync/push-files` | POST | `{files: [{path, content, parent_hash, current_hash}]}` | `{results: [{path, action}], sync_time}` |
| `/api/sync/pull-files/verify` | POST | `{paths: [...]}` | `{files: [{path, current_hash}]}` |
| `/api/sync/pull-files/commit` | POST | `{paths: [...]}` | `{status: "ok", committed: [...]}` |

### 11 状态决策矩阵

| # | 本地 parent | 本地 current | 云端 parent | 云端 current | 判定 |
|---|-------------|-------------|-------------|--------------|------|
| 1 | NULL | A1 | — | — | PUSH |
| 2 | — | — | NULL | A2 | PULL |
| 3 | NULL | A1 | NULL | A2 | CONFLICT |
| 4 | NULL | A1 | A | A | PULL |
| 5 | A | A | NULL | A2 | PUSH |
| 6 | A | A | A | A | SKIP |
| 7 | A | A1 | A | A | PUSH |
| 8 | A | A | A | A1 | PULL |
| 9 | A | A1 | A | A2 | CONFLICT |
| 10 | A1 | A1 | A2 | A2 | CONFLICT |
| 11 | A | A1 | A2 | A2 | CONFLICT |

"`—`" 表示文件不存在（云端文件不存在通过 `all_paths` 查询判定）。A、A1、A2 为不同 hash 值。

**关键边界场景**：

| 场景 | 矩阵行 | 判定 | 说明 |
|------|-------|------|------|
| 云端新部署空文档 | #5 | PUSH | 不会反向覆盖（区别于纯 LWW mtime） |
| 换电脑绑云端 | #4 | PULL | 新机器拉取全部文件 |
| 云端重装文件丢失 | 不在 files 中 + path not in all_paths | PUSH | 显式存在性判断（区别于 `local_parent is not None` 猜测） |

### 冲突解决分流

| 文件类型 | 策略 | 理由 |
|---------|------|------|
| `session/*.jsonl` | 文件级 LWW（保留本地版本 PUSH 覆盖） | 追加式写入、主备模式下本地为活跃端 |
| `.md`（agent/diary/user） | AI 驱动合并（CONFLICT_RESOLVE） | MD 文件全部由 AI 生成，AI 最理解语义 |
| `account.json`（过渡期） | 保留本地版 + 备份云端版 | 改为数据库后不再走文件同步 |

### CONFLICT_RESOLVE 消息类型

文件同步冲突时构建 InboundMessage：

```python
msg = InboundMessage(
    type=MessageType.CONFLICT_RESOLVE,
    content=f"""## 文件冲突需要解决

文件路径：{file_path}

### 本地版本（当前保留的版本）
{local_content}

### 云端版本（备份的版本）
{remote_content}

### 任务
请阅读以上两份文档，结合相关上下文（可以使用 read_file 读取相关文件），
决定如何合并。合并完成后使用 write_file 写入最终版本到：{file_path}
""",
    extra={
        "conflict_file_path": file_path,
        "local_hash": local_hash,
        "remote_hash": remote_hash,
    },
)
```

AI 工具权限：ReadFileTool、WriteFileTool、EditFileTool、FileTreeTool、SearchFileTool、SearchStringTool。不含数据库工具和 Session 工具。

**跨线程桥接**：SyncClient 同步线程通过 `asyncio.run_coroutine_threadsafe(bus.send(msg), loop)` 提交到主线程事件循环，同步等待结果（`future.result(timeout=600)`）。

**冲突备份**：云端版本备份到 `sync_conflict/{timestamp}/{relative_path}`，不在 SYNC_DIRECTORIES 和 ALLOWED_DIRS 中，不会被再次同步或 AI 访问。

## Design Rationale

**为什么用 per-file version tracking 而非纯 LWW mtime？**
- mtime 反映文件系统操作时间而非内容更新时间，空文档覆盖问题无法解决
- content hash 精确反映内容变更，parent_hash + current_hash 能区分"仅一方改"还是"双方都改"
- 改装范围可控（新增 file_sync_state 表），不需要完整 git-like snapshot 树

**为什么三阶段协议？**
- Phase 1（check）只需传输 hash，轻量快速
- Phase 2（fetch/push）仅传输需要同步的文件，避免全量传输
- Phase 3（verify/commit）确保两端一致后才推进 parent_hash
- 分离"快照交换""内容传输""一致性校验"三个职责

**为什么 check 需要返回 all_paths？**
- 增量响应（只返回变更文件）的 API 设计，客户端无法区分"未变更（云端有但未改）"和"不存在（云端没有此文件）"
- 远程状态必须显式查询，不能用本地元数据（如 local_parent is not None）猜测

**为什么 .jsonl 不走 AI 合并？**
- JSONL 是追加式写入，没有消息 ID，按时间戳排序合并有歧义
- 主备模式下发起同步的本地端是活跃端，保留本地版本数据更新
- 复杂度高收益低

**为什么 hash 需要规范化？**
- 两端可能因操作系统差异（Windows \r\n vs Linux \n）导致相同语义内容 hash 不同
- 去除行尾空白避免编辑器自动 strip trailing spaces 导致误判
- 保留词语间空格避免内容碰撞

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **数据库同步 + 动态表 + 心跳路由**：[`docs/specs/2026-07-16-data-sync-core-spec.md`](./2026-07-16-data-sync-core-spec.md) — 静态表、动态表、心跳、配置初始化
- **同步模块总览**：[`docs/specs/2026-07-16-data-sync-overview.md`](./2026-07-16-data-sync-overview.md) — 子模块架构、依赖规则、跨层交互
- **ADR 时间线**：[`docs/adr/2026-07-27-sync-system-timeline.md`](../adr/2026-07-27-sync-system-timeline.md)
- **数据流**：[`docs/flows/2026-07-11-data-sync-flow.md`](../flows/2026-07-11-data-sync-flow.md)
