---
title: CommitmentProvider 端到端迁移
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

将 `CommitmentProvider` 从 `server/providers/commitment_provider.py` 迁移到 `repository/providers/`，完成端到端的 CRUD 通道统一，并新增 3 个级联方法供 ValueProvider 使用：

1. 迁移文件到 `repository/providers/commitment_provider.py`，定义完整子类元数据（`_TABLE_NAME = "commitments"`、`_PRIMARY_KEY = "id"`、`_UPDATE_FIELDS = {"content", "value_id", "status"}`、`_ON_CONFLICT = "abort"`）。

2. `create_commitment` 改用 `_generic_insert(data, id_prefix="cmt-")`，`update_commitment` 改用 `_generic_update(commitment_id, data)`（修复时间戳不一致，改用 `get_utc_now_iso()`），`delete_commitment` 改用 `_generic_delete(commitment_id)`（走墓碑通道）。

3. 新增 3 个级联方法：
   - `delete_by_value_id(value_id) -> int`：级联删除某价值下所有承诺（走 `_generic_batch_delete`）
   - `null_value_id(value_id) -> int`：置空某价值下所有承诺的 value_id
   - `count_by_value(value_id) -> int`：从 ValueProvider 迁移

4. 迁移前先补基线测试，迁移后验证 API 端点 `/commitment/` 的 5 个端点行为等价。

## Acceptance criteria

- [ ] `CommitmentProvider` 迁移到 `repository/providers/commitment_provider.py`
- [ ] 定义完整子类元数据
- [ ] `create_commitment` 走 `_generic_insert`
- [ ] `update_commitment` 走 `_generic_update`（时间戳使用 `get_utc_now_iso()`）
- [ ] `delete_commitment` 走 `_generic_delete`（含写墓碑）
- [ ] 新增 `delete_by_value_id(value_id)` 方法（走 `_generic_batch_delete`，含写墓碑）
- [ ] 新增 `null_value_id(value_id)` 方法
- [ ] 新增 `count_by_value(value_id)` 方法
- [ ] 迁移前基线测试已补齐
- [ ] `/commitment/` 的 5 个 API 端点行为等价
- [ ] `server/providers/commitment_provider.py` 已删除或清空

## Blocked by

- `.scratch/deletion-sync-02-code/issues/01-base-infra-generic-delete-tombstone.md`（基类基础设施）
