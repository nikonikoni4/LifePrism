# API 时间格式覆盖率审查报告

> 审查日期：2026-07-12
> 审查范围：LifeWatch-AI 项目所有 API 端点的时间格式处理
> 架构要求：数据库存储 UTC ISO 8601，API 应暴露本地时区 `YYYY-MM-DD HH:MM:SS` 给前端/AI

---

## 1. API 测试覆盖率统计

### 1.1 表分类

#### A 类：可通过 API 创建的表（19 张）

| 序号 | 表名 | API 端点 | 方法 | timestamps | update_at | E2E 测试 |
|------|------|---------|------|-----------|-----------|---------|
| 1 | `todo_list` | `/todos` | POST/PUT | ✅ | ✅ | ✅ 已测 |
| 2 | `diary` | `/diary/{date}` | GET(自动创建)/PATCH/PUT | ✅ | ✅ | ✅ 已测 |
| 3 | `goal` | `/goal/goals` | POST/PATCH | ✅ | ✅ | ✅ 已测 |
| 4 | `goal_journal` | `/goal/journals` | POST/PATCH | ✅ | ✅ | ✅ 已测 |
| 5 | `plan_doc` | `/goal/plan-docs` | POST/PATCH | ✅ | ✅ | ✅ 已测 |
| 6 | `mood_types` | `/mood/types` | POST | ✅ | ❌ | ✅ 已测 |
| 7 | `mood_entries` | `/mood/entries` | POST | ✅ | ❌ | ✅ 已测 |
| 8 | `mood_impacts` | `/mood/impacts` | POST | ✅ | ❌ | ✅ 已测 |
| 9 | `habits` | `/habits` | POST | ✅ | ✅ | ✅ 已测 |
| 10 | `habit_chains` | `/chains` | POST | ✅ | ✅ | ✅ 已测 |
| 11 | `habit_chain_nodes` | `/chains/{id}/nodes` | POST | ✅ | ✅ | ✅ 已测 |
| 12 | `category` | `/category/manage` | POST | ✅ | ✅ | ✅ 已测 |
| 13 | `sub_category` | `/category/manage/{id}/sub` | POST | ✅ | ✅ | ✅ 已测 |
| 14 | `timeline_custom_block` | `/timeline/custom-blocks` | POST | ✅ | ✅ | ✅ 已测 |
| 15 | `user_values` | `/value/` | POST | ✅ | ✅ | ✅ 已测 |
| 16 | `commitments` | `/commitment/` | POST | ✅ | ✅ | ✅ 已测 |
| 17 | `custom_record_types` | `/custom-records/types` | POST | ✅ | ✅ | ✅ 已测 |
| 18 | `time_paradoxes` | `/being/{mode}` | POST/PUT | ✅ | ✅ | ⚠️ 未测 |
| 19 | `chat_session` | `/chatbot/sessions` | POST/PATCH | ❌ | ❌ | ⚠️ 未测 |

**说明**：
- `custom_record_fields` 表随 `custom_record_types` 创建时一并写入（子操作），归入 A 类但未独立计数
- `custom_record_data_*` 动态表通过 `POST /custom-records/{type_id}/entries` 创建，归入 A 类但未独立计数
- `time_paradoxes` 通过 `being_api` 的 POST/PUT 端点写入，有 API 端点但未纳入 E2E 测试
- `chat_session` 配置为 `timestamps: False`（自定义时间戳），有 API 端点但未纳入 E2E 测试

#### B 类：不可通过 API 创建的表（20 张）

