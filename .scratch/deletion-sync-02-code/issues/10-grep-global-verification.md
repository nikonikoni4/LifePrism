---
title: grep 全局验证：无残留 DELETE FROM / self.db.delete
created_at: 2026-07-22
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02-code/prd.md`（PRD 2：代码适配）

## What to build

在所有其他切片完成后，执行全局 grep 验证，确认 `lifeprism/` 目录下（排除 migrations/、api/、test/、SyncRepository.full_clear）无残留的不合规删除路径：

1. 无残留的原生 `DELETE FROM` SYNC_TABLES SQL 语句
2. 无残留的 `self.db.delete(` 调用 SYNC_TABLES
3. 所有 SYNC_TABLES 的删除都经过 `_generic_delete` 或 `_generic_batch_delete`
4. 云端 `full_clear` 和迁移脚本 DELETE 不写墓碑（特殊路径，排除验证）
5. `SyncRepository.upsert_rows_with_lww` 的 hash_id 逻辑正常

同时确认废弃表状态：
- `category_map_cache`、`daily_focus`、`weekly_focus` 是否应从 SYNC_TABLES 移除

## Acceptance criteria

- [ ] grep 验证：`lifeprism/` 目录下（排除 migrations/、api/、test/、SyncRepository.full_clear）无残留的 `DELETE FROM` SYNC_TABLES 原生 SQL
- [ ] grep 验证：`lifeprism/` 目录下无残留的 `self.db.delete(` 调用 SYNC_TABLES
- [ ] 所有 SYNC_TABLES 的删除都经过 `_generic_delete` 或 `_generic_batch_delete`
- [ ] 云端 `full_clear` 和迁移脚本 DELETE 不写墓碑
- [ ] `SyncRepository.upsert_rows_with_lww` 的 hash_id 逻辑正常
- [ ] 废弃表状态已确认（是否从 SYNC_TABLES 移除）

## Blocked by

- `.scratch/deletion-sync-02-code/issues/02-journal-provider-migration.md`
- `.scratch/deletion-sync-02-code/issues/03-commitment-provider-migration.md`
- `.scratch/deletion-sync-02-code/issues/04-being-provider-migration.md`
- `.scratch/deletion-sync-02-code/issues/05-value-provider-migration.md`
- `.scratch/deletion-sync-02-code/issues/06-write-channel-audit-w2.md`
- `.scratch/deletion-sync-02-code/issues/07-l1-remaining-single-delete-unification.md`
- `.scratch/deletion-sync-02-code/issues/08-l2-batch-delete-unification.md`
- `.scratch/deletion-sync-02-code/issues/09-l3-cascade-l4-service-sink.md`
