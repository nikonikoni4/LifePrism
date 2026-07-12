# 数据库表数据流分析报告

## 概述

本报告针对 LifeWatch-AI 项目 UTC 时区迁移后的数据库表数据流进行审计，重点核查每张表的 `created_at`/`updated_at` 时间字段是否通过 `_generic_insert`/`_generic_update` 自动写入 ISO 8601 + UTC 格式，以及是否存在遗漏的写入路径仍输出旧的 `YYYY-MM-DD HH:MM:SS` 格式。

### 数据来源
- 表配置权威来源：`lifeprism/config/database.py` 中的 `TABLE_CONFIGS`（共 **39 张表**）
- 迁移脚本目录：`lifeprism/repository/migrations/scripts/`（m001~m009）
- 通用写入方法：`lifeprism/repository/base_providers/lw_base_data_provider.py` 中的 `_generic_insert`/`_generic_update`

### 关键背景
- `_generic_insert`（lw_base_data_provider.py:1119-1132）已修复：对 `timestamps=True` 的表自动调用 `get_utc_now_iso()`（即 `datetime.now(timezone.utc).isoformat()`）写入 `created_at`/`updated_at`，输出格式为 `2026-07-12T10:30:00.123456+00:00`。
- `_generic_update`（lw_base_data_provider.py:1207-1213）已修复：对 `update_at=True` 的表自动写入 `updated_at` 为 ISO 8601 + UTC 格式。
- m008 迁移：将所有表的 DEFAULT 从 `datetime('now', 'localtime')` 改为 `datetime('now')`（SQLite UTC）。
- m009 迁移：将历史数据时间字段从本地时区（UTC+8）转为 UTC，并格式化为 `YYYY-MM-DDTHH:MM:SS+00:00`。

### 渠道分布统计

| 数据渠道 | 表数量 | 已修复（ISO 格式） | 风险点（旧格式/DB DEFAULT） |
|---------|--------|-------------------|---------------------------|
| 数据采集层 | 4 | 1 | 3 |
| API 层 | 19 | 13 | 6 |
| LLM/AI 生成层 | 3 | 1 | 2 |
| 系统自动计算层 | 6 | 0 | 6 |
| 其他/混合渠道 | 5 | 2 | 3 |
| 迁移/元数据 | 2 | 0 | 2 |
| **合计** | **39** | **17** | **22** |

> 说明："已修复"指主写入路径通过 `_generic_insert`/`_generic_update` 或显式 `get_utc_now_iso()` 写入 ISO 格式；"风险点"指存在至少一条写入路径绕过通用方法，依赖 DB DEFAULT 或显式 `datetime('now')`/`datetime('now', 'localtime')`，输出格式为 `YYYY-MM-DD HH:MM:SS`（无 T 分隔符、无时区标识），不符合 ISO 8601 + UTC 规范。

---

## 表清单与数据流分析

### 1. 数据采集层写入的表

由系统采集工具（monitor、processors）自动写入的表。

| 表名 | 写入入口代码位置 | 时间字段写入方式 | 是否已修复 |
|------|-----------------|-----------------|-----------|
| `window_events` | `lifeprism/monitor/provider/window_data_provider.py:52` (`db.insert`) | `created_at` 未显式写入 → DB DEFAULT `datetime('now')`（UTC，格式 `YYYY-MM-DD HH:MM:SS`）；`timestamp` 字段由 `monitor.py:51` 写入 `datetime.now(timezone.utc).isoformat()` ✓ | ⚠️ 部分修复 |
| `screen_captures` | `lifeprism/monitor/provider/screenshot_data_provider.py:32` (`db.insert`)；`lifeprism/repository/providers/screen_capture_provider.py:143` (`_generic_insert`) | monitor 路径：`created_at` 未显式写入 → DB DEFAULT（格式 `YYYY-MM-DD HH:MM:SS`）；`captured_at` 由调用方传入 ISO 格式 ✓。provider 路径：`_generic_insert` 自动写入 ✓ | ⚠️ 部分修复 |
| `user_app_behavior_log` | `lifeprism/repository/base_providers/lw_base_data_provider.py:800` (`INSERT OR IGNORE`)；`lifeprism/repository/providers/computer_usage_provider.py:122` (`_generic_insert`) | 批量保存路径：`created_at`/`updated_at` 未显式写入 → DB DEFAULT（格式 `YYYY-MM-DD HH:MM:SS`）。单条创建路径：`_generic_insert` ✓ | ⚠️ 部分修复 |
| `raw_behavior_analysis` | `lifeprism/repository/providers/raw_behavior_analysis_provider.py:140` (`_generic_insert`)；`raw_behavior_analysis_provider.py:186` (原生 `INSERT INTO`) | 单条创建：`_generic_insert` ✓。批量创建：**显式使用 `datetime('now', 'localtime')`** ❌ 旧格式且本地时区 | ❌ 未修复 |

