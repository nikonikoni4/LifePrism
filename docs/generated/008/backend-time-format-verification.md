# Backend Time Format Verification Report

> **生成时间**: 2026-07-12
> **数据来源**: 实际数据库查询结果
> **数据库路径**: `D:\数据文档\lifeprismData\dataset\lifewatch_ai.db`

---

## 第一部分：格式统计

### 1. 标准格式 (`YYYY-MM-DD HH:MM:SS`)

**SQLite DEFAULT 格式**，空格分隔，无 T，秒级精度

| 表名 | 字段名 | 示例值 |
|------|--------|--------|
| behavior_analysis | created_at | `2026-06-26 10:04:47` |
| behavior_analysis | end_time | `2026-06-25 22:50:00` |
| behavior_analysis | start_time | `2026-06-25 22:40:00` |
| behavior_analysis | updated_at | `2026-07-10 15:42:26` |
| category | created_at | `2025-12-03 20:49:37` |
| category | updated_at | `2026-07-10 15:42:26` |
| category_map_cache | created_at | `2026-01-02 01:24:19` |
| category_map_cache | updated_at | `2026-01-02 01:24:19` |
| custom_record_fields | created_at | `2026-07-10 16:33:56` |
| custom_record_types | created_at | `2026-07-10 16:33:56` |
| custom_record_types | updated_at | `2026-07-10 16:33:56` |
| daily_focus | created_at | `2026-01-23 09:46:38` |
| daily_focus | updated_at | `2026-07-10 15:42:27` |
| daily_report | created_at | `2026-07-10 00:37:18` |
| daily_report | updated_at | `2026-07-10 00:37:18` |
| diary | created_at | `2026-07-11 10:09:20` |
| diary | updated_at | `2026-07-11 10:09:20` |
| goal | created_at | `2026-07-04 16:16:13` |
| goal | updated_at | `2026-07-10 15:42:26` |
| goal_journal | created_at | `2026-02-04 12:01:15` |
| goal_journal | updated_at | `2026-07-10 15:42:27` |
| goal_stats | created_at | `2026-01-23 20:33:59` |
| habit_chain_nodes | created_at | `2026-04-10 08:59:06` |
| habit_chain_nodes | updated_at | `2026-04-10 09:01:59` |
| habit_chains | created_at | `2026-03-15 07:20:49` |
| habit_chains | updated_at | `2026-03-15 07:23:12` |
| habit_challenges | created_at | `2026-05-15 00:19:28` |
| habit_checkins | completed_at | `2026-05-15 00:19:38` |
| habit_checkins | created_at | `2026-05-15 00:19:38` |
| habits | created_at | `2026-04-10 08:50:31` |
| habits | updated_at | `2026-04-10 08:50:31` |
| monthly_report | created_at | `2026-07-02 11:21:53` |
| monthly_report | updated_at | `2026-07-02 11:21:53` |
| mood_entries | created_at | `2026-07-11 11:51:03` |
| mood_impacts | created_at | `2026-05-25 08:42:44` |
| mood_types | created_at | `2026-05-20 12:27:01` |
| multi_purpose_map_cache | created_at | `2026-07-10 23:38:18` |
| multi_purpose_map_cache | updated_at | `2026-07-10 23:38:18` |
| plan_doc | created_at | `2026-07-04 16:16:17` |
| plan_doc | updated_at | `2026-07-04 08:17:24` |
| raw_behavior_analysis | created_at | `2026-06-27 10:02:46` |
| raw_behavior_analysis | end_time | `2026-06-27 02:00:00` |
| raw_behavior_analysis | start_time | `2026-06-27 01:50:00` |
| schema_version | applied_at | `2026-07-10 15:42:27` |
| screen_captures | captured_at | `2026-06-29 18:59:59` |
| screen_captures | created_at | `2026-06-29 18:59:59` |
| single_purpose_map_cache | created_at | `2026-07-08 10:00:52` |
| single_purpose_map_cache | updated_at | `2026-07-08 10:00:52` |
| sub_category | created_at | `2026-02-10 10:33:55` |
| sub_category | updated_at | `2026-07-10 15:42:26` |
| time_paradoxes | created_at | `2026-01-09 18:10:07` |
| time_paradoxes | updated_at | `2026-01-09 18:10:07` |
| timeline_custom_block | created_at | `2026-07-11 11:40:05` |
| timeline_custom_block | end_time | `2026-07-11 19:40:00` |
| timeline_custom_block | start_time | `2026-07-11 19:00:00` |
| timeline_custom_block | updated_at | `2026-07-11 11:40:05` |
| todo_list | created_at | `2026-07-06 09:55:21` |
| todo_list | updated_at | `2026-07-10 15:42:26` |
| tokens_usage_log | created_at | `2026-07-11 23:34:57` |
| user_app_behavior_log | created_at | `2026-07-10 23:38:18` |
| user_app_behavior_log | end_time | `2026-07-10 23:37:37` |
| user_app_behavior_log | start_time | `2026-07-10 23:36:06` |
| weekly_focus | created_at | `2026-01-05 13:48:01` |
| weekly_focus | updated_at | `2026-07-10 15:42:27` |
| weekly_report | created_at | `2026-07-10 00:37:21` |
| weekly_report | updated_at | `2026-07-10 00:37:21` |
| window_events | created_at | `2026-07-12 00:35:28` |
| window_events | timestamp | `2026-07-12 00:35:27` |

