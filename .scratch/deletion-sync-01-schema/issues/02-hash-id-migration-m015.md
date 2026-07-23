---
title: hash_id 迁移脚本 m015（ALTER + 回填 + CREATE UNIQUE INDEX）
status: ready-for-agent
created_at: 2026-07-22
parent_prd: .scratch/deletion-sync-01-schema/prd.md
---

# 02 - hash_id 迁移脚本 m015

## Parent

- PRD: [.scratch/deletion-sync-01-schema/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/deletion-sync-01-schema/prd.md)

## What to build

为 6 张 AUTOINCREMENT 表的现有数据回填 `hash_id`。采用 `ALTER TABLE ADD COLUMN` + 回填 + `CREATE UNIQUE INDEX` 方法（不丢数据，与现有 m012 迁移脚本风格一致）。

具体方法：

1. `ALTER TABLE {table} ADD COLUMN hash_id TEXT`（允许 NULL，绕过 SQLite 不能直接加 NOT NULL UNIQUE 列的限制）
2. `UPDATE {table} SET hash_id = ? WHERE hash_id IS NULL`（回填，前缀 + `uuid.uuid4().hex[:12]`）
3. `CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_hash_id ON {table}(hash_id)`（部分索引，NULL 不参与唯一性检查）

参考现有迁移脚本 `lifeprism/repository/migrations/scripts/m012_add_updated_at_to_sync_tables.py` 的风格。

## Acceptance criteria

- [ ] 新建迁移脚本 `lifeprism/repository/migrations/scripts/m015_add_hash_id_to_autoincrement_tables.py`
- [ ] 对 6 张表（`timeline_custom_block`、`time_paradoxes`、`mood_impacts`、`habit_chains`、`habit_chain_nodes`、`user_app_behavior_log`）执行 ALTER + 回填 + CREATE UNIQUE INDEX
- [ ] 回填时用对应前缀（来自 `HASH_ID_PREFIXES`）+ `uuid.uuid4().hex[:12]` 生成 hash_id
- [ ] 重复运行幂等（已有 `hash_id` 的记录不重复回填，通过 `WHERE hash_id IS NULL` 实现）
- [ ] 回填后所有记录 `hash_id` 唯一（无碰撞，由 CREATE UNIQUE INDEX 强制）
- [ ] 回填过程事务保护（失败回滚）
- [ ] 迁移脚本注册到迁移系统（参考 m012 的注册方式）
- [ ] 测试覆盖 6 张表的回填 + 幂等
- [ ] 测试覆盖回填后 `hash_id` 唯一性
- [ ] 测试覆盖事务保护（失败回滚）
- [ ] Prior art: `test/core/unit/repository/test_m008_migrate_to_utc.py`、`test/core/unit/repository/test_m012_migrate_updated_at.py`

## Blocked by

- Issue 01（hash_id schema 基础）— 必须先完成 schema 定义才能写迁移脚本

## Comments

### 关键设计约束（来自 ADR）

- 迁移方法采用 ALTER + 回填 + CREATE UNIQUE INDEX，**不采用删表重建**（数据丢失风险）。详见 [ADR 2026-07-22-add-hash-id-to-autoincrement-tables.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/ADR/2026-07-22-add-hash-id-to-autoincrement-tables.md)
- 旧库 hash_id 列实际为 NULLABLE，缺少 NOT NULL 约束；新库按 schema 配置会有列级 NOT NULL+UNIQUE。新旧库 schema 不一致已承认，靠 `_generic_insert` 兜底保证不写 NULL
- 幂等性天然实现：`PRAGMA table_info` 检查 hash_id 列是否已存在（参考 m012 L56-60），`UPDATE ... WHERE hash_id IS NULL` 天然跳过已回填记录，`CREATE UNIQUE INDEX IF NOT EXISTS` 天然幂等
- **UNIQUE 冲突处理**：回填时若发生 UNIQUE 冲突（12 位 hex 碰撞概率极低，个人级使用场景可忽略），重新生成 hash_id 重试即可