| 序号 | 表名 | 数据来源 | timestamps | update_at |
|------|------|---------|-----------|-----------|
| 1 | `habit_checkins` | 习惯引擎/系统自动 | ✅ | ❌ |
| 2 | `habit_challenges` | 系统/LLM 生成 | ✅ | ✅ |
| 3 | `screen_captures` | 监控采集层 | ✅ | ❌ |
| 4 | `window_events` | 监控采集层 | ✅ | ❌ |
| 5 | `raw_behavior_analysis` | 系统批量计算 | ✅ | ❌ |
| 6 | `behavior_analysis` | 系统批量计算 | ✅ | ✅ |
| 7 | `user_app_behavior_log` | 监控/计算层 | ✅ | ✅ |
| 8 | `category_map_cache` | 系统缓存 | ✅ | ✅ |
| 9 | `single_purpose_map_cache` | 系统缓存 | ✅ | ✅ |
| 10 | `multi_purpose_map_cache` | 系统缓存 | ✅ | ✅ |
| 11 | `daily_focus` | 系统计算 | ✅ | ✅ |
| 12 | `weekly_focus` | 系统计算 | ✅ | ✅ |
| 13 | `daily_report` | 系统生成 | ✅ | ✅ |
| 14 | `weekly_report` | 系统生成 | ✅ | ✅ |
| 15 | `monthly_report` | 系统生成 | ✅ | ✅ |
| 16 | `goal_stats` | 系统计算 | ✅ | ❌ |
| 17 | `tokens_usage_log` | LLM/系统记录 | ✅ | ❌ |
| 18 | `schema_version` | 系统元数据 | ❌ | ❌ |
| 19 | `custom_record_fields` | 随类型创建（子操作） | ✅ | ❌ |
| 20 | `custom_record_data_*` | API 创建（动态表） | ✅ | ✅ |

### 1.2 覆盖率

| 指标 | 数值 |
|------|------|
| 总表数 | 39 |
| A 类（有 API 端点） | 19 张 |
| B 类（无 API 端点） | 20 张 |
| **潜在 API 覆盖率** | **19/39 ≈ 48.7%** |
| E2E 已测表数 | 17 张 |
| **已测 API 覆盖率** | **17/39 ≈ 43.6%** |
| 未测 A 类表 | `time_paradoxes`、`chat_session` |

---

## 2. API 端点时间格式处理详情

### 2.1 todos_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/todos` | POST | `date`, `expected_finished_at` | `YYYY-MM-DD` | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/todos/{id}` | PUT | `date`, `expected_finished_at` | `YYYY-MM-DD` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/todos/waid/reorder` | PUT | 无 | - | 无 | - | - |
| `/todos/{id}/waid` | PUT | 无 | - | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

**问题**：响应直接返回 DB 存储的 UTC ISO 8601 格式（如 `2026-07-12T07:08:57.529846+00:00`），未转换为本地时区 `YYYY-MM-DD HH:MM:SS`。

### 2.2 diary_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/diary/{date}` | GET | `date`（路径参数） | `YYYY-MM-DD` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/diary/{date}` | PATCH | `date`（路径参数） | `YYYY-MM-DD` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/diary/{date}/content` | PUT | `date`（路径参数） | `YYYY-MM-DD` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

**说明**：GET `/diary/{date}` 会在日记不存在时自动创建。

### 2.3 goal_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/goal/goals` | POST | `start_date`, `expected_finished_at` | `YYYY-MM-DD` | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/goal/goals/{id}` | PATCH | `start_date`, `expected_finished_at` | `YYYY-MM-DD` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/goal/journals` | POST | `journal_date` | `YYYY-MM-DD` | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/goal/journals/{id}` | PATCH | `journal_date` | `YYYY-MM-DD` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/goal/plan-docs` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/goal/plan-docs/{id}` | PATCH | 无 | - | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

**问题**：`goal_journal` PATCH 不刷新 `updated_at`（P2 遗留问题）；`plan_doc` PATCH 仅接受 `status`/`order_index`，content 走文件存储，不触发 DB 行 `updated_at` 刷新。

### 2.4 mood_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/mood/types` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/mood/entries` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/mood/impacts` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.5 habit_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/habits` | POST | `start_date`, `end_date`, `trigger_time`, `paused_at` | `YYYY-MM-DD` / `YYYY-MM-DD HH:MM:SS` | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/chains` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/chains/{id}/nodes` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.6 category_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/category/manage` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/category/manage/{id}/sub` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.7 timeline_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/timeline/custom-blocks` | POST | `start_time`, `end_time` | ISO `YYYY-MM-DDTHH:MM:SS` | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

**注意**：请求 `start_time`/`end_time` 要求 ISO 格式（含 `T` 分隔符），与 `activity_api` 的 `YYYY-MM-DD HH:MM:SS` 格式不一致。