**总计**: 68 个字段

### 3. ISO 格式（带 T 和微秒）

**格式**: `YYYY-MM-DDTHH:MM:SS.ffffff`

| 表名 | 字段名 | 示例值 |
|------|--------|--------|
| chat_session | created_at | `2026-02-25T10:25:16.030220` |
| chat_session | updated_at | `2026-02-25T10:25:16.054716` |
| habit_challenges | updated_at | `2026-05-15T00:19:32.413120` |

**总计**: 3 个字段

### 4. 日期格式 (`YYYY-MM-DD`)

**纯日期字段**，无时间部分

| 表名 | 字段名 | 示例值 |
|------|--------|--------|
| daily_focus | date | `2026-01-23` |
| daily_report | date | `2026-07-09` |
| diary | date | `2026-07-10` |
| goal | start_date | `2026-07-04` |
| goal_journal | date | `2026-02-04` |
| goal_stats | date | `2026-01-23` |
| habit_challenges | end_date | `2026-06-12` |
| habit_challenges | start_date | `2026-05-15` |
| habit_checkins | date | `2026-05-15` |
| monthly_report | date | `2026-07-01` |
| todo_list | date | `2026-07-06` |
| weekly_report | date | `2026-07-05` |

**总计**: 12 个字段

### 5. 时间格式 (`HH:MM` 或 `HH:MM:SS`)

**纯时间字段**，无日期部分

| 表名 | 字段名 | 示例值 |
|------|--------|--------|
| goal_journal | time | `12:01` |
| habit_chain_nodes | trigger_time | `17:00` |

**总计**: 2 个字段

### 6. 整数格式

**用于 year, month, week_num 等字段**

| 表名 | 字段名 | 示例值 |
|------|--------|--------|
| weekly_focus | month | `1` |
| weekly_focus | week_num | `2` |
| weekly_focus | year | `2026` |

**总计**: 3 个字段

### 7. 空值字段

**值为 NULL 的字段**，可能是可选字段

| 表名 | 字段名 |
|------|--------|
| goal | expected_finished_at |
| goal | time_invested_updated_at |
| habit_challenges | finished_at |
| habits | paused_at |
| mood_entries | updated_at |
| todo_list | actual_finished_at |
| todo_list | expected_finished_at |
| user_app_behavior_log | updated_at |

**总计**: 8 个字段

---

## 第二部分：异常字段

### 1. 同表内格式不一致

#### todo_list

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-07-06 09:55:21` |
| updated_at | STANDARD | `2026-07-10 15:42:26` |
| date | DATE_ONLY | `2026-07-06` |

#### daily_focus

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-01-23 09:46:38` |
| updated_at | STANDARD | `2026-07-10 15:42:27` |
| date | DATE_ONLY | `2026-01-23` |

#### goal

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-07-04 16:16:13` |
| updated_at | STANDARD | `2026-07-10 15:42:26` |
| start_date | DATE_ONLY | `2026-07-04` |

#### goal_journal

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-02-04 12:01:15` |
| updated_at | STANDARD | `2026-07-10 15:42:27` |
| date | DATE_ONLY | `2026-02-04` |
| time | TIME_ONLY | `12:01` |

#### goal_stats

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-01-23 20:33:59` |
| date | DATE_ONLY | `2026-01-23` |

#### daily_report

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-07-10 00:37:18` |
| updated_at | STANDARD | `2026-07-10 00:37:18` |
| date | DATE_ONLY | `2026-07-09` |

#### weekly_report

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-07-10 00:37:21` |
| updated_at | STANDARD | `2026-07-10 00:37:21` |
| date | DATE_ONLY | `2026-07-05` |

#### monthly_report

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-07-02 11:21:53` |
| updated_at | STANDARD | `2026-07-02 11:21:53` |
| date | DATE_ONLY | `2026-07-01` |

#### diary

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-07-11 10:09:20` |
| updated_at | STANDARD | `2026-07-11 10:09:20` |
| date | DATE_ONLY | `2026-07-10` |

#### habit_challenges

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-05-15 00:19:28` |
| updated_at | ISO_WITH_MICROSECONDS | `2026-05-15T00:19:32.413120` |
| start_date | DATE_ONLY | `2026-05-15` |
| end_date | DATE_ONLY | `2026-06-12` |

