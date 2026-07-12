# API 创建数据时间格式审查报告

> **审查日期**: 2026-07-12
> **审查范围**: LifeWatch-AI 项目 API 创建数据时时间字段格式不符合 PRD 要求的问题
> **审查类型**: 纯研究任务（未修改任何代码）
> **关联 Issue**: #20 — UTC 时区迁移验证发现 24 个时间字段中仅 3 个格式正确

---

## 一、问题根因分析

### 1.1 核心结论

**21 个字段使用错误格式的根本原因是：provider 层的 `_generic_insert` 方法在 INSERT 时不设置 `created_at`/`updated_at` 字段，完全依赖数据库 DEFAULT `datetime('now')`，而该 DEFAULT 输出的是 SQLite 原生格式 `YYYY-MM-DD HH:MM:SS`（无 T 分隔符、无时区标识），不符合 PRD 要求的 ISO 8601 + UTC 格式。**

### 1.2 根因链条

```
API 创建请求
  → service 层 create_xxx() 调用 provider
    → provider 层 _generic_insert(data)
      → data 字典中【不包含】created_at / updated_at
        → INSERT SQL 不含这两列
          → 数据库 DEFAULT datetime('now') 生效
            → 输出 "2026-07-12T08:30:00" 的 SQLite 格式 "2026-07-12 08:30:00"
              → ❌ 无 T 分隔符、无时区标识
```

### 1.3 对比：UPDATE 路径是正确的

`_generic_update` 方法（`lw_base_data_provider.py` 第 1177-1184 行）**会**手动设置 `updated_at`：

```python
# lw_base_data_provider.py:1181-1184
if self._TABLE_NAME in self._TABLES_WITH_UPDATE_AT and "updated_at" not in data:
    from datetime import datetime, timezone
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
```

这解释了为什么 **UPDATE 后** `updated_at` 字段格式正确，但 **INSERT 时** `created_at` 和 `updated_at` 格式错误。

---

## 二、数据库 DEFAULT 问题分析

### 2.1 m008 迁移做了什么

文件：`lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py`

- **第 27-29 行**：定义替换规则
  - 旧：`datetime('now', 'localtime')`（本地时间）
  - 新：`datetime('now')`（UTC 时间）
- **第 45-82 行**：通过表重建模式，将所有表的 DEFAULT 从 `localtime` 改为 UTC

**m008 只修改了时区（localtime → UTC），没有修改输出格式。**

### 2.2 `datetime('now')` 的输出格式

SQLite 的 `datetime('now')` 函数输出格式为：`YYYY-MM-DD HH:MM:SS`

- 示例：`2026-07-12 08:30:45`
- **无 T 分隔符**（用空格分隔日期和时间）
- **无时区标识**（不包含 `+00:00` 或 `Z`）

这是 SQLite 的固定行为，无法通过参数改变。

### 2.3 lw_table_manager.py 的 DEFAULT 定义

文件：`lifeprism/repository/lw_table_manager.py`

**第 79-83 行**（关键代码）：

```python
# 2. 添加时间戳列（SQLite datetime('now') 返回 UTC 时间）
if timestamps:
    column_definitions.append("created_at TIMESTAMP DEFAULT (datetime('now'))")
    if update_at:
        column_definitions.append("updated_at TIMESTAMP DEFAULT (datetime('now'))")
```

所有通过 `timestamps: True` 配置自动添加时间戳的表，其 DEFAULT 都是 `datetime('now')`，输出 `YYYY-MM-DD HH:MM:SS` 格式。

### 2.4 PRD 要求的格式

PRD 要求：`YYYY-MM-DDTHH:MM:SS+00:00`（含 T 分隔符和时区标识）

即 Python `datetime.now(timezone.utc).isoformat()` 的输出，例如：`2026-07-12T08:30:45.123456+00:00`

### 2.5 结论

**`datetime('now')` 的输出格式本身就是问题根因之一。** 即使 m008 已经将时区从 localtime 改为 UTC，格式仍然不符合 PRD 要求。新创建的数据会继承这个错误的格式。