### 2.8 value_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/value/` | POST | 无 | - | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.9 commitment_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/commitment/` | POST | 无 | - | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.10 custom_records_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/custom-records/types` | POST | 无 | - | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/custom-records/{type_id}/entries` | POST | 无 | - | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.11 being_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/being/{mode}` | POST | `time`（业务时间字段） | 未明确 | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/being/{mode}/{version}` | PUT | `time` | 未明确 | `created_at`, `updated_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

### 2.12 activity_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/activity/logs` | GET | `start_time`, `end_time`（查询参数） | `YYYY-MM-DD HH:MM:SS`（正则强制） | `start_time`, `end_time` | `YYYY-MM-DD HH:MM:SS`（DB 透传） | ❌ 无转换 |

**注意**：查询参数强制 `YYYY-MM-DD HH:MM:SS` 格式（pattern 正则），响应直接透传 DB 中的 `start_time`/`end_time`（本地时间格式，非 UTC）。

### 2.13 report_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/report/daily/{date}` | GET | `date`（路径参数） | `YYYY-MM-DD` | `date` | `YYYY-MM-DD`（DB 透传） | ❌ 无转换 |
| `/report/weekly/{date}` | GET | `date` | `YYYY-MM-DD` | `week_start_date` | `YYYY-MM-DD`（DB 透传） | ❌ 无转换 |
| `/report/monthly/{date}` | GET | `date` | `YYYY-MM-DD` | `month_start_date` | `YYYY-MM-DD`（DB 透传） | ❌ 无转换 |

**说明**：report_api 仅有 GET/DELETE，无 POST/PUT，报告由系统自动生成。

### 2.14 chatbot_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/chatbot/sessions` | POST | 无 | - | `created_at`, `updated_at` | `datetime.isoformat()` | ❌ 无时区转换 |
| `/chatbot/sessions/{id}` | PATCH | 无 | - | `created_at`, `updated_at` | `datetime.isoformat()` | ❌ 无时区转换 |

**问题**：`chatbot_service.py` 第 143-146 行直接调用 `session.created_at.isoformat()` 输出，取决于 `ChatSession` ORM 模型的 `created_at` 字段类型。若为 naive datetime，则输出无时区信息；若为 aware datetime，则输出带时区的 ISO 格式。

### 2.15 taskpool_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/taskpool/sync` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |
| `/taskpool/regenerate-summary` | POST | 无 | - | `created_at` | UTC ISO 8601（DB 透传） | ❌ 无转换 |

**说明**：`taskpool_service.py` 的 `db_to_todo_item` 函数直接透传 `db_item.get("created_at")`，无时间格式转换。

### 2.16 sync_cloud_api.py

| 端点 | 方法 | 请求时间字段 | 请求格式 | 响应时间字段 | 响应格式 | 转换逻辑 |
|------|------|------------|---------|------------|---------|---------|
| `/api/sync/pull` | POST | `start_time`, `end_time` | `YYYY-MM-DD HH:MM:SS` | `sync_time` | UTC ISO 8601 | ✅ 使用 `datetime.now(timezone.utc).isoformat()` |
| `/api/sync/push` | POST | 无 | - | `sync_time` | UTC ISO 8601 | ✅ 同上 |
| `/api/sync/heartbeat` | POST | 无 | - | `sync_time` | UTC ISO 8601 | ✅ 同上 |

**说明**：sync_cloud_api 是唯一显式使用 `datetime.now(timezone.utc).isoformat()` 生成响应时间的 API，但这是同步业务时间，非 DB 记录时间戳。

### 2.17 sync_status_api.py / cloud_config_api.py / system_api.py / setting_api.py / add_on_api.py

| API 文件 | 端点 | 方法 | 时间字段处理 |
|---------|------|------|------------|
| `sync_status_api.py` | `/api/sync/status` | GET/POST | 无时间字段响应 |
| `cloud_config_api.py` | `/api/sync/generate-cloud-config` | POST | 无时间字段响应 |
| `system_api.py` | `/system/*` | GET | 无时间字段响应 |
| `setting_api.py` | `/setting/*` | GET/PATCH/POST | 不涉及业务表时间字段 |
| `add_on_api.py` | `/api/v2/add_on/expand_dir` | POST | `created_at`（UTC ISO 8601 透传） |

