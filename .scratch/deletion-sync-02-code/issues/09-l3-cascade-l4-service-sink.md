---
title: L3 级联删除 + L4 Service/Aggregator 下沉
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

完成 3 组剩余级联删除改造 + 6 处 Service/Aggregator 层直接 DELETE 下沉到 Provider：

### L3 级联删除（3 组）

1. `habit_chain_providers.delete_chain` 在级联删除 `habit_chain_nodes` + `habit_chains` 时，分别为两张表调用 `_generic_batch_delete` / `_generic_delete`（含写墓碑）。

2. `habit_providers.delete_habit` 在级联删除 `habit_challenges` + `habit_checkins` + `habits` 时，分别为三张表写墓碑。

3. `custom_record_aggregator.delete_type` 在级联删除 `custom_record_fields` + 动态表 `custom_*` 时，分别为每张表写墓碑。

### L4 Service/Aggregator 下沉（6 处）

4. `category_service.py` 中 4 处直接 `DELETE FROM multi/single_purpose_map_cache`（`_enable_category_map_records_by_category` 和 `_enable_category_map_records_by_sub_category` 的 multi/single 分支）下沉到对应 Provider 调用 `_generic_batch_delete`（先查 ID 列表）。

5. `custom_record_aggregator.py` 中 2 处直接 `DELETE FROM custom_record_fields/custom_record_types`（L3 第 3 组已列出）下沉到对应 Provider 调用 `_generic_delete` / `_generic_batch_delete`。

注意：Service/Aggregator 层无法直接调用 `_generic_*`（因为没有 `_TABLE_NAME`），必须通过对应 Provider 实例调用。

## Acceptance criteria

- [ ] `habit_chain_providers.delete_chain` 级联删除为 `habit_chain_nodes` 和 `habit_chains` 分别写墓碑
- [ ] `habit_providers.delete_habit` 级联删除为 `habit_challenges`、`habit_checkins`、`habits` 分别写墓碑
- [ ] `custom_record_aggregator.delete_type` 级联删除为 `custom_record_fields` 和动态表分别写墓碑
- [ ] `category_service.py` 4 处直接 DELETE 下沉到 Provider 调用 `_generic_batch_delete`
- [ ] `custom_record_aggregator.py` 2 处直接 DELETE 下沉到 Provider 调用 `_generic_*`
- [ ] Service 层和 Aggregator 层无直接执行 `DELETE FROM` SYNC_TABLES 的 SQL

## Blocked by

- `.scratch/deletion-sync-02-code/issues/08-l2-batch-delete-unification.md`（L2 批量删除统一，habit 级联清理依赖此）

## 执行提示

本 issue 涉及 4+ 个文件（habit_chain_providers、habit_providers、custom_record_aggregator、category_service），超过 CLAUDE.md 核心规则 2 的"修改超过 3 个文件先分解"阈值。执行时按级联表组或下沉目标拆分子 PR，每个 PR 修改不超过 3 个文件，便于审查和回滚。