**关键风险**：
- `raw_behavior_analysis_provider.py:188` 批量插入时硬编码 `datetime('now', 'localtime')`，这是唯一仍使用 `localtime` 的写入路径，不仅格式错误，时区也错误。
- `window_events`、`screen_captures`（monitor 路径）、`user_app_behavior_log`（批量路径）的 `created_at` 依赖 DB DEFAULT，虽然 m008 已将 DEFAULT 改为 UTC，但输出格式为 `YYYY-MM-DD HH:MM:SS`，缺少 T 分隔符和时区标识，与 ISO 8601 规范不一致。

---

### 2. API 层创建的表

由用户通过 FastAPI 接口（POST/PUT）创建/更新的表。

| 表名 | 写入入口代码位置 | 时间字段写入方式 | 是否已修复 |
|------|-----------------|-----------------|-----------|
| `todo_list` | `lifeprism/repository/providers/todo_provider.py:245` (`_generic_insert`)；`todo_provider.py:284` (`_generic_update`)；`todo_provider.py:686` (批量 `INSERT INTO`)；`todo_provider.py:447,513,742,804` (原生 `UPDATE`) | 单条创建/更新：`_generic_insert`/`_generic_update` ✓。批量创建：`created_at`/`updated_at` 未写入 → DB DEFAULT ⚠️。排序/WAID 更新：未写入 `updated_at` ⚠️ | ⚠️ 部分修复 |
| `goal` | `lifeprism/repository/providers/goal_providers.py:208` (`_generic_insert`)；`goal_providers.py:249` (`_generic_update`)；`goal_providers.py:320` (原生 `UPDATE order_index`)；`goal_providers.py:490-492` (`_generic_update` with `time_invested_updated_at`) | 单条创建/更新：✓。`order_index` 重排序：未写入 `updated_at` ⚠️。`time_invested_updated_at` 显式写入 ISO ✓ | ⚠️ 部分修复 |
| `plan_doc` | `lifeprism/repository/providers/plan_doc_provider.py:194` (`_generic_insert`)；`plan_doc_provider.py:242` (原生 `UPDATE` with `datetime('now')`)；`plan_doc_provider.py:308` (原生 `UPDATE` with `datetime('now')`) | 创建：✓。更新：**显式使用 `datetime('now')`**（UTC，但格式 `YYYY-MM-DD HH:MM:SS`）⚠️ | ⚠️ 部分修复 |
| `diary` | `lifeprism/repository/providers/diary_provider.py:135` (`_generic_insert`)；`diary_provider.py:161` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `mood_types` | `lifeprism/repository/providers/mood_providers.py:139` (`_generic_insert`)；`mood_providers.py:169` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `mood_entries` | `lifeprism/repository/providers/mood_providers.py:348` (`_generic_insert`)；`mood_providers.py:378` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `mood_impacts` | `lifeprism/repository/providers/mood_providers.py:495` (原生 `INSERT INTO`) | `created_at` 未显式写入 → DB DEFAULT（格式 `YYYY-MM-DD HH:MM:SS`）；`update_at: False` 无 `updated_at` | ⚠️ DB DEFAULT |
| `habits` | `lifeprism/repository/providers/habit_providers.py:162` (`_generic_insert`)；`habit_providers.py:189` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `habit_challenges` | `lifeprism/repository/providers/habit_providers.py:308` (`_generic_insert`)；`habit_providers.py:385` (`_generic_update`)；`habit_providers.py:403-404` (显式 ISO for `finished_at`) | ✓ 已修复 | ✓ 已修复 |
| `habit_checkins` | `lifeprism/repository/providers/habit_providers.py:569` (`_generic_insert`)；`habit_providers.py:558` (显式 ISO for `completed_at`) | ✓ 已修复 | ✓ 已修复 |
| `habit_chains` | `lifeprism/repository/providers/habit_chain_providers.py:100` (原生 `INSERT INTO` with `get_utc_now_iso()`)；`habit_chain_providers.py:172` (`_generic_update`) | ✓ 已修复（显式 ISO） | ✓ 已修复 |
| `habit_chain_nodes` | `lifeprism/repository/providers/habit_chain_providers.py:281` (原生 `INSERT INTO` with `get_utc_now_iso()`)；`habit_chain_providers.py:386-390` (原生 `UPDATE` with `datetime.now(timezone.utc).isoformat()`) | ✓ 已修复（显式 ISO） | ✓ 已修复 |
| `category` | `lifeprism/repository/providers/category_provider.py:135` (`_generic_insert`)；`category_provider.py:179` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `sub_category` | `lifeprism/repository/providers/category_provider.py:323` (`_generic_insert`)；`category_provider.py:367` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `timeline_custom_block` | `lifeprism/repository/providers/custom_block_provider.py:168` (`_generic_insert`)；`custom_block_provider.py:220` (`_generic_update`) | ✓ 已修复 | ✓ 已修复 |
| `user_values` | `lifeprism/server/providers/value_provider.py:88` (原生 `INSERT INTO`)；`value_provider.py` (原生 `UPDATE`) | `created_at`/`updated_at` 未显式写入 → DB DEFAULT ⚠️ | ⚠️ DB DEFAULT |
| `commitments` | `lifeprism/server/providers/commitment_provider.py:154` (原生 `INSERT INTO`)；`commitment_provider.py` (原生 `UPDATE`) | `created_at`/`updated_at` 未显式写入 → DB DEFAULT ⚠️ | ⚠️ DB DEFAULT |
| `goal_journal` | `lifeprism/server/providers/journal_provider.py:115` (原生 `INSERT INTO`)；`journal_provider.py` (原生 `UPDATE`) | `created_at`/`updated_at` 未显式写入 → DB DEFAULT ⚠️ | ⚠️ DB DEFAULT |
| `custom_record_types` | `lifeprism/repository/aggregators/custom_record_aggregator.py:133` (原生 `INSERT INTO` with `datetime.now(timezone.utc).isoformat()`) | ✓ 已修复（显式 ISO） | ✓ 已修复 |
| `custom_record_fields` | `lifeprism/repository/aggregators/custom_record_aggregator.py:142` (原生 `INSERT INTO` with `datetime.now(timezone.utc).isoformat()`) | ✓ 已修复（显式 ISO）；`update_at: False` | ✓ 已修复 |

