# B2: Repository 基础层 + 迁移脚本 审查报告

## 审查概要
- 审查文件: 7
- 审查标准: time-handling-rules.md Section 2, 3.1-3.5
- 审查日期: 2026-07-12

| # | 文件 | 变更类型 | 行数变更 |
|---|------|---------|---------|
| 1 | `lifeprism/repository/base_providers/lw_base_data_provider.py` | 修改 | ~90 lines |
| 2 | `lifeprism/repository/base_providers/aw_base_data_provider.py` | 修改 | ~5 lines |
| 3 | `lifeprism/repository/database_manager.py` | 修改 | ~64 lines |
| 4 | `lifeprism/repository/lw_table_manager.py` | 修改 | ~6 lines |
| 5 | `lifeprism/repository/migrations/migration_runner.py` | 修改 | ~3 lines |
| 6 | `lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py` | 新增 | 160 lines |
| 7 | `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py` | 新增 | 393 lines |

---

## 1. 规则遵守程度

### 1.1 lw_base_data_provider.py -- 符合规则

**规则 Section 3.1 (时间生成) -- 完全符合**

所有时间戳生成改为 `get_utc_now_iso()`（内部调用 `datetime.now(timezone.utc).isoformat()`），符合 "所有时间戳必须生成 UTC aware datetime" 要求。旧代码 `datetime.now().isoformat()`（naive local time）已全部替换。

关键变更点：

- **`_generic_insert`，行 1157-1163**：
  ```python
  from lifeprism.utils.time_utils import get_utc_now_iso
  now_iso = get_utc_now_iso()
  if "created_at" not in data:
      data["created_at"] = now_iso
  if self._TABLE_NAME in self._TABLES_WITH_UPDATE_AT and "updated_at" not in data:
      data["updated_at"] = now_iso
  ```
  自动注入 ISO 8601 + UTC 格式的时间戳，不依赖数据库 DEFAULT 的 `YYYY-MM-DD HH:MM:SS` 格式。

- **`_generic_update`，行 1241-1244**：
  ```python
  # 旧: data["updated_at"] = datetime.now().isoformat()
  # 新: data["updated_at"] = get_utc_now_iso()
  ```
  正确从本地 naive → UTC aware + ISO 8601。

- **`_save_map_data_upsert`，行 610-620**：
  正确注入 `created_at` + `updated_at` 到 `single_purpose_map_cache` 和 `multi_purpose_map_cache`。

- **`_save_user_app_behavior_events`，行 792-808**：
  正确注入 `created_at` + `updated_at`，与 `user_app_behavior_log` 表配置 (`timestamps=True, update_at=True`) 一致。

- **`_save_token_usage_batch`，行 869-874**：
  正确注入 `created_at`（`tokens_usage_log` 没有 `updated_at` 配置）。

- **`save_session_tokens_usage`，行 975-978**：
  INSERT 路径正确注入 `created_at`；UPDATE 路径不写 `updated_at`（因为 `tokens_usage_log` 无 `update_at`）。符合字段分类。

**规则 Section 3.2 (序列化) -- 完全符合**

全部使用 `get_utc_now_iso()` 返回 `.isoformat()` 格式。

**规则 Section 2 (字段分类) -- 完全符合**

`_TABLES_WITH_TIMESTAMPS` 和 `_TABLES_WITH_UPDATE_AT` 缓存正确区分两类表配置。

### 1.2 aw_base_data_provider.py -- 符合规则

行 44：`LOCAL_TIMEZONE` 硬编码常量 → `get_user_timezone()` 动态获取。符合 Section 3.1 规则 "统一通过配置动态获取，禁止硬编码时区字符串"。

### 1.3 database_manager.py -- 符合规则，有一处可改进