---

## 3. Schema 时间字段定义

### 3.1 时间字段汇总

| Schema 文件 | Schema 类 | 字段 | 类型 | 验证器 | 格式要求 |
|------------|----------|------|------|--------|---------|
| `todo_schemas.py` | TodoItem | `created_at` | `str \| None` | ❌ 无 | 无 |
| `todo_schemas.py` | TodoItem | `date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `todo_schemas.py` | TodoItem | `expected_finished_at` | `str \| None` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `diary_schemas.py` | DiaryResponse | `created_at` | `str` | ❌ 无 | 无 |
| `diary_schemas.py` | DiaryResponse | `updated_at` | `str \| None` | ❌ 无 | 无 |
| `goal_schemas.py` | GoalResponse | `created_at` | `str` | ❌ 无 | 无 |
| `goal_schemas.py` | GoalResponse | `finish_time` | `str \| None` | ❌ 无 | 无 |
| `goal_schemas.py` | GoalResponse | `start_date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `goal_schemas.py` | GoalResponse | `expected_finished_at` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `goal_schemas.py` | GoalJournalResponse | `created_at` | `str` | ❌ 无 | 无 |
| `goal_schemas.py` | GoalJournalResponse | `journal_date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `plan_doc_schemas.py` | PlanDocResponse | `created_at` | `str` | ❌ 无 | 无 |
| `plan_doc_schemas.py` | PlanDocResponse | `updated_at` | `str \| None` | ❌ 无 | 无 |
| `mood_schemas.py` | MoodTypeResponse | `created_at` | `str` | ❌ 无 | 无 |
| `mood_schemas.py` | MoodEntryResponse | `created_at` | `str` | ❌ 无 | 无 |
| `mood_schemas.py` | MoodImpactResponse | `created_at` | `str` | ❌ 无 | 无 |
| `habit_schemas.py` | HabitResponse | `created_at` | `str` | ❌ 无 | 无 |
| `habit_schemas.py` | HabitResponse | `completed_at` | `str \| None` | ❌ 无 | 无 |
| `habit_schemas.py` | HabitResponse | `finished_at` | `str \| None` | ❌ 无 | 无 |
| `habit_schemas.py` | HabitResponse | `paused_at` | `str \| None` | ❌ 无 | 无 |
| `habit_schemas.py` | HabitResponse | `start_date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `habit_schemas.py` | HabitResponse | `end_date` | `str \| None` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `habit_schemas.py` | HabitChainResponse | `created_at` | `str` | ❌ 无 | 无 |
| `habit_schemas.py` | HabitChainNodeResponse | `created_at` | `str` | ❌ 无 | 无 |
| `category_schemas.py` | CategoryResponse | `created_at` | `str \| None` | ❌ 无 | 无 |
| `category_schemas.py` | SubCategoryResponse | `created_at` | `str \| None` | ❌ 无 | 无 |
| `timeline_schemas.py` | CustomBlockResponse | `start_time` | `str` | ❌ 无 | ISO `YYYY-MM-DDTHH:MM:SS`（约定） |
| `timeline_schemas.py` | CustomBlockResponse | `end_time` | `str` | ❌ 无 | ISO `YYYY-MM-DDTHH:MM:SS`（约定） |
| `timeline_schemas.py` | CustomBlockResponse | `created_at` | `str \| None` | ❌ 无 | 无 |
| `timeline_schemas.py` | CustomBlockResponse | `updated_at` | `str \| None` | ❌ 无 | 无 |
| `value_schemas.py` | ValueResponse | `created_at` | `str` | ❌ 无 | 无 |
| `value_schemas.py` | ValueResponse | `updated_at` | `str \| None` | ❌ 无 | 无 |
| `commitment_schemas.py` | CommitmentResponse | `created_at` | `str` | ❌ 无 | 无 |
| `commitment_schemas.py` | CommitmentResponse | `updated_at` | `str \| None` | ❌ 无 | 无 |
| `custom_records_schemas.py` | CustomRecordTypeResponse | `created_at` | `str` | ❌ 无 | 无 |
| `custom_records_schemas.py` | CustomRecordTypeResponse | `updated_at` | `str` | ❌ 无 | 无 |
| `being_schemas.py` | BeingResponse | `created_at` | `str \| None` | ❌ 无 | 无 |
| `being_schemas.py` | BeingResponse | `updated_at` | `str \| None` | ❌ 无 | 无 |
| `being_schemas.py` | BeingResponse | `time` | `str` | ❌ 无 | 无 |
| `activity_schemas.py` | ActivityLogResponse | `start_time` | `str` | ❌ 无 | `YYYY-MM-DD HH:MM:SS`（正则） |
| `activity_schemas.py` | ActivityLogResponse | `end_time` | `str` | ❌ 无 | `YYYY-MM-DD HH:MM:SS`（正则） |
| `report_schemas.py` | DailyReportResponse | `date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `report_schemas.py` | WeeklyReportResponse | `week_start_date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `report_schemas.py` | MonthlyReportResponse | `month_start_date` | `str` | ❌ 无 | `YYYY-MM-DD`（约定） |
| `chatbot_schemas.py` | ChatSessionResponse | `created_at` | `str` | ❌ 无 | 无 |
| `chatbot_schemas.py` | ChatSessionResponse | `updated_at` | `str` | ❌ 无 | 无 |
| `chatbot_schemas.py` | ChatSessionResponse | `timestamp` | `str \| None` | ❌ 无 | 无 |
| `add_on_schemas.py` | ExpandDirItem | `created_at` | `str` | ❌ 无 | 无 |
| `sync.py` | SyncTimeRangeRequest | `start_time` | `str` | ❌ 无 | `YYYY-MM-DD HH:MM:SS`（注释） |
| `sync.py` | SyncTimeRangeRequest | `end_time` | `str` | ❌ 无 | `YYYY-MM-DD HH:MM:SS`（注释） |