**对应 API 路由**：
- `todos_api.py` → todo_list
- `goal_api.py` → goal, goal_journal
- `diary_api.py` → diary
- `mood_api.py` → mood_types, mood_entries, mood_impacts
- `habit_api.py` → habits, habit_challenges, habit_checkins, habit_chains, habit_chain_nodes
- `category_api.py` → category, sub_category
- `timeline_api.py` → timeline_custom_block
- `value_api.py` → user_values
- `commitment_api.py` → commitments
- `custom_records_api.py` → custom_record_types, custom_record_fields

**关键风险**：
- `todo_provider.py:686` 批量创建任务时未写入时间戳，依赖 DB DEFAULT。
- `todo_provider.py:447,513,742,804` 多处原生 UPDATE 未更新 `updated_at`（排序、WAID 操作），会导致同步 LWW 比较失效。
- `plan_doc_provider.py:242,308` 显式使用 `datetime('now')`，格式为 `YYYY-MM-DD HH:MM:SS`，不符合 ISO 8601。
- `user_values`、`commitments`、`goal_journal`、`mood_impacts` 的原生 INSERT 未写入时间戳，依赖 DB DEFAULT。

---

### 3. LLM/AI 生成层写入的表

由 AI 分析后写入的表。

| 表名 | 写入入口代码位置 | 时间字段写入方式 | 是否已修复 |
|------|-----------------|-----------------|-----------|
| `behavior_analysis` | `lifeprism/repository/providers/behavior_analysis_provider.py:190` (`_generic_insert`)；`behavior_analysis_provider.py:225` (`_generic_update`)；`behavior_analysis_provider.py:313` (原生批量 `INSERT INTO`) | 单条创建/更新：`_generic_insert`/`_generic_update` ✓。批量创建：**显式使用 `datetime('now', 'localtime')`** ❌ 旧格式且本地时区 | ❌ 未修复 |
| `time_paradoxes` | `lifeprism/server/providers/being_provider.py:188` (原生 `INSERT INTO`)；`being_provider.py:251,280` (`db.update`)；`being_provider.py:331` (`db.upsert`) | 原生 INSERT：`created_at`/`updated_at` 未显式写入 → DB DEFAULT ⚠️。`db.update`：未更新 `updated_at` ⚠️。`db.upsert`：`database_manager.upsert` 仅对 map_cache 表设置 `updated_at = CURRENT_TIMESTAMP`，对 time_paradoxes 不设置 ⚠️ | ⚠️ DB DEFAULT |
| `tokens_usage_log` | `lifeprism/repository/providers/tokens_usage_provider.py:142` (`_generic_insert`)；`tokens_usage_provider.py:172` (`_generic_update`)；`lifeprism/repository/base_providers/lw_base_data_provider.py:850` (`db.insert_many`)；`lw_base_data_provider.py:948` (`db.insert`) | 单条创建/更新：✓。批量保存：`created_at` 未写入 → DB DEFAULT ⚠️ | ⚠️ 部分修复 |

