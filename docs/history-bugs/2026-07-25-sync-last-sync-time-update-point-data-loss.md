---
version: 1.0
created_at: 2026-07-25
updated_at: 2026-07-25
last_updated: 记录 sync_once 末尾更新 last_sync_time 为结束时间导致期间写入数据被永久排除的修复过程
abstract: sync_once 在全部步骤成功后将 last_sync_time 更新为"同步结束时间"（T_end），导致 sync 期间其他任务（如 dreaming、AgentLoop）写入数据库的数据 updated_at 落在 (T_start, T_end) 区间，下次 sync 的 query_incremental 使用 WHERE updated_at > T_end 永远查不到这些数据，造成静默数据丢失；修复为在 sync_once 开始时记录 sync_cutoff_time（开始时间），末尾用该值更新 last_sync_time，代价是下次 sync 会重复 Push 已 Push 过的数据（LWW 幂等处理，无副作用）。
status: fixed
---

# sync_once 末尾更新 last_sync_time 为结束时间导致期间写入数据被永久排除

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 记录问题根因、修复方案、回归测试和规则沉淀 |

## 元信息

- **发生时间**: 2026-07-25（GlobalTaskState 互斥机制实施过程中发现）
- **发现时间**: 2026-07-25
- **修复状态**: 已修复（2026-07-25）
- **影响范围**: 任何在 sync_once 执行期间写入数据库的任务，包括 AgentLoop（用户聊天）、dreaming（LLM 写 mood_entries 等）、`_process_session_message`（4h chat history）、incremental_sync（ActivityWatch 数据）
- **bug 类型**: 同步机制设计缺陷（last_sync_time 更新点错误）
- **严重程度**: P1 — 静默数据丢失，不会触发任何异常或错误日志，但需要 sync 期间恰好有写入才会触发

## 触发规则

在以下场景时阅读本文档：

- 修改 `sync_client.py` 中 `sync_once` 函数的 `last_sync_time` 更新逻辑
- 修改 `sync_repository.py` 中 `query_incremental` 的 `WHERE updated_at > ?` 查询条件
- 排查"本地写入的数据同步后云端没有"
- 排查"sync 期间写入的数据下次 sync 仍不会被 Push"
- 讨论 sync_once 与 AgentLoop / dreaming / 其他定时任务的并发写入问题
- 设计或修改 GlobalTaskState 互斥机制（[ADR 2026-07-25](../adr/2026-07-25-global-task-state.md)）
- 评估"last_sync_time 应该取开始时间还是结束时间"

## Bug 简述

[`SyncClient.sync_once()`](../../lifeprism/sync/sync_client.py) 的原始实现：

1. 在函数开头读取 `last_sync_time = get_setting("sync.last_sync_time", "")`
2. 执行 Pull（拉云端数据）→ Push（推送本地增量）→ 文件同步等步骤
3. 在末尾用 `current_time = datetime.now(timezone.utc).isoformat()`（**结束时间 T_end**）更新 `last_sync_time`

[`SyncRepository.query_incremental()`](../../lifeprism/repository/sync_repository.py) 用 `WHERE updated_at > ?` 查询增量数据，严格 `>`。

**问题**：sync_once 期间（T0 ~ T_end）如果有其他任务写入数据库（如 dreaming 在 Push 之后写入 batch2，updated_at = T3，T0 < T3 < T_end），由于：

- 本次 Push 在 T3 之前完成，未读到 batch2 → 本次不 Push batch2
- 末尾更新 `last_sync_time = T_end`（T_end > T3）
- 下次 sync: `WHERE updated_at > T_end` → batch2（updated_at = T3 < T_end）永远查不到 → **数据永久丢失**

## 复用场景

此问题可作为以下设计和排查场景的参考：

- 任何"增量同步 + last_sync_time"模式（CDC / Change Data Capture）
- 同步系统与业务写入并发执行的边界条件分析
- "时间戳作为增量游标"的更新点选择（开始 vs 结束）
- 跨任务并发写入同一数据库的隔离性分析
- 评估"互斥机制能否彻底避免数据丢失"

核心经验是：**增量同步的 last_sync_time 必须记录"读取数据的时刻"（即 sync 开始时间），而不是"同步完成的时刻"**。否则 sync 期间的任何写入都会落入时间窗口黑洞，被永久排除。

## 代码位置

### Bug 发生位置

