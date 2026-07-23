---
title: 写入通道审计（W2）：6 张 AUTOINCREMENT 表 create 通道验证
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

审计 `repository/providers/` 下所有 SYNC_TABLES 的 Provider，确认 create 方法是否都走 `_generic_insert`。重点审计 6 张 AUTOINCREMENT 表（不走 `_generic_insert` 会导致 hash_id 为空，删除时墓碑 record_id 跨端不匹配）：

| AUTOINCREMENT 表 | 前缀 | Provider | 审计要点 | 修复归属 |
|------------------|------|---------|---------|---------|
| `user_app_behavior_log` | `awbl-` | `ComputerUsageProvider` | `create_computer_usage` 是否走 `_generic_insert` | **P5（deletion-sync-02a-statistical）**，本 issue 仅审计记录结果，修复 deferred 到 P5 |
| `time_paradoxes` | `tp-` | `BeingProvider`（Slice 4 迁移后） | `create` 是否走 `_generic_insert` | 本 issue（已在 Slice 04 迁移时处理） |
| `habits` | `hb-` | `HabitProvider` | create 方法是否走 `_generic_insert` | 本 issue |
| `habit_chains` | `hc-` | `HabitChainProvider` | create 方法是否走 `_generic_insert` | 本 issue |
| `habit_chain_nodes` | `hcn-` | `HabitChainProvider` | create 方法是否走 `_generic_insert` | 本 issue |
| `habit_challenges` / `habit_checkins` | `hc-` / `hci-` | `HabitProvider` | create 方法是否走 `_generic_insert` | 本 issue |

**范围边界**：
- `ComputerUsageProvider`（`user_app_behavior_log` 表）属于 P5（deletion-sync-02a-statistical），本 issue **仅审计记录结果**，若发现不合规，修复工作 **deferred 到 P5**，避免与 P5 迁移冲突。
- 其余 5 张表的审计发现不合规时，本 issue 负责修复。

审计后发现的绕过路径（除 ComputerUsageProvider 外），必须改造为走 `_generic_insert`。

同时验证 `SyncRepository.upsert_rows_with_lww` 对 AUTOINCREMENT 表的 hash_id 处理逻辑（PRD 1 已实现）未被回退。

## Acceptance criteria

- [ ] 5 张 AUTOINCREMENT 表（除 `user_app_behavior_log` 外）的 Provider create 全部走 `_generic_insert`
- [ ] `ComputerUsageProvider` 的 create 通道审计完成，不合规结果已记录（修复 deferred 到 P5）
- [ ] 本 issue 范围内发现的绕过路径已改造为走 `_generic_insert`
- [ ] 插入 AUTOINCREMENT 表的记录 hash_id 非空且唯一
- [ ] `SyncRepository.upsert_rows_with_lww` 的 hash_id 逻辑正常（未被回退）
- [ ] 无绕过 `_generic_insert` 直接执行 `INSERT INTO` 的写入路径（grep 验证，`user_app_behavior_log` 除外）

## Blocked by

- `.scratch/deletion-sync-02-code/issues/04-being-provider-migration.md`（BeingProvider 迁移后才能审计 time_paradoxes）
