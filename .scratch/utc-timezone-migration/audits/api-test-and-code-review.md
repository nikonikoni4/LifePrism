# API 测试与代码审查报告

## 概述

本报告基于数据流分析报告（`data-flow-audit-report.md`），对 LifeWatch-AI 项目进行 API 测试和代码审查，验证所有数据库表的时间字段（`created_at`/`updated_at`）是否写入正确的 ISO 8601 + UTC 格式（`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`）。

- **测试时间**：2026-07-12
- **测试数据库**：`d:\desktop\软件开发\LifeWatch-AI\localData\dataset\lifewatch_ai.db`
- **FastAPI 服务**：`http://127.0.0.1:8000`（端口 8000）
- **测试方式**：HTTP POST 创建 + 数据库直查验证
- **代码审查范围**：P0（localtime 残留）、P1（DB DEFAULT 依赖）、P2（UPDATE 不更新 updated_at）
- **重要说明**：本次为测试和审查任务，**未修改任何代码**

---

## Part 1: API 层测试结果

### 1.1 测试环境

- **服务启动**：`python -m uvicorn lifeprism.server.main:app --host 127.0.0.1 --port 8000`
- **健康检查**：`GET /health` 返回 HTTP 200
- **测试脚本**：
  - `verify_api.py`（16 个测试用例）
  - `verify_api_extra.py`（8 个补充测试用例，使用唯一名称避免冲突）
