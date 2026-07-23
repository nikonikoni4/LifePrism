---
title: 基类基础设施：_generic_delete 写墓碑 + _generic_batch_delete 实现
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

改造 `LWBaseDataProvider` 基类，为所有后续删除通道统一提供基础设施：

1. `_generic_delete` 内部判断 `self._TABLE_NAME in SYNC_TABLES` 时，在执行 DELETE 前先写墓碑到 `deletion_log` 表。墓碑写入与 DELETE 在同一事务内（失败回滚）。对非 SYNC_TABLES 不写墓碑。AUTOINCREMENT 表的墓碑 `record_id` 使用 `hash_id`，TEXT 主键表使用主键值。

2. 新增 `_generic_batch_delete(record_ids: list[str]) -> int` 方法：批量写墓碑 + 批量 DELETE 在同一事务，采用批量 SQL（1 次墓碑批量插入 + 1 次 DELETE ... IN），而非循环单条。

3. 移除 `habit_chain_nodes` 表的 DB CASCADE（`ON DELETE CASCADE`），改为纯应用层级联，确保墓碑必写。

这是所有其他切片的预重构（prefactoring），必须最先完成。

## Acceptance criteria

- [ ] `_generic_delete` 对 SYNC_TABLES 在删除前写墓碑到 `deletion_log`
- [ ] `_generic_delete` 对非 SYNC_TABLES 不写墓碑
- [ ] AUTOINCREMENT 表删除时墓碑 `record_id` 为 `hash_id`
- [ ] TEXT 主键表删除时墓碑 `record_id` 为主键值
- [ ] 墓碑写入与 DELETE 在同一事务（失败回滚验证通过）
- [ ] `_generic_batch_delete` 实现并测试（批量墓碑 + 批量 DELETE）
- [ ] `_generic_batch_delete` 采用批量 SQL 而非循环单条
- [ ] `habit_chain_nodes` 的 DB CASCADE 已移除
- [ ] **`_generic_update` 调用后 `updated_at` 字段被自动更新**（回归验证：修改记录后 `updated_at` 变化，确保 LWW 同步触发，PRD story 12）
- [ ] 单元测试覆盖：墓碑写入、事务回滚、批量删除、非 SYNC_TABLES 跳过、`_generic_update` 的 `updated_at` 自动更新

## Blocked by

None - can start immediately（PRD 1 已完成）