- **last_sync_time 读取**：[`lifeprism/sync/sync_client.py`](../../lifeprism/sync/sync_client.py) `sync_once()` 函数开头 — `last_sync_time = get_setting("sync.last_sync_time", "")`
- **last_sync_time 写入（bug 点）**：[`lifeprism/sync/sync_client.py`](../../lifeprism/sync/sync_client.py) `sync_once()` 函数末尾 — 原代码 `current_time = datetime.now(timezone.utc).isoformat()` 后 `set_setting("sync.last_sync_time", current_time)`
- **增量查询入口**：[`lifeprism/repository/sync_repository.py`](../../lifeprism/repository/sync_repository.py) `query_incremental()` — `WHERE updated_at > ?` 严格 `>`
- **Push 调用**：[`lifeprism/sync/sync_client.py`](../../lifeprism/sync/sync_client.py) `_push_db_records()` — 调用 `query_incremental(last_sync_time)` 读取增量数据

### 修复位置

- [`lifeprism/sync/sync_client.py`](../../lifeprism/sync/sync_client.py) `sync_once()` 函数：
  - 函数开头新增：`sync_cutoff_time = datetime.now(timezone.utc).isoformat()`（记录开始时间）
  - 末尾修改：`set_setting("sync.last_sync_time", sync_cutoff_time)`（用开始时间替代结束时间）

## 触发条件

以下条件同时成立时触发：

1. sync_once 开始执行（T0），读取 `last_sync_time = T_prev`
2. sync_once 执行 Push 阶段，`query_incremental` 用 `WHERE updated_at > T_prev` 读到 batch1（updated_at = T1，T1 > T_prev）
3. Push 完成，但 sync_once 还在继续执行（如文件同步、verify 等）
4. 其他任务（AgentLoop / dreaming / 4h 任务）在 Push 之后写入 batch2（updated_at = T3，T0 < T3 < T_end）
5. sync_once 全部完成，更新 `last_sync_time = T_end`（T_end > T3）
6. 下次 sync_once: `WHERE updated_at > T_end` → batch2 永远查不到

**触发概率**：
- AgentLoop 是常驻进程，用户随时可能在 sync 期间聊天触发数据库写入 → 概率较高
- dreaming / incremental_sync 与 sync_once 有 GlobalTaskState 互斥，但超时降级时可能并发 → 概率较低但存在
- `_process_session_message` 同样有互斥，但同样存在超时降级

## 完整失败数据流

假设 sync_once 在 T0 开始，期间有 dreaming 写入：

```text
T0: sync_once 开始, last_sync_time = T_prev
    ↓
    Pull 阶段：拉云端数据 upsert 到本地（用 last_sync_time=T_prev 作为云端查询参数）
    ↓
    Push 阶段：
    query_incremental: WHERE updated_at > T_prev
    → 读到 batch1 (updated_at=T1, T1 > T_prev)
    → Push batch1 到云端 ✅
    → 未读到 batch2（batch2 还没写入）
    ↓
    文件同步、verify 等步骤...
    ↓
    dreaming 在此期间写入 batch2 (updated_at=T3, T0 < T3 < T_end)
    ↓
T_end: sync_once 全部完成
       set_setting("sync.last_sync_time", T_end)  # T_end > T3
    ↓
下次 sync_once:
    query_incremental: WHERE updated_at > T_end
    → batch2.updated_at = T3 < T_end
    → batch2 永远查不到 ❌ 数据丢失
```

## 发生原因

### 1. last_sync_time 语义误用

`last_sync_time` 的字面含义是"最后一次同步的时间"，但实际作为增量游标使用时，它的语义必须是"下次增量查询的起点"。

作为增量游标，它应该记录**"本次增量查询已经读到的数据时间点"**，即 sync 开始时间 T0（query_incremental 用 `WHERE > T_prev`，T0 之前的数据已经被读过了）。

错误地记录为 T_end，等于把 sync 期间的写入"划归"给了本次 sync，但实际上本次 sync 的 Push 并没有读到这些数据。

### 2. 事务边界假设错误

原始设计隐含假设"sync_once 是原子的，期间不会有其他写入"。但实际上：
- SQLite 本身支持并发读写（WAL 模式）
- AgentLoop 是 asyncio 常驻循环，与 sync_once 在同一进程内并发
- 即使有 GlobalTaskState 互斥，也只能互斥 dreaming / 4h 任务等"已知任务"，无法互斥 AgentLoop

### 3. GlobalTaskState 互斥的局限

GlobalTaskState 互斥机制（[ADR 2026-07-25](../adr/2026-07-25-global-task-state.md)）可以避免：
- dreaming 与 sync_once 同时执行
- `_process_session_message` 与 sync_once 同时执行

但**无法避免**：
- AgentLoop 与 sync_once 同时执行（AgentLoop 不参与互斥）
- 互斥超时降级后的并发执行

因此互斥机制是"减少冲突概率"而非"彻底避免"，**根本性的修复必须从 last_sync_time 更新点入手**。

## 最佳方案

采用最小修改：在 sync_once 开头记录 `sync_cutoff_time`（开始时间），末尾用该值更新 `last_sync_time`。

