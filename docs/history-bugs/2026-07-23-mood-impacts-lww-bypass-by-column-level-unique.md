---
version: 1.0
created_at: 2026-07-23
updated_at: 2026-07-23
last_updated: 记录 mood_impacts 列级 UNIQUE 未被同步层解析，导致 LWW 被 INSERT OR REPLACE 绕过的修复过程
abstract: mood_impacts 将业务唯一键 UNIQUE(name) 声明在列级，SyncRepository 只能解析表级 UNIQUE，导致 LWW 按 hash_id 判重而 SQLite REPLACE 按 name 冲突，较旧跨端数据可静默覆盖较新本地数据；修复为将 UNIQUE(name) 移入 table_constraints，并补充双向 LWW 回归测试。
status: fixed
---

# mood_impacts 列级 UNIQUE 导致 LWW 保护被 INSERT OR REPLACE 绕过

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 记录问题根因、修复方案、回归测试和规则沉淀 |

## 元信息

- **发生时间**: 2026-07-22（数据库删除同步阶段 1 引入 hash_id 后具备触发条件）
- **发现时间**: 2026-07-23（第二轮代码审查）
- **修复状态**: 已修复（2026-07-23）
- **影响范围**: `mood_impacts` 跨端同步；两端独立创建同名影响因素且 hash_id 不同时的 LWW 冲突处理
- **bug 类型**: Schema 元数据声明与同步解析器契约不一致
- **严重程度**: P1 — 仅影响单表且需要多设备独立创建同名记录才触发，但触发后会静默丢失较新数据

## 触发规则

在以下场景时阅读本文档：

- 创建或修改加入 `SYNC_TABLES` 的数据库表
- 修改同步表的 `UNIQUE` 约束声明位置
- 修改 `SyncRepository.get_unique_fields()`、`upsert_rows_with_lww()` 或 `upsert_rows()`
- 排查“本地较新 `mood_impacts` 数据同步后被较旧远端数据覆盖”
- 为 AUTOINCREMENT 同步表新增或调整 `hash_id`
- 评估 `INSERT OR REPLACE` 与 LWW 查找键是否一致

## Bug 简述

`mood_impacts` 的业务唯一键是 `name`，但配置曾将它声明为列级约束：

```python
"name": {
    "type": "TEXT",
    "constraints": ["NOT NULL", "UNIQUE"],
},
"table_constraints": [],
```

同步层的 [`SyncRepository.get_unique_fields()`](../../lifeprism/repository/sync_repository.py) 只解析 `TABLE_CONFIGS[table_name]["table_constraints"]` 中的表级 `UNIQUE(...)`，不会解析列级 `columns.<name>.constraints`。因此它无法发现 `UNIQUE(name)`，并因 `mood_impacts` 位于 `HASH_ID_PREFIXES` 而回退到 `hash_id`。

当两台设备独立创建同名、不同 `hash_id` 的影响因素时，LWW 按 `hash_id` 查不到本地等价记录，错误地允许较旧数据进入写入阶段。最终的 `INSERT OR REPLACE` 会响应 SQLite 中所有 UNIQUE 冲突，包括同步层未解析到的列级 `UNIQUE(name)`，于是删除本地较新行并插入远端较旧行，造成静默数据覆盖。

## 复用场景

此问题可作为以下设计和排查场景的参考：

- 配置驱动的 DDL 同时被业务代码当作 schema 元数据读取
- LWW、幂等写入或去重逻辑依赖“业务唯一键”的同步系统
- SQLite `INSERT OR REPLACE` 与多个 UNIQUE 约束同时存在的表
- AUTOINCREMENT 表通过额外稳定标识参与跨端同步
- 数据库引擎认为等价、但应用层解析器采用不同声明入口的约束

核心经验是：数据库层面的约束等价，不代表应用层元数据解析也等价。凡是应用层需要解析约束，声明位置必须符合解析器的明确契约。

## 代码位置

### Bug 发生位置

- **Schema 声明**：[`lifeprism/config/database.py` L1084-L1112](../../lifeprism/config/database.py) — 修复前 `name.constraints` 含 `UNIQUE`，而 `table_constraints=[]`
- **业务唯一键解析**：[`lifeprism/repository/sync_repository.py` L877-L916](../../lifeprism/repository/sync_repository.py) — `get_unique_fields()` 只遍历 `table_constraints`
- **LWW 过滤入口**：[`lifeprism/repository/sync_repository.py` L699-L793](../../lifeprism/repository/sync_repository.py) — `upsert_rows_with_lww()` 按 `get_unique_fields()` 返回字段批量查询本地记录
- **REPLACE 触发点**：[`lifeprism/repository/sync_repository.py` L483-L559](../../lifeprism/repository/sync_repository.py) — 第 525 行构造 `INSERT OR REPLACE`
- **同步范围**：[`lifeprism/sync/constants.py` L24-L64](../../lifeprism/sync/constants.py) — `mood_impacts` 位于 `SYNC_TABLES`
- **hash_id 前缀**：[`lifeprism/sync/constants.py` L66-L76](../../lifeprism/sync/constants.py) — `mood_impacts` 注册 `mi-` 前缀