#### habit_checkins

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-05-15 00:19:38` |
| date | DATE_ONLY | `2026-05-15` |
| completed_at | STANDARD | `2026-05-15 00:19:38` |

#### habit_chain_nodes

| 字段名 | 格式 | 示例值 |
|--------|------|--------|
| created_at | STANDARD | `2026-04-10 08:59:06` |
| updated_at | STANDARD | `2026-04-10 09:01:59` |
| trigger_time | TIME_ONLY | `17:00` |

### 2. 无数据字段

以下字段所在表无数据，无法验证格式：

- `commitments.created_at`
- `commitments.updated_at`
- `user_values.created_at`
- `user_values.updated_at`

**总计**: 4 个字段

**注意**: 这些字段需要查看代码确认格式

---

## 第三部分：验证结果

### 统计摘要

| 格式类型 | 字段数量 | 占比 |
|---------|---------|------|
| 标准格式 (`YYYY-MM-DD HH:MM:SS`) | 68 | 68.0% |
| ISO 格式（带 T，无微秒） | 0 | 0.0% |
| ISO 格式（带 T 和微秒） | 3 | 3.0% |
| 日期格式 | 12 | 12.0% |
| 时间格式 | 2 | 2.0% |
| 整数格式 | 3 | 3.0% |
| 空值 | 8 | 8.0% |
| 无数据 | 4 | 4.0% |
| **总计** | **100** | **100%** |

### 关键发现

#### 🔴 格式不一致问题

- **SQLite DEFAULT 格式**: `YYYY-MM-DD HH:MM:SS` (68 个字段)
- **Python `.isoformat()` 格式**: `YYYY-MM-DDTHH:MM:SS[.ffffff]` (3 个字段)

**影响**:
1. 同一表内 `created_at` 和 `updated_at` 可能格式不一致
2. 云端同步时可能因格式不一致判断为"需要更新"
3. 字符串比较可能出错（`YYYY-MM-DD HH:MM:SS` < `YYYY-MM-DDTHH:MM:SS`）

#### 🟡 同表内格式不一致

- **todo_list**: DATE_ONLY, STANDARD
- **daily_focus**: DATE_ONLY, STANDARD
- **goal**: DATE_ONLY, STANDARD
- **goal_journal**: DATE_ONLY, STANDARD, TIME_ONLY
- **goal_stats**: DATE_ONLY, STANDARD
- **daily_report**: DATE_ONLY, STANDARD
- **weekly_report**: DATE_ONLY, STANDARD
- **monthly_report**: DATE_ONLY, STANDARD
- **diary**: DATE_ONLY, STANDARD
- **habit_challenges**: DATE_ONLY, ISO_WITH_MICROSECONDS, STANDARD
- **habit_checkins**: DATE_ONLY, STANDARD
- **habit_chain_nodes**: STANDARD, TIME_ONLY

#### ⚠️ 无数据字段

有 4 个字段所在表无数据，需要查看代码确认格式

### 格式一致性评分

**一致性得分**: 96.6%

**计算方式**:
- 一致字段数: 85
- 可验证字段数: 88
- 得分 = 85 / 88 × 100%

✅ **评级**: 优秀（≥90%）

### 修复建议

#### 1. 统一 Python 代码写入格式（高优先级）

**问题**: Python 代码使用 `.isoformat()` 导致格式与 SQLite DEFAULT 不一致

**修复**:
```python
# 错误写法
data["updated_at"] = datetime.now().isoformat()  # 带 T

# 正确写法
data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 不带 T
```

**涉及文件**:
- `lifeprism/repository/base_providers/lw_base_data_provider.py:1184`
- `lifeprism/repository/providers/habit_providers.py:403`
- `lifeprism/repository/providers/map_cache_providers.py:311, 672`

#### 2. 修复同表内格式不一致（高优先级）

- **todo_list**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **daily_focus**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **goal**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **goal_journal**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **goal_stats**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **daily_report**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **weekly_report**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **monthly_report**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **diary**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **habit_challenges**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **habit_checkins**: 检查业务逻辑代码，确保所有时间字段使用相同格式
- **habit_chain_nodes**: 检查业务逻辑代码，确保所有时间字段使用相同格式

#### 3. 验证无数据字段（中优先级）

以下字段需要查看代码确认格式：

- `commitments.created_at`
- `commitments.updated_at`
- `user_values.created_at`
- `user_values.updated_at`

---

## 结论

1. **总字段数**: 100 个时间字段
2. **一致性得分**: 96.6%
3. **主要问题**:
   - 格式不一致: 3 个字段使用 ISO 格式（带 T）
   - 同表不一致: 12 个表
   - 无数据字段: 4 个字段

**下一步**:
1. 修复 Python 代码中的 `.isoformat()` 调用
2. 验证无数据字段的格式
3. 测试数据同步逻辑