---

## 三、provider 层审查结果

### 3.1 基类 `_generic_insert` — 根因所在

文件：`lifeprism/repository/base_providers/lw_base_data_provider.py`

**第 1034-1141 行** `_generic_insert` 方法：

- **第 1105-1120 行**：构建 INSERT 语句时，只使用 `data` 字典中的列
- **不会**自动添加 `created_at` / `updated_at` 到 INSERT 语句
- 完全依赖数据库 DEFAULT 来填充这两个字段

```python
# 第 1105-1108 行：columns 只来自 data 字典
columns = list(data.keys())
placeholders = ",".join(["?"] * len(columns))
values = [data[col] for col in columns]
```

**如果 provider 子类在调用 `_generic_insert` 时没有在 data 中包含 `created_at`/`updated_at`，就会触发 DB DEFAULT，输出错误格式。**

### 3.2 各出错表的 provider 审查

#### 3.2.1 GoalProvider（goal 表）

文件：`lifeprism/repository/providers/goal_providers.py`

**`create_goal` 方法（第 166-222 行）**：
- 第 181-201 行：构造 `data` 字典，包含 id、order_index、默认值
- **未设置** `created_at` / `updated_at`
- 第 208 行：调用 `self._generic_insert(data)` → 依赖 DB DEFAULT
- **结论**：`goal.created_at`、`goal.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

注：`update_time_invested` 方法（第 490 行）正确使用 `datetime.now(timezone.utc).isoformat()` 设置 `time_invested_updated_at`，但该字段不在 24 个审查字段范围内。

#### 3.2.2 HabitProvider（habits 表）

文件：`lifeprism/repository/providers/habit_providers.py`

**`create_habit` 方法（第 139-164 行）**：
- 第 150-161 行：构造 `insert_data` 字典，包含 id、name、frequency_type 等
- **未设置** `created_at` / `updated_at`
- 第 162 行：调用 `self._generic_insert(insert_data)` → 依赖 DB DEFAULT
- **结论**：`habits.created_at`、`habits.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.3 HabitChallengeProvider（habit_challenges 表）

文件：`lifeprism/repository/providers/habit_providers.py`

**`create_challenge` 方法（第 283-310 行）**：
- 第 294-307 行：构造 `insert_data` 字典
- **未设置** `created_at` / `updated_at`
- 第 308 行：调用 `self._generic_insert(insert_data)` → 依赖 DB DEFAULT
- **结论**：`habit_challenges.created_at`、`habit_challenges.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.4 HabitCheckinProvider（habit_checkins 表）

文件：`lifeprism/repository/providers/habit_providers.py`

**`create_checkin` 方法（第 546-574 行）**：
- 第 558 行：`now_str = datetime.now(timezone.utc).isoformat()` ✅ 正确生成 ISO 时间
- 第 565 行：`"completed_at": data.get("completed_at", now_str)` ✅ `completed_at` 被显式写入
- **但** `insert_data`（第 560-566 行）**不包含** `created_at`
- 第 569 行：调用 `self._generic_insert(insert_data)` → `created_at` 依赖 DB DEFAULT
- **结论**：
  - `habit_checkins.completed_at` → 格式正确 ✅（手动写入 `.isoformat()`）
  - `habit_checkins.created_at` → 格式错误 ❌（依赖 DB DEFAULT）

#### 3.2.5 CategoryProvider（category 表）

文件：`lifeprism/repository/providers/category_provider.py`

**`create_category` 方法（第 86-140 行）**：
- 第 135 行：调用 `self._generic_insert(data)` → 依赖 DB DEFAULT
- **结论**：`category.created_at`、`category.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.6 SubCategoryProvider（sub_category 表）

文件：`lifeprism/repository/providers/category_provider.py`

**`create_sub_category` 方法（第 274-328 行）**：
- 第 323 行：调用 `self._generic_insert(data)` → 依赖 DB DEFAULT
- **结论**：`sub_category.created_at`、`sub_category.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.7 DiaryProvider（diary 表）

文件：`lifeprism/repository/providers/diary_provider.py`

**`create_diary` 方法（约第 105-140 行）**：
- 第 135 行：调用 `self._generic_insert(insert_data)` → 依赖 DB DEFAULT
- **结论**：`diary.created_at`、`diary.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