### 回归测试位置

- [`test/core/integration/repository/test_sync_repository.py` L907-L910](../../test/core/integration/repository/test_sync_repository.py) — 验证 `get_unique_fields("mood_impacts") == ["name"]`
- [`test/core/integration/repository/test_sync_repository.py` L1074-L1110](../../test/core/integration/repository/test_sync_repository.py) — 相同 name、不同 hash_id、远端较旧时保留本地新数据
- [`test/core/integration/repository/test_sync_repository.py` L1112-L1148](../../test/core/integration/repository/test_sync_repository.py) — 相同 name、不同 hash_id、远端较新时覆盖本地旧数据

## 触发条件

以下条件同时成立时触发：

1. 设备 A 与设备 B 各自在本地独立创建一条 `mood_impacts` 记录。
2. 两条记录的 `name` 相同，例如均为 `"工作"`。
3. 两端生成的 `hash_id` 不同，例如 `mi-A` 与 `mi-B`。
4. 其中一端已有较新的 `updated_at=T2`，另一端随后同步一条较旧的 `updated_at=T1`，且 `T1 < T2`。
5. 接收端调用 `upsert_rows_with_lww()`，最终写入仍使用 `INSERT OR REPLACE`。

单设备正常 CRUD、两端 `hash_id` 相同、或没有同名业务键冲突时不会触发。

## 完整失败数据流

假设设备 B 已有较新记录，设备 A 推送较旧记录：

```text
设备 B 本地:
{name="工作", hash_id="mi-B", sort_order=20, updated_at=T2}

设备 A 传入:
{name="工作", hash_id="mi-A", sort_order=5, updated_at=T1}
T1 < T2
```

执行路径：

1. `upsert_rows_with_lww("mood_impacts", rows)` 调用 `get_unique_fields("mood_impacts")`。
2. 修复前 `table_constraints=[]`，解析器读不到列级 `UNIQUE(name)`。
3. 因表存在于 `HASH_ID_PREFIXES`，解析器回退为 `unique_fields=["hash_id"]`。
4. `_batch_get_existing_updated_at_by_unique()` 查询 `WHERE hash_id = "mi-A"`。
5. 设备 B 只有 `mi-B`，查询无结果；LWW 误判传入行为“新记录”，未比较 T1 与 T2。
6. `upsert_rows()` 从 AUTOINCREMENT 行中剥离远端 `id`，执行 `INSERT OR REPLACE`。
7. SQLite 发现 `name="工作"` 违反列级 `UNIQUE(name)`。
8. SQLite 删除本地 `{mi-B, T2}` 行，再插入远端 `{mi-A, T1}` 行。
9. 较新本地数据被较旧远端数据静默覆盖，且操作无异常，常规监控难以发现。

## 发生原因

### 1. hash_id 职责被错误扩展

`hash_id` 的定位是“同步专用标识”，不是主键，也不是业务唯一键。它为 AUTOINCREMENT 表提供跨端稳定定位能力：自增 `id` 在两端不同，不能作为同步记录标识；但两端独立创建的同一业务对象也可能产生不同 `hash_id`。

因此，LWW 判断“两行是否属于同一业务记录”时，若表存在业务 UNIQUE，必须优先使用业务 UNIQUE。`hash_id` 只能在没有业务唯一键时作为回退定位字段，不能替代 `name` 所表达的业务等价关系。

### 2. get_unique_fields 只解析表级 UNIQUE

`get_unique_fields()` 的明确实现契约是遍历 `TABLE_CONFIGS[table_name]["table_constraints"]`，解析 `UNIQUE(...)`。它不会遍历 `columns` 内的列级 `UNIQUE`。

这并非 SQLite 层差异：单列列级 `UNIQUE` 与单列表级 `UNIQUE(name)` 在 SQLite 中都会创建等价的唯一约束和自动索引。差异只存在于 Python 配置的元数据结构与解析路径。

### 3. INSERT OR REPLACE 响应所有 UNIQUE 约束

`INSERT OR REPLACE` 不知道同步层选择了哪个字段做 LWW。只要插入违反任一 UNIQUE 约束，SQLite 都会执行 REPLACE 语义。对于本表，虽然 LWW 错按 `hash_id` 查询，SQLite 仍会按 `name` 冲突并替换。

因此必须满足以下不变量：

```text
LWW 用于查找已有业务记录的键
=
INSERT OR REPLACE 实际可能触发替换的业务冲突键
```

若二者不一致，LWW 会放行本应比较时间戳的行，REPLACE 随后在更底层完成不可见替换。

### 4. Schema 声明位置违反同步层契约

`mood_impacts` 把 `UNIQUE(name)` 放在 `columns.name.constraints`，同时把 `table_constraints` 留空。DDL 功能正常，但同步层无法读取业务唯一键，于是回退 `hash_id`，形成“Python 侧判重键”和“SQLite 侧替换键”不一致。

## 最佳方案

采用最小且无数据迁移的修复：将 `UNIQUE(name)` 从列级声明移动到表级声明。

