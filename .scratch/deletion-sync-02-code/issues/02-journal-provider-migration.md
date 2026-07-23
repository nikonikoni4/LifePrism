---
title: JournalProvider 端到端迁移
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

将 `JournalProvider` 从 `server/providers/journal_provider.py` 迁移到 `repository/providers/`，完成端到端的 CRUD 通道统一：

1. 迁移文件到 `repository/providers/journal_provider.py`，定义完整子类元数据（`_TABLE_NAME = "goal_journal"`、`_PRIMARY_KEY = "id"`、`_FILTER_FIELDS`、`_UPDATE_FIELDS`、`_ON_CONFLICT = "abort"`）。

2. `create_journal` 改用 `_generic_insert(data, id_prefix="journal-")`，`update_journal` 改用 `_generic_update(journal_id, data)`，`delete_journal` 改用 `_generic_delete(journal_id)`（走墓碑通道）。

3. 异常处理从"静默返回 None/False"改为"抛出 `DataAccessError`"。

4. 迁移前先补基线测试，迁移后验证 API 端点 `/goal/journals` 的 5 个端点行为等价。

## Acceptance criteria

- [ ] `JournalProvider` 迁移到 `repository/providers/journal_provider.py`
- [ ] 定义完整子类元数据（`_TABLE_NAME`、`_PRIMARY_KEY`、`_FILTER_FIELDS`、`_UPDATE_FIELDS`、`_ON_CONFLICT`）
- [ ] `create_journal` 走 `_generic_insert`
- [ ] `update_journal` 走 `_generic_update`
- [ ] `delete_journal` 走 `_generic_delete`（含写墓碑）
- [ ] 异常处理改为抛出 `DataAccessError`
- [ ] 迁移前基线测试已补齐
- [ ] `/goal/journals` 的 5 个 API 端点行为等价
- [ ] `server/providers/journal_provider.py` 已删除或清空

## Blocked by

- `.scratch/deletion-sync-02-code/issues/01-base-infra-generic-delete-tombstone.md`（基类基础设施）
