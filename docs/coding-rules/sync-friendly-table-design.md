---
version: 1.0
created_at: 2026-07-23
updated_at: 2026-07-23
last_updated: 新增同步表主键选型、AUTOINCREMENT hash_id 补丁、业务 UNIQUE 声明和接入检查规则
abstract: 面向创建或修改同步表的开发者与 AI，规定优先使用 TEXT PRIMARY KEY；AUTOINCREMENT 同步表必须注册 hash_id，并将所有业务 UNIQUE 显式放入 table_constraints，确保 LWW 查找键与 INSERT OR REPLACE 冲突键一致。
---

# 同步友好建表规则

## 触发条件

遇到以下任一场景时，必须阅读并遵循本文档：

- 创建新的数据库表
- 将现有表加入 `SYNC_TABLES`
- 修改同步表的主键、AUTOINCREMENT、UNIQUE 或时间戳约束
- 新增、删除或修改 `hash_id` 字段
- 修改 `HASH_ID_PREFIXES`
- 修改 `SyncRepository.get_unique_fields()`、LWW 或同步 upsert 行为

本文档补充 [`create-table-rules.md`](./create-table-rules.md)；后者定义通用建表与 Provider 规则，本文档专门约束跨端同步友好性。

## 核心规则

### 规则 1：同步表尽量避免使用 AUTOINCREMENT 主键

同步表优先使用应用层生成的 `TEXT PRIMARY KEY`，例如 UUID 或稳定的语义化 ID。

推荐结构：

```python
"id": {
    "type": "TEXT",
    "constraints": ["PRIMARY KEY", "NOT NULL"],
}
```

原因：

- SQLite AUTOINCREMENT `id` 只在单个数据库内稳定。
- 同一逻辑记录在两端独立创建时，自增 ID 通常不同，不能作为跨端定位标识。
- 使用 AUTOINCREMENT 的同步表需要额外引入 `hash_id`、前缀注册、生成/迁移、墓碑映射和业务唯一键约束，复杂度明显更高。
- TEXT PRIMARY KEY 由应用层生成，天然可以在 pull、push、LWW 和删除同步中保持跨端一致。

只有以下情况可以使用 AUTOINCREMENT：

1. 旧表已经存在，改主键会破坏大量本地 CRUD 调用方。
2. 有明确且经过验证的性能需求，例如高频写入的日志表。

不得仅因为 AUTOINCREMENT “写起来简单”而用于新同步表。

### 规则 2：同步表使用 AUTOINCREMENT 时必须完成全部配套

若同步表因历史或性能原因必须使用 AUTOINCREMENT，以下要求缺一不可。

#### 2.1 注册 hash_id 前缀

在 [`lifeprism/sync/constants.py`](../../lifeprism/sync/constants.py) 的 `HASH_ID_PREFIXES` 中注册前缀：

```python
HASH_ID_PREFIXES = {
    "your_table": "yt-",
}
```

前缀必须在相关表之间清晰、稳定、无歧义。修改已投入使用的前缀属于数据兼容性变更，不能直接替换。

#### 2.2 添加 hash_id 字段

在表的 `columns` 中声明：

```python
"hash_id": {
    "type": "TEXT",
    "constraints": ["NOT NULL", "UNIQUE"],
    "comment": "同步用全局唯一标识（12位 hex + 表名前缀）",
}
```

`hash_id` 的列级 UNIQUE 保持在字段定义中。它表达同步稳定标识自身必须唯一，不是业务唯一键。

#### 2.3 所有业务 UNIQUE 必须声明在 table_constraints

同步表的所有业务唯一约束必须显式写在 `table_constraints`，包括单列 UNIQUE。

正确：

```python
"name": {
    "type": "TEXT",
    "constraints": ["NOT NULL"],
},
"table_constraints": ["UNIQUE(name)"],
```

错误：

```python
"name": {
    "type": "TEXT",
    "constraints": ["NOT NULL", "UNIQUE"],
},
"table_constraints": [],
```

