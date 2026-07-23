---
title: 同步删除 - 阶段 1：Schema 变更（hash_id + 墓碑表）
created_at: 2026-07-22
updated_at: 2026-07-22
status: ready-for-agent
type: feature
---

# 同步删除 - 阶段 1：Schema 变更（hash_id + 墓碑表）

## 总任务说明

本 PRD 是"数据库删除同步"任务链的**第 1 步（共 3 步）**。

```
[PRD 1] Schema 变更（本 PRD）
    │   6 张 AUTOINCREMENT 表加 hash_id 字段
    │   新增 deletion_log 墓碑表
    │   迁移脚本回填 hash_id
    │   _generic_insert 的 hash_id 兜底生成逻辑
    │   upsert_rows_with_lww / get_unique_fields 的 hash_id 逻辑
    ▼
[PRD 2] 代码适配
    │   server/providers/ 迁移到 repository/providers/
    │   所有写入通道统一走 _generic_insert
    │   所有删除通道统一走 _generic_delete（含写墓碑）
    │   LWW 去重键改用 hash_id
    ▼
[PRD 3] 墓碑同步流程
        sync_once 集成墓碑 Pull/Push/清理
        DeletionLogProvider
        端到端验证（A 设备删除 → B 设备同步删除）
```

**本 PRD 的边界**：只做数据库 schema 变更、基类方法的 hash_id 兜底生成与同步去重逻辑调整，不涉及 Provider 迁移、不涉及墓碑同步流程。

## Problem Statement

LifeWatch-AI 的本地↔云端双向同步系统存在一个核心功能缺口：**删除操作无法同步**。用户在 A 设备删除一条记录后，下次 B 设备 pull 时云端把这条记录又拉了回来——删除操作完全失效。

要实现删除同步，需要采用 **Tombstone Pattern（墓碑表模式）**：独立的 `deletion_log` 表记录"已死亡"的数据。每次同步时，先传播墓碑，对端按墓碑执行真实删除。

但墓碑机制的前提是：**被删记录必须有一个跨端稳定的标识**。当前 6 张 AUTOINCREMENT 表（`timeline_custom_block` / `time_paradoxes` / `mood_impacts` / `habit_chains` / `habit_chain_nodes` / `user_app_behavior_log`）使用自增 `id` 作为主键，而自增 `id` 在两端不同——A 设备的 id=5 不等于 B 设备的 id=5。如果墓碑记录的是自增 `id`，对端无法正确执行删除。

因此，本 PRD 的核心任务是为这 6 张表新增 `hash_id` 字段，作为跨端稳定的**同步专用标识**。

## 核心设计决策

### hash_id 的定位：同步专用标识（非主键）

- **`_PRIMARY_KEY` 保持为 `id`（自增）不变**，所有 Provider 的 update/delete/get_by_id 仍按自增 id 工作，调用方（API/Service/前端）完全无感知
- **`hash_id` 仅在以下场景使用**：
  1. 同步去重：`upsert_rows_with_lww` 对 AUTOINCREMENT 表用 `hash_id` 作 LWW 查找键
  2. 删除同步：墓碑表 `record_id` 字段存 `hash_id`（PRD 3 实现）
- 本地 CRUD 操作不使用 `hash_id`，避免改动面扩散到 Provider/API/Service/前端

### `_generic_insert` 用前缀字典判断

- 不依赖 `_is_autoincrement_table()`（该方法在 SyncRepository 中，不在基类）
- 直接用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断：返回非 None 即需要生成 hash_id
- 前缀字典的 key 集合 = 有 hash_id 字段的表集合（一对一映射）

## Solution

