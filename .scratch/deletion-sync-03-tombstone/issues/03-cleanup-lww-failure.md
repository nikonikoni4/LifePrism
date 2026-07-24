---
title: 墓碑清理 + LWW + 失败处理
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-03-tombstone/prd.md`（同步删除 - 阶段 3：墓碑同步流程）

## What to build

在 `sync_once` 主流程中集成墓碑清理（成功后执行），实现墓碑 LWW 比较，并确保失败时整个 `sync_once` 失败不更新 `last_sync_time`。

**sync_once 主流程修改**（依据 PRD "Implementation Decisions > sync_once 主流程"）：

```
1. _sync_dynamic_tables_definitions   → 已有
2. _pull_deletion_log                 → Slice 02 已实现
3. pull_from_remote                   → 已有
4. _push_deletion_log                 → Slice 02 已实现
5. push_to_remote                     → 已有
6. _sync_files_full_flow              → 已有
7. _cleanup_deletion_log              → 【新增】清理 created_at <= last_sync_time 的墓碑
8. 更新 last_sync_time                → 已有（只有全部成功才更新）
```

**墓碑清理流程**（`_cleanup_deletion_log`）：

1. 清理本地 `deletion_log` 中 `created_at <= last_sync_time` 的记录（通过 `deletion_log_repository.cleanup_before(last_sync_time)`）
2. HTTP 调用 `POST /api/sync/cleanup-deletion-log` 清理云端 `created_at <= last_sync_time` 的记录
3. 采用激进策略——本项目是严格两节点（本地↔云端），不存在多设备清理导致删除丢失的风险

**清理时间点说明**（Minor-5）：
- 清理用**旧 `last_sync_time`**（同步前的值），在更新 `last_sync_time` 之前执行
- 刚 Pull/Push 产生的墓碑 `created_at > 旧 last_sync_time`，不会被清理
- 清理是同步成功后的内部操作，**不写墓碑**（墓碑表自身清理不记录到 `deletion_log`）

**墓碑 LWW 比较**（M1 修正，依据实际代码）：

- 墓碑的 `created_at == updated_at`（墓碑不修改），`deletion_log` schema 配置 `update_at: True`
- LWW 通过标准 `upsert_rows_with_lww` 用 **`updated_at`** 字段比较（不是 `created_at`，但因墓碑不修改，两者值相同，行为等价）
- 两端都有同一墓碑时（按 `UNIQUE(target_table, record_id)` 约束去重），保留 `updated_at` 更晚的
- **LWW 跳过 DELETE（简化，M6）**：在 Pull 阶段，对每条云端墓碑，先调用 `deletion_log_repository.get_tombstone(target_table, record_id)` 查本地墓碑，若本地已存在（无论 source 是 local 还是 cloud）则跳过 DELETE 和副本写入。理由：本地有墓碑意味着已删除过该记录，DELETE 幂等，INSERT OR IGNORE 忽略重复。这是性能优化，不是正确性必需。

**失败处理**（M5 决策，依据 PRD "User Stories > 事务与失败处理"）：

- 墓碑同步失败时整个 `sync_once` 必须失败，不更新 `last_sync_time`，下次重试
- 失败包括：网络错误、DELETE 执行失败、写入副本失败等
- **事务边界决策**：`_pull_deletion_log` 内部用一个事务包裹所有 DELETE + 本地副本写入（HTTP 拉取在事务外，避免长事务占用连接）。失败则整个事务回滚，`sync_once` 抛异常不更新 `last_sync_time`
  - 流程：1. HTTP 拉取云端墓碑列表（事务外）→ 2. 开始事务 → 3. 对每条墓碑执行 LWW 检查 + DELETE + 副本写入 → 4. 提交事务（失败则回滚）

**S2 测试**（依据 PRD "Testing Decisions > S2"）：

位置：`test/core/integration/sync/test_sync_deletion.py`（扩展）

测试场景：
1. 墓碑清理在同步成功后执行（验证 `deletion_log` 中 `created_at <= last_sync_time` 的记录被清理）
2. 墓碑 LWW 冲突（两端都有同一墓碑，保留 `updated_at` 更晚的）
3. 墓碑同步失败时整个 `sync_once` 失败（验证 `last_sync_time` 未更新）
4. 墓碑 Pull 失败回滚（部分删除后失败，验证已执行删除被回滚，下次重试）

Prior art：`test/core/integration/sync/test_sync_conflict_resolve.py`

**注意**：
- 清理是同步成功后的内部操作，**不写墓碑**（墓碑表自身清理不记录到 `deletion_log`）
- 清理时机在"全部成功后才更新 `last_sync_time`"之前，使用旧 `last_sync_time` 值

## Acceptance criteria

- [ ] `sync_once` 主流程含 `_cleanup_deletion_log`（在 `_sync_files_full_flow` 之后、更新 `last_sync_time` 之前调用）
- [ ] 墓碑清理清理本地（通过 `cleanup_before`）+ 云端（通过 `POST /api/sync/cleanup-deletion-log`）`created_at <= last_sync_time` 的记录
- [ ] 墓碑清理不写墓碑（清理是内部操作）
- [ ] 墓碑清理使用旧 `last_sync_time`（同步前的值），刚 Pull/Push 产生的墓碑不会被清理
- [ ] 墓碑 LWW 比较使用 `updated_at` 字段（墓碑不修改，`created_at == updated_at`，行为等价）
- [ ] LWW 跳过 DELETE：本地已有同一 `(target_table, record_id)` 的墓碑则跳过（简化版，不需要 LWW 时间比较）
- [ ] 墓碑同步失败时整个 `sync_once` 失败，不更新 `last_sync_time`
- [ ] 事务边界：`_pull_deletion_log` 内部用事务包裹 DELETE + 副本写入，HTTP 在事务外，失败则回滚
- [ ] 端到端测试：墓碑清理在同步成功后执行
- [ ] 端到端测试：墓碑 LWW 冲突保留更晚的 `updated_at`
- [ ] 端到端测试：墓碑同步失败时 `sync_once` 失败，`last_sync_time` 未更新
- [ ] 端到端测试：墓碑 Pull 失败回滚

## Blocked by

- `.scratch/deletion-sync-03-tombstone/issues/02-tombstone-pull-push.md`（墓碑 Pull + Push 集成）