复合业务唯一键同样放入 `table_constraints`：

```python
"table_constraints": ["UNIQUE(app, start_time)"]
```

原因：

- LWW 冲突判定通过 [`SyncRepository.get_unique_fields()`](../../lifeprism/repository/sync_repository.py) 解析 `table_constraints`。
- 当前解析器不读取 `columns.<column>.constraints` 中的列级 UNIQUE。
- 最终写入使用 `INSERT OR REPLACE`，SQLite 会响应所有 UNIQUE 约束，不区分 Python 同步层是否解析到了该约束。
- 如果 REPLACE 按业务列发生冲突，而 LWW 按 `hash_id` 或其他字段判重，LWW 会漏掉等价记录，较旧数据可能被放行并静默替换较新数据。

因此必须保持以下不变量：

```text
LWW 查找的业务唯一键 = INSERT OR REPLACE 会触发业务替换的唯一键
```

单列 UNIQUE 与单列表级 `UNIQUE(column)` 在 SQLite 中功能等价，但在项目的 Python 配置解析器中并不等价。同步表必须选择后者。

历史案例见 [`mood_impacts` LWW 绕过 Bug](../history-bugs/2026-07-23-mood-impacts-lww-bypass-by-column-level-unique.md)。

### 规则 3：hash_id 是同步专用标识，不是主键

`hash_id` 的定位遵循 ADR [`2026-07-22-hash-id-sync-only-identifier.md`](../adr/2026-07-22-hash-id-sync-only-identifier.md)：

- 它是 AUTOINCREMENT 表的跨端定位补丁。
- 它不是主键，Provider 的 `_PRIMARY_KEY` 仍保持本地自增 `id`。
- 本地 `get_by_id`、update、delete 等 CRUD 继续使用自增 `id`。
- 同步 pull/push 和删除墓碑可使用 `hash_id` 定位逻辑记录。
- 当表存在业务 UNIQUE 时，LWW 冲突判定必须使用业务 UNIQUE，不得用 `hash_id` 替代。
- 只有表不存在业务 UNIQUE 时，`get_unique_fields()` 才可回退到 `hash_id`。

不要因为字段名包含 `id` 就把它当作本地实体主键，也不要把 `hash_id` 放入 `table_constraints` 伪装成业务唯一键。

### 规则 4：新加入 SYNC_TABLES 的表检查清单

将新表加入 `SYNC_TABLES` 前，逐项确认：

- [ ] 主键是否为 `TEXT PRIMARY KEY`？这是推荐方案。
- [ ] 如果使用 `INTEGER PRIMARY KEY AUTOINCREMENT`，是否已在 `HASH_ID_PREFIXES` 注册前缀？
- [ ] AUTOINCREMENT 同步表是否有 `hash_id TEXT NOT NULL UNIQUE`？
- [ ] 所有业务 UNIQUE 是否全部显式声明在 `table_constraints`？
- [ ] 单列业务 UNIQUE 是否也从列级移动到了 `table_constraints`？
- [ ] 是否配置了 `update_at: True`，使 LWW 可以比较 `updated_at`？
- [ ] 是否配置了 `timestamps: True`，保证 `created_at`、`updated_at` 字段完整？
- [ ] 所有写入路径是否都会生成有效且非空的 `hash_id`？不要只检查 `_generic_insert`，还要检查手写 INSERT、批量 INSERT 和初始化数据。
- [ ] `get_unique_fields(table_name)` 返回的字段是否正是预期的业务唯一键？
- [ ] 是否有端到端 LWW 测试覆盖“相同业务键、不同 hash_id、传入较旧”和“传入较新”两个方向？
- [ ] 删除同步使用的记录标识是否明确：AUTOINCREMENT 表用 `hash_id`，TEXT PK 表用主键？

配置完成后可运行：

```bash
python -c "from lifeprism.repository.sync_repository import SyncRepository; print(SyncRepository().get_unique_fields('your_table'))"
```