**符合点：**
- `insert_on_conflict`（行 380-411）和 `insert_many_on_conflict`（行 453-483）新增参数化 `updated_at` 绑定：
  ```python
  need_update_at = config.get("timestamps") and (
      table_name == "single_purpose_map_cache" or table_name == "multi_purpose_map_cache"
  )
  if need_update_at:
      exclude_cols.update({"created_at", "updated_at"})  # created_at 不被 UPDATE 覆盖
      update_str += ", updated_at = ?"
      params.append(now_iso)  # 参数化绑定，非内联拼接
  ```
  正确排除 `created_at` 防止 UPSERT 覆盖初始创建时间；使用参数化绑定避免 SQL 注入风险。

- 模块顶部 `from lifeprism.utils.time_utils import get_utc_now_iso`，使用统一时间工具。

**可改进（详见 2.4）：**
`need_update_at` 条件硬编码表名，应改为通用配置驱动。

### 1.4 lw_table_manager.py -- 符合 Section 3.4

行 79-84，DEFAULT 子句变更：
```python
# 旧: DEFAULT (datetime('now', 'localtime'))
# 新: DEFAULT (datetime('now'))  # SQLite 返回 UTC
```
完全符合 Section 3.4 "所有表 DEFAULT 使用 datetime('now')（SQLite 返回 UTC），禁止 datetime('now', 'localtime')"。

注意：`datetime('now')` 输出格式为 `YYYY-MM-DD HH:MM:SS`（无 T 分隔符、无时区标识、无微秒），但应用层 `_generic_insert` 会覆盖为完整 ISO 8601 格式，因此 DEFAULT 仅作为未指定列时的安全网。

### 1.5 migration_runner.py -- 符合规则

行 78：备份文件名时间戳改为 UTC：
```python
# 旧: datetime.now().strftime("%Y%m%d%H%M%S")
# 新: datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
```
正确从本地 naive → UTC aware。

### 1.6 m008_migrate_to_utc.py -- 符合规则，文档有小问题

**符合 Section 3.4：** 所有 `datetime('now', 'localtime')` DEFAULT 子句改为 `datetime('now')`。

**表重建模式正确实现：**
1. 获取原始 CREATE SQL + 索引
2. 替换 DEFAULT 子句
3. 用正则表达式替换表名创建临时表（支持双引号/单引号/反引号）
4. 复制数据 + 删除旧表 + 重命名 + 重建索引

**边界情况处理：**
- 跳过空名表/空白表名（行 86-88，Bug #3 修复）
- 支持带引号的 CREATE TABLE 表名（Bug #4 修复）

**幂等性：** `check_if_applied` 检查所有 CREATE 语句中无 `datetime('now', 'localtime')` 残留。

**文档问题（详见 2.2）：** "3 张使用 CURRENT_TIMESTAMP 的旧表（todo_list、timeline_custom_block）已经是 UTC，无需处理" 不准确--这两个表由 `lw_table_manager.py` 创建，DEFAULT 是 `datetime('now', 'localtime')`，不是 `CURRENT_TIMESTAMP`。不过 m008 通过实际检查 `sqlite_master` 中的 CREATE 语句来决定是否迁移，不依赖文档描述，因此功能正确。

### 1.7 m009_migrate_history_to_utc.py -- 基本符合规则，有一处严重问题

**符合点：**

1. 正确排除日期字段（`date`, `start_date`, `end_date` 等 YYYY-MM-DD 格式）、时间字段（`time`, `trigger_time` HH:MM 格式）、整数字段（`year`, `month`, `week_num`）、内部元数据（`schema_version.applied_at`）。符合 Section 2 字段分类。

2. NULL 和空字符串安全跳过：
   ```python
   WHERE "field" IS NOT NULL AND "field" != ''
   ```

3. 含 PRIMARY KEY/UNIQUE/CHECK 约束的表使用表重建模式（Bug #1/#2 修复），避免逐行更新时的值冲突。

4. SQL 转换逻辑正确：
   ```python
   strftime('%Y-%m-%dT%H:%M:%S', datetime("field", '-8 hours')) || '+00:00'
   ```
   `datetime()` 做时区偏移（UTC+8 → UTC），`strftime()` 格式化为 ISO-like 格式，`|| '+00:00'` 补时区标识。

5. 幂等性由 `schema_version` 表保证。

