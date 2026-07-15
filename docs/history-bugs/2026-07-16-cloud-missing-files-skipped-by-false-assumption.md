# 云端缺失文件被错误 SKIP — per-file version tracking 引入的回归 bug

## 元信息

- **发生时间**: 2026-07-15
- **发现时间**: 2026-07-16
- **修复状态**: ✅ 已修复（all_paths 完整路径清单方案）
- **影响范围**: 文件同步全流程 — 云端重装/重新初始化后，本地已同步且未修改的文件无法重新推送
- **bug 类型**: 回归 bug — 新冲突处理策略引入的错误假设
- **严重程度**: 严重（P0）— 云端丢失全部 session/diary/agent/user 文件且无法自动恢复

## 触发规则

在以下场景时阅读此文档：
- 云端重装/重新初始化后，本地文件不再同步到云端
- 排查"session JSONL 文件之前能同步，改了冲突策略后不能了"
- 涉及 `_sync_files_full_flow` 中 `remote_state is None` 分支逻辑的修改
- 涉及 `/pull-files/check` 端点返回值结构的修改
- 排查 `file_sync_state` 表状态与文件同步行为的关系
- 修改 11 态矩阵判定逻辑（`_decide_sync_action`）

## Bug 简述

从纯 mtime LWW 切换到 per-file version tracking（parent_hash + current_hash + 11 态矩阵）后，`/pull-files/check` 端点只返回 mtime 过滤后的变更文件，不返回云端完整文件路径清单。本地在文件不在变更列表中时，用 `local_parent is not None` 猜测"云端有但未改"，导致云端已缺失的文件被错误 SKIP，永远无法重新推送。

## 复现场景

1. 本地与云端正常同步一次 → 本地 `file_sync_state` 记录 `parent_hash = current_hash = X`（已同步且未修改）
2. 云端重装/重新初始化 → 云端文件全部丢失
3. 本地触发 `sync_once` → check 端点返回空变更列表（云端无文件）
4. 本地代码：`remote_state is None` + `local_parent is not None` → 假设"云端有但未改" → `remote_current = local_parent` → 11 态矩阵判定 SKIP
5. **结果：文件永远不会重新推送到云端**

## 复用场景

- 任何"用本地状态猜测远端状态"的同步逻辑设计 — 远端状态必须通过显式查询获取，不能用本地元数据猜测
- API 端点设计 — 增量响应（只返回变更项）时，需额外提供完整清单或存在性信息，否则客户端无法区分"未变更"和"不存在"

## 代码位置

### 问题代码（修复前）

**客户端**：[lifeprism/sync/sync_client.py:1351-1360](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1351-L1360)（`_sync_files_full_flow` 内）

```python
# 文件不在 check 响应中 → 远端未变更或不存在
if remote_state is None:
    if local_parent is not None:
        # 本地有 parent（之前同步过）→ 远端有但未改  ← 错误假设
        remote_parent = local_parent
        remote_current = local_parent
    else:
        # 本地无 parent（新文件）→ 远端不存在
        remote_parent = None
        remote_current = None
```

**云端 check 端点**：[lifeprism/server/api/sync_cloud_api.py:531-610](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L531-L610)

只返回 `files`（mtime > last_sync_time 的变更文件），不返回云端完整文件路径清单。

## 发生原因

### 时间线

1. **最初（纯 mtime LWW，`1d7637c8` 之前）**：无 check 端点，`/pull-files` + `/push-files` 直接传内容，push 侧只收集 `mtime > last_sync_time` 的文件
2. **改为 per-file version tracking**（ADR 2026-07-14，提交 `1d7637c8`）：引入 `file_sync_state` 表 + parent_hash/current_hash + 11 态矩阵 + check 端点
3. **check 端点设计缺陷**：只返回 mtime 过滤后的变更文件，不返回完整路径清单
4. **客户端猜测逻辑**：当文件不在变更列表中时，用 `local_parent is not None` 猜测云端是否有文件

### 根因分析

`/pull-files/check` 端点用 mtime 做第一重过滤，只返回变更文件。当文件不在变更列表中时，存在两种可能：

| 情况 | 含义 | 正确处理 |
|------|------|---------|
| 云端有文件但 mtime <= last_sync_time | 未变更 | SKIP |
| 云端根本没有此文件 | 文件丢失/重装 | PUSH |

修复前的代码无法区分这两种情况，用 `local_parent is not None` 做猜测：
- `local_parent` 有值（之前同步过）→ 假设"云端有但未改" → SKIP
- `local_parent` 无值（新文件）→ 假设"云端不存在" → PUSH

这个猜测在**云端文件存在且未变更**时恰好正确，但在**云端文件不存在**时导致错误 SKIP。

### 为什么最初能同步 — 旧 mtime LWW 也有同样问题

**用户反馈"之前能同步"指的是首次同步场景**，并非旧逻辑本身无此 bug。经 git history 调查（`1d7637c8` 之前），旧 mtime LWW 逻辑同样存在"云端缺失 + 本地未改 → 不推送"的问题，只是触发条件不同：

