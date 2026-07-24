---
title: 同步删除 - 阶段 3：墓碑同步流程
created_at: 2026-07-22
updated_at: 2026-07-23
status: completed
type: feature
---

# 同步删除 - 阶段 3：墓碑同步流程

## 总任务说明

本 PRD 是"数据库删除同步"任务链的**第 3 步（共 3 步）**，依赖 PRD 1（Schema 变更）和 PRD 2（代码适配）完成。

```
[PRD 1] Schema 变更（已完成 2026-07-22）
    │   6 张 AUTOINCREMENT 表加 hash_id 字段
    │   新增 deletion_log 墓碑表
    ▼
[PRD 2] 代码适配（已完成 2026-07-23）
    │   Provider 迁移 + 写入/删除通道统一
    │   _generic_delete 内部写墓碑（写入 deletion_log 表）
    ▼
[PRD 3] 墓碑同步流程（本 PRD，已完成 2026-07-23）
        DeletionLogProvider
        sync_once 集成墓碑 Pull/Push/清理
        端到端验证（A 设备删除 → B 设备同步删除）
```

**本 PRD 的边界**：实现墓碑在两端的传播流程和端到端验证。墓碑的写入逻辑（`_generic_delete` 内部）已在 PRD 2 完成，本 PRD 负责让墓碑跨端传播。

## Problem Statement

PRD 1 和 PRD 2 完成后：
- 6 张 AUTOINCREMENT 表有 `hash_id` 字段
- `deletion_log` 墓碑表已创建
- 所有删除通道走 `_generic_delete`，删除时写墓碑到 `deletion_log` 表

但墓碑只在**本地** `deletion_log` 表中，**云端和对端不知道**。需要：
1. Pull 阶段拉取云端墓碑，本地执行删除
2. Push 阶段推送本地墓碑，云端执行删除
3. 同步成功后清理过期墓碑

## Solution

### 1. DeletionLogProvider

新建 `DeletionLogProvider`（继承 `LWBaseDataProvider`），提供墓碑表的 CRUD：
- 写入墓碑（`create_tombstone` + `write_tombstone_with_cursor` cursor 变体）
- 按 `created_at > last_sync_time` 增量查询（`get_tombstones_since`）
- 按 `source` 过滤
- 清理 `created_at <= last_sync_time` 的记录（`cleanup_before`）
- 查询/写入墓碑的 cursor 变体（`get_tombstone_with_cursor` + `create_tombstone_with_cursor`）保证事务原子性

### 2. sync_once 主流程集成墓碑

```
sync_once 主流程（修改后）：

1. _sync_dynamic_tables_definitions   → 拉取云端定义、slug 对比、双向建表
2. _pull_deletion_log                 → 【新增】拉取云端墓碑，本地执行删除
3. pull_from_remote                   → 分批拉取数据库变更
4. _push_deletion_log                 → 【新增】推送本地墓碑，云端执行删除
5. push_to_remote                     → 推送本地数据库变更
6. _sync_files_full_flow              → 文件三阶段同步
7. _cleanup_deletion_log              → 【新增】清理 created_at <= last_sync_time 的墓碑
8. 更新 last_sync_time                → 全部成功后才更新
```

**顺序关键**：墓碑 Pull/Push 必须在数据 Pull/Push 之前，避免删除被后续 upsert 覆盖。

### 3. 墓碑同步通道：专用端点（替代 SYNC_TABLES）

**关键决策变更（v2）**：原计划将 `deletion_log` 加入 `SYNC_TABLES` 走数据同步通道，实施前发现该方案有严重的双重同步和 LWW 语义不匹配问题。最终采用 3 个专用端点：

- `/api/sync/pull-deletion-log` — 拉取云端 `created_at > last_sync_time` 的墓碑列表
- `/api/sync/push-deletion-log` — 推送本地墓碑到云端（云端对每条墓碑独立事务处理 LWW + DELETE + 写副本）
- `/api/sync/cleanup-deletion-log` — 清理云端 `created_at <= last_sync_time` 的墓碑

`deletion_log` **不在 `SYNC_TABLES`** 中，避免被 `pull_from_remote`/`push_to_remote` 当作普通数据 upsert 导致双重同步。

### 4. 墓碑 LWW 简化：INSERT OR IGNORE 跳过

墓碑不更新（`updated_at == created_at`），不比较 `updated_at`。本地已有同 `(target_table, record_id)` 墓碑时 `INSERT OR IGNORE` 跳过，利用 `UNIQUE(target_table, record_id)` 约束自然去重。

### 5. 事务边界：HTTP 外事务内

