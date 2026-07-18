---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 2026-07-17
abstract: 备份范围与同步范围解耦——plan 加入备份但不加入同步，因为两者职责不同（同步是功能性，备份是数据安全性）
status: decided
---

# 备份范围与同步范围解耦：职责不同

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

在定义数据备份范围时，面临一个选择：
- 复用现有 `SYNC_DIRECTORIES`（单一数据源原则）
- 独立定义 `BACKUP_DIRS`（解耦）

冲突点：`plan/` 目录当前既不在同步范围也不在备份范围，但其中包含用户重要的计划文档（减肥计划、学习计划、项目计划等 30+ 个文件），是用户长期累积的核心资产。

### 讨论范围

- 备份范围的定义方式（复用 SYNC_DIRECTORIES vs 独立定义）
- `plan/` 目录是否加入同步范围
- `plan/` 目录是否加入备份范围

### 非讨论范围

- 同步机制本身（仅决定 plan 是否加入同步）
- 备份机制本身（见 ADR `2026-07-17-data-backup-strategy.md`）
- 其他目录（session/diary/agent/user 是否在备份范围）

### 模糊信息的明确定义

- `SYNC_DIRECTORIES`：现有同步白名单，定义为 `["session/", "diary/", "agent/", "user/"]`
- `BACKUP_DIRS`：本次新建的备份白名单
- `plan/`：用户主动创建的计划文档目录，通过前端 UI 创建，路径为 `lifeprismData/plan/{id}.md`

### 问题深度

涉及架构原则——关注点分离。同步和备份是两个独立的目的，不应该强行耦合。

## 现状