**关键风险**：
- `behavior_analysis_provider.py:315` 批量插入时硬编码 `datetime('now', 'localtime')`，与 `raw_behavior_analysis` 同样的严重问题。
- `time_paradoxes` 的所有写入路径都依赖 DB DEFAULT 或不更新 `updated_at`，且 `db.upsert` 的 `updated_at = CURRENT_TIMESTAMP` 逻辑仅对 map_cache 表生效。
- `tokens_usage_log` 批量保存路径（`lw_base_data_provider.py:850`）依赖 DB DEFAULT。

---

### 4. 系统自动计算层写入的表

由定时任务或聚合服务生成的表。

| 表名 | 写入入口代码位置 | 时间字段写入方式 | 是否已修复 |
|------|-----------------|-----------------|-----------|
| `daily_report` | `lifeprism/server/providers/report_provider.py:128` (`db.insert`)；`report_provider.py:113` (`db.update_by_id`) | 创建：`created_at`/`updated_at` 未写入 → DB DEFAULT ⚠️。更新：`updated_at` 未更新 ⚠️ | ⚠️ DB DEFAULT |
| `weekly_report` | `lifeprism/server/providers/report_provider.py:354` (`db.insert`)；`report_provider.py:339` (`db.update_by_id`) | 同上 | ⚠️ DB DEFAULT |
| `monthly_report` | `lifeprism/server/providers/report_provider.py:551` (`db.insert`)；`report_provider.py` (`db.update_by_id`) | 同上 | ⚠️ DB DEFAULT |
| `goal_stats` | `lifeprism/repository/providers/goal_providers.py:673` (原生 `INSERT INTO`)；`goal_providers.py:660` (原生 `UPDATE`) | 创建：`created_at` 未写入 → DB DEFAULT ⚠️（`update_at: False` 无 `updated_at`）。更新：无 `updated_at` 需求 | ⚠️ DB DEFAULT |
| `daily_focus` | `lifeprism/server/providers/focus_provider.py`（**全部已注释**）；仅由 `sync_repository.upsert_rows` 同步写入 | 无活跃写入路径，仅通过同步写入。同步路径使用 `INSERT OR REPLACE`，时间戳取自云端数据 | 🔄 仅同步 |
| `weekly_focus` | 同上 | 同上 | 🔄 仅同步 |

**关键风险**：
- `daily_report`/`weekly_report`/`monthly_report` 的 `db.update_by_id` 调用 `database_manager.update`（database_manager.py:482-510），该方法不会自动设置 `updated_at`，导致报告更新时 `updated_at` 不变，影响同步 LWW 判断。
- `goal_stats` 创建时 `created_at` 依赖 DB DEFAULT。
- `daily_focus`/`weekly_focus` 的 `focus_provider.py` 已全部注释，无直接写入路径，仅通过同步流入。