**额外问题** — `update_diary` 方法（第 142-190 行）：
- **第 175 行**：`set_clauses.append("updated_at = datetime('now','localtime')")`
- **仍然使用 `datetime('now','localtime')`**，未迁移到 UTC！这是一个遗留问题，m008 迁移遗漏了代码中的 SQL 语句。

#### 3.2.8 TodoProvider（todo_list 表）

文件：`lifeprism/repository/providers/todo_provider.py`

**`create_todo` 方法（约第 220-253 行）**：
- 第 245 行：调用 `self._generic_insert(data, on_conflict=self._ON_CONFLICT)` → 依赖 DB DEFAULT
- **结论**：`todo_list.updated_at` 依赖 DB DEFAULT → 格式错误 ❌
- 注：`todo_list.created_at` 在 m009 迁移注释中标记为"已排除（CURRENT_TIMESTAMP = UTC）"，但 `CURRENT_TIMESTAMP` 同样输出 `YYYY-MM-DD HH:MM:SS` 格式。

#### 3.2.9 CustomBlockProvider（timeline_custom_block 表）

文件：`lifeprism/repository/providers/custom_block_provider.py`

**`create_custom_block` 方法（第 145-184 行）**：
- 第 174 行：调用 `self._generic_insert(data)` → `created_at` 依赖 DB DEFAULT
- **结论**：`timeline_custom_block.created_at` → 格式错误 ❌

**额外问题 1** — `start_time` / `end_time` 的 T 分隔符被主动移除：
- **第 161-164 行**（create）和**第 202-205 行**（update）：
  ```python
  if "start_time" in data and data["start_time"]:
      data["start_time"] = data["start_time"].replace("T", " ")
  if "end_time" in data and data["end_time"]:
      data["end_time"] = data["end_time"].replace("T", " ")
  ```
- 这段代码**主动将 ISO 格式的 T 分隔符替换为空格**，是反向操作！
- 即使 API 接收到正确的 ISO 格式 `2026-07-12T14:00:00`，也会被转换为 `2026-07-12 14:00:00`
- **结论**：`timeline_custom_block.start_time`、`timeline_custom_block.end_time` → 格式错误 ❌（双重问题：DB DEFAULT + 主动 T 替换）

#### 3.2.10 MoodEntryProvider（mood_entries 表）

文件：`lifeprism/repository/providers/mood_providers.py`

**`create_mood_entry` 方法（第 324-353 行）**：
- 第 340-347 行：构造 `insert_data = {"id": new_id}`，然后 `insert_data.update(data)`
- **未设置** `created_at` / `updated_at`
- 第 348 行：调用 `self._generic_insert(insert_data)` → 依赖 DB DEFAULT
- **结论**：`mood_entries.created_at`、`mood_entries.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.11 HabitChainProvider（habit_chains 表）

文件：`lifeprism/repository/providers/habit_chain_providers.py`

**`create_chain` 方法（第 78-110 行）**：
- 第 96-104 行：使用**原始 SQL** `INSERT INTO habit_chains (name, description, show_in_timeline) VALUES (?, ?, ?)`
- **不包含** `created_at` / `updated_at` → 依赖 DB DEFAULT
- **结论**：`habit_chains.created_at`、`habit_chains.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.12 chat_session 表

文件：`lifeprism/config/database.py` 第 643-667 行

