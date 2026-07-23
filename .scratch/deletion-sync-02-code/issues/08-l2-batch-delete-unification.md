---
title: L2 批量删除统一
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

将 `repository/providers/` 下已迁移 Provider 中的 6 处批量删除改用 `_generic_batch_delete`（走墓碑通道）：

1. `map_cache_providers.batch_delete_multi_purpose_map_cache`（multi_purpose_map_cache 表）→ 改用 `_generic_batch_delete`

2. `map_cache_providers.batch_delete_single_purpose_map_cache`（single_purpose_map_cache 表）→ 改用 `_generic_batch_delete`

3. `todo_provider.delete_todo_cascade`（todo_list 表，`:356`，级联删除，内部循环单条 DELETE）→ 改用 `_generic_batch_delete`（先递归收集所有子任务 ID 列表，再一次性批量删除+写墓碑）

4. `todo_provider.batch_delete_todos`（todo_list 表，`:416`，批量删除，内部循环单条 DELETE）→ 改用 `_generic_batch_delete`（直接传入 ID 列表，一次性批量删除+写墓碑）

5. `habit_challenge_provider.delete_by_habit_id`（habit_challenges 表级联清理）→ 改用 `_generic_batch_delete`（先查 ID 列表）

6. `habit_checkin_provider.delete_by_habit_id`（habit_checkins 表级联清理）→ 改用 `_generic_batch_delete`（先查 ID 列表）

注意：
- `category_service.py` 中 4 处直接 DELETE 属于 L4 下沉范围（Slice 9），不在本切片内。
- **todo_provider 的两处方法说明**：`delete_todo_cascade`（`:356`）和 `batch_delete_todos`（`:416`）内部都是循环执行单条 `DELETE FROM ... WHERE id = ?`，改造时改为先收集所有 ID，然后一次性调用 `_generic_batch_delete`（批量写墓碑 + 批量 DELETE），避免循环单条调用。
- **与 Issue 07 的文件冲突提示**：本 issue 修改 `habit_checkin_provider.delete_by_habit_id`（批量），Issue 07 修改 `habit_checkin_provider.delete_checkin`（单条），两者操作同一文件的不同方法。建议串行执行或合并为同一 PR，避免 merge 冲突。

## Acceptance criteria

- [ ] `map_cache_providers` 2 处批量删除走 `_generic_batch_delete`（含写墓碑）
- [ ] `todo_provider` 2 处批量删除走 `_generic_batch_delete`（含写墓碑）
- [ ] `habit_challenge_provider.delete_by_habit_id` 走 `_generic_batch_delete`（先查 ID 列表，含写墓碑）
- [ ] `habit_checkin_provider.delete_by_habit_id` 走 `_generic_batch_delete`（先查 ID 列表，含写墓碑）
- [ ] 无残留的原生 `DELETE FROM ... IN` 批量删除 SQL（这 6 处范围内）

## Blocked by

- `.scratch/deletion-sync-02-code/issues/01-base-infra-generic-delete-tombstone.md`（基类基础设施）

## 执行提示

本 issue 涉及 4 个 Provider 文件（map_cache_providers、todo_provider、habit_challenge/habit_checkin_provider），超过 CLAUDE.md 核心规则 2 的"修改超过 3 个文件先分解"阈值。执行时按 Provider 文件拆分子 PR，每个 PR 修改不超过 3 个文件，便于审查和回滚。