```python
MOOD_IMPACTS_CONFIG = {
    "columns": {
        "hash_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
        },
    },
    "table_constraints": ["UNIQUE(name)"],
}
```

选择该方案的原因：

1. SQLite 层列级单列 UNIQUE 与表级单列 UNIQUE 功能等价，不需要迁移已有数据。
2. `get_unique_fields()` 无需扩展列级解析逻辑，保持当前单一元数据入口。
3. 配置风格与 `user_app_behavior_log`、`timeline_custom_block`、`time_paradoxes` 一致。
4. `hash_id` 的列级 UNIQUE 保持不变，因为它是同步专用稳定标识，不是业务唯一键，不应放入 `table_constraints` 被业务键解析器优先采用。

## 修复内容

### 1. Schema 配置

修改 `MOOD_IMPACTS_CONFIG`：

- `columns.name.constraints`: `["NOT NULL", "UNIQUE"]` → `["NOT NULL"]`
- `table_constraints`: `[]` → `["UNIQUE(name)"]`
- `columns.hash_id.constraints`: 继续保持 `["NOT NULL", "UNIQUE"]`

### 2. 元数据解析测试

将原来验证回退 hash_id 的测试更新为正确业务契约：

```python
assert repository.get_unique_fields("mood_impacts") == ["name"]
```

### 3. 端到端 LWW 测试

新增两个真实写入路径测试：

- 相同 `name` + 不同 `hash_id` + 传入数据较旧：`affected == 0`，本地较新记录及其 `hash_id`、`sort_order`、`updated_at` 保持不变。
- 相同 `name` + 不同 `hash_id` + 传入数据较新：`affected == 1`，远端较新业务数据写入。

测试中的远端 `id` 被同步层剥离，断言不依赖 AUTOINCREMENT `id`，只验证业务数据与 LWW 结果。

## 验证结果

### 配置验证

```bash
python -c "from lifeprism.repository.sync_repository import SyncRepository; from lifeprism.config.database import TABLE_CONFIGS; print(TABLE_CONFIGS['mood_impacts']['table_constraints'])"
```

输出：

```text
['UNIQUE(name)']
```

### 回归测试

```bash
python -m pytest test/core/integration/repository/test_sync_repository.py::TestHashIdSyncDedup -x -v
```

结果：

```text
17 passed
```

## 教训与规则沉淀

1. **同步表的业务 UNIQUE 必须写在 `table_constraints`**：凡位于 `SYNC_TABLES` 的表，所有参与业务等价判断的 UNIQUE 约束，包括单列 UNIQUE，都必须显式写为 `UNIQUE(...)`，使 `get_unique_fields()` 可解析。
2. **hash_id 不是业务唯一键**：它是 AUTOINCREMENT 表的跨端定位补丁，不参与本地 CRUD，也不能在已有业务 UNIQUE 时替代其承担 LWW 冲突判定。
3. **LWW 查找键必须覆盖 REPLACE 冲突键**：使用 `INSERT OR REPLACE` 前，必须确保 LWW 已按会触发业务替换的唯一键找到并比较现有记录。
4. **数据库等价不等于配置等价**：列级与表级单列 UNIQUE 在 SQLite 引擎中等价，但在应用层解析器中不等价；配置格式也是代码契约的一部分。
5. **同步表尽量避免 AUTOINCREMENT**：AUTOINCREMENT 需要额外的 hash_id、生成与迁移逻辑、业务 UNIQUE 声明纪律以及删除墓碑映射，显著增加同步复杂度。新表优先使用应用层生成的 TEXT PRIMARY KEY。
6. **规则文档**：后续创建或修改同步表必须遵循 [`docs/coding-rules/sync-friendly-table-design.md`](../coding-rules/sync-friendly-table-design.md)。

## 预防措施

- 新表加入 `SYNC_TABLES` 前运行 `get_unique_fields(table_name)`，核对返回结果是否为预期业务键。
- 对每张 AUTOINCREMENT 同步表至少覆盖“相同业务键、不同 hash_id”的较旧跳过与较新写入测试。
- Code Review 检查 `columns.*.constraints` 中的 `UNIQUE`：若表参与同步且该 UNIQUE 表达业务等价，要求移动到 `table_constraints`。
- 新建同步表优先采用 TEXT PRIMARY KEY，只有历史兼容或明确性能理由时使用 AUTOINCREMENT。

## 关联问题

- 第二轮审查 Issue 2：[`docs/generated/019/2026-07-23-code-review-deletion-sync-schema-round2.md`](../generated/019/2026-07-23-code-review-deletion-sync-schema-round2.md)
- 原始审查 Issue 1：[`docs/generated/019/2026-07-22-code-review-deletion-sync-schema.md`](../generated/019/2026-07-22-code-review-deletion-sync-schema.md)
- hash_id 定位 ADR：[`docs/adr/2026-07-22-hash-id-sync-only-identifier.md`](../adr/2026-07-22-hash-id-sync-only-identifier.md)
- AUTOINCREMENT 表增加 hash_id ADR：[`docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md`](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md)
- 同步友好建表规则：[`docs/coding-rules/sync-friendly-table-design.md`](../coding-rules/sync-friendly-table-design.md)