- 表配置 `"timestamps": False`（第 666 行），使用自定义时间戳列
- `created_at` / `updated_at` 在 columns 中显式定义（第 653-662 行），但**无 DEFAULT**
- 数据写入主要通过 sync 同步机制（`sync_repository.py`）或 SessionManager JSON 文件
- SessionManager（`lifeprism/llm/session/manager.py` 第 28-29 行）使用 `datetime.now(timezone.utc)` 创建 datetime 对象，序列化时用 `.isoformat()`（第 207-208 行）
- 但 SQLite `chat_session` 表的数据写入路径未在 provider 层找到显式 INSERT，可能通过 sync 的 upsert_many 写入，此时如果数据中不含时间字段，则字段为 NULL 或依赖写入的数据
- **结论**：`chat_session.created_at`、`chat_session.updated_at` 格式取决于写入数据源，sync 写入时可能携带 LEGACY 格式数据 → 格式错误 ❌

#### 3.2.13 daily_focus 表

文件：`lifeprism/config/database.py` 第 445-467 行

- 表配置 `"timestamps": True, "update_at": True`（第 465-466 行）
- `focus_provider.py` 中的 daily_focus 方法全部被注释掉（第 25-95 行）
- 数据写入主要通过 sync 同步机制
- **结论**：`daily_focus.created_at`、`daily_focus.updated_at` 依赖 DB DEFAULT → 格式错误 ❌

#### 3.2.14 MapCache Providers（multi_purpose_map_cache / single_purpose_map_cache 表）

文件：`lifeprism/repository/providers/map_cache_providers.py`

**`create_multi_purpose_map_cache` 方法（第 120-158 行）**：
- 第 144 行：调用 `self._generic_insert(data)` → 依赖 DB DEFAULT
- `create_single_purpose_map_cache` 方法（第 481-519 行）同理
- **结论**：这两个表的 `created_at` / `updated_at` 依赖 DB DEFAULT → 格式错误 ❌（虽然不在 24 个审查字段中，但存在相同问题）

### 3.3 额外发现的问题

#### 问题 A：diary_provider UPDATE 仍用 localtime

文件：`lifeprism/repository/providers/diary_provider.py` **第 175 行**：

```python
set_clauses.append("updated_at = datetime('now','localtime')")
```

这是 m008 迁移遗漏的代码级问题。m008 只迁移了 DB DEFAULT，没有迁移代码中硬编码的 `datetime('now','localtime')` SQL。

#### 问题 B：custom_block_provider 主动移除 T 分隔符

文件：`lifeprism/repository/providers/custom_block_provider.py` **第 161-164 行、202-205 行**：

```python
data["start_time"] = data["start_time"].replace("T", " ")
data["end_time"] = data["end_time"].replace("T", " ")
```

这段代码将 ISO 8601 格式（带 T）反向转换为 LEGACY 格式（带空格），与 PRD 要求背道而驰。

#### 问题 C：category_service 使用 CURRENT_TIMESTAMP

文件：`lifeprism/server/services/category_service.py` **第 944、955、981、992、1061、1099、1172、1206 行**：

```sql
SET state = 0, updated_at = CURRENT_TIMESTAMP
```

SQLite 的 `CURRENT_TIMESTAMP` 同样输出 `YYYY-MM-DD HH:MM:SS` 格式（无 T、无时区），不符合 PRD 要求。

---

## 四、正确的 3 个字段对比分析

### 4.1 custom_record_types.created_at / updated_at

文件：`lifeprism/repository/aggregators/custom_record_aggregator.py`

**`create_type` 方法（第 53-191 行）**：

- **第 126 行**：`now = datetime.now(timezone.utc).isoformat()` ✅ 生成正确的 ISO 8601 + UTC 格式
- **第 133-135 行**：INSERT 语句显式包含 `created_at` 和 `updated_at`：
  ```python
  cursor.execute(
      "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
      "VALUES (?, ?, ?, ?, ?, ?)",
      (type_id, name, slug, description or "", now, now),
  )
  ```
- **不依赖 DB DEFAULT**，时间值由代码层显式写入
- **不使用 `_generic_insert`**，使用原始 SQL INSERT

**`update_type_config` 方法（第 560-623 行）**：
- **第 601 行**：`now = datetime.now(timezone.utc).isoformat()` ✅
- **第 604-605 行**：`set_clauses.append("updated_at = ?")` + `params.append(now)` ✅