**SYNC_DIRECTORIES**（[constants.py:63-68](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/constants.py#L63-L68)）：
```python
SYNC_DIRECTORIES = [
    "session/",  # 聊天会话 JSONL
    "diary/",    # 日记 MD
    "agent/",    # Agent 身份/记忆/chat 配置
    "user/",     # 用户级数据
]
```

**plan 目录当前状态**：
- 路径：`{lifeprism_data_path}/plan/{id}.md`
- 写入方式：通过 [plan_doc_service.py:5](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/plan_doc_service.py#L5) 由前端 UI 创建
- 实际数据：30+ 个用户计划文档（减肥计划、学习计划、项目计划等）
- 同步状态：❌ 不同步（不在 SYNC_DIRECTORIES 中）
- 备份状态：❌ 不备份（无定时备份机制）
- **风险**：本地文件损坏时所有计划文档丢失

## 决策前提

- 前提 1（事实）：plan 目录当前既不同步也不备份，处于"裸奔"状态
- 前提 2（用户判断）：同步和备份的职责本来就不同——同步是从云端和本地功能性考虑，备份是从数据安全性考虑
- 前提 3（用户判断）：从功能性看 plan 没有同步必要（Agent 无法读取 plan 文件夹）
- 前提 4（事实）：plan 与数据库高度绑定（plan_doc 表存储元数据，plan/ 目录存储 .md 内容）
- 前提 5（用户判断）：plan 一旦修改错误很难恢复，更需要备份保护
- 前提 6（事实）：sync_client 一直在打补丁（近 15 个 commit 中有 10 个是同步相关 fix），加入新目录到同步范围是引入新变量
- 前提 7（用户偏好）：避免不必要的耦合（单一数据源原则在职责不同时不适用）

## 可选方案

### 方案 A：复用 SYNC_DIRECTORIES（同时让 plan 加入同步和备份）

将 plan 加入 SYNC_DIRECTORIES，备份范围复用同步范围。

**优势**

- 单一数据源原则
- plan 同时获得同步和备份保护

**劣势**

- 修改同步范围引入新变量，可能触发未知 bug
- plan 加入同步是独立的决策，不应该在备份 PRD 中顺带决定
- 违背"职责不同不应耦合"原则
- Agent 无法读取 plan 文件夹，同步 plan 无功能性价值
- plan 与数据库高度绑定，文件同步可能与数据库同步产生不一致

### 方案 B：独立定义 BACKUP_DIRS（plan 加入备份但不加入同步）（当前选择）

**优势**

- 关注点分离：备份范围与同步范围独立演进
- 不引入同步风险：不修改 SYNC_DIRECTORIES，避免触发 sync_client 未知 bug
- plan 获得备份保护：防止数据丢失
- 职责清晰：备份是"防止数据丢失"，同步是"多端数据一致"

**劣势**

- 违反"单一数据源"原则（但仅在职责相同时适用）
- plan 没有同步保护（但备份已足够防止数据丢失）

### 方案 C：除 screenshots 外全部备份（黑名单模式）

```python
BACKUP_DIRS = None  # 备份所有，排除 screenshots/
```

**优势**

- 永远不会遗漏新目录

**劣势**

- 黑名单模式不如白名单安全
- 可能备份意外内容（如 exports/、temp/）

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 同步和备份职责不同 + plan 无同步必要 + sync_client 不稳定 | 方案 B（独立 BACKUP_DIRS） | 当前选择 |
| 未来 plan 需要多端访问 | 方案 A（加入 SYNC_DIRECTORIES） | 备选触发条件（独立决策） |
| 接受黑名单风险 + 希望永远不遗漏新目录 | 方案 C（黑名单） | 不推荐 |

## 最终决策

当前成立的前提：
- 前提 2（同步和备份职责不同）
- 前提 3（plan 无同步必要，Agent 无法读取）
- 前提 5（plan 更需要备份保护）
- 前提 6（sync_client 不稳定，不引入新变量）
- 前提 7（避免不必要耦合）

因此选择 **方案 B**：

```python
# lifeprism/backup/constants.py（新建）

BACKUP_DIRS = [
    "session/",   # 聊天会话 JSONL
    "diary/",     # 日记 MD
    "agent/",     # Agent 身份/记忆/配置
    "user/",      # 用户级数据
    "plan/",      # 计划文档（仅备份，不加入同步范围）
]

BACKUP_EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}
```

- `BACKUP_DIRS` 独立定义，不依赖 `SYNC_DIRECTORIES`
- 内容与 `SYNC_DIRECTORIES` 保持一致 + 多了 `plan/`
- 排除文件名与同步一致（`chat_history.json`、`bootstrap.md`）
- 不依赖 `SYNC_DIRECTORIES` 但**保持一致性**是纪律性约束，不是代码依赖

前提失效时的切换路径：
- 若未来 plan 需要多端访问 → 在 SYNC_DIRECTORIES 中加入 plan（独立决策）
- 若未来需要更严格的"单一数据源"约束 → 重新评估方案 A

## 决策原因

- 原因 1：同步和备份职责不同，不应该强行耦合
- 原因 2：plan 无同步必要（Agent 无法读取，且与数据库高度绑定）
- 原因 3：plan 一旦修改错误难恢复，更需要备份保护
- 原因 4：sync_client 不稳定，不引入新变量到同步范围
- 原因 5：避免不必要耦合，让备份与同步各自独立演进

## 后续影响

**代码结构**：
- 新建 `lifeprism/backup/constants.py`（BACKUP_DIRS 独立定义）
- 不修改 `lifeprism/sync/constants.py`（SYNC_DIRECTORIES 保持不变）

**纪律性约束**：
- BACKUP_DIRS 与 SYNC_DIRECTORIES 内容应保持一致（除 plan 外）
- 未来修改 SYNC_DIRECTORIES 时需检查 BACKUP_DIRS 是否需要同步更新
- 但这是纪律性约束，不是代码依赖

**plan 同步的独立决策**：
- 是否让 plan 多端同步是独立决策，应该在独立 ADR 中决定
- 不在本备份 PRD 中顺带决定

**关联文档**：
- `docs/adr/2026-07-17-data-backup-strategy.md`（数据备份 ADR）
- `docs/adr/2026-07-14-file-sync-conflict-resolution.md`（原同步 ADR，定义了 SYNC_DIRECTORIES）
- `.scratch/file-conflict-resolution-redesign/prd.md`（完整 PRD）