1. **6 张目标表新增 `hash_id` 字段**（含 `time_paradoxes` 改造为 AUTOINCREMENT）：`TEXT NOT NULL UNIQUE`，12 位 hex + 表名前缀（如 `tcb-a3f8b2c1d4e6`）。
2. **`time_paradoxes` 表的 id 字段改为 AUTOINCREMENT**：当前为 `INTEGER PRIMARY KEY NOT NULL`，改为 `INTEGER PRIMARY KEY AUTOINCREMENT`（该表未投入使用，无需向后兼容）。
3. **新增 `deletion_log` 墓碑表**：记录 `target_table` + `record_id` + `source` + `created_at` / `updated_at`。
4. **迁移脚本回填 `hash_id`**：为 6 张表的现有数据回填 `hash_id`，幂等。方法：`ALTER TABLE ADD COLUMN hash_id TEXT`（允许 NULL，绕过 SQLite 不能直接加 NOT NULL UNIQUE 列的限制）→ 回填 `hash_id`（`UPDATE ... SET hash_id = ? WHERE hash_id IS NULL`）→ `CREATE UNIQUE INDEX IF NOT EXISTS`（部分索引，NULL 不参与唯一性检查）。参考 m012 迁移脚本风格（具体实现由执行方决定，PRD 只描述需求）。
5. **`HASH_ID_PREFIXES` 字典**：前缀清单集中在 `lifeprism/sync/constants.py`。
6. **`_generic_insert` 改造**：用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断，非 None 且 `hash_id` 未传入时兜底生成。
7. **`upsert_rows_with_lww` / `get_unique_fields` 改造**：对在 `HASH_ID_PREFIXES` 中的表，用 `hash_id` 作去重键。
8. **`habit_chains` / `habit_chain_nodes` 从 `SYNC_TABLES` 临时移除**：因 `habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致会导致外键断裂。这两张表仍加 `hash_id` 字段，但暂不参与同步。

## User Stories

### hash_id 字段

1. 作为同步系统，6 张 AUTOINCREMENT 表（`timeline_custom_block` / `time_paradoxes` / `mood_impacts` / `habit_chains` / `habit_chain_nodes` / `user_app_behavior_log`）必须有跨端稳定的标识字段 `hash_id`，这样两端能识别同一条记录。
2. 作为同步系统，`hash_id` 必须是 12 位 hex（48 bit 熵），支持单表 1677 万条记录无显著碰撞。
3. 作为同步系统，现有 18 张 TEXT 主键表的 ID（8 位 hex）保持不变，不做破坏性改动。
4. 作为系统开发者，`hash_id` 在 `_generic_insert` 中兜底生成（前缀 + `uuid.uuid4().hex[:12]`），如果调用方未传入 `hash_id` 则自动生成，已传入则保留。Provider 子类无感知。
5. 作为同步系统，`hash_id` 字段必须有 `NOT NULL` + `UNIQUE` 约束，数据库层强制唯一。
6. 作为系统开发者，`hash_id` 前缀清单集中在 `lifeprism/sync/constants.py` 的 `HASH_ID_PREFIXES` 字典中，不分散在各 Provider。前缀字典同时作为"哪些表需要 hash_id"的判断依据。

### time_paradoxes 表改造

7. 作为系统开发者，`time_paradoxes` 表的 id 字段从 `INTEGER PRIMARY KEY NOT NULL` 改为 `INTEGER PRIMARY KEY AUTOINCREMENT`，与其它 5 张 AUTOINCREMENT 表保持一致。该表未投入使用，无需向后兼容。

### 迁移脚本

8. 作为数据迁移脚本，运行时必须为 6 张表的现有数据回填 `hash_id`，未填充的记录用对应前缀生成 12 位 hex。
9. 作为数据迁移脚本，重复运行必须幂等（已有 `hash_id` 的记录不重复回填）。
10. 作为数据迁移脚本，回填后所有记录 `hash_id` 唯一（无碰撞）。
11. 作为数据迁移脚本，回填过程中事务保护（失败回滚）。
12. 作为数据迁移脚本，方法为 `ALTER TABLE ADD COLUMN hash_id TEXT`（允许 NULL）→ 回填 `hash_id` → `CREATE UNIQUE INDEX IF NOT EXISTS`（具体 SQL 由执行方决定，参考 m012 迁移脚本风格）。

### 墓碑表

13. 作为同步系统，必须有独立的 `deletion_log` 表记录删除意图，这样删除操作能跨端传播。
14. 作为同步系统，墓碑表必须包含字段：`id`（`dl-` 前缀，8 位 hex，与 TEXT 主键表一致）、`target_table`、`record_id`、`source`（`local`/`cloud`）、`created_at` / `updated_at`。`id` 生成在 PRD 3 的 DeletionLogProvider 中通过 `_generic_insert(id_prefix='dl-')` 实现，**本 PRD 只建表结构，不将 `dl-` 加入 `HASH_ID_PREFIXES`**（`dl-` 不是 hash_id）。
15. 作为同步系统，墓碑表必须加入 `SYNC_TABLES`，参与同步。
16. 作为系统开发者，墓碑表的字段名必须用 `target_table` 而非 `table_name`，避免与代码中 `table_name` 变量名混淆，语义更清晰。
17. 作为同步系统，墓碑表配置 `update_at: True`，LWW 比较用 `updated_at` 字段。插入时 `updated_at` 与 `created_at` 同时写入且不再修改（墓碑不更新）。

### 基类方法改造

18. 作为系统开发者，`_generic_insert` 用 `HASH_ID_PREFIXES.get(self._TABLE_NAME)` 判断是否需要生成 `hash_id`（非 None 即需要）。如果 `hash_id` 未传入则兜底生成（前缀 + `uuid.uuid4().hex[:12]`），已传入则保留。
19. 作为系统开发者，`upsert_rows_with_lww` 对在 `HASH_ID_PREFIXES` 中的表：仍然剥离 `id` 字段（避免污染 `sqlite_sequence`），但保留 `hash_id`，按 `hash_id` 做 LWW 比较。
20. 作为系统开发者，`get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表必须返回 `["hash_id"]`，不再依赖原表的 UNIQUE 约束。
21. 作为系统开发者，`_batch_get_existing_updated_at_by_unique` 必须支持按 `hash_id` 查询已存在记录的 `updated_at`。