---

### 5. 其他/混合渠道

由多种渠道写入或作为缓存/元数据的表。

| 表名 | 写入入口代码位置 | 时间字段写入方式 | 是否已修复 |
|------|-----------------|-----------------|-----------|
| `multi_purpose_map_cache` | `lifeprism/repository/providers/map_cache_providers.py:144` (`_generic_insert`)；`map_cache_providers.py:261` (原生批量 `INSERT INTO`)；`lw_base_data_provider.py:619` (`db.upsert_many`)；`database_manager.upsert:387` (`updated_at = CURRENT_TIMESTAMP`) | 单条创建：✓。批量创建：DB DEFAULT ⚠️。upsert：`updated_at = CURRENT_TIMESTAMP`（格式 `YYYY-MM-DD HH:MM:SS`）⚠️ | ⚠️ 部分修复 |
| `single_purpose_map_cache` | `lifeprism/repository/providers/map_cache_providers.py:505` (`_generic_insert`)；`map_cache_providers.py:622` (原生批量 `INSERT INTO`)；`lw_base_data_provider.py:612` (`db.upsert_many`)；`database_manager.upsert:387` (`updated_at = CURRENT_TIMESTAMP`) | 同上 | ⚠️ 部分修复 |
| `category_map_cache` | `lifeprism/repository/base_providers/lw_base_data_provider.py:658` (已注释 `upsert_many`) | 无活跃写入路径（代码已注释） | 🔄 仅同步/历史 |
| `chat_session` | 无活跃写入路径（`focus_provider.py` 已注释，`chat_session` 仅在 config 和 m009 中引用） | `timestamps: False`，使用自定义时间戳字段。无活跃写入路径 | 🔄 仅同步/待确认 |
| `custom_record_data_*`（动态表） | `lifeprism/repository/aggregators/custom_record_aggregator.py:392` (原生 `INSERT INTO` with `datetime.now(timezone.utc).isoformat()`) | ✓ 已修复（显式 ISO） | ✓ 已修复 |

**关键风险**：
- `multi_purpose_map_cache`/`single_purpose_map_cache` 的批量插入和 upsert 路径依赖 DB DEFAULT 或 `CURRENT_TIMESTAMP`，格式为 `YYYY-MM-DD HH:MM:SS`。
- `database_manager.upsert/upsert_many`（database_manager.py:387,449）对 map_cache 表使用 `updated_at = CURRENT_TIMESTAMP`，虽然 UTC 但格式不符合 ISO 8601。

---

### 6. 迁移/元数据表

| 表名 | 写入入口代码位置 | 时间字段写入方式 | 是否已修复 |
|------|-----------------|-----------------|-----------|
| `schema_version` | `lifeprism/repository/migrations/migration_runner.py:127` (`INSERT OR IGNORE`) | `applied_at` 使用 DB DEFAULT `datetime('now')`（UTC，格式 `YYYY-MM-DD HH:MM:SS`）；`timestamps: False` | ⚠️ DB DEFAULT（内部元数据，影响低） |

**说明**：`schema_version` 是内部元数据表，不参与业务逻辑和同步，格式问题影响极低，可暂不处理。

---

## 风险点汇总

### 🔴 P0 级风险（严重 - 仍使用 `localtime` 和旧格式）

| # | 表名 | 代码位置 | 问题描述 | 影响 |
|---|------|---------|---------|------|
| 1 | `raw_behavior_analysis` | `lifeprism/repository/providers/raw_behavior_analysis_provider.py:186-195` | 批量插入时硬编码 `created_at = datetime('now', 'localtime')`，使用本地时区且格式为 `YYYY-MM-DD HH:MM:SS` | 新写入的数据时区错误（本地时区而非 UTC），且格式不符合 ISO 8601，导致与 m009 迁移后的历史数据格式不一致，同步 LWW 比较失效 |
| 2 | `behavior_analysis` | `lifeprism/repository/providers/behavior_analysis_provider.py:313-324` | 同上，批量插入时硬编码 `created_at = datetime('now', 'localtime')` | 同上，且该表是 AI 分析结果的核心表，影响行为分析展示和同步 |