如果项目当前构造 `SyncRepository` 需要注入数据库实例，可在对应集成测试 fixture 中调用同一公共方法。验证目标不是命令形式本身，而是确认返回值为预期业务唯一键。

对于 `mood_impacts`，验证命令为：

```bash
python -c "from lifeprism.repository.sync_repository import SyncRepository; from lifeprism.config.database import TABLE_CONFIGS; print(TABLE_CONFIGS['mood_impacts']['table_constraints'])"
```

预期输出：

```text
['UNIQUE(name)']
```

## 常见陷阱

### 陷阱 1：认为列级 UNIQUE 与表级 UNIQUE 完全等价

在 SQLite 引擎中，下面两种声明对单列唯一性约束功能等价：

```sql
name TEXT UNIQUE
```

```sql
name TEXT,
UNIQUE(name)
```

但项目中的 `get_unique_fields()` 只解析 `table_constraints`，因此应用层行为不等价。

真实案例：`mood_impacts` 曾把 `UNIQUE(name)` 写在列级。LWW 读不到 `name`，回退到 `hash_id`；两端同名记录的 hash_id 不同时，LWW 查不到本地记录并放行较旧数据；随后 `INSERT OR REPLACE` 仍按 SQLite 的 `UNIQUE(name)` 删除较新本地行并插入较旧远端行。

修复不是迁移数据，而是把 Python 配置声明移动到：

```python
"table_constraints": ["UNIQUE(name)"]
```

### 陷阱 2：把 hash_id 当成业务唯一键

两端独立创建同一业务对象时，可能生成不同 hash_id。业务唯一键表达的是“业务上是否为同一条记录”，例如：

- `mood_impacts`: `name`
- `timeline_custom_block`: `start_time`
- `user_app_behavior_log`: `(app, start_time)`
- `time_paradoxes`: `(user_id, mode, version)`

这些字段与 hash_id 职责不同，不可互相替代。

### 陷阱 3：只给 schema 加 hash_id，不检查所有 INSERT 路径

`hash_id TEXT NOT NULL UNIQUE` 会影响所有写入入口，包括：

- 通用 `_generic_insert`
- Provider 手写 INSERT
- 批量 INSERT / INSERT OR IGNORE
- 默认数据初始化
- 数据迁移和恢复脚本

加入 hash_id 后必须审计所有路径，否则新库可能因 NOT NULL 失败，旧迁移库可能产生 NULL 或无效标识。

### 陷阱 4：只测试相同 hash_id

只测试“相同 hash_id + 不同 updated_at”无法发现业务 UNIQUE 与 REPLACE 键不一致。AUTOINCREMENT 同步表必须测试：

1. 相同业务唯一键。
2. 不同 hash_id。
3. 传入数据较旧时跳过。
4. 传入数据较新时写入。

## 推荐配置示例

```python
YOUR_TABLE_CONFIG = {
    "table_name": "your_table",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
        },
        "hash_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
        },
        "business_key": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
        },
    },
    "table_constraints": ["UNIQUE(business_key)"],
    "timestamps": True,
    "update_at": True,
}
```

同时在 `HASH_ID_PREFIXES` 注册前缀，并为 LWW 的旧数据跳过、新数据写入添加端到端测试。

## 关联文档

- ADR：[`docs/adr/2026-07-22-hash-id-sync-only-identifier.md`](../adr/2026-07-22-hash-id-sync-only-identifier.md)
- ADR：[`docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md`](../adr/2026-07-22-add-hash-id-to-autoincrement-tables.md)
- Bug：[`docs/history-bugs/2026-07-23-mood-impacts-lww-bypass-by-column-level-unique.md`](../history-bugs/2026-07-23-mood-impacts-lww-bypass-by-column-level-unique.md)
- 通用建表规则：[`docs/coding-rules/create-table-rules.md`](./create-table-rules.md)
- 数据同步 Spec：[`docs/specs/2026-07-16-data-sync-core-spec.md`](../specs/2026-07-16-data-sync-core-spec.md)
