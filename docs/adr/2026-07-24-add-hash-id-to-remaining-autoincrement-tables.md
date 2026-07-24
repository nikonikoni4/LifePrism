---
version: 1.0
created_at: 2026-07-24
updated_at: 2026-07-24
last_updated: 2026-07-24
abstract: m015 审计遗漏的 3 张 AUTOINCREMENT 同步表（daily_focus/weekly_focus/category_map_cache）补充 hash_id 字段，修复墓碑跨端删除命中错误记录的问题
status: decided
---

# 为遗漏的 AUTOINCREMENT 表补充 hash_id 字段

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

代码审查（docs/generated/022/2026-07-24-code-review-deletion-sync-tombstone.md Issue 1）发现：
`daily_focus`、`weekly_focus`、`category_map_cache` 三张表是 AUTOINCREMENT 同步表（在 `SYNC_TABLES` 中），
但未被 m015 迁移覆盖（不在 `HASH_ID_PREFIXES` 中）。

墓碑同步时，`execute_tombstone_delete_with_cursor` 通过 `HASH_ID_PREFIXES` 判断用 `hash_id` 列还是主键列。
这三张表 fallback 到整数主键 `id`，而 `id` 在两端不同，导致墓碑可能删除错误记录。

### 讨论范围

- 3 张遗漏表：`daily_focus`、`weekly_focus`、`category_map_cache`
- 修复方案：补充 hash_id vs 文档化为已知限制
- 迁移方法与 m015 一致

### 不在讨论范围

- m015 已覆盖的 6 张表（无需变更）
- `habit_chains`/`habit_chain_nodes`（因 chain_id 外键问题从 SYNC_TABLES 移除，见已知限制）

## 决策

### 方案 A：补充 hash_id（采用）

为 3 张表补充 `hash_id TEXT NOT NULL UNIQUE` 字段，注册到 `HASH_ID_PREFIXES`，
创建 m016 迁移脚本回填现有数据。

### 方案 B：文档化为已知限制

记录这 3 张表不支持墓碑删除同步。不彻底，且 `category_map_cache` 有确认的删除路径。

### 决策理由

方案 A 与已有 6 张表保持一致，彻底修复问题。`category_map_cache` 有确认的删除路径
（`category_api.py` 的 `delete_category_map_cache`），不能作为已知限制接受。
`daily_focus`/`weekly_focus` 虽然当前主要是更新操作，但未来可能增加删除功能。

## 实施细节

### 迁移方法

采用与 m015 完全相同的方法（ALTER + CREATE UNIQUE INDEX + 回填）：
1. `ALTER TABLE ADD COLUMN hash_id TEXT`（允许 NULL）
2. `CREATE UNIQUE INDEX IF NOT EXISTS`
3. 逐行 `UPDATE` 回填（碰撞重试）

### 前缀映射

| 表名 | 前缀 |
| ---- | ---- |
| daily_focus | `df-` |
| weekly_focus | `wf-` |
| category_map_cache | `cmc-` |

### 已知限制

与 m015 相同：迁移前两端各自独立创建的记录，回填后 hash_id 不同，
迁移前的删除仍可能命中错误记录。此限制在 m015 中已接受，本迁移不额外处理。

## 关联文档

- 上游 ADR: [2026-07-22-add-hash-id-to-autoincrement-tables.md](2026-07-22-add-hash-id-to-autoincrement-tables.md)
- 上游 ADR: [2026-07-22-hash-id-sync-only-identifier.md](2026-07-22-hash-id-sync-only-identifier.md)
- 代码审查: [docs/generated/022/2026-07-24-code-review-deletion-sync-tombstone.md](../generated/022/2026-07-24-code-review-deletion-sync-tombstone.md) Issue 1
- 迁移脚本: `lifeprism/repository/migrations/scripts/m016_add_hash_id_to_remaining_autoincrement_tables.py`
- 常量: `lifeprism/sync/constants.py` — `HASH_ID_PREFIXES`
- Schema: `lifeprism/config/database.py` — 3 张表配置新增 `hash_id` 列
