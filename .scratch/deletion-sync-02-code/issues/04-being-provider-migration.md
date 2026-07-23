---
title: BeingProvider 端到端迁移
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

将 `BeingProvider` 从 `server/providers/being_provider.py` 迁移到 `repository/providers/`，完成端到端的 CRUD 通道统一。`time_paradoxes` 是 AUTOINCREMENT 表，create 必须走 `_generic_insert` 以保证 hash_id 生成：

1. 迁移文件到 `repository/providers/being_provider.py`，修复表名常量命名（`TABLE_NAME` → `_TABLE_NAME`），定义完整子类元数据（`_TABLE_NAME = "time_paradoxes"`、`_PRIMARY_KEY = "hash_id"`、`_FILTER_FIELDS = {"user_id", "mode", "version"}`、`_ON_CONFLICT = "abort"`）。

2. `create` 改用 `_generic_insert(data)`（PRD 1 后自动生成 hash_id）。

3. `update` / `delete` 改用 `_generic_update(hash_id, data)` / `_generic_delete(hash_id)`（走墓碑通道）。两处删除（`delete` 和 `delete_by_user_mode_version`）都要改。

4. 复合键方法（`*_by_user_mode_version`）采用"先查 `hash_id` 再调用 `_generic_*`"方案。

5. `upsert` 保留 `self.db.upsert(...)`（基类无 `_generic_upsert`），`get_latest_version` 保留原生 SQL（基类无 `_generic_max`）。单例改用 `LazySingleton`。

6. 迁移前先补基线测试，迁移后验证 API 端点 `/being` 的 7 个端点行为等价。

## Acceptance criteria

- [ ] `BeingProvider` 迁移到 `repository/providers/being_provider.py`
- [ ] 表名常量修复：`TABLE_NAME` → `_TABLE_NAME`
- [ ] 定义完整子类元数据（`_PRIMARY_KEY = "hash_id"`）
- [ ] `create` 走 `_generic_insert`（AUTOINCREMENT 表，保证 hash_id 生成）
- [ ] `update` 走 `_generic_update(hash_id, data)`
- [ ] `delete` 走 `_generic_delete(hash_id)`（含写墓碑）
- [ ] `delete_by_user_mode_version` 走 `_generic_delete`（先查 hash_id 再删除）
- [ ] 复合键方法（`*_by_user_mode_version`）先查 hash_id 再调用 `_generic_*`
- [ ] `upsert` 保留 `self.db.upsert`
- [ ] `get_latest_version` 保留原生 SQL
- [ ] 单例改用 `LazySingleton`
- [ ] 迁移前基线测试已补齐
- [ ] `/being` 的 7 个 API 端点行为等价
- [ ] `server/providers/being_provider.py` 已删除或清空

## Blocked by

- `.scratch/deletion-sync-02-code/issues/01-base-infra-generic-delete-tombstone.md`（基类基础设施）
- None - PRD 1（Schema 变更）已完成，`time_paradoxes` 表的 `hash_id` 字段已添加，可立即开始
