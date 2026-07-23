---
title: 已迁移 Provider L1 剩余删除统一
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

将 `repository/providers/` 下已迁移 Provider 中的 5 处单表单条删除改用 `_generic_delete`（走墓碑通道）。这些 Provider 不在 P1-P4 迁移范围内，但删除通道不合规：

1. `behavior_analysis_provider.delete_behaviors_by_date_range`（behavior_analysis 表）→ 改用 `_generic_delete`（按日期范围查询 ID 列表后逐条删除，或改为先查 ID 再 `_generic_batch_delete`）

2. `raw_behavior_analysis_provider.delete_raw_behaviors_by_date_range`（raw_behavior_analysis 表）→ 同上

3. `plan_doc_provider.delete_plan_doc`（plan_doc 表）→ 改用 `_generic_delete`

4. `habit_checkin_provider.delete_checkin`（habit_checkins 表，按 habit_id+date 单条）→ 改用 `_generic_delete`（先查 id 再删除）

5. `custom_block_provider.delete_custom_block`（timeline_custom_block 表，当前用 `self.db.delete`）→ 改用 `_generic_delete`

注意：
- `behavior_analysis` 和 `raw_behavior_analysis` 的原方法是按日期范围批量删除，如果适合批量场景可以改用 `_generic_batch_delete`（先查 ID 列表再批量删除）。
- **todo_provider 不在本 issue 范围**：`todo_provider.py:356`（`delete_todo_cascade` 内部）和 `:416`（`batch_delete_todos` 内部）虽然内部是循环单条 `DELETE FROM ... WHERE id = ?`，但它们属于批量场景（级联删除和批量删除），归 Issue 08 处理（改用 `_generic_batch_delete`，先收集 ID 列表再一次性批量删除+写墓碑）。

## Acceptance criteria

- [ ] `behavior_analysis_provider` 删除走 `_generic_delete` 或 `_generic_batch_delete`（含写墓碑）
- [ ] `raw_behavior_analysis_provider` 删除走 `_generic_delete` 或 `_generic_batch_delete`（含写墓碑）
- [ ] `plan_doc_provider.delete_plan_doc` 走 `_generic_delete`（含写墓碑）
- [ ] `habit_checkin_provider.delete_checkin` 走 `_generic_delete`（含写墓碑）
- [ ] `custom_block_provider.delete_custom_block` 走 `_generic_delete`（含写墓碑）
- [ ] 无残留的 `self.db.delete(` 调用 SYNC_TABLES（这 5 个 Provider 范围内）
- [ ] 无残留的原生 `DELETE FROM` SYNC_TABLES SQL（这 5 个 Provider 范围内）

## Blocked by

- `.scratch/deletion-sync-02-code/issues/01-base-infra-generic-delete-tombstone.md`（基类基础设施）

## 执行提示

本 issue 涉及 5 个 Provider 文件，超过 CLAUDE.md 核心规则 2 的"修改超过 3 个文件先分解"阈值。执行时按 Provider 文件拆分子 PR，每个 PR 修改不超过 3 个文件，便于审查和回滚。