### habit 链条表同步限制

22. 作为系统开发者，`habit_chains` 和 `habit_chain_nodes` 必须从 `SYNC_TABLES` 中移除，因为 `habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致会导致外键断裂。
23. 作为系统开发者，`habit_chains` 和 `habit_chain_nodes` 仍需新增 `hash_id` 字段并回填，保持与其他 4 张表一致，为未来恢复同步做准备。

## Implementation Decisions

### 模块改造清单

| 模块 | 改造内容 |
|------|---------|
| `lifeprism/config/database.py` | 6 张 AUTOINCREMENT 表新增 `hash_id` 字段；`time_paradoxes` id 改为 AUTOINCREMENT；新增 `DELETION_LOG_CONFIG` |
| `lifeprism/sync/constants.py` | 新增 `HASH_ID_PREFIXES` 字典；`SYNC_TABLES` 加入 `deletion_log`；`SYNC_TABLES` 移除 `habit_chains` 和 `habit_chain_nodes` |
| `lifeprism/repository/base_providers/lw_base_data_provider.py` | `_generic_insert` 用 `HASH_ID_PREFIXES.get` 判断，兜底生成 `hash_id` |
| `lifeprism/repository/sync_repository.py` | `upsert_rows_with_lww` 对 `HASH_ID_PREFIXES` 中的表用 `hash_id` 作去重键；`get_unique_fields` 返回 `["hash_id"]`；`_batch_get_existing_updated_at_by_unique` 支持按 `hash_id` 查询。所有依赖 `get_unique_fields` 的方法（含 `_find_existing_updated_at` 单行版本）自动受益 |
| `lifeprism/repository/migrations/scripts/m015_add_hash_id_to_autoincrement_tables.py`（新建） | 为 6 张 AUTOINCREMENT 表回填 `hash_id`（ALTER + 回填 + CREATE UNIQUE INDEX，参考 m012 风格） |
| `docs/known-limitations/`（新建） | 记录 habit 链条表不同步的限制 |

### 6 张 AUTOINCREMENT 表清单

| 表名 | hash_id 前缀 | 示例 hash_id | 当前是否在 SYNC_TABLES |
|------|-------------|-------------|----------------------|
| `timeline_custom_block` | `tcb-` | `tcb-a3f8b2c1d4e6` | 是（保留） |
| `time_paradoxes` | `tp-` | `tp-...` | 是（保留） |
| `mood_impacts` | `mi-` | `mi-...` | 是（保留） |
| `habit_chains` | `hc-` | `hc-...` | **否（移除）** |
| `habit_chain_nodes` | `hcn-` | `hcn-...` | **否（移除）** |
| `user_app_behavior_log` | `awbl-` | `awbl-...` | 是（保留） |

### Schema 变更

#### 6 张 AUTOINCREMENT 表新增 `hash_id` 字段

```python
"hash_id": {
    "type": "TEXT",
    "constraints": ["NOT NULL", "UNIQUE"],
    "comment": "同步用全局唯一标识（12位 hex + 表名前缀）",
},
```

#### time_paradoxes id 字段改造

```python
# 改造前
"id": {"type": "INTEGER", "constraints": ["PRIMARY KEY", "NOT NULL"], "comment": "ID"}

