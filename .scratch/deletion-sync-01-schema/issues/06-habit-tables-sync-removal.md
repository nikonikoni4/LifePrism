---
title: habit 表同步限制（从 SYNC_TABLES 移除 + 已知限制文档）
status: ready-for-agent
created_at: 2026-07-22
parent_prd: .scratch/deletion-sync-01-schema/prd.md
---

# 06 - habit 表同步限制

## Parent

- PRD: [.scratch/deletion-sync-01-schema/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/deletion-sync-01-schema/prd.md)

## What to build

将 `habit_chains` 和 `habit_chain_nodes` 从 `SYNC_TABLES` 移除，因 `habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致会导致外键断裂。这两张表仍加 `hash_id` 字段（在 Issue 01 中完成），为未来恢复同步做准备。

同时写已知限制文档，记录此限制的原因和恢复条件。

具体改造：

1. 在 `lifeprism/sync/constants.py` 的 `SYNC_TABLES` 中注释掉 `habit_chains` 和 `habit_chain_nodes`，标注 `# TODO PRD 2: 恢复同步前需先解决 chain_id 外键映射问题（chain_id 改引用 hash_id）`。

2. 写已知限制文档 `docs/known-limitations/habit-chain-tables-not-synced.md`。

## Acceptance criteria

- [ ] `habit_chains` 和 `habit_chain_nodes` 从 `lifeprism/sync/constants.py` 的 `SYNC_TABLES` 中移除
- [ ] `SYNC_TABLES` 中标注 `# TODO PRD 2: 恢复同步前需先解决 chain_id 外键映射问题（chain_id 改引用 hash_id）`
- [ ] `HASH_ID_PREFIXES` 仍包含这两张表（hash_id 字段照加，在 Issue 01 中完成）
- [ ] 测试覆盖 `habit_chains` / `habit_chain_nodes` 不在 `SYNC_TABLES` 中
- [ ] 写已知限制文档 `docs/known-limitations/habit-chain-tables-not-synced.md`
- [ ] 更新 `docs/known-limitations/index.md`（新增条目，遵循 CLAUDE.md 文档地图规则）
- [ ] 已知限制文档记录原因（`chain_id` 引用自增 id，同步后断裂）
- [ ] 已知限制文档记录恢复条件（`chain_id` 改引用 `hash_id` 后可恢复，属于 PRD 2 代码适配范围）
- [ ] 已知限制文档记录当前云端 agent 无 habit 链条数据需求，不同步也能接受

## Blocked by

None - can start immediately（与 Issue 01 并行）

## Comments

### 关键设计约束（来自 ADR）

- 这是**临时移除**，不是永久放弃。恢复同步的前置条件：云端 agent 需要 habit 链条数据 + 服务器网页浏览。详见 [ADR 2026-07-22-habit-chain-tables-not-synced.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/ADR/2026-07-22-habit-chain-tables-not-synced.md)
- 恢复同步前**必须先解决 chain_id 外键问题**（`chain_id` 改引用 `hash_id`），属于 PRD 2 代码适配范围
- 当前云端 agent 实际上没有使用 habit 链条数据的需求，因此不同步也能接受
- `HASH_ID_PREFIXES` 仍包含这两张表，hash_id 字段照加，迁移脚本仍回填（在 Issue 01 和 Issue 02 中完成）
- **spec 更新延后**：PRD 1 完成后，`data-sync-core-spec.md` 中"30 张静态表"描述需更新（移除 2 张 habit 表 + 新增 1 张 deletion_log = 30 张），但本 PRD 不强制要求同步更新 spec，延后到 PRD 2/3 统一处理

### 已知限制文档内容要点

`docs/known-limitations/habit-chain-tables-not-synced.md` 应包含：
- 问题描述：`habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致导致外键断裂
- 影响范围：`habit_chains` 和 `habit_chain_nodes` 两张表不参与同步
- 原因：`chain_id` 改引用 `hash_id` 属于 PRD 2 代码适配范围，不在 PRD 1 schema 变更范围内
- 当前状态：云端 agent 无 habit 链条数据需求，不同步也能接受
- 恢复条件：云端 agent 需要 habit 链条数据 + 服务器网页浏览时恢复同步，恢复前必须先解决 `chain_id` 外键问题