**正确原因总结**：
1. 不继承 `LWBaseDataProvider`，使用独立的 `CustomRecordRepository` 类
2. 不调用 `_generic_insert`，使用原始 SQL 显式写入时间字段
3. 使用 `datetime.now(timezone.utc).isoformat()` 生成正确格式

### 4.2 habit_checkins.completed_at

文件：`lifeprism/repository/providers/habit_providers.py`

**`create_checkin` 方法（第 546-574 行）**：

- **第 558 行**：`now_str = datetime.now(timezone.utc).isoformat()` ✅
- **第 565 行**：`"completed_at": data.get("completed_at", now_str)` ✅
  - `completed_at` 被包含在 `insert_data` 字典中
  - 如果调用方未提供 `completed_at`，使用 `now_str` 作为默认值
- **第 569 行**：调用 `self._generic_insert(insert_data)` — 虽然 `_generic_insert` 不设置时间字段，但 `completed_at` 已经在 `insert_data` 中了

**正确原因总结**：
1. `completed_at` 是业务字段（非自动时间戳），在 `insert_data` 中显式设置
2. 使用 `datetime.now(timezone.utc).isoformat()` 生成正确格式
3. 通过 `data.get("completed_at", now_str)` 确保即使调用方不传值也有正确默认值

**注意**：同一个 `habit_checkins` 表的 `created_at` 字段（自动时间戳）**不在** `insert_data` 中，因此依赖 DB DEFAULT → 格式错误。这正好解释了为什么 `habit_checkins.completed_at` 正确而 `habit_checkins.created_at` 错误。

### 4.3 对比总结表

| 字段 | 正确/错误 | 实现方式 | 是否依赖 DB DEFAULT |
|------|----------|---------|-------------------|
| custom_record_types.created_at | ✅ 正确 | aggregator 层原始 SQL，手动 `.isoformat()` | 否 |
| custom_record_types.updated_at | ✅ 正确 | aggregator 层原始 SQL，手动 `.isoformat()` | 否 |
| habit_checkins.completed_at | ✅ 正确 | provider 层 insert_data 包含此字段，手动 `.isoformat()` | 否 |
| 其他 21 个字段 | ❌ 错误 | `_generic_insert` 不含时间字段 | **是** |

---

## 五、修复方案建议

### 方案 A：在 provider/service 层手动写入 `.isoformat()` 时间

**思路**：修改 `_generic_insert` 基类方法，在 INSERT 时自动设置 `created_at` / `updated_at`。

**具体实现**：
- 在 `lw_base_data_provider.py` 的 `_generic_insert` 方法中，检查表是否配置了 `timestamps: True`
- 如果是，且 data 中未包含 `created_at`，则自动添加 `data["created_at"] = get_utc_now_iso()`
- 同理处理 `updated_at`（如果 `update_at: True`）

**优点**：
1. **一处修改，全局生效** — 修改基类即可修复所有 21 个字段
2. 不依赖数据库 DEFAULT，格式由代码层完全控制
3. 与 `_generic_update` 的处理方式一致（第 1181-1184 行已有类似逻辑）
4. 不需要修改数据库表结构
5. 不需要修改每个 provider 子类

**缺点**：
1. 需要确认所有 provider 子类的 `create_xxx` 方法都通过 `_generic_insert`（部分使用原始 SQL 的需单独处理：`habit_chains` 的 `create_chain`、`habit_chain_nodes` 的 `create_node`）
2. `custom_block_provider` 的 `start_time`/`end_time` 需要单独移除 `.replace("T", " ")` 逻辑
3. `diary_provider` 的 `update_diary` 需要单独修复 `datetime('now','localtime')` 代码
4. `chat_session` 表（`timestamps: False`）需要单独处理

**影响范围**：
- `lifeprism/repository/base_providers/lw_base_data_provider.py` — 修改 `_generic_insert`
- `lifeprism/repository/providers/habit_chain_providers.py` — 修改 `create_chain`、`create_node`（使用原始 SQL）
- `lifeprism/repository/providers/custom_block_provider.py` — 移除 T 替换逻辑
- `lifeprism/repository/providers/diary_provider.py` — 修复 `update_diary` 的 localtime
- `lifeprism/server/services/category_service.py` — 修复 CURRENT_TIMESTAMP

