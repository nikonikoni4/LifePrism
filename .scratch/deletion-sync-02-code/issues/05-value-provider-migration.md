---
title: ValueProvider 端到端迁移（含级联删除重构）
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

将 `ValueProvider` 从 `server/providers/value_provider.py` 迁移到 `repository/providers/`，完成端到端的 CRUD 通道统一，并重构级联删除逻辑：

1. 迁移文件到 `repository/providers/value_provider.py`，定义完整子类元数据（`_TABLE_NAME = "user_values"`、`_PRIMARY_KEY = "id"`、`_ON_CONFLICT = "abort"`、`_UPDATE_FIELDS = {"keywords", "content_positive", "content_negative", "sort_order"}`）。

2. `create_value` 改用 `_generic_insert(data, id_prefix="val-")`，`update_value` 改用 `_generic_update(value_id, data)`（修复时间戳不一致），`delete_value` 改用 `_generic_delete(value_id)`（走墓碑通道）。

3. 级联删除重构：`delete_value_with_cascade` → `delete_value(value_id)` 调用 `_generic_delete(value_id)`，级联逻辑上移到 `value_service.delete_value`（协调 `CommitmentProvider.delete_by_value_id` + `ValueProvider.delete_value`）。

4. `count_commitments_by_value` 迁移到 `CommitmentProvider.count_by_value`（已在 Slice 3 实现）。

5. 迁移前先补基线测试，迁移后验证 API 端点 `/value/` 的 5 个端点行为等价，包括 `DELETE /value/{value_id}?cascade=True/False`。

## Acceptance criteria

- [ ] `ValueProvider` 迁移到 `repository/providers/value_provider.py`
- [ ] 定义完整子类元数据（`_ON_CONFLICT = "abort"` 防止默认 replace 覆盖）
- [ ] `create_value` 走 `_generic_insert`
- [ ] `update_value` 走 `_generic_update`（时间戳使用 `get_utc_now_iso()`）
- [ ] `delete_value` 走 `_generic_delete`（含写墓碑）
- [ ] `delete_value_with_cascade` 重构为 `delete_value(value_id)`，级联逻辑上移到 service 层
- [ ] `value_service.delete_value` 协调 `CommitmentProvider.delete_by_value_id` + `ValueProvider.delete_value`
- [ ] `count_commitments_by_value` 已迁移到 `CommitmentProvider.count_by_value`
- [ ] 迁移前基线测试已补齐
- [ ] `/value/` 的 5 个 API 端点行为等价（含 `DELETE /value/{value_id}?cascade=True/False`）
- [ ] `server/providers/value_provider.py` 已删除或清空

## Blocked by

- `.scratch/deletion-sync-02-code/issues/01-base-infra-generic-delete-tombstone.md`（基类基础设施）
- `.scratch/deletion-sync-02-code/issues/03-commitment-provider-migration.md`（CommitmentProvider 的级联方法）