### 3.2 Schema 关键发现

1. **所有时间字段均为 `str` 类型**：无一使用 `datetime` 类型，无法利用 Pydantic 的自动解析能力
2. **无任何 `@field_validator`**：22 个 schema 文件中没有任何一个使用 `@field_validator` 做时间格式转换或校验
3. **格式约定仅在注释/Field description 中**：如 `sync.py` 的 `# Format: YYYY-MM-DD HH:MM:SS`，无运行时校验
4. **`activity_schemas.py` 是唯一有正则强制的**：查询参数通过 pattern 正则强制 `YYYY-MM-DD HH:MM:SS` 格式

---

## 4. 数据正确性验证

### 4.1 A 类表数据验证（E2E 已测 17 张）

| 表名 | created_at 格式 | updated_at 格式 | 业务时间字段 | 存储格式 | 状态 |
|------|----------------|----------------|------------|---------|------|
| `todo_list` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | `date`, `expected_finished_at` | `YYYY-MM-DD` | ✅ 正常 |
| `diary` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | `date` | `YYYY-MM-DD` | ✅ 正常 |
| `goal` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | `start_date`, `expected_finished_at` | `YYYY-MM-DD` | ✅ 正常 |
| `goal_journal` | ✅ UTC ISO 8601 | ⚠️ UPDATE 不刷新 | `journal_date` | `YYYY-MM-DD` | ⚠️ P2 问题 |
| `plan_doc` | ✅ UTC ISO 8601 | ⚠️ PATCH 限制 | 无 | - | ⚠️ P2 问题 |
| `mood_types` | ✅ UTC ISO 8601 | N/A (无 updated_at) | 无 | - | ✅ 正常 |
| `mood_entries` | ✅ UTC ISO 8601 | N/A | 无 | - | ✅ 正常 |
| `mood_impacts` | ✅ UTC ISO 8601 | N/A | 无 | - | ✅ 正常 |
| `habits` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | `start_date`, `end_date`, `trigger_time` | `YYYY-MM-DD` / `YYYY-MM-DD HH:MM:SS` | ✅ 正常 |
| `habit_chains` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |
| `habit_chain_nodes` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |
| `category` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |
| `sub_category` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |
| `timeline_custom_block` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | `start_time`, `end_time` | ISO `YYYY-MM-DDTHH:MM:SS` | ✅ 正常 |
| `user_values` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |
| `commitments` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |
| `custom_record_types` | ✅ UTC ISO 8601 | ✅ UTC ISO 8601 | 无 | - | ✅ 正常 |