HTTP 请求（拉取/推送墓碑）在事务外执行，获取到墓碑列表后开事务执行 DELETE + 写副本，失败则整个事务回滚。cursor 变体方法（`get_tombstone_with_cursor`、`create_tombstone_with_cursor`、`execute_tombstone_delete_with_cursor`）保证 SQL 封装在 Repository 层但事务边界由调用方控制。

## User Stories

### DeletionLogProvider

1. 作为系统开发者，新建 `DeletionLogProvider`（继承 `LWBaseDataProvider`），定义元数据（`_TABLE_NAME = "deletion_log"`、`_PRIMARY_KEY = "id"`、`_FILTER_FIELDS = {"source", "target_table"}`、`_ORDER_FIELDS = {"created_at"}`）。
2. 作为系统开发者，`DeletionLogProvider` 支持写入墓碑（`id` 用 `dl-` 前缀 + 8 位 hex）。
3. 作为系统开发者，`DeletionLogProvider` 支持按 `created_at > last_sync_time` 增量查询。
4. 作为系统开发者，`DeletionLogProvider` 支持按 `source` 过滤（local/cloud）。
5. 作为系统开发者，`DeletionLogProvider` 支持清理 `created_at <= last_sync_time` 的记录。
6. 作为系统开发者，`DeletionLogProvider` 字段约束：`target_table` 非空、`record_id` 非空、`source` 只能是 local/cloud。

### 墓碑 Pull

7. 作为同步系统，Pull 阶段必须先拉取云端墓碑（`created_at > last_sync_time` 的 `deletion_log` 记录）。
8. 作为同步系统，Pull 阶段对每条云端墓碑执行 `DELETE FROM {target_table} WHERE {pk 或 hash_id} = {record_id}`，传播删除意图到本地。
9. 作为同步系统，Pull 阶段拉取的云端墓碑必须写入本地 `deletion_log` 副本，标记 `source=cloud`，避免下次 Pull 重复执行删除。
10. 作为同步系统，墓碑 Pull 的顺序必须在数据 Pull 之前（先传播删除，再传播更新）。

### 墓碑 Push

11. 作为同步系统，Push 阶段必须推送本地墓碑（`created_at > last_sync_time` 且 `source=local`）到云端。
12. 作为同步系统，云端收到墓碑后执行真实删除，并写入云端 `deletion_log` 副本（标记 `source=cloud` 表示已传播）。
13. 作为同步系统，墓碑 Push 的顺序必须在数据 Push 之前（先传播删除，再传播更新）。

### 墓碑清理

14. 作为同步系统，同步全部成功后，两端清理 `created_at <= last_sync_time` 的墓碑记录。
15. 作为同步系统，墓碑清理采用激进策略——本项目是严格两节点（本地↔云端），不存在多设备清理导致删除丢失的风险。

### 墓碑 LWW

16. 作为同步系统，墓碑比较使用 `updated_at` 字段作 LWW——墓碑不修改，插入时 `created_at == updated_at`，行为等价。
17. 作为同步系统，两端都有同一墓碑时（按 `target_table + record_id` 唯一），保留 `updated_at` 更晚的。

### 事务与失败处理

18. 作为同步系统，墓碑同步失败时整个 `sync_once` 必须失败，不更新 `last_sync_time`，下次重试。

### 边界场景

19. 作为用户，重置同步进度（`POST /api/sync/reset-sync-progress`）后，墓碑机制必须仍然工作——重置只清 `last_sync_time`，不清 `deletion_log` 表。
20. 作为用户，全量首同步（`_full_sync_to_cloud`）时不应传播墓碑——首同步假设云端为空。
21. 作为用户，A 设备删除一条记录后，B 设备在下一次同步后该记录应消失。
22. 作为用户，A 设备删除一条记录后，云端保留的该记录在 B 设备 Pull 后应被正确删除（删除被传播，不被回滚）。
23. 作为系统，删除-更新冲突（一边删、另一边改）作为已知限制接受——不自动处理。

## Implementation Decisions

### 模块改造清单

| 模块 | 改造内容 |
|------|---------|
| `lifeprism/repository/providers/deletion_log_provider.py`（新建） | 墓碑表 Provider，CRUD + 增量查询 + 清理 |
| `lifeprism/repository/providers/__init__.py` | 注册 `deletion_log_provider` 单例 |
| `lifeprism/sync/sync_client.py` | `sync_once` 主流程新增 `_pull_deletion_log` + `_push_deletion_log` + `_cleanup_deletion_log` |
| `lifeprism/server/api/sync_cloud_api.py` | 新增 3 个专用端点（`pull-deletion-log`、`push-deletion-log`、`cleanup-deletion-log`），云端执行 DELETE + 写副本。`deletion_log` 已从 `SYNC_TABLES` 移除，墓碑仅通过专用通道同步 |
| `lifeprism/sync/constants.py` | 从 `SYNC_TABLES` 移除 `deletion_log`（墓碑走专用通道） |
| `lifeprism/server/api/sync_cloud_api.py`（`full-clear` 端点） | 在 `SYNC_TABLES` 遍历清空之后，显式调用 `delete_all_rows("deletion_log")` 清空墓碑表 |
| `lifeprism/server/api/sync_status_api.py` | 显式追加 `deletion_log` 到状态查询表列表 |
| `lifeprism/repository/sync_repository.py` | 新增 `execute_tombstone_delete(target_table, record_id)` 方法，通过 `HASH_ID_PREFIXES` 判断列，不写墓碑 |
| `lifeprism/repository/aggregators/custom_record_aggregator.py` | `delete_entry` 通过 `write_tombstone_with_cursor` 写墓碑（与 DELETE 同事务） |