**严重问题（详见 2.1）：** `strftime()` 不产生微秒 -- 迁移后数据格式与 `get_utc_now_iso()` 产生的新数据格式不一致。

**文档问题（详见 2.2）：** 排除字段说明与 `_MIGRATION_FIELDS` 实际内容冲突--docstring 说排除 `todo_list.created_at`, `timeline_custom_block.created_at`, `timeline_custom_block.updated_at`，但代码包含它们（commit `27a2e04` 修复添加，docstring 未更新）。

---

## 2. 潜在 Bug

### 2.1 m009: strftime() 丢弃微秒 -- 格式不一致（严重性：高）

**位置：** `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py`

- 逐字段迁移 SQL，行 246-251:
  ```python
  sql = (
      f'UPDATE "{table_name}" '
      f"SET \"{field_name}\" = strftime('%Y-%m-%dT%H:%M:%S', datetime(\"{field_name}\", ?)) || '+00:00' "
      f'WHERE "{field_name}" IS NOT NULL AND "{field_name}" != ?'
  )
  ```
- 表重建模式 SQL，行 360-364:
  ```python
  select_cols.append(
      f'CASE WHEN "{col}" IS NOT NULL AND "{col}" != ? '
      f"THEN strftime('%Y-%m-%dT%H:%M:%S', datetime(\"{col}\", ?)) || '+00:00' "
      f'ELSE "{col}" END AS "{col}"'
  )
  ```

**问题：** SQLite `strftime()` 不支持微秒（`%f` 在 SQLite 中不存在）。迁移后数据格式为：
```
2026-07-11T16:29:54+00:00          (迁移数据，无微秒)
```

而新数据（通过 `get_utc_now_iso()` = `datetime.now(timezone.utc).isoformat()`）格式为：
```
2026-07-11T16:29:54.123456+00:00   (新数据，有微秒)
```

**影响：**

1. **违反 Section 3.2**："统一格式为 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`" -- 迁移数据缺少 `.ffffff` 部分。

2. **违反 Section 6**："LWW 冲突解决依赖字符串比较，**格式和时区必须完全一致**" -- 迁移数据和新增数据格式不同。虽然字符串比较在大多数情况下仍然正确（因为两个格式的日期时间部分完全相同，只有末尾的微秒部分差异），但存在边缘情况：
   - `2026-07-11T16:29:54+00:00` vs `2026-07-11T16:29:54.000000+00:00` 在 ASCII 排序中：`+` (0x2B) < `.` (0x2E)，所以迁移数据会被排在新数据前面。但这仅当两者恰好在同一秒时发生，实际影响很小。

3. **前端解析：** 两种格式都是有效的 ISO 8601，`new Date()` 都能正确解析。不是阻塞性问题。

**建议：** 评估实际影响。如果 LWW 冲突解决不受影响（实际场景中 updated_at 精准到秒已足够），可接受此不一致。或在文档中记录此已知限制。SQLite 无原生微秒支持，需借助应用层后处理才能统一格式。

### 2.2 m008/m009: docstring 与代码不一致（严重性：中）

**m009 排除字段说明过时，行 8-12：**
```
排除的字段：
1. 3 张旧表的 created_at/updated_at（已经是 UTC）：
   - todo_list.created_at
   - timeline_custom_block.created_at
   - timeline_custom_block.updated_at
```
但 `_MIGRATION_FIELDS`（行 74-75, 88-89）实际包含这些字段：
```python
("todo_list", "created_at"),
("todo_list", "updated_at"),
...
("timeline_custom_block", "created_at"),
("timeline_custom_block", "updated_at"),
```

**根因分析：** Commit `27a2e04` 修复了代码（将这些字段加入 `_MIGRATION_FIELDS`），但忽略了 docstring 更新。这些表的实际 DEFAULT 是 `datetime('now', 'localtime')`（通过 `lw_table_manager.py` 生成），不是 `CURRENT_TIMESTAMP`，因此数据是本地时间，确实需要迁移。代码正确，docstring 错误。