### 方案 B：修改数据库 DEFAULT

**思路**：将数据库 DEFAULT 从 `datetime('now')` 改为能输出 ISO 8601 格式的 SQL 表达式。

**具体实现**：
修改 `lw_table_manager.py` 第 80-83 行：

```python
# 方案 B1：使用 strftime 拼接
column_definitions.append(
    "created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', datetime('now')) || '+00:00')"
)

# 方案 B2：使用 strftime 直接输出
column_definitions.append(
    "created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+00:00', datetime('now')))"
)
```

同时需要编写 m010 迁移脚本，重建所有表以更新 DEFAULT。

**优点**：
1. 数据库层一劳永逸，所有 INSERT 都能获得正确格式
2. 不需要修改 provider 层代码

**缺点**：
1. **需要重建所有表**（SQLite 不支持 ALTER 修改 DEFAULT），迁移风险高
2. **精度问题**：`strftime` 不支持微秒，而 `.isoformat()` 包含微秒（`2026-07-12T08:30:45.123456+00:00`）
3. **格式不完全一致**：DB 生成的 `2026-07-12T08:30:45+00:00` 与 Python 生成的 `2026-07-12T08:30:45.123456+00:00` 不完全相同
4. **混合格式风险**：代码层 `.isoformat()` 和 DB 层 `strftime` 产生的格式有细微差异（微秒），可能导致 LWW 比较问题
5. `diary_provider` 的 `datetime('now','localtime')` 代码仍需单独修复
6. `custom_block_provider` 的 T 替换逻辑仍需单独修复
7. `category_service` 的 `CURRENT_TIMESTAMP` 仍需单独修复

**影响范围**：
- `lifeprism/repository/lw_table_manager.py` — 修改 DEFAULT 定义
- 新增 `m010_migrate_default_to_iso.py` — 迁移脚本
- 仍需修复方案 A 中提到的代码级问题

### 方案 C：方案 A + 方案 B 组合

**思路**：以方案 A 为主（代码层强制写入），方案 B 为辅（DB DEFAULT 作为兜底）。

**优点**：
1. 代码层确保格式正确，不依赖 DB DEFAULT
2. DB DEFAULT 也使用正确格式，即使有遗漏的 INSERT 路径也能兜底
3. 格式一致性最好（都由 Python `.isoformat()` 生成）

**缺点**：
1. 修改范围最大
2. 需要迁移脚本

### 推荐方案：方案 A

**推荐理由**：
1. **最小改动、最大收益**：主要修改 `_generic_insert` 一个方法即可修复 21 个字段中的大部分
2. **与现有模式一致**：`_generic_update` 已经采用了"代码层写入 `.isoformat()`"的模式（第 1181-1184 行），`_generic_insert` 应该与之对齐
3. **格式一致性**：所有时间字段都由 Python `datetime.now(timezone.utc).isoformat()` 生成，确保格式完全一致
4. **避免迁移风险**：不需要重建数据库表
5. **已有工具函数**：`lifeprism/utils/time_utils.py` 已提供 `get_utc_now_iso()` 函数

---

## 六、受影响的文件清单

### 6.1 方案 A 需要修改的文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `lifeprism/repository/base_providers/lw_base_data_provider.py` | `_generic_insert` 方法添加 created_at/updated_at 自动写入逻辑 | **高**（核心修复） |
| `lifeprism/repository/providers/habit_chain_providers.py` | `create_chain`（第 78-110 行）、`create_node`（第 259-289 行）添加时间字段 | 高 |
| `lifeprism/repository/providers/custom_block_provider.py` | 移除第 161-164 行、202-205 行的 `.replace("T", " ")` 逻辑 | 高 |
| `lifeprism/repository/providers/diary_provider.py` | 修复第 175 行 `datetime('now','localtime')` → 使用 `.isoformat()` | 高 |
| `lifeprism/server/services/category_service.py` | 修复第 944、955、981、992、1061、1099、1172、1206 行的 `CURRENT_TIMESTAMP` | 中 |
| `lifeprism/repository/providers/map_cache_providers.py` | `batch_insert_*` 方法（第 222-280、583-641 行）确认时间字段处理 | 中 |