### DeletionLogProvider 元数据

```python
_TABLE_NAME = "deletion_log"
_PRIMARY_KEY = "id"
_ON_CONFLICT = "ignore"  # 与 _write_tombstone 的 INSERT OR IGNORE 语义一致
_FILTER_FIELDS = {"source", "target_table"}
_ORDER_FIELDS = {"created_at"}
_SELECT_FIELDS = {"id", "target_table", "record_id", "source", "created_at", "updated_at"}
```

### sync_once 主流程

```
1. _sync_dynamic_tables_definitions
2. _pull_deletion_log           → 【新增】拉取云端墓碑，本地执行删除
3. pull_from_remote
4. _push_deletion_log           → 【新增】推送本地墓碑，云端执行删除
5. push_to_remote
6. _sync_files_full_flow
7. _cleanup_deletion_log        → 【新增】清理过期墓碑
8. 更新 last_sync_time
```

### 墓碑 Pull 流程

```
_pull_deletion_log(last_sync_time):
    1. 查询云端 deletion_log 中 created_at > last_sync_time 的记录
    2. 对每条墓碑：
       a. DELETE FROM {target_table} WHERE {pk 或 hash_id} = {record_id}
       b. 写入本地 deletion_log 副本（source=cloud）
    3. 全部成功后返回
```

### 墓碑 Push 流程

```
_push_deletion_log(last_sync_time):
    1. 查询本地 deletion_log 中 created_at > last_sync_time 且 source=local 的记录
    2. 推送到云端
    3. 云端对每条墓碑：
       a. DELETE FROM {target_table} WHERE {pk 或 hash_id} = {record_id}
       b. 写入云端 deletion_log 副本（source=cloud）
    4. 全部成功后返回
```

### 墓碑清理流程

```
_cleanup_deletion_log(last_sync_time):
    1. 清理本地 deletion_log 中 created_at <= last_sync_time 的记录
    2. 清理云端 deletion_log 中 created_at <= last_sync_time 的记录
```

### 决策汇总

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 节点模型 | 严格两节点 | 本地↔云端，可激进清理墓碑 |
| 冲突策略 | 墓碑 `updated_at` 作 LWW | 墓碑不修改，`created_at == updated_at`，行为等价 |
| 墓碑清理 | 同步成功后立即清理 | 清理 `created_at <= last_sync_time` |
| 墓碑顺序 | Pull/Push 在数据 Pull/Push 之前 | 避免删除被 upsert 覆盖 |
| 失败处理 | 整个 sync_once 失败 | 不更新 last_sync_time，下次重试 |

## Testing Decisions

### 测试接缝

#### S1：DeletionLogProvider CRUD

**位置**：`test/core/unit/storage/test_deletion_log_provider.py`（新增）

**测试内容**：
- 写入墓碑（`target_table` / `record_id` / `source` / `created_at`）
- 按 `created_at > last_sync_time` 增量查询
- 按 `source` 过滤
- 清理 `created_at <= last_sync_time`
- 字段约束验证

**Prior art**：`test/core/unit/storage/test_wechat_account_state_provider.py`

#### S2：sync_once 删除传播（端到端）

**位置**：`test/core/integration/sync/test_sync_deletion.py`（新增）

**测试内容**：
- A 设备删除 TEXT 主键表记录 → 同步 → B 设备记录消失
- A 设备删除 AUTOINCREMENT 表记录（按 hash_id）→ 同步 → B 设备记录消失
- A 设备删除 → B 设备拉回该记录 → A 设备下次同步时该记录不被回写（墓碑阻止）
- 重置 `last_sync_time` 后墓碑仍工作
- 全量首同步不传播墓碑
- 多表批量删除同步
- 级联删除同步（删 habit 同时删 habit_challenges + habit_checkins）
- 动态表（custom_*）删除同步
- 墓碑清理在同步成功后执行
- 墓碑同步失败时整个 sync_once 失败

**Prior art**：`test/core/integration/sync/test_sync_conflict_resolve.py`

### 测试覆盖矩阵