**m008 docstring 不准确，行 17：**
> 3 张使用 CURRENT_TIMESTAMP 的旧表（todo_list、timeline_custom_block）已经是 UTC，无需处理

实际上 `todo_list` 和 `timeline_custom_block` 由 `lw_table_manager.py` 创建，使用 `datetime('now', 'localtime')` 作为 DEFAULT，不是 `CURRENT_TIMESTAMP`。m008 的 `upgrade()` 通过检查实际 CREATE 语句中的 DEFAULT 文本来决定是否迁移（`_OLD_DEFAULT in create_sql`），因此功能不受影响，但文档描述有误导性。

**建议：** 更新 m009 docstring，移除过时的排除说明；更新 m008 docstring，修正 DEFAULT 描述。

### 2.3 m009: UTC+8 硬编码假设，无回滚路径（严重性：低）

**位置：** `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py`，行 41

```python
_TIMEZONE_OFFSET = "-8 hours"
```

**问题：** 假设所有历史数据都是 UTC+8（北京时间）。这一假设：
- 在 docstring 行 3 有文档说明："假设所有历史数据都是 UTC+8（北京时间）"
- 对于中国用户群合理
- 但对于非 UTC+8 时区的用户（或未来国际化场景），会错误转换数据
- **迁移不可回滚**：减 8 小时的逆操作是加 8 小时，但无法区分"原本就是 UTC+8"和"被误转换的 UTC+X"数据

**当前影响：** 如果用户群全部在 UTC+8 时区，无实际问题。是一个已知的架构限制。

**建议：** 在 `docs/known-limitations/` 中记录此限制；若未来支持多时区，需提供时区来源元数据。

### 2.4 database_manager.py: need_update_at 硬编码表名（严重性：低）

**位置：** `lifeprism/repository/database_manager.py`，行 380-382 和 453-455

```python
need_update_at = config.get("timestamps") and (
    table_name == "single_purpose_map_cache" or table_name == "multi_purpose_map_cache"
)
```

**问题：** `updated_at` 自动更新逻辑通过硬编码表名而非配置驱动来限定范围。如果未来其他表（也配置了 `timestamps=True, update_at=True`）通过 `insert_many_on_conflict` 写入，它们的 `updated_at` 不会被自动更新。

**当前影响：** 当前只有这两个 map cache 表使用 `insert_many_on_conflict`，无实际 bug。

**建议：** 改为 `config.get("update_at")` 驱动：
```python
need_update_at = config.get("timestamps") and config.get("update_at")
```
这样对所有使用 UPSERT 方法的表都生效。

---

## 3. 功能缺失风险

### 3.1 _generic_insert 行为变更对现有调用方的影响

**变更：** `_generic_insert` (行 1150-1163) 新增自动注入 `created_at`/`updated_at`。

**分析：**
- 旧行为：依赖数据库 DEFAULT 写入时间，对调用方透明
- 新行为：Python 层主动注入 ISO 8601 格式的 UTC 时间

**风险场景：**
- 如果某个调用方**显式传入**了 `created_at` 或 `updated_at` 字段值，`_generic_insert` 不会覆盖（`if "created_at" not in data` 守卫）。不会产生问题。
- 如果某个调用方**依赖**数据库 DEFAULT 的格式（`YYYY-MM-DD HH:MM:SS`），读取时可能期望该格式。现在改为 ISO 8601，需确认所有读取路径都能正确解析。由于 `datetime.fromisoformat()` 和前端 `new Date()` 都支持 ISO 8601，风险较低。

**评估：无实际功能缺失风险。**

### 3.2 m009 迁移是否遗漏字段

检查 `_MIGRATION_FIELDS` 与 `TABLE_CONFIGS` 的覆盖度：