### 6.2 需要验证的文件（可能无需修改但需确认）

| 文件路径 | 验证内容 |
|---------|---------|
| `lifeprism/repository/providers/goal_providers.py` | 确认 `create_goal` 通过 `_generic_insert`（修复后自动生效） |
| `lifeprism/repository/providers/habit_providers.py` | 确认 `create_habit`、`create_challenge` 通过 `_generic_insert`（修复后自动生效） |
| `lifeprism/repository/providers/category_provider.py` | 确认 `create_category`、`create_sub_category` 通过 `_generic_insert`（修复后自动生效） |
| `lifeprism/repository/providers/mood_providers.py` | 确认 `create_mood_entry` 通过 `_generic_insert`（修复后自动生效） |
| `lifeprism/repository/providers/todo_provider.py` | 确认 `create_todo` 通过 `_generic_insert`（修复后自动生效） |
| `lifeprism/repository/providers/diary_provider.py` | 确认 `create_diary` 通过 `_generic_insert`（修复后自动生效） |
| `lifeprism/repository/sync_repository.py` | 确认 sync 写入时是否携带时间字段 |

### 6.3 不需要修改的文件（已正确实现）

| 文件路径 | 说明 |
|---------|------|
| `lifeprism/repository/aggregators/custom_record_aggregator.py` | 已正确使用 `.isoformat()`，无需修改 |
| `lifeprism/utils/time_utils.py` | 已提供 `get_utc_now_iso()` 工具函数，无需修改 |
| `lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py` | 已完成 DB DEFAULT 迁移（localtime → UTC），无需修改 |
| `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py` | 已完成历史数据迁移，无需修改 |

---

## 七、21 个出错字段修复路径映射

| 字段 | 修复路径 |
|------|---------|
| category.created_at / updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| sub_category.created_at / updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| goal.created_at / updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| habits.created_at / updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| diary.created_at / updated_at | 方案 A 修复 `_generic_insert`（created_at）+ 单独修复 update_diary 的 localtime |
| todo_list.updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| timeline_custom_block.start_time / end_time | 移除 `.replace("T", " ")` 逻辑 |
| timeline_custom_block.created_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| habit_checkins.created_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| habit_challenges.created_at / updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| mood_entries.created_at / updated_at | 方案 A 修复 `_generic_insert` → 自动生效 |
| chat_session.created_at / updated_at | 需确认写入路径，可能需单独处理（timestamps: False） |
| daily_focus.created_at / updated_at | 方案 A 修复 `_generic_insert` + 确认 sync 写入路径 |

---

## 八、附录：关键代码位置索引

| 代码位置 | 说明 |
|---------|------|
| `lw_table_manager.py:79-83` | DB DEFAULT 定义：`datetime('now')` |
| `lw_base_data_provider.py:1034-1141` | `_generic_insert` 方法（不设置时间字段） |
| `lw_base_data_provider.py:1177-1184` | `_generic_update` 方法（正确使用 `.isoformat()`） |
| `m008_migrate_to_utc.py:27-29` | m008 迁移：localtime → UTC（仅改时区，未改格式） |
| `custom_record_aggregator.py:126-136` | 正确示例：手动 `datetime.now(timezone.utc).isoformat()` |
| `habit_providers.py:558-565` | 正确示例：`completed_at` 手动写入 `.isoformat()` |
| `time_utils.py:28-37` | `get_utc_now_iso()` 工具函数 |
| `diary_provider.py:175` | 遗留问题：`datetime('now','localtime')` |
| `custom_block_provider.py:161-164` | 额外问题：`.replace("T", " ")` 反向转换 |
| `category_service.py:944,955,981,992` | 额外问题：`CURRENT_TIMESTAMP` |