# 改造后
"id": {"type": "INTEGER", "constraints": ["PRIMARY KEY", "AUTOINCREMENT"], "comment": "自增主键"}
```

#### 墓碑表 schema

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

### `_generic_insert` 的 hash_id 兜底生成

```python
# 兜底生成 hash_id（同步专用标识，与 _PRIMARY_KEY 无关）
# 前缀字典同时作为"哪些表需要 hash_id"的判断依据
hash_prefix = HASH_ID_PREFIXES.get(self._TABLE_NAME)
if hash_prefix and "hash_id" not in data:
    data["hash_id"] = f"{hash_prefix}{uuid.uuid4().hex[:12]}"
```

### 同步去重逻辑调整

**当前逻辑**（需修改）：对 AUTOINCREMENT 表，从行数据副本中移除 `id`。

**改造后**：
- 对在 `HASH_ID_PREFIXES` 中的表（即有 hash_id 的表）：
  - 仍然剥离 `id` 字段（避免污染 `sqlite_sequence`）
  - **保留 `hash_id` 字段**
  - 去重键从原 UNIQUE 字段改为 `hash_id`
  - LWW 比较按 `hash_id` 查询已存在记录的 `updated_at`
- 不在 `HASH_ID_PREFIXES` 中的表：保持现有逻辑不变

`get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`。

## Testing Decisions

### 测试原则

- **只测试外部行为，不测试实现细节**
- **迁移脚本测试**：覆盖回填 + 幂等 + 唯一性
- **基类方法测试**：覆盖 hash_id 生成和 LWW 去重

### 测试接缝

**位置**：`test/core/unit/repository/test_migrate_hash_id.py`（新增）+ 扩展 `test/core/unit/storage/test_base_provider_generic_methods.py` + 扩展 `test/core/integration/repository/test_sync_repository.py`

**测试内容**：
- 迁移脚本对 6 张表回填 `hash_id`，NULL → 回填 12 位 hex + 前缀
- 重复执行幂等
- 每张表前缀正确
- 回填后所有记录 `hash_id` 唯一
- `_generic_insert` 对 AUTOINCREMENT 表自动生成 `hash_id`（未传入时）
- `_generic_insert` 已传入 `hash_id` 时保留不覆盖
- `upsert_rows_with_lww` 对 AUTOINCREMENT 表用 `hash_id` 作去重键
- `get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`
- `deletion_log` 表 schema 正确（字段名 `target_table` 非 `table_name`）
- `habit_chains` / `habit_chain_nodes` 不在 `SYNC_TABLES` 中

**Prior art**：`test/core/unit/repository/test_m008_migrate_to_utc.py`、`test/core/unit/storage/test_base_provider_generic_methods.py`

## Out of Scope

1. **Provider 迁移**：server/providers/ 迁移到 repository/providers/，属于 PRD 2。
2. **删除通道统一**：17 处直接 SQL DELETE 改为 `_generic_delete`，属于 PRD 2。
3. **`_generic_delete` 写墓碑逻辑**：墓碑写入实现，属于 PRD 2。
4. **墓碑同步流程**：sync_once 集成墓碑 Pull/Push/清理，属于 PRD 3。
5. **DeletionLogProvider**：墓碑表 Provider 的 CRUD，属于 PRD 3。
6. **文件删除同步**：文件操作不走 LifePrism 同步管控，文档化为已知限制。
7. **删除-更新冲突自动处理**：一端删除、另一端更新时，不自动处理，属于已知限制。
8. **AUTOINCREMENT 表外键断裂问题**：`habit_chain_nodes.chain_id` 引用 `habit_chains.id`，本 PRD 通过临时移除同步解决，详见已知限制文档。
9. **列级 UNIQUE 约束解析 bug 修复**：`get_unique_fields` 无法识别列级 UNIQUE（如 `mood_impacts.name`），但改造后 AUTOINCREMENT 表用 `hash_id` 作去重键，bug 对这些表无实际影响。剩余 TEXT PK 表（如 `goal.name`、`user_values.keywords`）的 bug 无实际影响（主键在两端一致，按主键查找也能工作）。本 PRD 不修复，留作独立 issue。
10. **墓碑清理策略**：墓碑记录的清理逻辑属于 PRD 3 范围，本 PRD 只负责建表。

## Further Notes

### 关联文档

- **交接文档**：[docs/temp/2026-07-22-deletion-sync-handoff.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/temp/2026-07-22-deletion-sync-handoff.md)
- **数据同步核心 spec**：[docs/specs/2026-07-16-data-sync-core-spec.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-core-spec.md)
- **LWW 冲突解决 ADR**：[docs/adr/2026-07-09-lww-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-09-lww-conflict-resolution.md)

### 待写 ADR

1. **`2026-07-22-autoincrement-hash-id.md`** — AUTOINCREMENT 表 `hash_id` 字段决策（含 12 位 hex 位数选择依据、前缀清单、hash_id 定位为同步专用标识而非主键的决策、与 8 位 TEXT 主键的并存策略）
2. **`2026-07-22-deletion-log-table.md`** — 墓碑表 schema 决策（含字段命名 `target_table` 的理由、`updated_at == created_at` 语义、LWW 比较字段选择）

### 待写已知限制

- **`habit-chain-tables-not-synced.md`** — `habit_chains` 和 `habit_chain_nodes` 不参与同步的限制，记录原因（`chain_id` 外键引用自增 id，同步后断裂）和恢复条件（`chain_id` 改引用 `hash_id` 后可恢复）

### 验收标准

- [ ] 6 张 AUTOINCREMENT 表新增 `hash_id` 字段（`TEXT NOT NULL UNIQUE`）
- [ ] `time_paradoxes` 表 id 字段改为 `INTEGER PRIMARY KEY AUTOINCREMENT`
- [ ] `HASH_ID_PREFIXES` 字典在 `lifeprism/sync/constants.py` 定义，包含 6 张表
- [ ] 新增 `deletion_log` 墓碑表，schema 符合决策（`update_at: True`）
- [ ] `deletion_log` 加入 `SYNC_TABLES`
- [ ] `habit_chains` 和 `habit_chain_nodes` 从 `SYNC_TABLES` 移除
- [ ] 迁移脚本对 6 张表回填 `hash_id`，重复执行幂等
- [ ] 迁移脚本回填后所有记录 `hash_id` 唯一（无碰撞）
- [ ] 迁移脚本回填过程事务保护（失败回滚）
- [ ] `_generic_insert` 用 `HASH_ID_PREFIXES.get` 判断，未传入 `hash_id` 时兜底生成
- [ ] `upsert_rows_with_lww` 对在 `HASH_ID_PREFIXES` 中的表用 `hash_id` 作去重键
- [ ] `get_unique_fields` 对在 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`
- [ ] `_batch_get_existing_updated_at_by_unique` 支持按 `hash_id` 查询已存在记录的 `updated_at`
- [ ] AUTOINCREMENT 表的 `id` 仍被剥离（不污染 `sqlite_sequence`）
- [ ] 迁移脚本测试覆盖 6 张表的回填 + 幂等
- [ ] `_generic_insert` 测试覆盖未传入/已传入 `hash_id` 两种情况
- [ ] `upsert_rows_with_lww` 测试覆盖用 `hash_id` 作去重键
- [ ] `_batch_get_existing_updated_at_by_unique` 测试覆盖按 `hash_id` 查询
- [ ] `deletion_log` schema 测试覆盖字段名 `target_table`
- [ ] `SYNC_TABLES` 测试覆盖 `habit_chains` / `habit_chain_nodes` 不在列表中
- [ ] 写 ADR `docs/adr/2026-07-22-autoincrement-hash-id.md`
- [ ] 写 ADR `docs/adr/2026-07-22-deletion-log-table.md`
- [ ] 写已知限制 `docs/known-limitations/habit-chain-tables-not-synced.md`

### 已知风险

1. **迁移脚本 UNIQUE 冲突**：现有数据回填 `hash_id` 时若发生 UNIQUE 冲突（极小概率），需要重试。12 位 hex 在个人级使用场景下碰撞概率可忽略。
2. **habit 链条表恢复同步**：未来恢复 `habit_chains` / `habit_chain_nodes` 同步时，需先将 `habit_chain_nodes.chain_id` 改为引用 `habit_chains.hash_id`（schema + Provider + API 适配），属于 PRD 2/3 范围。
3. **`data-sync-core-spec.md` 需同步更新**：PRD 1 完成后，同步表数量从 31 张变为 30 张（移除 2 张 habit 表）+ 1 张 deletion_log = 30 张。spec 中的"30 张静态表"描述需更新，但本 PRD 不强制要求同步更新 spec（可在 PRD 2/3 时统一更新）。