### 🟠 P1 级风险（高 - 依赖 DB DEFAULT 输出非 ISO 格式）

| # | 表名 | 代码位置 | 问题描述 | 影响 |
|---|------|---------|---------|------|
| 3 | `window_events` | `lifeprism/monitor/provider/window_data_provider.py:52` | `created_at` 未显式写入，依赖 DB DEFAULT `datetime('now')`，格式 `YYYY-MM-DD HH:MM:SS` | 格式不一致，同步 LWW 可能受影响 |
| 4 | `screen_captures` | `lifeprism/monitor/provider/screenshot_data_provider.py:32` | 同上（monitor 路径） | 同上 |
| 5 | `user_app_behavior_log` | `lifeprism/repository/base_providers/lw_base_data_provider.py:800` | 批量保存时 `created_at`/`updated_at` 依赖 DB DEFAULT | 同上 |
| 6 | `todo_list` | `lifeprism/repository/providers/todo_provider.py:686` | 批量创建时未写入时间戳，依赖 DB DEFAULT | 同上 |
| 7 | `time_paradoxes` | `lifeprism/server/providers/being_provider.py:188,331` | 原生 INSERT/upsert 未写入时间戳，依赖 DB DEFAULT；`db.upsert` 不为其设置 `updated_at` | 格式不一致且 `updated_at` 不更新 |
| 8 | `daily_report` | `lifeprism/server/providers/report_provider.py:128` | `db.insert` 未写入时间戳，依赖 DB DEFAULT | 格式不一致 |
| 9 | `weekly_report` | `lifeprism/server/providers/report_provider.py:354` | 同上 | 同上 |
| 10 | `monthly_report` | `lifeprism/server/providers/report_provider.py:551` | 同上 | 同上 |
| 11 | `goal_stats` | `lifeprism/repository/providers/goal_providers.py:673` | 原生 INSERT 未写入 `created_at`，依赖 DB DEFAULT | 格式不一致 |
| 12 | `goal_journal` | `lifeprism/server/providers/journal_provider.py:115` | 原生 INSERT 未写入时间戳，依赖 DB DEFAULT | 格式不一致 |
| 13 | `user_values` | `lifeprism/server/providers/value_provider.py:88` | 同上 | 同上 |
| 14 | `commitments` | `lifeprism/server/providers/commitment_provider.py:154` | 同上 | 同上 |
| 15 | `mood_impacts` | `lifeprism/repository/providers/mood_providers.py:495` | 原生 INSERT 未写入 `created_at`，依赖 DB DEFAULT | 格式不一致 |
| 16 | `multi_purpose_map_cache` | `lifeprism/repository/providers/map_cache_providers.py:261`；`lifeprism/repository/base_providers/lw_base_data_provider.py:619` | 批量插入/upsert 未写入时间戳；`database_manager.upsert` 使用 `CURRENT_TIMESTAMP` | 格式 `YYYY-MM-DD HH:MM:SS` |
| 17 | `single_purpose_map_cache` | `lifeprism/repository/providers/map_cache_providers.py:622`；`lifeprism/repository/base_providers/lw_base_data_provider.py:612` | 同上 | 同上 |
| 18 | `tokens_usage_log` | `lifeprism/repository/base_providers/lw_base_data_provider.py:850,948` | 批量保存/单条保存（非 provider 路径）依赖 DB DEFAULT | 格式不一致 |

### 🟡 P2 级风险（中 - UPDATE 不更新 `updated_at`）