| 表配置 | timestamps | update_at | _MIGRATION_FIELDS 中字段 | 状态 |
|--------|-----------|-----------|-------------------------|------|
| category_map_cache | True | True | created_at, updated_at | OK |
| single/multi_purpose_map_cache | True | True | created_at, updated_at | OK |
| user_app_behavior_log | True | True | created_at, updated_at (+ start_time, end_time) | OK |
| category | True | True | created_at, updated_at | OK |
| sub_category | True | True | created_at, updated_at | OK |
| tokens_usage_log | True | - | created_at | OK |
| todo_list | True | True | created_at, updated_at | OK |
| daily_focus | True | True | created_at, updated_at | OK |
| weekly_focus | True | True | created_at, updated_at | OK |
| goal | True | True | created_at, updated_at (+ time_invested_updated_at) | OK |
| goal_journal | True | True | created_at, updated_at | OK |
| plan_doc | True | True | created_at, updated_at | OK |
| chat_session | True | True | created_at, updated_at | OK |
| timeline_custom_block | True | True | created_at, updated_at (+ start_time, end_time) | OK |
| goal_stats | True | - | created_at | OK |
| daily_report | True | True | created_at, updated_at | OK |
| weekly_report | True | True | created_at, updated_at | OK |
| monthly_report | True | True | created_at, updated_at | OK |
| time_paradoxes | True | True | created_at, updated_at | OK |
| diary | True | True | created_at, updated_at | OK |
| mood_types | True | False | created_at | OK |
| mood_entries | True | True | created_at, updated_at | OK |
| mood_impacts | True | False | created_at | OK |
| user_values | True | True | created_at, updated_at | OK |
| commitments | True | True | created_at, updated_at | OK |
| habits | True | True | created_at, updated_at (+ paused_at) | OK |
| habit_challenges | True | True | created_at, updated_at (+ finished_at) | OK |
| habit_checkins | True | False | created_at (+ completed_at) | OK |
| habit_chains | True | True | created_at, updated_at | OK |
| habit_chain_nodes | True | True | created_at, updated_at | OK |
| screen_captures | True | False | created_at (+ captured_at) | OK |
| window_events | True | False | created_at (+ timestamp) | OK |
| raw_behavior_analysis | True | False | created_at (+ start_time, end_time) | OK |
| behavior_analysis | True | True | created_at, updated_at (+ start_time, end_time) | OK |
| custom_record_types | True | True | created_at, updated_at | OK |
| custom_record_fields | True | False | created_at | OK |

**评估：无遗漏。所有 `timestamps=True` 的表及其对应字段均在 `_MIGRATION_FIELDS` 中。**

### 3.3 schema_version.applied_at 排除是否正确

m009 行 58 注释说明排除了 `schema_version.applied_at`：
```python
# - schema_version.applied_at（内部元数据）
```

分析：`schema_version.applied_at` 记录迁移执行时间。如果执行迁移的环境是 UTC+8，DEFAULT `datetime('now', 'localtime')` 会写入本地时间。但该字段不参与业务逻辑（不显示给用户、不参与 LWW 同步、不影响数据查询），排除它是合理的。

**评估：正确排除，无功能缺失。**

---

## 4. 安全隐患

### 4.1 迁移不可回滚

m008（表结构重建）和 m009（历史数据减 8 小时）都是**单向迁移**，没有提供回滚（downgrade）函数。

- **m008：** 可以通过再次重建表恢复 `datetime('now', 'localtime')`，但会丢失后续写入的 UTC 数据
- **m009：** 时间转换不可逆。减 8 小时后无法区分"原始就是 UTC+8"和"原始是 UTC+0"，加 8 小时也无法恢复原始值

**缓解措施：** `migration_runner.py` 在每次迁移前自动备份数据库文件（行 78），备份文件名包含迁移版本号和 UTC 时间戳。手动恢复可用。

**建议：** 在 `docs/adr/` 或迁移脚本注释中说明回滚方案。

### 4.2 迁移事务安全性

migration_runner 在事务内执行迁移（由 migration_runner 保证），迁移失败时自动回滚。`check_if_applied` 提供幂等性保护。无安全隐患。

### 4.3 SQL 注入风险检查