### 4.2 A 类表数据验证（未测 2 张）

| 表名 | created_at 格式 | updated_at 格式 | 业务时间字段 | 存储格式 | 状态 |
|------|----------------|----------------|------------|---------|------|
| `time_paradoxes` | ⚠️ 未验证 | ⚠️ 未验证 | `time` | ⚠️ 未验证 | ⚠️ 需测试 |
| `chat_session` | ⚠️ 自定义时间戳 | ⚠️ 自定义时间戳 | `timestamp` | ⚠️ `datetime.isoformat()` 输出 | ⚠️ 需测试 |

### 4.3 B 类表数据状态（参考数据流审计报告）

| 表名 | 数据来源 | created_at | updated_at | 风险等级 |
|------|---------|-----------|-----------|---------|
| `habit_checkins` | 习惯引擎 | ⚠️ 依赖 DB DEFAULT | N/A | P1 |
| `habit_challenges` | 系统/LLM | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `screen_captures` | 监控采集 | ⚠️ 依赖 DB DEFAULT | N/A | P1 |
| `window_events` | 监控采集 | ⚠️ 依赖 DB DEFAULT | N/A | P1 |
| `raw_behavior_analysis` | 系统计算 | 🔴 硬编码 `datetime('now','localtime')` | N/A | P0 |
| `behavior_analysis` | 系统计算 | 🔴 硬编码 `datetime('now','localtime')` | ⚠️ 批量插入缺失 | P0 |
| `user_app_behavior_log` | 监控/计算 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `category_map_cache` | 系统缓存 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `single_purpose_map_cache` | 系统缓存 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `multi_purpose_map_cache` | 系统缓存 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `daily_focus` | 系统计算 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `weekly_focus` | 系统计算 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `daily_report` | 系统生成 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `weekly_report` | 系统生成 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `monthly_report` | 系统生成 | ⚠️ 依赖 DB DEFAULT | ⚠️ 依赖 DB DEFAULT | P1 |
| `goal_stats` | 系统计算 | ⚠️ 依赖 DB DEFAULT | N/A | P1 |
| `tokens_usage_log` | LLM/系统 | ⚠️ 依赖 DB DEFAULT | N/A | P1 |
| `schema_version` | 系统元数据 | N/A (timestamps: False) | N/A | - |

---

## 5. 发现的问题

### 5.1 🔴 P0 严重问题：API 响应未转换时区

**问题描述**：所有 API 端点的响应直接透传数据库存储的 UTC ISO 8601 格式（如 `2026-07-12T07:08:57.529846+00:00`），未转换为架构要求的本地时区 `YYYY-MM-DD HH:MM:SS` 格式。

**影响范围**：全部 21 个 API 文件、所有包含时间字段的响应

**违反约束**：用户声明的架构要求"数据库存储 UTC ISO 8601，API 应暴露本地时区 `YYYY-MM-DD HH:MM:SS` 给前端/AI"

**根因**：
- Schema 时间字段全部为 `str` 类型，直接接收 DB 字典值
- 无 `@field_validator` 做格式转换
- Provider/Service 层直接返回 DB 查询结果，无后处理

**示例**：
```python
# taskpool_service.py - db_to_todo_item 函数
created_at=db_item.get("created_at"),  # 直接透传 UTC ISO 8601 字符串

# value_provider.py - get_values 方法
return [dict(zip(columns, row)) for row in cursor.fetchall()]  # 直接返回 DB 字典
```

### 5.2 🟡 P1 问题：Schema 缺少时间格式验证

**问题描述**：22 个 schema 文件中没有任何一个使用 `@field_validator` 做时间格式校验或转换。

**影响**：
- 无法保证响应时间格式的一致性
- 无法在运行时捕获格式异常
- 前端/AI 消费者可能收到不可预期的格式

### 5.3 🟡 P1 问题：请求时间格式不一致