| 决策 | 接缝覆盖 |
|------|---------|
| DeletionLogProvider CRUD | S1 |
| 墓碑 Pull | S2 |
| 墓碑 Push | S2 |
| 墓碑清理 | S1 + S2 |
| 墓碑 LWW | S2 |
| 重置同步进度 | S2 |
| 全量首同步 | S2 |
| 级联删除同步 | S2 |
| 动态表删除同步 | S2 |
| 失败处理 | S2 |

## Out of Scope

1. **hash_id schema 变更**：已在 PRD 1 完成。
2. **Provider 迁移 + 删除通道统一**：已在 PRD 2 完成。
3. **`_generic_delete` 写墓碑逻辑**：已在 PRD 2 完成。
4. **文件删除同步**：文件操作不走 LifePrism 同步管控，文档化为已知限制。
5. **删除-更新冲突自动处理**：已知限制，不处理。
6. **AUTOINCREMENT 表外键断裂问题**：需独立处理。
7. **墓碑表自身被删除时是否写墓碑**：清理过期墓碑是同步成功后的内部操作，不写墓碑。

## Further Notes

### 关联文档

- **交接文档**：[docs/temp/2026-07-22-deletion-sync-handoff.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/temp/2026-07-22-deletion-sync-handoff.md)
- **数据同步核心 spec**：[docs/specs/2026-07-16-data-sync-core-spec.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-core-spec.md)
- **LWW 冲突解决 ADR**：[docs/adr/2026-07-09-lww-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-09-lww-conflict-resolution.md)
- **动态表定义对比 ADR**：[docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md)

### 待写 ADR

1. **`2026-07-22-deletion-sync-tombstone.md`** — 删除同步墓碑机制决策（含两节点假设、墓碑清理策略、`updated_at` LWW、Pull/Push 顺序、专用端点、`deletion_log` 从 SYNC_TABLES 移除）

### 未决问题（均已解决）

1. **墓碑 Pull/Push 与数据 Pull/Push 的事务关系** ✅ 已决策：`_pull_deletion_log` 内部用事务包裹所有 DELETE + 副本写入（HTTP 在事务外），失败则回滚，`sync_once` 抛异常不更新 `last_sync_time`。
2. **`deletion_log` 表通过 `SYNC_TABLES` 同步时的循环引用** ✅ 已决策：`deletion_log` 从 `SYNC_TABLES` 移除，墓碑仅通过专用通道（`_pull/_push_deletion_log`）同步，不再有循环引用问题。
3. **动态表墓碑** ✅ 已决策：`custom_*` 动态表通过 `DeletionLogProvider.write_tombstone_with_cursor` 写墓碑（在 `delete_entry` 中调用，与 DELETE 同事务），`target_table` 用动态表名 `custom_{slug}`，`record_id` 用 TEXT 主键。

### 验收标准

#### DeletionLogProvider 验收

- [ ] `DeletionLogProvider` 新建并注册
- [ ] CRUD 方法实现并测试
- [ ] 增量查询、source 过滤、清理功能正常

#### sync_once 集成验收

- [ ] `sync_once` 主流程含墓碑 Pull（数据 Pull 前）
- [ ] `sync_once` 主流程含墓碑 Push（数据 Push 前）
- [ ] `sync_once` 主流程含墓碑清理（成功后）
- [ ] 墓碑 Pull/Push 顺序在数据 Pull/Push 之前

#### 端到端验收

- [ ] A 设备删除 → 同步 → B 设备记录消失
- [ ] A 设备删除 → B 设备拉回该记录 → A 设备下次同步时该记录不被回写
- [ ] 重置 `last_sync_time` 后墓碑仍工作
- [ ] 全量首同步不传播墓碑
- [ ] 级联删除同步传播所有级联表
- [ ] 动态表（custom_*）删除同步传播
- [ ] 墓碑清理在同步成功后执行
- [ ] 墓碑同步失败时整个 `sync_once` 失败，不更新 `last_sync_time`

#### 文档验收

- [ ] 写 ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`
- [ ] 更新 `docs/specs/2026-07-16-data-sync-core-spec.md`（墓碑同步流程）
- [ ] 更新 `docs/known-limitations/`（文件删除不同步、删除-更新冲突不处理）
- [ ] 更新 `docs/history-bugs/2026-07-16-database-delete-not-synced.md`（标记为已修复）

### 已知风险

1. **墓碑表增长风险**：每次删除都写墓碑，长期累积。但严格两节点 + 同步成功后立即清理，风险可控。
2. **动态表墓碑**：`custom_*` 动态表 schema 不在 `TABLE_CONFIGS`，需确认 `_generic_delete` 能正确处理。
3. **墓碑 Pull/Push 事务边界**：失败时回滚范围需要确认。