- `_generic_insert` (行 1165-1166): 使用参数化查询 `placeholders = ",".join(["?"] * len(columns))`，无 SQL 注入风险
- `_generic_update` (行 1247-1248): 使用参数化查询 `set_clause = ", ".join([f"{key} = ?" for key in data])`，列名来自 `data` dict keys（由调用方控制），参数值使用 `?` 占位符。列名虽非参数化，但来自内部代码而非用户输入，接受风险。
- m008/m009: 使用 f-string 拼接表名和列名，但值来自 `sqlite_master`（m008）和硬编码常量 `_MIGRATION_FIELDS`（m009），不接受外部输入。其他参数使用 `?` 占位符。无 SQL 注入风险。
- database_manager.py: 全部参数化绑定（`cursor.execute(sql, params)`）。

**评估：无 SQL 注入安全隐患。**

---

## 5. 其他发现

### 5.1 不一致的时间戳注入模式

不同方法使用不同的时间戳注入方式：

| 方法 | 模式 | 位置（行） |
|------|------|-----------|
| `_save_map_data_upsert` | `record.setdefault("created_at", now_iso)` | 616-620 |
| `_save_token_usage_batch` | `if "created_at" not in data: data["created_at"] = now_iso` | 873-874 |
| `_generic_insert` | `if "created_at" not in data: data["created_at"] = now_iso` | 1160-1161 |
| `save_session_tokens_usage` | `if "created_at" not in data: data["created_at"] = get_utc_now_iso()` | 977-978 |

功能等价（`.setdefault` 和 `if key not in dict` 在 key 不存在时行为一致），但风格不统一。建议统一为 `data.setdefault("created_at", now_iso)`。

### 5.2 m008 check_if_applied 空数据库边缘情况

**位置：** `m008_migrate_to_utc.py`，行 41-43

```python
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
return all(
    not (create_sql and _OLD_DEFAULT in create_sql) for (create_sql,) in cursor.fetchall()
)
```

当数据库完全为空（无任何表）时，`all()` 作用于空序列返回 `True`，表示迁移已应用。虽然功能正确（空数据库不需要迁移），但逻辑上 "没有待迁移表" 和 "迁移已应用" 语义不同。建议显式处理：
```python
create_sqls = [row[0] for row in cursor.fetchall()]
if not create_sqls:
    return True  # 空数据库，视为已迁移
return all(not (_OLD_DEFAULT in sql) for sql in create_sqls if sql)
```

### 5.3 lw_table_manager docstring 未更新

**位置：** `lw_base_data_provider.py`，行 35

```python
# 旧: - datetime('now','localtime') - SQLite 日期时间函数
# 新: - datetime('now') - SQLite 日期时间函数（返回 UTC 时间）
```

已正确更新。确认无遗漏。

---

## 总结

| 维度 | 评级 | 说明 |
|------|------|------|
| 规则遵守程度 | 良好 | 完整遵循 Section 2-3.5 规则；`_generic_insert`/`_generic_update` 正确注入 ISO 8601 + UTC 时间戳；DEFAULT 全部改为 `datetime('now')` |
| 潜在 Bug | 1 个中等问题 | m009 `strftime()` 丢弃微秒导致迁移数据与新数据格式不一致（违反 Section 3.2/6.1）；m008/m009 docstring 与代码不一致 |
| 功能缺失 | 无 | 迁移覆盖所有表；字段分类正确；无遗漏 |
| 安全隐患 | 低 | 迁移不可回滚但有备份机制；无 SQL 注入风险；UTC+8 硬编码有文档说明 |

**核心风险：** m009 迁移后时间格式 `YYYY-MM-DDTHH:MM:SS+00:00`（无微秒）与 `get_utc_now_iso()` 产生的 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`（有微秒）不一致。在极端情况下可能影响 LWW 同步（同一秒内的事件排序），但对大多数实际场景无明显影响。

**建议优先修复：**
1. 更新 m009 docstring，移除过时的"排除字段"说明（`todo_list.created_at` 等）
2. 评估 m009 微秒丢失的实际影响，在 `docs/known-limitations/` 记录
3. database_manager.py 的 `need_update_at` 改为配置驱动
