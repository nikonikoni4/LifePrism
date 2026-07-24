---
title: 墓碑 Pull + Push 集成 + 端到端（TEXT 主键表）
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-03-tombstone/prd.md`（同步删除 - 阶段 3：墓碑同步流程）

## What to build

在 `sync_once` 主流程中集成墓碑 Pull 和 Push，实现删除意图的双向传播。Pull 和 Push 合并为一个 slice 因为它们是对称流程，端到端测试需要双向验证。

**架构决策**（C1/C2）：
- `deletion_log` 从 `SYNC_TABLES` 移除（C2），墓碑仅通过专用通道同步，避免双重同步和回环
- 新增 3 个专用端点（C1），云端执行 DELETE + 写副本，不干扰现有 `/pull`、`/push` 的 upsert 语义

**新增专用端点**（在 `lifeprism/server/api/sync_cloud_api.py` 中）：

1. `POST /api/sync/pull-deletion-log`：
   - 请求：`{last_sync_time: str}`
   - 云端返回 `created_at > last_sync_time` 的墓碑列表
   - 响应：`{tombstones: [...]}`

2. `POST /api/sync/push-deletion-log`：
   - 请求：`{tombstones: [...]}`
   - 云端对每条墓碑：
     a. 检查本地是否已有同一 `(target_table, record_id)` 的墓碑，若有则跳过（DELETE 和副本写入都跳过）
     b. 执行 `DELETE FROM {target_table} WHERE {pk 或 hash_id} = {record_id}`（通过 `SyncRepository.execute_tombstone_delete`）
     c. 写入云端 `deletion_log` 副本（`source=cloud`，通过 `deletion_log_repository.create_tombstone(source='cloud', created_at=原墓碑.created_at)`）
   - 响应：`{success: bool, applied_count: int, skipped_count: int}`

3. `POST /api/sync/cleanup-deletion-log`（Slice 03 使用）：
   - 请求：`{last_sync_time: str}`
   - 云端清理 `created_at <= last_sync_time` 的墓碑
   - 响应：`{success: bool, cleaned_count: int}`

**sync_once 主流程修改**（依据 PRD "Implementation Decisions > sync_once 主流程"）：

```
1. _sync_dynamic_tables_definitions   → 已有
2. _pull_deletion_log                 → 【新增】HTTP 拉取云端墓碑（事务外）→ 事务内 LWW 检查+DELETE+写副本
3. pull_from_remote                   → 已有（不再包含 deletion_log 表，因已从 SYNC_TABLES 移除）
4. _push_deletion_log                 → 【新增】查询本地 source=local 墓碑 → HTTP 推送到云端
5. push_to_remote                     → 已有（不再包含 deletion_log 表）
6. _sync_files_full_flow              → 已有
7. （_cleanup_deletion_log 在 Slice 03 实现）
8. 更新 last_sync_time                → 已有（只有全部成功才更新）
```

**顺序关键**：墓碑 Pull/Push 必须在数据 Pull/Push 之前，避免删除被后续 upsert 覆盖。

**墓碑 Pull 流程**（`_pull_deletion_log`）：

1. HTTP 调用 `POST /api/sync/pull-deletion-log` 拉取云端墓碑列表（`created_at > last_sync_time`）— **事务外**
2. 开始事务（`with self.db.get_connection() as conn`）
3. 对每条云端墓碑：
   a. **LWW 检查（简化）**：调用 `deletion_log_repository.get_tombstone(target_table, record_id)` 查本地墓碑，若本地已存在（无论 source 是 local 还是 cloud）则跳过（M6 简化：本地有墓碑意味着已删除过该记录，DELETE 幂等，INSERT OR IGNORE 忽略重复，跳过是性能优化）
   b. **执行 DELETE**：调用 `SyncRepository.execute_tombstone_delete(target_table, record_id)` — 通过 `HASH_ID_PREFIXES.get(target_table)` 判断：若非 None 则 `WHERE hash_id = ?`，否则 `WHERE {get_primary_key_field(target_table)} = ?`（M3）；**不写墓碑**（墓碑已在 Pull 时写入本地副本）
   c. **写本地副本**：调用 `deletion_log_repository.create_tombstone(target_table, record_id, source='cloud', created_at=云端墓碑.created_at)` — 保留原墓碑时间戳，保持两端 LWW 一致（M7）
4. 提交事务（失败则回滚，`sync_once` 抛异常不更新 `last_sync_time`）（M5）

**墓碑 Push 流程**（`_push_deletion_log`）：

1. 查询本地 `deletion_log` 中 `created_at > last_sync_time` 且 `source=local` 的记录（通过 `deletion_log_repository.get_tombstones_since(last_sync_time, source='local')`）
2. HTTP 调用 `POST /api/sync/push-deletion-log` 推送墓碑列表到云端
3. 云端对每条墓碑（在端点处理中）：
   a. 检查云端是否已有同一 `(target_table, record_id)` 的墓碑，若有则跳过
   b. 执行 `DELETE FROM {target_table} WHERE {pk 或 hash_id} = {record_id}`（通过 `SyncRepository.execute_tombstone_delete`）
   c. 写入云端 `deletion_log` 副本（`source=cloud`，通过 `deletion_log_repository.create_tombstone(source='cloud', created_at=原墓碑.created_at)`）
4. 全部成功后返回

**新增 SyncRepository 方法**（M3/M4）：

- `execute_tombstone_delete(target_table, record_id)` — 执行 `DELETE FROM {target_table} WHERE {pk 或 hash_id} = {record_id}`，**不写墓碑**（墓碑已在 Pull 时写入本地副本）。通过 `HASH_ID_PREFIXES.get(target_table)` 判断用 `hash_id` 列还是主键列。

**端到端测试**（S2，依据 PRD "Testing Decisions > S2"）：

位置：`test/core/integration/sync/test_sync_deletion.py`

测试场景（本 slice 覆盖 TEXT 主键表场景）：
1. A 设备删除 TEXT 主键表记录 → 同步 → B 设备记录消失

**注意**：
- 原"墓碑阻止回写"测试场景已删除（C3）：该场景本质是"删除-更新冲突"（A 删除 → B 更新 → A 拉回），PRD US23 明确为已知限制。反向测试（验证删除被更新覆盖的预期行为）在 Issue 04 补充。
- `_full_sync_to_cloud`（首次同步路径）不调用 `_pull_deletion_log`/`_push_deletion_log`，墓碑同步仅在增量 `sync_once` 中执行（m3）。首同步假设云端为空，符合 PRD US20。
- `deletion_log` 已从 `SYNC_TABLES` 移除（C2），不再有循环引用问题。原 PRD"未决问题 2"已不再适用。
- 本 slice 只验证 TEXT 主键表（如 `mood_entries`、`todo_list`、`diary` 等），AUTOINCREMENT 表（hash_id）在 Slice 04 覆盖。

## Acceptance criteria

- [ ] 新增 `POST /api/sync/pull-deletion-log` 端点，返回 `created_at > last_sync_time` 的墓碑列表
- [ ] 新增 `POST /api/sync/push-deletion-log` 端点，云端执行 DELETE + 写副本（跳过已有墓碑）
- [ ] 新增 `SyncRepository.execute_tombstone_delete(target_table, record_id)` 方法，通过 `HASH_ID_PREFIXES` 判断列，不写墓碑
- [ ] `sync_once` 主流程含 `_pull_deletion_log`（在 `pull_from_remote` 之前调用）
- [ ] `sync_once` 主流程含 `_push_deletion_log`（在 `push_to_remote` 之前调用）
- [ ] 墓碑 Pull：HTTP 拉取（事务外）→ 事务内 LWW 检查（本地有就跳过）+ DELETE + 写本地副本（`source=cloud`，保留原 `created_at`）
- [ ] 墓碑 Push：查询本地 `source=local` 墓碑 → HTTP 推送到云端 → 云端执行 DELETE + 写云端副本
- [ ] 墓碑 Pull/Push 顺序在数据 Pull/Push 之前
- [ ] 端到端测试：A 设备删除 TEXT 主键表记录 → 同步 → B 设备记录消失
- [ ] `_full_sync_to_cloud` 不调用墓碑同步方法

## Blocked by

- `.scratch/deletion-sync-03-tombstone/issues/01-deletion-log-provider.md`（DeletionLogProvider 基础设施）