| 阶段 | push 侧收集逻辑 | 云端重装 + 本地未改场景 |
|------|----------------|----------------------|
| 旧 mtime LWW（`1d7637c8` 前） | `mtime > last_sync_time` 的文件 | last_sync_time 有值时同样推不了（mtime 未变） |
| per-file version tracking（修复前） | check 响应中含 path 或 local_parent 无值 | local_parent 有值时错误 SKIP |

**首次同步能成功的原因**：`last_sync_time` 为空时，代码置为 `datetime(1970, 1, 1)`，所有文件 mtime > 1970 → 全部进入 push 列表。一旦首次同步成功写入 `last_sync_time`，之后云端重装 + 本地未改 → mtime 未变 → 不进 push 列表 → 同样推不了。

**用户观察到"改了冲突策略后不能同步"的真实原因**：首次同步成功后（无论新旧逻辑），后续云端重装时本地文件 mtime 未变，两种逻辑都推不了。只是 per-file version tracking 引入 check 端点 + local_parent 猜测后，问题从"mtime 过滤漏掉"变成了"错误 SKIP"，更隐蔽。

**结论**：此 bug 是"远端状态未显式查询"的设计通病，不因新旧策略而消失。新策略通过 `all_paths` 方案修复后，同时覆盖了旧逻辑下也存在的该问题。

### `file_sync_state` 表变空的影响

`file_sync_state` 表不在 `SYNC_TABLES` 中（[sync_client.py:51-90](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L51-L90)），不会通过数据库同步通道传输。两端各自独立维护。

如果本地 `file_sync_state` 表被清空（如测试 fixture 执行 `DELETE FROM file_sync_state`），`_refresh_current_hashes` 会在下次同步时重新填充，所有文件的 `parent_hash = None` → 走"云端不存在"分支 → PUSH。所以表空时反而不会触发此 bug。

此 bug 的触发条件是：**表有数据**（parent_hash 有值）+ **云端文件不存在**。

## 最佳方案

### 修复方案：check 端点返回完整路径清单

让 `/pull-files/check` 端点在原有 `files`（变更文件 hash 状态）基础上，新增返回 `all_paths`（云端 SYNC_DIRECTORIES 下所有文件的相对路径列表，应用相同黑白名单）。本地用 `all_paths` 集合替代"基于 local_parent 猜测"的逻辑。

### 具体改动

**1. 云端 check 端点**（[sync_cloud_api.py:531-627](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L531-L627)）

单次遍历同时收集：
- `files`：mtime > last_sync_time 的变更文件（含 path + parent_hash + current_hash）— 已有逻辑
- `all_paths`：所有非黑名单文件的相对路径（仅路径字符串，不做 mtime 过滤）— 新增

返回值新增 `all_paths` 字段。

**2. 客户端 `_pull_files_check`**（[sync_client.py:688-735](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L688-L735)）

返回值从 `list[dict]` 改为 `tuple[list[dict], list[str]]`（files + all_paths）。

**3. 客户端 `_sync_files_full_flow`**（[sync_client.py:1302-1447](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1302-L1447)）

替换错误假设逻辑：

```python
# 修复后：
if remote_state is None:
    if path in remote_all_paths_set:
        # 云端有文件但未变更 → SKIP（正确）
        remote_parent = local_parent
        remote_current = local_parent
    else:
        # 云端没有此文件 → PUSH（修复）
        remote_parent = None
        remote_current = None
```

11 态矩阵判定函数 `_decide_sync_action` 不改 — 矩阵本身正确，bug 在于喂给矩阵的 remote 状态被错误假设。

### 修复前后对比

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 云端缺失 + 本地未改（parent==current） | SKIP（永远不推送） | PUSH ✅ |
| 云端缺失 + 本地已改 | PUSH | PUSH ✅ |
| 云端有未改 + 本地未改 | SKIP | SKIP ✅ |
| 云端有未改 + 本地已改 | PUSH | PUSH ✅ |
| 云端有未改 + 本地无（换电脑） | PULL | PULL ✅ |

### 设计教训

1. **远端状态必须显式查询，不能用本地元数据猜测** — `local_parent is not None` 只能证明"本地之前同步过"，不能证明"云端当前有此文件"
2. **增量响应需附带存在性信息** — 只返回变更项的 API 设计，必须额外提供完整清单或存在性标记，否则客户端无法区分"未变更"和"不存在"
3. **回归 bug 隐蔽性** — 从纯 mtime LWW 切换到 per-file version tracking 时，新引入的 parent_hash 机制在"云端有但未改"场景恰好正确，掩盖了"云端不存在"场景的错误。只有云端重装/文件丢失时才暴露

## 相关文档

- ADR: [2026-07-14-file-sync-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-14-file-sync-conflict-resolution.md) — per-file version tracking 设计决策
- 前序 bug: [2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md) — 同步链路未打通 + 空文档覆盖
- 修复提交：`all_paths` 完整路径清单方案（2026-07-16）