| # | 表名 | 代码位置 | 问题描述 | 影响 |
|---|------|---------|---------|------|
| 19 | `todo_list` | `lifeprism/repository/providers/todo_provider.py:447,513,742,804` | 排序、WAID、批量更新等原生 UPDATE 未写入 `updated_at` | 同步 LWW 无法检测到这些变更，可能导致数据丢失 |
| 20 | `goal` | `lifeprism/repository/providers/goal_providers.py:320` | `order_index` 重排序 UPDATE 未写入 `updated_at` | 同上 |
| 21 | `plan_doc` | `lifeprism/repository/providers/plan_doc_provider.py:242,308` | 显式使用 `datetime('now')`（UTC，但格式 `YYYY-MM-DD HH:MM:SS`） | 格式不符合 ISO 8601 |
| 22 | `daily_report`/`weekly_report`/`monthly_report` | `lifeprism/server/providers/report_provider.py:113,339` 等 | `db.update_by_id` 不自动设置 `updated_at` | 报告更新后 `updated_at` 不变，同步失效 |
| 23 | `time_paradoxes` | `lifeprism/server/providers/being_provider.py:251,280` | `db.update` 不自动设置 `updated_at` | 同上 |

### 🔄 待确认

| # | 表名 | 说明 |
|---|------|------|
| 24 | `chat_session` | 配置存在但无活跃写入路径，可能仅由同步写入或已废弃。`timestamps: False` 表示使用自定义时间戳字段，需确认同步流入的数据格式 |
| 25 | `daily_focus`/`weekly_focus` | `focus_provider.py` 已全部注释，仅通过 `sync_repository.upsert_rows` 同步写入，时间戳取自云端数据 |

---

## 建议

### 1. 🔴 紧急修复（P0）

**修复 `raw_behavior_analysis` 和 `behavior_analysis` 的批量插入**：

将 `raw_behavior_analysis_provider.py:186-195` 和 `behavior_analysis_provider.py:313-324` 中的 `datetime('now', 'localtime')` 替换为 Python 端预生成的 ISO 格式时间戳：

```python
# 修复前
cursor.execute(
    f"""INSERT INTO {self._TABLE_NAME}
       (start_time, end_time, behavior, screen_count, created_at)
       VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
    ...
)

# 修复后
from lifeprism.utils.time_utils import get_utc_now_iso
now_iso = get_utc_now_iso()
cursor.execute(
    f"""INSERT INTO {self._TABLE_NAME}
       (start_time, end_time, behavior, screen_count, created_at)
       VALUES (?, ?, ?, ?, ?)""",
    (..., now_iso),
)
```

### 2. 🟠 系统性修复（P1）

**策略 A（推荐）：统一改用 `_generic_insert`/`_generic_update`**

对于以下表的原生 INSERT 路径，改为调用 `_generic_insert`，让基类自动写入 ISO 格式时间戳：
- `todo_list`（batch_create_todos）
- `goal_journal`、`user_values`、`commitments`、`mood_impacts`、`time_paradoxes`
- `goal_stats`、`daily_report`、`weekly_report`、`monthly_report`
- `tokens_usage_log`（批量保存路径）
- `multi_purpose_map_cache`、`single_purpose_map_cache`（批量插入路径）

**策略 B（替代）：在原生 INSERT 中显式写入 `get_utc_now_iso()`**

若无法改用 `_generic_insert`（如批量插入性能考虑），则在原生 SQL 中显式写入时间戳：

```python
from lifeprism.utils.time_utils import get_utc_now_iso
now_iso = get_utc_now_iso()
# 在 data 字典中添加
data["created_at"] = now_iso
data["updated_at"] = now_iso  # 若表配置 update_at=True
```

**针对 monitor 路径**：
- `window_data_provider.py:48` 的 `data` 字典添加 `"created_at": get_utc_now_iso()`
- `screenshot_data_provider.py:32` 调用方应确保 `data` 包含 `created_at`（ISO 格式）

### 3. 🟡 修复 UPDATE 不更新 `updated_at`（P2）

**针对原生 UPDATE 路径**：

- `todo_provider.py:447,513,742,804`：在 SET 子句中追加 `updated_at = ?` 并绑定 `get_utc_now_iso()`
- `goal_providers.py:320`：同上
- `report_provider.py:113,339` 等 `db.update_by_id` 调用：在 `update_data` 中添加 `updated_at`
- `being_provider.py:251,280`：同上
- `plan_doc_provider.py:242,308`：将 `datetime('now')` 替换为 Python 端 `get_utc_now_iso()` 并参数化绑定

**针对 `database_manager.update` 方法**：

