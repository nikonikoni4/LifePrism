---
title: hash_id schema 基础（HASH_ID_PREFIXES + 6 张表加字段 + time_paradoxes 改造）
status: ready-for-agent
created_at: 2026-07-22
parent_prd: .scratch/deletion-sync-01-schema/prd.md
---

# 01 - hash_id schema 基础

## Parent

- PRD: [.scratch/deletion-sync-01-schema/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/deletion-sync-01-schema/prd.md)

## What to build

为 6 张目标 AUTOINCREMENT 表新增 `hash_id` 字段作为跨端稳定同步标识。这是删除同步任务链 PRD 1 的 schema 基础切片，后续切片（迁移脚本、`_generic_insert` 兜底生成、同步去重）都依赖此切片完成。

具体改造：

1. 在 `lifeprism/sync/constants.py` 新增 `HASH_ID_PREFIXES` 字典，包含 6 张表的前缀映射。该字典同时作为"哪些表需要 hash_id"的判断依据。建议结构：

```python
HASH_ID_PREFIXES = {
    "timeline_custom_block": "tcb-",
    "time_paradoxes": "tp-",
    "mood_impacts": "mi-",
    "habit_chains": "hc-",
    "habit_chain_nodes": "hcn-",
    "user_app_behavior_log": "awbl-",
}
```

2. 在 `lifeprism/config/database.py` 的 `TABLE_CONFIGS` 中为以下 6 张表新增 `hash_id` 字段配置：

```python
"hash_id": {
    "type": "TEXT",
    "constraints": ["NOT NULL", "UNIQUE"],
    "comment": "同步用全局唯一标识（12位 hex + 表名前缀）",
},
```

涉及表：`timeline_custom_block`、`time_paradoxes`、`mood_impacts`、`habit_chains`、`habit_chain_nodes`、`user_app_behavior_log`。

3. `time_paradoxes` 表的 id 字段从 `["PRIMARY KEY", "NOT NULL"]` 改为 `["PRIMARY KEY", "AUTOINCREMENT"]`（该表未投入使用，无需向后兼容）。

## Acceptance criteria

- [ ] `lifeprism/sync/constants.py` 定义 `HASH_ID_PREFIXES` 字典，包含 6 张表的前缀映射
- [ ] 6 张表在 `TABLE_CONFIGS` 中新增 `hash_id` 字段，类型 `TEXT`，约束 `["NOT NULL", "UNIQUE"]`
- [ ] `time_paradoxes` 表 id 字段改为 `["PRIMARY KEY", "AUTOINCREMENT"]`
- [ ] 新库启动时 `LWTableManager` 自动建表成功，6 张表都有 `hash_id` 字段
- [ ] 18 张 TEXT 主键表的 schema 保持不变（不做破坏性改动）
- [ ] 编写测试验证 6 张表的 `hash_id` 字段存在且有正确约束
- [ ] 编写测试验证 `HASH_ID_PREFIXES` 包含 6 张表且前缀正确
- [ ] 编写测试验证 `time_paradoxes` 的 id 字段为 AUTOINCREMENT

## Blocked by

None - can start immediately

## Comments

### 关键设计约束（来自 ADR）

- `hash_id` 定位为**同步专用标识**，不作为主键。`_PRIMARY_KEY` 保持为 `id`（自增）不变。详见 [ADR 2026-07-22-hash-id-sync-only-identifier.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/ADR/2026-07-22-hash-id-sync-only-identifier.md)
- `HASH_ID_PREFIXES` 字典同时作为"哪些表需要 hash_id"的判断依据，后续 `_generic_insert` 用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断
- 新库按 schema 配置 `["NOT NULL", "UNIQUE"]` 会有列级 NOT NULL+UNIQUE；旧库通过迁移脚本用 ALTER + CREATE UNIQUE INDEX 实现（见 Issue 02）
- 新旧库 schema 差异已在 ADR 中承认，靠 `_generic_insert` 兜底保证不写 NULL
- **两个相关 ADR 已存在**（`2026-07-22-add-hash-id-to-autoincrement-tables.md` 和 `2026-07-22-hash-id-sync-only-identifier.md`），Issue 01 只需遵守，不需新建 ADR。PRD 1 验收标准中的"写 ADR `2026-07-22-autoincrement-hash-id.md`"已通过这两个 ADR 落地
