---
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-22
last_updated: 创建文档初稿，记录 habit_chains 和 habit_chain_nodes 从 SYNC_TABLES 移除的限制
abstract: habit_chain_nodes.chain_id 引用 habit_chains.id（自增 id），同步后两端 id 不一致导致外键断裂，故 habit_chains 和 habit_chain_nodes 两张表临时不参与同步，待 PRD 2 解决 chain_id 改引用 hash_id 后恢复。
---

# habit 链条表不参与同步限制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题描述

`habit_chain_nodes.chain_id` 字段引用 `habit_chains.id`（自增 id）。两端（客户端与云端）的 SQLite 数据库自增 id 序列不同，同步后 B 端的 `habit_chains.id` 与 A 端不一致，导致 `habit_chain_nodes.chain_id` 指向错误的链条记录（外键断裂）。

当前 `upsert_rows` 已对 AUTOINCREMENT 表剥离 id（见 `lifeprism/repository/sync_repository.py`），因此同步时 `habit_chains` 的 id 不会被同步，B 端会按自身自增序列重新分配 id，从而与 `habit_chain_nodes.chain_id` 的原值错位。

## 影响范围

- **状态**: `acknowledged`（已确认，按当前使用场景接受现状，待 PRD 2 恢复）
- **严重程度**: 低（当前云端 agent 无 habit 链条数据需求）
- **影响范围**: `habit_chains` 和 `habit_chain_nodes` 两张表不参与数据库同步
- **不影响**: `habits`、`habit_challenges`、`habit_checkins` 三张 habit 相关表仍正常同步（它们不引用 `habit_chains.id`）

## 当前假设

- **前提 1**: 当前云端 agent 实际上没有使用 habit 链条数据的需求，不同步也能接受
- **前提 2**: `chain_id` 改引用 `hash_id` 属于 PRD 2 代码适配范围，不在 PRD 1（deletion-sync-01-schema）schema 变更范围内
- **前提 3**: `HASH_ID_PREFIXES` 仍包含这两张表（`habit_chains` → `hc-`，`habit_chain_nodes` → `hcn-`），hash_id 字段照加，迁移脚本仍回填，为未来恢复同步做准备

如果前提 1 改变（云端 agent 需要 habit 链条数据 + 服务器网页浏览），则必须恢复同步，恢复前必须先解决 `chain_id` 外键问题。

## 触发条件

恢复同步的条件（满足以下全部时）：

1. 云端 agent 产生 habit 链条数据需求
2. 服务器网页浏览需要展示 habit 链条数据
3. `chain_id` 已从引用 `habit_chains.id`（自增 id）改为引用 `habit_chains.hash_id`（PRD 2 代码适配）

## 临时方案

已从 `lifeprism/sync/constants.py` 的 `SYNC_TABLES` 中移除 `habit_chains` 和 `habit_chain_nodes`，并标注 TODO 注释：

```python
# TODO PRD 2: 恢复同步前需先解决 chain_id 外键映射问题（chain_id 改引用 hash_id）
```

`HASH_ID_PREFIXES` 仍保留这两张表的映射，hash_id 字段在 Issue 01（schema 变更）中已添加，迁移脚本在 Issue 02 中回填。

## 恢复同步的步骤

当上述触发条件满足时，恢复同步需完成以下改造（属于 PRD 2 代码适配范围）：

1. `chain_id` 字段类型从 `INTEGER` 改为 `TEXT`，引用 `habit_chains.hash_id`
2. 适配 `lifeprism/repository/providers/habit_chain_providers.py` 中所有 `chain_id: int` → `chain_id: str` 的类型注解
3. 适配相关 JOIN 查询（`chain_id` 与 `hash_id` 关联）
4. 将 `habit_chains` 和 `habit_chain_nodes` 重新加入 `SYNC_TABLES`
5. 验证同步后两端 `chain_id` 一致性

## 相关文档

- ADR: [2026-07-22-habit-chain-tables-not-synced.md](../adr/2026-07-22-habit-chain-tables-not-synced.md) — 移除决策（方案 A：临时从 SYNC_TABLES 移除）
- ADR: [2026-07-22-hash-id-sync-only-identifier.md](../adr/2026-07-22-hash-id-sync-only-identifier.md) — hash_id 定位为同步专用标识
- Issue: [.scratch/deletion-sync-01-schema/issues/06-habit-tables-sync-removal.md](../../.scratch/deletion-sync-01-schema/issues/06-habit-tables-sync-removal.md)
- 代码: `lifeprism/sync/constants.py` — `SYNC_TABLES` 与 `HASH_ID_PREFIXES`
- 代码: `lifeprism/config/database.py` — `habit_chain_nodes.chain_id` 外键定义
- 代码: `lifeprism/repository/sync_repository.py` — `upsert_rows` 对 AUTOINCREMENT 表剥离 id 的逻辑

## 注意事项

1. **不要把这两张表加回 SYNC_TABLES**：在 `chain_id` 改引用 `hash_id` 之前，加回会导致同步后链条错乱（用户可见 bug）
2. **不要移除 HASH_ID_PREFIXES 中的映射**：hash_id 字段需要照常添加和回填，为恢复同步做准备
3. **spec 更新延后**：`data-sync-core-spec.md` 中"30 张静态表"描述需更新（移除 2 张 habit 表 + 新增 1 张 deletion_log = 30 张），但延后到 PRD 2/3 统一处理，不在本 PRD 范围内