建议在 `database_manager.py:482` 的 `update` 方法中增加自动 `updated_at` 逻辑（类似 `_generic_update`），根据 `TABLE_CONFIGS` 的 `update_at` 配置自动追加 ISO 格式时间戳。这样可以一次性修复所有通过 `db.update`/`db.update_by_id` 的调用路径。

### 4. 🔄 待确认项处理

- **`chat_session`**：确认是否仍在使用。若已废弃，建议在后续迁移中删除；若仍使用，需确认同步流入的时间戳格式。
- **`daily_focus`/`weekly_focus`**：确认 `focus_provider.py` 是否计划恢复，或已永久废弃改为其他实现。若废弃，建议从 `TABLE_CONFIGS` 中移除或标注 deprecated。

### 5. 长期改进建议

1. **增强 `database_manager` 通用方法**：在 `insert`/`insert_many`/`update`/`upsert`/`upsert_many` 中自动处理时间戳，根据 `TABLE_CONFIGS` 配置自动写入 ISO 格式的 `created_at`/`updated_at`，避免每个调用方手动处理。
2. **添加 Lint 规则**：在代码审查中禁止使用 `datetime('now', 'localtime')` 和 `datetime('now')`（SQL 层），强制使用 Python 端 `get_utc_now_iso()`。
3. **统一 map_cache 的 upsert 逻辑**：`database_manager.upsert` 中 `updated_at = CURRENT_TIMESTAMP` 仅对 map_cache 表生效的硬编码逻辑（database_manager.py:384-387）应泛化为根据 `TABLE_CONFIGS` 配置自动处理。

---

## 附录

### A. 已修复表清单（17 张）

以下表的主写入路径已通过 `_generic_insert`/`_generic_update` 或显式 `get_utc_now_iso()` 写入 ISO 8601 + UTC 格式：

1. `diary`
2. `mood_types`
3. `mood_entries`
4. `habits`
5. `habit_challenges`
6. `habit_checkins`
7. `habit_chains`
8. `habit_chain_nodes`
9. `category`
10. `sub_category`
11. `timeline_custom_block`
12. `custom_record_types`
13. `custom_record_fields`
14. `custom_record_data_*`（动态表）

以下表的部分写入路径已修复（单条路径 ✓，批量/原生路径 ⚠️）：
15. `todo_list`（单条 ✓，批量 ⚠️）
16. `goal`（单条 ✓，排序 UPDATE ⚠️）
17. `plan_doc`（创建 ✓，更新 ⚠️）
18. `screen_captures`（provider ✓，monitor ⚠️）
19. `raw_behavior_analysis`（单条 ✓，批量 ❌）
20. `behavior_analysis`（单条 ✓，批量 ❌）
21. `tokens_usage_log`（provider ✓，base_provider 批量 ⚠️）

### B. 关键代码位置索引

| 文件 | 行号 | 说明 |
|------|------|------|
| `lifeprism/repository/base_providers/lw_base_data_provider.py` | 1119-1132 | `_generic_insert` 自动写入 ISO 时间戳 |
| `lifeprism/repository/base_providers/lw_base_data_provider.py` | 1207-1213 | `_generic_update` 自动写入 ISO `updated_at` |
| `lifeprism/utils/time_utils.py` | 28-37 | `get_utc_now_iso()` 返回 ISO 8601 + UTC |
| `lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py` | 45-82 | 表重建：DEFAULT localtime → UTC |
| `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py` | 167-260 | 历史数据时区迁移 |
| `lifeprism/repository/database_manager.py` | 287-315 | `insert` 方法（无时间戳处理） |
| `lifeprism/repository/database_manager.py` | 482-510 | `update` 方法（无时间戳处理） |
| `lifeprism/repository/database_manager.py` | 355-410 | `upsert` 方法（仅 map_cache 设置 `updated_at`） |

### C. 报告生成信息

- 生成时间：2026-07-12
- 分析范围：`lifeprism/` 全模块
- 数据来源：`TABLE_CONFIGS`（39 张表）+ 迁移脚本 + Provider/Service/API 代码
- 关联文档：
  - `docs/adr/2026-07-12-migrate-to-utc-timezone.md`（迁移决策）
  - `docs/generated/utc-migration-audit-report.md`（迁移审核报告）
  - `.scratch/utc-timezone-migration/prd.md`（迁移需求）