```python
def sync_once(self, tables=None, directories=None):
    # sync 开始时间作为增量游标的"已读点"
    sync_cutoff_time = datetime.now(timezone.utc).isoformat()
    
    # ... 所有同步步骤（Pull/Push/文件同步等）...
    
    # 用开始时间更新 last_sync_time
    # - 保证 sync 期间写入的数据 updated_at > sync_cutoff_time
    # - 下次 sync 的 query_incremental WHERE > sync_cutoff_time 会包含这些数据
    set_setting("sync.last_sync_time", sync_cutoff_time)
```

选择该方案的原因：

1. **修复彻底**：sync 期间任何写入的 updated_at 都 > T0（sync_cutoff_time），下次 sync 都会被 Push
2. **实现简单**：只改 2 行代码（新增 1 行 + 修改 1 行）
3. **代价可接受**：下次 sync 会重复 Push 本次已 Push 过的数据（updated_at ∈ (T_prev, T0]），但云端 LWW 幂等处理（updated_at 相同跳过覆盖），无副作用
4. **保持事务一致性**：仍然在 sync_once 末尾更新 last_sync_time，任何步骤失败都不会推进游标，下次完整重试

## 修复内容

### 1. sync_once 开头记录开始时间

[`lifeprism/sync/sync_client.py`](../../lifeprism/sync/sync_client.py) `sync_once()` 函数开头，在读取 `last_sync_time` 之后新增：

```python
sync_cutoff_time = datetime.now(timezone.utc).isoformat()
```

### 2. sync_once 末尾用开始时间更新 last_sync_time

[`lifeprism/sync/sync_client.py`](../../lifeprism/sync/sync_client.py) `sync_once()` 函数末尾：

```python
# 修改前
current_time = datetime.now(timezone.utc).isoformat()
set_setting("sync.last_sync_time", current_time)

# 修改后
set_setting("sync.last_sync_time", sync_cutoff_time)
```

### 3. 关键注释说明

在 `sync_cutoff_time` 声明处添加详细注释，说明：
- 为什么用开始时间而非结束时间
- 代价是下次重复 Push（LWW 幂等）
- 参考 ADR 文档

## 验证结果

### 回归测试

```bash
python -m pytest test/core/unit/sync/ -v
```

结果：

```text
212 passed, 2 failed
```

2 个失败是预存的 `test_hash_id_prefixes.py`（与本次修复无关，是关于 hash_id 表数量不匹配的预存问题）。

## 教训与规则沉淀

1. **增量游标必须记录"已读点"而非"完成点"**：`last_sync_time` 作为增量查询的游标，应该记录"本次查询已经读到的数据时间点"（sync 开始时间），而不是"同步完成的时刻"。否则 sync 期间的写入会落入时间窗口黑洞。

2. **同步系统与业务写入的并发是常态**：不能假设 sync_once 期间数据库不会被其他任务写入。AgentLoop 是常驻循环，任何用户聊天都会触发数据库写入，sync_once 必须能容忍并发写入。

3. **互斥机制不能替代游标正确性**：GlobalTaskState 互斥可以减少冲突概率，但无法彻底避免（AgentLoop 不参与互斥，超时降级也存在）。根本性的修复必须从机制本身入手，而非依赖外层互斥。

4. **"原子事务"假设需要校验**：原设计隐含假设"sync_once 是原子的"，但 SQLite WAL 模式支持并发读写，asyncio 多任务也会在 sync 期间穿插执行。任何"原子性"假设都需要在代码中显式校验。

5. **代价分析要量化**：本修复的代价是下次 sync 重复 Push 一批数据（updated_at ∈ (T_prev, T0]），但 LWW 幂等处理（云端 updated_at 相同跳过覆盖），无副作用，性能影响可忽略。设计修复方案时必须量化代价，不能因"重复 Push 听起来不好"而否定方案。

## 预防措施

- 任何"增量游标"（last_xxx_time / last_xxx_id / last_xxx_offset）的更新值必须是"读取数据的时刻"，不能是"处理完成的时刻"。
- 同步系统设计时，必须分析"sync 期间业务写入"的去向，确保这些写入在下次 sync 时能被正确捕获。
- Code Review 检查 `last_sync_time` / `last_sync_id` 等游标的更新点，确保不是 `datetime.now()`（结束时间）。
- 同步系统的单元测试必须覆盖"sync 期间有写入"的场景，验证下次 sync 能捕获这些写入。

## 关联问题

- GlobalTaskState 互斥机制 ADR：[`docs/adr/2026-07-25-global-task-state.md`](../adr/2026-07-25-global-task-state.md)
- 数据备份策略 ADR：[`docs/adr/2026-07-17-data-backup-strategy.md`](../adr/2026-07-17-data-backup-strategy.md)
- 数据备份 Spec：[`docs/specs/2026-07-17-data-backup-spec.md`](../specs/2026-07-17-data-backup-spec.md)