**问题描述**：不同 API 端点对请求中时间字段的格式要求不一致。

| API | 格式要求 | 校验方式 |
|-----|---------|---------|
| `timeline_api` | `YYYY-MM-DDTHH:MM:SS`（ISO 含 T） | 无运行时校验 |
| `activity_api` | `YYYY-MM-DD HH:MM:SS`（空格分隔） | ✅ 正则强制 |
| `todos_api` / `goal_api` / `diary_api` / `habit_api` | `YYYY-MM-DD`（仅日期） | 无运行时校验 |
| `sync.py` | `YYYY-MM-DD HH:MM:SS` | 仅注释说明 |

### 5.4 🟢 P2 问题：goal_journal UPDATE 不刷新 updated_at

**问题描述**：`goal_journal` 表配置了 `update_at: True`，但 PATCH `/goal/journals/{id}` 端点不刷新 `updated_at` 字段。

**状态**：遗留问题，已在 E2E 测试报告中记录

### 5.5 🟢 P2 问题：plan_doc PATCH 字段范围限制

**问题描述**：`plan_doc` PATCH 仅接受 `status`/`order_index`，content 走文件存储路径，不触发 DB 行 `updated_at` 刷新。

**状态**：遗留问题，已在 E2E 测试报告中记录

### 5.6 🟢 P2 问题：B 类表 P0 风险（遗留）

**问题描述**：`raw_behavior_analysis` 和 `behavior_analysis` 表的批量 INSERT 硬编码 `datetime('now', 'localtime')`，输出本地时间格式而非 UTC ISO 8601。

**状态**：已在数据流审计报告中记录，属于 B 类表（非 API 创建），本次审查不再展开

### 5.7 🟢 P2 问题：chatbot_api 时间格式不确定

**问题描述**：`chatbot_service.py` 使用 `session.created_at.isoformat()` 输出时间，取决于 ORM 模型字段类型：
- 若为 naive datetime → 输出 `2026-07-12T10:30:00`（无时区）
- 若为 aware datetime → 输出 `2026-07-12T10:30:00+00:00`（UTC ISO 8601）

**建议**：需检查 `ChatSession` ORM 模型确认具体输出格式

---

## 6. 总结

### 6.1 覆盖率总结

| 指标 | 数值 |
|------|------|
| 总表数 | 39 |
| A 类（有 API 端点） | 19 张（48.7%） |
| B 类（无 API 端点） | 20 张（51.3%） |
| E2E 已测 | 17 张（43.6%） |
| 未测 A 类 | 2 张（`time_paradoxes`、`chat_session`） |

### 6.2 数据正确性总结

| 维度 | 状态 |
|------|------|
| A 类表 DB 存储格式（created_at/updated_at） | ✅ 17/17 已测表通过 UTC ISO 8601 |
| A 类表业务时间字段 | ✅ 正确存储（`YYYY-MM-DD` 或 ISO 格式） |
| B 类表 DB 存储格式 | ⚠️ 多数依赖 DB DEFAULT，2 张表 P0 风险 |
| **API 响应时区转换** | **🔴 全部未转换，直接返回 UTC ISO 8601** |
| Schema 时间字段验证 | 🔴 无任何 `@field_validator` |
| 请求时间格式一致性 | ⚠️ 不同 API 格式要求不一致 |

### 6.3 关键结论

1. **数据库存储层正确**：17 张 A 类已测表的 `created_at`/`updated_at` 全部以 UTC ISO 8601 格式存储，符合架构要求

2. **API 暴露层不合规**：所有 API 响应直接透传 DB 的 UTC ISO 8601 格式，未转换为本地时区 `YYYY-MM-DD HH:MM:SS`，**违反架构要求**

3. **Schema 层缺失验证**：22 个 schema 文件无任何时间格式验证器，无法保证响应格式一致性

4. **请求格式不统一**：`timeline_api`（ISO 含 T）、`activity_api`（空格分隔）、其他 API（仅日期）三种格式并存

5. **修复建议**：需在 Schema 层或 Provider/Service 层增加 UTC → 本地时区的格式转换逻辑，推荐在 Schema 响应模型中添加 `@field_validator` 统一处理

---

*报告结束*
