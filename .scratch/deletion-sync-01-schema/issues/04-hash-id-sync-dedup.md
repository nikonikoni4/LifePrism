---
title: hash_id 同步去重（upsert_rows_with_lww + get_unique_fields + _batch_get_existing_updated_at_by_unique）
status: ready-for-agent
created_at: 2026-07-22
parent_prd: .scratch/deletion-sync-01-schema/prd.md
---

# 04 - hash_id 同步去重

## Parent

- PRD: [.scratch/deletion-sync-01-schema/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/deletion-sync-01-schema/prd.md)

## What to build

改造 `lifeprism/repository/sync_repository.py` 中的同步去重逻辑，对在 `HASH_ID_PREFIXES` 中的表（即有 hash_id 字段的表）用 `hash_id` 作 LWW 去重键。

具体改造：

1. `upsert_rows_with_lww` 对在 `HASH_ID_PREFIXES` 中的表：
   - 仍然剥离 `id` 字段（避免污染 `sqlite_sequence`）
   - **保留 `hash_id` 字段**
   - 去重键从原 UNIQUE 字段改为 `hash_id`
   - LWW 比较按 `hash_id` 查询已存在记录的 `updated_at`

2. `get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`，不再依赖原表的 UNIQUE 约束。

3. `_batch_get_existing_updated_at_by_unique` 必须支持按 `hash_id` 查询已存在记录的 `updated_at`。

4. 所有依赖 `get_unique_fields` 的方法（含 `_find_existing_updated_at` 单行版本）自动受益，无需单独改造。

## Acceptance criteria

- [ ] `upsert_rows_with_lww` 对在 `HASH_ID_PREFIXES` 中的表用 `hash_id` 作去重键
- [ ] `upsert_rows_with_lww` 对在 `HASH_ID_PREFIXES` 中的表仍然剥离 `id`（不污染 `sqlite_sequence`）
- [ ] `upsert_rows_with_lww` 对在 `HASH_ID_PREFIXES` 中的表保留 `hash_id` 字段（不剥离，否则跨端无法识别同一条记录）
- [ ] `get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`
- [ ] `_batch_get_existing_updated_at_by_unique` 支持按 `hash_id` 查询已存在记录的 `updated_at`
- [ ] 不在 `HASH_ID_PREFIXES` 中的表（TEXT 主键表）保持现有逻辑不变
- [ ] 测试覆盖 `upsert_rows_with_lww` 对 AUTOINCREMENT 表用 `hash_id` 作去重键
- [ ] 测试覆盖 `get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`
- [ ] 测试覆盖 `_batch_get_existing_updated_at_by_unique` 按 `hash_id` 查询
- [ ] 测试覆盖 TEXT 主键表不受影响
- [ ] Prior art: `test/core/integration/repository/test_sync_repository.py`

## Blocked by

- Issue 01（hash_id schema 基础）— 必须先有 `HASH_ID_PREFIXES` 字典定义
- Issue 03（_generic_insert 兜底生成）— 同步插入时需要 hash_id 已生成

## Comments

### 关键设计约束（来自 ADR）

- `hash_id` 定位为同步专用标识，本地 CRUD 不使用。详见 [ADR 2026-07-22-hash-id-sync-only-identifier.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/ADR/2026-07-22-hash-id-sync-only-identifier.md)
- 列级 UNIQUE bug 修复已移出范围（因 AUTOINCREMENT 表改用 hash_id 后该 bug 对这些表无实际影响）。详见 PRD Out of Scope 第 9 条
- `get_unique_fields` 当前只解析 `table_constraints` 中的 `UNIQUE(...)`，无法识别列级 UNIQUE。改造后对 `HASH_ID_PREFIXES` 中的表直接返回 `["hash_id"]`，不依赖列级 UNIQUE 解析，冲突已消除