- **验证规则**：正则 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$`

### 1.2 测试结果汇总

| 表名 | API 路由 | HTTP 状态 | `created_at` 格式 | `updated_at` 格式 | 结果 |
|------|---------|----------|------------------|------------------|------|
| `category` | `POST /api/v2/category/manage` | 200 | `2026-07-12T02:28:51.658506+00:00` | `2026-07-12T02:28:51.658506+00:00` | ✅ 通过 |
| `sub_category` | `POST /api/v2/category/manage/{id}/sub` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `todo_list` | `POST /api/v2/todos` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `goal` | `POST /api/v2/goal/goals` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `plan_doc` | `POST /api/v2/goal/plan-docs` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `diary` | `GET /api/v2/diary/{date}`（自动创建） | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `mood_types` | `POST /api/v2/mood/types` | 200 | ISO UTC | N/A（`update_at: False`） | ✅ 通过 |
| `mood_entries` | `POST /api/v2/mood/entries` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `mood_impacts` | `POST /api/v2/mood/impacts` | 200 | `2026-07-12 02:30:19` | N/A（`update_at: False`） | ❌ 失败 |
| `user_values` | `POST /api/v2/value/` | 200 | `2026-07-12 02:30:19` | `2026-07-12 02:30:19` | ❌ 失败 |
| `commitments` | `POST /api/v2/commitment/` | 200 | `2026-07-12 02:30:19` | `2026-07-12 02:30:19` | ❌ 失败 |
| `goal_journal` | `POST /api/v2/goal/journals` | 200 | `2026-07-12 02:30:19` | `2026-07-12 02:30:19` | ❌ 失败 |
| `habits` | `POST /api/v2/habit/habits` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `habit_chains` | `POST /api/v2/habit/chains` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `habit_chain_nodes` | `POST /api/v2/habit/chains/{id}/nodes` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `habit_checkins` | `POST /api/v2/habit/habits/{id}/checkins` | 200 | ISO UTC（`completed_at` 也为 ISO UTC） | N/A | ✅ 通过 |
| `custom_record_types` | `POST /api/v2/custom-records/types` | 200 | ISO UTC | ISO UTC | ✅ 通过 |
| `timeline_custom_block` | `POST /api/v2/timeline/custom-blocks` | 200 | ISO UTC | ISO UTC | ✅ 通过 |

### 1.3 测试结论

- **总计测试**：17 张表（含 18 个 API 端点）
- **通过**：13 张表（76%）—— 主写入路径通过 `_generic_insert`/`_generic_update`，自动写入 ISO 8601 + UTC 格式
- **失败**：4 张表（24%）—— `mood_impacts`、`user_values`、`commitments`、`goal_journal`

**失败原因分析**：

这 4 张表的写入路径均使用原生 `INSERT INTO` SQL，未通过 `_generic_insert`，且 `data` 字典中未包含 `created_at`/`updated_at` 字段，导致依赖数据库 DEFAULT 值 `datetime('now')`。虽然 m008 迁移已将 DEFAULT 从 `datetime('now', 'localtime')` 改为 `datetime('now')`（UTC 时区正确），但 SQLite 的 `datetime('now')` 输出格式为 `YYYY-MM-DD HH:MM:SS`（无 T 分隔符、无时区标识），**不符合 ISO 8601 规范**。

---

## Part 2: 代码审查

### 2.1 🔴 P0 级风险（严重 - 仍使用 `localtime`）

#### P0-1: `raw_behavior_analysis` 表

- **文件**：`lifeprism/repository/providers/raw_behavior_analysis_provider.py`
- **行号**：186-195
- **问题代码**：
  ```python
  cursor.execute(
      f"""INSERT INTO {self._TABLE_NAME}
         (start_time, end_time, behavior, screen_count, created_at)
         VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
      (data["start_time"], data["end_time"], data["behavior"], data["screen_count"]),
  )
  ```
- **问题确认**：✅ 已确认。批量插入路径硬编码 `datetime('now', 'localtime')`，输出本地时区（UTC+8）且格式为 `YYYY-MM-DD HH:MM:SS`，时区错误 + 格式错误双重问题。
- **影响**：新写入数据时区错误（本地时区而非 UTC），与 m009 迁移后的历史数据格式不一致，同步 LWW 比较失效。
- **修复建议**：
  ```python
  from lifeprism.utils.time_utils import get_utc_now_iso
  now_iso = get_utc_now_iso()
  cursor.execute(
      f"""INSERT INTO {self._TABLE_NAME}
         (start_time, end_time, behavior, screen_count, created_at)
         VALUES (?, ?, ?, ?, ?)""",
      (data["start_time"], data["end_time"], data["behavior"], data["screen_count"], now_iso),
  )
  ```

#### P0-2: `behavior_analysis` 表

- **文件**：`lifeprism/repository/providers/behavior_analysis_provider.py`
- **行号**：313-324
- **问题代码**：
  ```python
  cursor.execute(
      f"""INSERT INTO {self._TABLE_NAME}
         (start_time, end_time, behavior, behavior_summary, title, screen_count, created_at)
         VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
      (data["start_time"], data["end_time"], data["behavior"], data.get("behavior_summary"),
       data.get("title"), data["screen_count"]),
  )
  ```
- **问题确认**：✅ 已确认。与 P0-1 相同的问题，批量插入路径硬编码 `datetime('now', 'localtime')`。
- **影响**：该表是 AI 行为分析结果的核心表，影响行为分析展示和同步。新写入数据时区错误且格式错误。
- **修复建议**：同 P0-1，使用 `get_utc_now_iso()` 参数化绑定。

---

### 2.2 🟠 P1 级风险（高 - 依赖 DB DEFAULT 输出非 ISO 格式）

以下所有 P1 风险点均已通过代码审查确认。共性问题：写入路径未显式写入 `created_at`/`updated_at`，依赖 DB DEFAULT `datetime('now')`，输出格式 `YYYY-MM-DD HH:MM:SS`（无 T 分隔符、无时区标识），不符合 ISO 8601。

#### P1-1: `window_events` 表

- **文件**：`lifeprism/monitor/provider/window_data_provider.py`
- **行号**：48-52
- **问题确认**：✅ `data` 字典仅包含 `timestamp`、`duration`、`app`、`title`，未包含 `created_at`，调用 `self.db.insert("window_events", data)` 时依赖 DB DEFAULT。
- **修复建议**：在 `data` 字典中添加 `"created_at": get_utc_now_iso()`。

#### P1-2: `screen_captures` 表

- **文件**：`lifeprism/monitor/provider/screenshot_data_provider.py`
- **行号**：32
- **问题确认**：✅ monitor 路径调用 `self.db.insert("screen_captures", data)` 时 `data` 未包含 `created_at`。`captured_at` 字段由调用方传入 ISO 格式（正确），但 `created_at` 依赖 DB DEFAULT。
- **修复建议**：在 `data` 字典中添加 `"created_at": get_utc_now_iso()`。

#### P1-3: `user_app_behavior_log` 表（批量路径）

- **文件**：`lifeprism/repository/base_providers/lw_base_data_provider.py`
- **行号**：800
- **问题确认**：✅ 批量保存使用 `INSERT OR IGNORE INTO user_app_behavior_log (...)`，`data_list` 中的字典未包含 `created_at`/`updated_at`，依赖 DB DEFAULT。单条创建路径（`computer_usage_provider.py:122`）使用 `_generic_insert` ✓。
- **修复建议**：在 `data_list` 的每个字典中添加 `created_at` 和 `updated_at` 字段，值为 `get_utc_now_iso()`。

#### P1-4: `todo_list` 表（批量路径）

- **文件**：`lifeprism/repository/providers/todo_provider.py`
- **行号**：686
- **问题确认**：✅ 批量创建任务使用原生 `INSERT INTO`，未写入时间戳，依赖 DB DEFAULT。单条创建（`:245`）和更新（`:284`）使用 `_generic_insert`/`_generic_update` ✓。
- **修复建议**：改用 `_generic_insert` 循环插入，或在原生 SQL 中显式写入 `get_utc_now_iso()`。

#### P1-5: `time_paradoxes` 表

- **文件**：`lifeprism/server/providers/being_provider.py`
- **行号**：188（INSERT）、331（upsert）
- **问题确认**：✅
  - 行 188：原生 `INSERT INTO` 未写入 `created_at`/`updated_at`，依赖 DB DEFAULT。
  - 行 331：`self.db.upsert(self.TABLE_NAME, data, ...)` 调用 `database_manager.upsert`，该方法仅对 `single_purpose_map_cache`/`multi_purpose_map_cache` 表设置 `updated_at = CURRENT_TIMESTAMP`（行 384-387），对 `time_paradoxes` 不设置。
- **修复建议**：在 `insert_data` 中添加 `created_at`/`updated_at`；在 `database_manager.upsert` 中根据 `TABLE_CONFIGS` 通用化 `updated_at` 处理。

#### P1-6: `daily_report` 表

- **文件**：`lifeprism/server/providers/report_provider.py`
- **行号**：128（INSERT）、113（update_by_id）
- **问题确认**：✅
  - 行 128：`self.db.insert(self.TABLE_NAME, insert_data)` 未写入时间戳，依赖 DB DEFAULT。
  - 行 113：`self.db.update_by_id(...)` 不自动设置 `updated_at`（`database_manager.update` 方法无时间戳处理逻辑）。
- **修复建议**：在 `insert_data` 中添加 `created_at`/`updated_at`；在 `update_data` 中添加 `updated_at`。

#### P1-7: `weekly_report` 表

- **文件**：`lifeprism/server/providers/report_provider.py`
- **行号**：354（INSERT）、339（update_by_id）
- **问题确认**：✅ 同 P1-6，结构与 `daily_report` 相同。
- **修复建议**：同 P1-6。

#### P1-8: `monthly_report` 表

- **文件**：`lifeprism/server/providers/report_provider.py`
- **行号**：551（INSERT）、对应 update_by_id
- **问题确认**：✅ 同 P1-6，结构与 `daily_report` 相同。
- **修复建议**：同 P1-6。

#### P1-9: `goal_stats` 表

- **文件**：`lifeprism/repository/providers/goal_providers.py`
- **行号**：660-677
- **问题确认**：✅ 原生 `INSERT INTO` 和 `UPDATE` 均未写入 `created_at`。该表配置 `update_at: False`，无 `updated_at` 需求，但 `created_at` 仍依赖 DB DEFAULT。
- **修复建议**：在 INSERT 的 `data` 字典中添加 `"created_at": get_utc_now_iso()`。

#### P1-10: `goal_journal` 表

- **文件**：`lifeprism/server/providers/journal_provider.py`
- **行号**：115
- **问题确认**：✅ 原生 `INSERT INTO` 未写入 `created_at`/`updated_at`，依赖 DB DEFAULT。**API 测试已验证此问题**：新创建的 `goal_journal` 记录 `created_at='2026-07-12 02:30:19'`（非 ISO 格式）。
- **修复建议**：改用 `_generic_insert`，或在原生 SQL 中显式写入 `get_utc_now_iso()`。

#### P1-11: `user_values` 表

- **文件**：`lifeprism/server/providers/value_provider.py`
- **行号**：88
- **问题确认**：✅ 原生 `INSERT INTO` 未写入 `created_at`/`updated_at`，依赖 DB DEFAULT。**API 测试已验证此问题**：新创建的 `user_values` 记录 `created_at='2026-07-12 02:30:19'`（非 ISO 格式）。
- **修复建议**：改用 `_generic_insert`，或在原生 SQL 中显式写入 `get_utc_now_iso()`。

#### P1-12: `commitments` 表

- **文件**：`lifeprism/server/providers/commitment_provider.py`
- **行号**：154
- **问题确认**：✅ 原生 `INSERT INTO` 未写入 `created_at`/`updated_at`，依赖 DB DEFAULT。**API 测试已验证此问题**：新创建的 `commitments` 记录 `created_at='2026-07-12 02:30:19'`（非 ISO 格式）。
- **修复建议**：改用 `_generic_insert`，或在原生 SQL 中显式写入 `get_utc_now_iso()`。

#### P1-13: `mood_impacts` 表

- **文件**：`lifeprism/repository/providers/mood_providers.py`
- **行号**：493-499
- **问题确认**：✅ 原生 `INSERT INTO mood_impacts (name, sort_order) VALUES (?, ?)` 未写入 `created_at`，依赖 DB DEFAULT。**API 测试已验证此问题**：新创建的 `mood_impacts` 记录 `created_at='2026-07-12 02:30:19'`（非 ISO 格式）。该表配置 `update_at: False`，无 `updated_at` 需求。
- **修复建议**：在 INSERT 语句中添加 `created_at` 列和 `get_utc_now_iso()` 参数。

#### P1-14: `multi_purpose_map_cache` 表（批量/upsert 路径）

- **文件**：
  - `lifeprism/repository/providers/map_cache_providers.py:261`（原生批量 INSERT）
  - `lifeprism/repository/base_providers/lw_base_data_provider.py:619`（`db.upsert_many`）
  - `lifeprism/repository/database_manager.py:387`（`updated_at = CURRENT_TIMESTAMP`）
- **问题确认**：✅
  - 批量 INSERT 路径依赖 DB DEFAULT。
  - `upsert_many` 调用 `database_manager.upsert_many`（行 446-449），对 map_cache 表设置 `updated_at = CURRENT_TIMESTAMP`，格式为 `YYYY-MM-DD HH:MM:SS`（非 ISO）。
  - 单条创建路径（`map_cache_providers.py:144`，`_generic_insert`）✓。
- **修复建议**：在批量 INSERT 数据中添加时间戳；将 `database_manager.upsert/upsert_many` 中的 `CURRENT_TIMESTAMP` 替换为参数化的 `get_utc_now_iso()`。

#### P1-15: `single_purpose_map_cache` 表（批量/upsert 路径）

- **文件**：
  - `lifeprism/repository/providers/map_cache_providers.py:622`（原生批量 INSERT）
  - `lifeprism/repository/base_providers/lw_base_data_provider.py:612`（`db.upsert_many`）
  - `lifeprism/repository/database_manager.py:387`（`updated_at = CURRENT_TIMESTAMP`）
- **问题确认**：✅ 同 P1-14，结构与 `multi_purpose_map_cache` 相同。
- **修复建议**：同 P1-14。

#### P1-16: `tokens_usage_log` 表（批量/单条非 provider 路径）

- **文件**：`lifeprism/repository/base_providers/lw_base_data_provider.py`
- **行号**：850（批量 `insert_many`）、948（单条 `db.insert`）
- **问题确认**：✅
  - 行 850：`self.db.insert_many("tokens_usage_log", tokens_usage_data)` —— `tokens_usage_data` 字典未包含 `created_at`，依赖 DB DEFAULT。
  - 行 928-948：`upsert_session_tokens_usage` 方法中，`data` 字典（行 928-935）未包含 `created_at`，INSERT 路径（行 948）依赖 DB DEFAULT。
  - Provider 路径（`tokens_usage_provider.py:142`，`_generic_insert`）✓。
- **修复建议**：在 `tokens_usage_data` 和 `data` 字典中添加 `"created_at": get_utc_now_iso()`。该表配置 `update_at: False`，无 `updated_at` 需求。

---

### 2.3 🟡 P2 级风险（中 - UPDATE 不更新 `updated_at`）

以下所有 P2 风险点均已通过代码审查确认。共性问题：UPDATE 操作未写入 `updated_at`，或使用 `datetime('now')`/`CURRENT_TIMESTAMP`（格式非 ISO 8601），导致同步 LWW 比较失效或格式不一致。

#### P2-1: `todo_list` 表（4 处 UPDATE）

- **文件**：`lifeprism/repository/providers/todo_provider.py`
- **行号**：447、513、742、804
- **问题确认**：✅
  - 行 447：`UPDATE todo_list SET order_index = ? WHERE id = ?`（reorder 排序）—— 未写入 `updated_at`。
  - 行 513：`UPDATE todo_list SET pool_order_index = ? WHERE id = ?`（pool reorder）—— 未写入 `updated_at`。
  - 行 742：`UPDATE todo_list SET {set_clauses} WHERE id = ?`（批量更新）—— 未写入 `updated_at`。
  - 行 804：`UPDATE todo_list SET waid_order = ? WHERE id = ?`（WAID reorder）—— 未写入 `updated_at`。
- **影响**：同步 LWW 无法检测到这些变更，可能导致数据丢失。
- **修复建议**：在每条 UPDATE 的 SET 子句中追加 `updated_at = ?` 并绑定 `get_utc_now_iso()`。

#### P2-2: `goal` 表（reorder 排序）

- **文件**：`lifeprism/repository/providers/goal_providers.py`
- **行号**：320
- **问题确认**：✅ `UPDATE goal SET order_index = ? WHERE id = ?`（`reorder_goals` 方法）—— 未写入 `updated_at`。
- **影响**：同 P2-1，排序变更不会被同步检测到。
- **修复建议**：在 SET 子句中追加 `updated_at = ?` 并绑定 `get_utc_now_iso()`。

#### P2-3: `plan_doc` 表（2 处 UPDATE 使用 `datetime('now')`）

- **文件**：`lifeprism/repository/providers/plan_doc_provider.py`
- **行号**：242、308
- **问题确认**：✅
  - 行 242：`set_clauses.append("updated_at = datetime('now')")` —— 使用 `datetime('now')`（UTC，但格式 `YYYY-MM-DD HH:MM:SS`，非 ISO 8601）。
  - 行 308：`UPDATE plan_doc SET id = ?, updated_at = datetime('now') WHERE id = ?`（`rename_plan_doc`）—— 同上。
- **影响**：格式不符合 ISO 8601，与 `_generic_update` 写入的 ISO 格式不一致。
- **修复建议**：将 `datetime('now')` 替换为参数化的 `get_utc_now_iso()`，即 `set_clauses.append("updated_at = ?")` 并 `values.append(get_utc_now_iso())`。

#### P2-4: `daily_report`/`weekly_report`/`monthly_report` 表（`db.update_by_id`）

- **文件**：`lifeprism/server/providers/report_provider.py`
- **行号**：113（daily）、339（weekly）、对应 monthly
- **问题确认**：✅ `self.db.update_by_id(self.TABLE_NAME, self.ID_COLUMN, date, update_data)` —— `update_data` 未包含 `updated_at`，`database_manager.update` 方法（行 482-510）不自动设置 `updated_at`。
- **影响**：报告更新后 `updated_at` 不变，同步 LWW 判断失效。
- **修复建议**：在 `update_data` 中添加 `updated_at: get_utc_now_iso()`；或在 `database_manager.update` 方法中增加自动 `updated_at` 逻辑（根据 `TABLE_CONFIGS` 的 `update_at` 配置）。

#### P2-5: `time_paradoxes` 表（`db.update`）

- **文件**：`lifeprism/server/providers/being_provider.py`
- **行号**：251、280
- **问题确认**：✅
  - 行 251：`self.db.update(self.TABLE_NAME, update_data, where={"id": record_id})` —— `update_data` 未包含 `updated_at`。
  - 行 280：`self.db.update(self.TABLE_NAME, update_data, where={"user_id": ..., "mode": ..., "version": ...})` —— 同上。
- **影响**：同 P2-4，更新后 `updated_at` 不变。
- **修复建议**：同 P2-4。

---

## 修复优先级与建议

### 优先级排序

| 优先级 | 数量 | 修复紧急度 | 建议 |
|--------|------|----------|------|
| 🔴 P0 | 2 处 | 立即修复 | `raw_behavior_analysis` 和 `behavior_analysis` 批量插入使用 `localtime`，时区错误 + 格式错误 |
| 🟠 P1 | 16 处 | 尽快修复 | 依赖 DB DEFAULT，格式为 `YYYY-MM-DD HH:MM:SS`，不符合 ISO 8601 |
| 🟡 P2 | 5 类（含 9+ 处） | 计划修复 | UPDATE 不更新 `updated_at` 或使用非 ISO 格式，影响同步 LWW |

### 修复策略建议

#### 策略 A（推荐）：统一改用 `_generic_insert`/`_generic_update`

对于 `todo_list`（批量）、`goal_journal`、`user_values`、`commitments`、`mood_impacts`、`time_paradoxes`、`goal_stats`、`daily_report`、`weekly_report`、`monthly_report`、`tokens_usage_log`（批量）的原生 INSERT 路径，改为调用 `_generic_insert`，让基类自动写入 ISO 格式时间戳。

#### 策略 B（替代）：在原生 SQL 中显式写入 `get_utc_now_iso()`

若无法改用 `_generic_insert`（如批量插入性能考虑），则在原生 SQL 中显式写入时间戳：
```python
from lifeprism.utils.time_utils import get_utc_now_iso
now_iso = get_utc_now_iso()
data["created_at"] = now_iso
data["updated_at"] = now_iso  # 若表配置 update_at=True
```

#### 策略 C（长期改进）：增强 `database_manager` 通用方法

在 `database_manager.py` 的 `insert`/`insert_many`/`update`/`upsert`/`upsert_many` 方法中，根据 `TABLE_CONFIGS` 配置自动写入 ISO 格式的 `created_at`/`updated_at`，避免每个调用方手动处理。这样可以一次性修复所有通过 `db.insert`/`db.update` 的调用路径。

具体修改点：
- `database_manager.py:287-315`（`insert` 方法）：添加 `created_at`/`updated_at` 自动写入
- `database_manager.py:482-510`（`update` 方法）：添加 `updated_at` 自动写入
- `database_manager.py:355-410`（`upsert` 方法）：将 `CURRENT_TIMESTAMP` 替换为 `get_utc_now_iso()`，并泛化为根据 `TABLE_CONFIGS` 处理
- `database_manager.py:384-387`：移除仅对 map_cache 表的硬编码逻辑

---

## 测试数据清理

测试完成后已清理所有测试数据：
- **清理脚本**：`cleanup_test_data.py`、`cleanup_remaining.py`、`cleanup_checkin.py`
- **清理范围**：18 张表，共删除 44 行测试数据
- **清理结果**：✅ 全部清理完毕，数据库恢复测试前状态
- **动态表检查**：检查 `custom_record_data_*` 动态表，无测试残留

---

## 附录

### A. 测试通过表清单（13 张）

以下表的主写入路径通过 `_generic_insert`/`_generic_update` 或显式 `get_utc_now_iso()` 写入 ISO 8601 + UTC 格式，API 测试验证通过：

1. `category` ✅
2. `sub_category` ✅
3. `todo_list`（单条路径）✅
4. `goal`（单条路径）✅
5. `plan_doc`（创建路径）✅
6. `diary` ✅
7. `mood_types` ✅
8. `mood_entries` ✅
9. `habits` ✅
10. `habit_chains` ✅
11. `habit_chain_nodes` ✅
12. `habit_checkins` ✅
13. `custom_record_types` ✅
14. `timeline_custom_block` ✅

### B. 测试失败表清单（4 张）

以下表的主写入路径使用原生 SQL，依赖 DB DEFAULT，API 测试验证失败：

1. `mood_impacts` ❌（`created_at='2026-07-12 02:30:19'`）
2. `user_values` ❌（`created_at='2026-07-12 02:30:19'`）
3. `commitments` ❌（`created_at='2026-07-12 02:30:19'`）
4. `goal_journal` ❌（`created_at='2026-07-12 02:30:19'`）

### C. 未进行 API 测试的表（仅代码审查）

以下表因无对应 API 端点或属于系统内部写入，未进行 API 测试，仅通过代码审查确认问题：

- `window_events`（monitor 采集）—— P1
- `screen_captures`（monitor 采集）—— P1
- `user_app_behavior_log`（批量路径）—— P1
- `raw_behavior_analysis`（批量路径）—— P0
- `behavior_analysis`（批量路径）—— P0
- `time_paradoxes` —— P1/P2
- `daily_report`/`weekly_report`/`monthly_report` —— P1/P2
- `goal_stats` —— P1
- `tokens_usage_log`（批量路径）—— P1
- `multi_purpose_map_cache`/`single_purpose_map_cache`（批量/upsert 路径）—— P1

### D. 关键代码位置索引

| 文件 | 行号 | 说明 | 风险等级 |
|------|------|------|---------|
| `raw_behavior_analysis_provider.py` | 186-195 | `datetime('now', 'localtime')` | 🔴 P0 |
| `behavior_analysis_provider.py` | 313-324 | `datetime('now', 'localtime')` | 🔴 P0 |
| `window_data_provider.py` | 48-52 | 未写入 `created_at` | 🟠 P1 |
| `screenshot_data_provider.py` | 32 | 未写入 `created_at` | 🟠 P1 |
| `lw_base_data_provider.py` | 800 | `INSERT OR IGNORE` 未写入时间戳 | 🟠 P1 |
| `todo_provider.py` | 686 | 批量 INSERT 未写入时间戳 | 🟠 P1 |
| `being_provider.py` | 188, 331 | 原生 INSERT/upsert 未写入时间戳 | 🟠 P1 |
| `report_provider.py` | 128, 354, 551 | `db.insert` 未写入时间戳 | 🟠 P1 |
| `goal_providers.py` | 660-677 | 原生 INSERT 未写入 `created_at` | 🟠 P1 |
| `journal_provider.py` | 115 | 原生 INSERT 未写入时间戳 | 🟠 P1 |
| `value_provider.py` | 88 | 原生 INSERT 未写入时间戳 | 🟠 P1 |
| `commitment_provider.py` | 154 | 原生 INSERT 未写入时间戳 | 🟠 P1 |
| `mood_providers.py` | 493-499 | 原生 INSERT 未写入 `created_at` | 🟠 P1 |
| `map_cache_providers.py` | 261, 622 | 批量 INSERT 未写入时间戳 | 🟠 P1 |
| `lw_base_data_provider.py` | 612, 619 | `upsert_many` 未写入时间戳 | 🟠 P1 |
| `database_manager.py` | 387, 449 | `CURRENT_TIMESTAMP`（非 ISO 格式） | 🟠 P1 |
| `lw_base_data_provider.py` | 850, 948 | 批量/单条 INSERT 未写入时间戳 | 🟠 P1 |
| `todo_provider.py` | 447, 513, 742, 804 | UPDATE 未写入 `updated_at` | 🟡 P2 |
| `goal_providers.py` | 320 | reorder UPDATE 未写入 `updated_at` | 🟡 P2 |
| `plan_doc_provider.py` | 242, 308 | `datetime('now')`（非 ISO 格式） | 🟡 P2 |
| `report_provider.py` | 113, 339 | `db.update_by_id` 未设置 `updated_at` | 🟡 P2 |
| `being_provider.py` | 251, 280 | `db.update` 未设置 `updated_at` | 🟡 P2 |

### E. 相关文档

- 数据流分析报告：`.scratch/utc-timezone-migration/data-flow-audit-report.md`
- 测试脚本：`.scratch/utc-timezone-migration/verify_api.py`、`verify_api_extra.py`
- 清理脚本：`.scratch/utc-timezone-migration/cleanup_test_data.py`、`cleanup_remaining.py`、`cleanup_checkin.py`
- 迁移决策：`docs/design-decisions/`（UTC 时区迁移相关 ADR）
- PRD：`.scratch/utc-timezone-migration/prd.md`
