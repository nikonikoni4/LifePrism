---
title: 墓碑表建表 + ADR（deletion_log schema + 加入 SYNC_TABLES）
status: ready-for-agent
created_at: 2026-07-22
parent_prd: .scratch/deletion-sync-01-schema/prd.md
---

# 05 - 墓碑表建表 + ADR

## Parent

- PRD: [.scratch/deletion-sync-01-schema/prd.md](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/deletion-sync-01-schema/prd.md)

## What to build

新增 `deletion_log` 墓碑表，记录删除意图，使删除操作能跨端传播。墓碑表加入 `SYNC_TABLES` 参与同步。同时写 ADR 记录墓碑表 schema 决策。

具体改造：

1. 在 `lifeprism/config/database.py` 新增 `DELETION_LOG_CONFIG`：

```python
DELETION_LOG_CONFIG = {
    "table_name": "deletion_log",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "墓碑ID（dl-+uuid8）",
        },
        "target_table": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "被删记录所在表名",
        },
        "record_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "被删记录的 hash_id（AUTOINCREMENT 表）或主键（TEXT PK 表）",
        },
        "source": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "来源：local/cloud",
        },
    },
    "timestamps": True,
    "update_at": True,  # LWW 比较用 updated_at；插入时 updated_at == created_at，墓碑不再修改
}
```

2. 在 `lifeprism/sync/constants.py` 的 `SYNC_TABLES` 中加入 `deletion_log`。

3. 写 ADR `docs/adr/2026-07-22-deletion-log-table.md`，记录墓碑表 schema 决策（含字段命名 `target_table` 的理由、`updated_at == created_at` 语义、LWW 比较字段选择）。

## Acceptance criteria

- [ ] `lifeprism/config/database.py` 新增 `DELETION_LOG_CONFIG`，schema 符合上述定义
- [ ] 字段名用 `target_table` 而非 `table_name`（避免与代码中 `table_name` 变量名混淆）
- [ ] 配置 `update_at: True`（LWW 比较用 `updated_at`）
- [ ] **不将 `dl-` 前缀加入 `HASH_ID_PREFIXES`**（`deletion_log` 的 id 是 `dl-` 前缀的 8 位 hex，不是 hash_id；id 生成在 PRD 3 的 DeletionLogProvider 中通过 `_generic_insert(id_prefix='dl-')` 实现）
- [ ] `deletion_log` 加入 `lifeprism/sync/constants.py` 的 `SYNC_TABLES`
- [ ] 新库启动时 `LWTableManager` 自动建表成功，`deletion_log` 表存在
- [ ] 测试覆盖 `deletion_log` schema 正确（字段名 `target_table` 非 `table_name`）
- [ ] 测试覆盖 `deletion_log` 在 `SYNC_TABLES` 中
- [ ] 写 ADR `docs/adr/2026-07-22-deletion-log-table.md`，记录墓碑表 schema 决策
- [ ] ADR 更新 `docs/adr/index.md`（在顶部新增条目）

## Blocked by

None - can start immediately（与 Issue 01 并行）

## Comments

### 关键设计约束

- `id` 生成在 PRD 3 的 DeletionLogProvider 中通过 `_generic_insert(id_prefix='dl-')` 实现，**本 PRD 只建表结构，不将 `dl-` 加入 `HASH_ID_PREFIXES`**（`dl-` 不是 hash_id）
- 墓碑表 `update_at: True` 会使 `has_updated_at()` 返回 True，LWW 比较使用 `updated_at` 字段。插入时 `updated_at` 与 `created_at` 同时写入且不再修改（墓碑不更新），因此用 `updated_at` 比较等价于用 `created_at` 比较
- 墓碑清理策略属于 PRD 3 范围，本 PRD 只负责建表
- `DeletionLogProvider` 的 CRUD 属于 PRD 3 范围

### ADR 内容要点

ADR `2026-07-22-deletion-log-table.md` 应包含：
- 字段命名 `target_table` 而非 `table_name` 的理由（避免与代码变量名混淆，语义更清晰）
- `updated_at == created_at` 语义（墓碑不更新，LWW 用 `updated_at` 等价于用 `created_at`）
- LWW 比较字段选择（用 `updated_at` 而非 `created_at`，因为 `update_at: True` 配置使 `has_updated_at()` 返回 True）
