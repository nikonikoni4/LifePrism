# 非 API 表数据链路代码审查报告

## 审查范围

本次审查针对 LifeWatch-AI 项目 UTC 时区迁移修复（commit 130a365 + 91419b3）后，**不能通过 API 端到端测试的表**的数据生成代码，确认时间戳写入路径是否已正确修复为 `get_utc_now_iso()`（ISO 8601 + UTC 格式）。

### 审查的表和写入路径

| 分类 | 表名 | 写入路径文件 | 关键方法/行号 |
|------|------|------------|-------------|
| 数据采集层 | window_events | `lifeprism/monitor/provider/window_data_provider.py` | `save_event` (L54) |
| 数据采集层 | screen_captures | `lifeprism/monitor/provider/screenshot_data_provider.py` | `create_capture` (L33) |
| 数据采集层 | user_app_behavior_log | `lifeprism/repository/base_providers/lw_base_data_provider.py` | `save_user_app_behavior_log` (L780-838) |
| 数据采集层 | raw_behavior_analysis | `lifeprism/repository/providers/raw_behavior_analysis_provider.py` | `batch_create_raw_behaviors` (L152-205) |
| LLM/AI 生成层 | behavior_analysis | `lifeprism/repository/providers/behavior_analysis_provider.py` | `batch_create_behaviors` (L271-334) |
| LLM/AI 生成层 | time_paradoxes | `lifeprism/server/providers/being_provider.py` | `create`/`update`/`upsert` (L171-356) |
| LLM/AI 生成层 | tokens_usage_log | `lifeprism/repository/base_providers/lw_base_data_provider.py` | `save_tokens_usage` (L840-887)、`upsert_session_tokens_usage` (L933-989) |
| 系统自动计算层 | daily_report | `lifeprism/server/providers/report_provider.py` | `upsert_daily_report` (L90-139) |
| 系统自动计算层 | weekly_report | `lifeprism/server/providers/report_provider.py` | `upsert_weekly_report` (L320-369) |
| 系统自动计算层 | monthly_report | `lifeprism/server/providers/report_provider.py` | `upsert_monthly_report` (L519-570) |
| 系统自动计算层 | goal_stats | `lifeprism/repository/providers/goal_providers.py` | `upsert_stat` (L633-693) |
| 混合渠道批量路径 | multi_purpose_map_cache | `lifeprism/repository/providers/map_cache_providers.py` | `batch_insert_multi_purpose_map_cache` (L223-282) |
| 混合渠道批量路径 | single_purpose_map_cache | `lifeprism/repository/providers/map_cache_providers.py` | `batch_insert_single_purpose_map_cache` (L585-644) |
| 混合渠道批量路径 | database_manager.upsert | `lifeprism/repository/database_manager.py` | `upsert` (L356-422)、`upsert_many` (L424-500) |

### 表配置汇总（来自 `lifeprism/config/database.py` 的 `TABLE_CONFIGS`）

| 表名 | timestamps | update_at | 需写入字段 |
|------|-----------|-----------|----------|
| window_events | True | False | created_at |
| screen_captures | True | False | created_at |
| user_app_behavior_log | True | True | created_at + updated_at |
| raw_behavior_analysis | True | False | created_at |
| behavior_analysis | True | True | created_at + updated_at |
| time_paradoxes | True | True | created_at + updated_at |
| tokens_usage_log | True | （未配置，默认 False） | created_at |
| daily_report | True | True | created_at + updated_at |
| weekly_report | True | True | created_at + updated_at |
| monthly_report | True | True | created_at + updated_at |
| goal_stats | True | （未配置，默认 False） | created_at |
| multi_purpose_map_cache | True | True | created_at + updated_at |
| single_purpose_map_cache | True | True | created_at + updated_at |

---

## 审查结果汇总

| 表名 | 写入路径 | 修复状态 | created_at | updated_at | 备注 |
|------|---------|---------|------------|------------|------|
| window_events | window_data_provider.py:save_event | ✅ 通过 | ✅ get_utc_now_iso() | N/A (update_at=False) | 显式写入 created_at |
| screen_captures | screenshot_data_provider.py:create_capture | ✅ 通过 | ✅ get_utc_now_iso() | N/A (update_at=False) | 显式写入 created_at |
| user_app_behavior_log | lw_base_data_provider.py:save_user_app_behavior_log | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | 循环外获取 now_iso 复用 |
| raw_behavior_analysis | raw_behavior_analysis_provider.py:batch_create_raw_behaviors | ✅ 通过 | ✅ get_utc_now_iso() | N/A (update_at=False) | 已移除 localtime，循环外获取 now_iso |
| behavior_analysis | behavior_analysis_provider.py:batch_create_behaviors | ❌ 未通过 | ✅ get_utc_now_iso() | ❌ 缺失，依赖 DB DEFAULT | created_at 已修复，updated_at 未写入 |
| time_paradoxes | being_provider.py:create/update/upsert | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | 所有写入路径均显式写入 |
| tokens_usage_log | lw_base_data_provider.py:save_tokens_usage/upsert_session_tokens_usage | ✅ 通过 | ✅ get_utc_now_iso() | N/A (无 update_at) | 批量和单条路径均注入 created_at |
| daily_report | report_provider.py:upsert_daily_report | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | INSERT/UPDATE 均正确；update_report_state 未写 updated_at（次要问题） |
| weekly_report | report_provider.py:upsert_weekly_report | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | 同上 |
| monthly_report | report_provider.py:upsert_monthly_report | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | 同上 |
| goal_stats | goal_providers.py:upsert_stat | ✅ 通过 | ✅ get_utc_now_iso() | N/A (无 update_at) | INSERT 写入 created_at，UPDATE 无需 updated_at |
| multi_purpose_map_cache | map_cache_providers.py:batch_insert_multi_purpose_map_cache | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | 循环外获取 now_iso 复用 |
| single_purpose_map_cache | map_cache_providers.py:batch_insert_single_purpose_map_cache | ✅ 通过 | ✅ get_utc_now_iso() | ✅ get_utc_now_iso() | 循环外获取 now_iso 复用 |
| database_manager.upsert | database_manager.py:upsert/upsert_many | ✅ 通过 | 调用方负责 | ✅ get_utc_now_iso() | CURRENT_TIMESTAMP 已替换为参数化绑定 |

---

## 详细审查记录

### 1. window_events

- **文件**：`lifeprism/monitor/provider/window_data_provider.py`
- **方法**：`save_event`
- **代码位置**：第 54 行
- **表配置**：`timestamps: True, update_at: False`（仅需 `created_at`）
- **导入**：第 11 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT
- **修复后**：显式写入 `get_utc_now_iso()`
- **审查结论**：✅ 正确

```python
# 第 49-55 行
data = {
    "timestamp": timestamp,
    "duration": duration,
    "app": app,
    "title": title,
    "created_at": get_utc_now_iso(),  # ✅ 显式写入 ISO 8601 + UTC
}
```

### 2. screen_captures（monitor 路径）

- **文件**：`lifeprism/monitor/provider/screenshot_data_provider.py`
- **方法**：`create_capture`
- **代码位置**：第 33 行
- **表配置**：`timestamps: True, update_at: False`（仅需 `created_at`）
- **导入**：第 11 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT
- **修复后**：显式写入 `get_utc_now_iso()`
- **审查结论**：✅ 正确

```python
# 第 33-34 行
insert_data = {**data, "created_at": get_utc_now_iso()}  # ✅ 显式写入
result = self.db.insert("screen_captures", insert_data) > 0
```

### 3. user_app_behavior_log（批量保存路径）

- **文件**：`lifeprism/repository/base_providers/lw_base_data_provider.py`
- **方法**：`save_user_app_behavior_log`
- **代码位置**：第 780-838 行
- **表配置**：`timestamps: True, update_at: True`（需 `created_at` + `updated_at`）
- **导入**：第 792 行局部导入 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT
- **修复后**：循环外获取 `now_iso` 一次，循环内复用，显式写入 `created_at` 和 `updated_at`
- **审查结论**：✅ 正确

```python
# 第 792-809 行
from lifeprism.utils.time_utils import get_utc_now_iso

now_iso = get_utc_now_iso()  # ✅ 循环外获取一次
for _, row in cleaned_events_df.iterrows():
    data_list.append(
        {
            ...
            "created_at": now_iso,   # ✅ 复用
            "updated_at": now_iso,   # ✅ 复用
        }
    )
```

### 4. raw_behavior_analysis（批量创建路径）

- **文件**：`lifeprism/repository/providers/raw_behavior_analysis_provider.py`
- **方法**：`batch_create_raw_behaviors`
- **代码位置**：第 182-198 行
- **表配置**：`timestamps: True, update_at: False`（仅需 `created_at`）
- **导入**：第 13 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：硬编码 `datetime('now', 'localtime')`（P0 级风险）
- **修复后**：循环外获取 `now_iso` 一次，参数化绑定，无 `localtime`
- **审查结论**：✅ 正确

```python
# 第 182-198 行
now_iso = get_utc_now_iso()  # ✅ 循环外获取一次
with self.db.get_connection() as conn:
    cursor = conn.cursor()
    for data in data_list:
        try:
            cursor.execute(
                f"""INSERT INTO {self._TABLE_NAME}
                   (start_time, end_time, behavior, screen_count, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    data["start_time"],
                    data["end_time"],
                    data["behavior"],
                    data["screen_count"],
                    now_iso,  # ✅ 参数化绑定，无 localtime
                ),
            )
```

### 5. behavior_analysis（批量创建路径）❌

- **文件**：`lifeprism/repository/providers/behavior_analysis_provider.py`
- **方法**：`batch_create_behaviors`
- **代码位置**：第 309-327 行
- **表配置**：`timestamps: True, update_at: True`（需 `created_at` + `updated_at`）
- **导入**：第 14 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：硬编码 `datetime('now', 'localtime')`（P0 级风险）
- **修复后**：`created_at` 已改为 `get_utc_now_iso()`，但 **`updated_at` 未写入**
- **审查结论**：❌ 存在问题

```python
# 第 309-327 行（当前代码）
now_iso = get_utc_now_iso()
with self.db.get_connection() as conn:
    cursor = conn.cursor()
    for data in data_list:
        try:
            cursor.execute(
                f"""INSERT INTO {self._TABLE_NAME}
                   (start_time, end_time, behavior, behavior_summary, title, screen_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                # ❌ SQL 列列表缺少 updated_at，VALUES 缺少对应占位符
                (
                    data["start_time"],
                    data["end_time"],
                    data["behavior"],
                    data.get("behavior_summary"),
                    data.get("title"),
                    data["screen_count"],
                    now_iso,  # ✅ created_at 已修复
                ),
            )
```

**问题描述**：
- 表配置 `update_at: True`，但批量 INSERT 的 SQL 列列表仅包含 `created_at`，缺少 `updated_at`
- `updated_at` 将回退到 DB DEFAULT `datetime('now')`，输出格式为 `YYYY-MM-DD HH:MM:SS`（无 T 分隔符、无时区标识）
- 导致同一行中 `created_at` 为 ISO 8601 格式（如 `2026-07-12T10:30:00.123456+00:00`），而 `updated_at` 为非 ISO 格式（如 `2026-07-12 10:30:00`），格式不一致
- 影响同步 LWW（Last-Write-Wins）字符串比较的可靠性

**建议修复**：
```python
cursor.execute(
    f"""INSERT INTO {self._TABLE_NAME}
       (start_time, end_time, behavior, behavior_summary, title, screen_count, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        data["start_time"],
        data["end_time"],
        data["behavior"],
        data.get("behavior_summary"),
        data.get("title"),
        data["screen_count"],
        now_iso,
        now_iso,  # 新增：updated_at
    ),
)
```

### 6. time_paradoxes

- **文件**：`lifeprism/server/providers/being_provider.py`
- **方法**：`create` (L171-199)、`update` (L242-265)、`update_by_user_mode_version` (L267-303)、`upsert` (L305-356)
- **表配置**：`timestamps: True, update_at: True`（需 `created_at` + `updated_at`）
- **导入**：第 14 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT，`db.update` 不更新 `updated_at`
- **修复后**：所有写入路径均显式写入时间戳
- **审查结论**：✅ 正确

```python
# create 方法（第 184-186 行）
now_iso = get_utc_now_iso()
insert_data["created_at"] = now_iso   # ✅
insert_data["updated_at"] = now_iso   # ✅

# update 方法（第 255 行）
update_data["updated_at"] = get_utc_now_iso()  # ✅

# update_by_user_mode_version 方法（第 284 行）
update_data["updated_at"] = get_utc_now_iso()  # ✅

# upsert 方法（第 327, 336-337 行）
now_iso = get_utc_now_iso()
data = {
    ...
    "created_at": now_iso,   # ✅
    "updated_at": now_iso,   # ✅
}
```

### 7. tokens_usage_log（批量保存 + 单条保存路径）

- **文件**：`lifeprism/repository/base_providers/lw_base_data_provider.py`
- **方法**：`save_tokens_usage` (L840-887)、`upsert_session_tokens_usage` (L933-989)
- **表配置**：`timestamps: True`，无 `update_at` 配置（仅需 `created_at`）
- **导入**：第 869、975 行局部导入 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT
- **修复后**：批量保存和单条插入均显式注入 `created_at`；UPDATE 路径正确地不写 `updated_at`
- **审查结论**：✅ 正确

```python
# save_tokens_usage（第 871-874 行）
now_iso = get_utc_now_iso()  # ✅ 循环外获取一次
for data in tokens_usage_data:
    if "created_at" not in data:
        data["created_at"] = now_iso  # ✅ 注入 created_at

# upsert_session_tokens_usage INSERT 路径（第 975-978 行）
from lifeprism.utils.time_utils import get_utc_now_iso
if "created_at" not in data:
    data["created_at"] = get_utc_now_iso()  # ✅

# upsert_session_tokens_usage UPDATE 路径（第 967 行注释）
# 存在则 UPDATE（tokens_usage_log 无 update_at，不需写 updated_at）✅ 正确
```

### 8. daily_report

- **文件**：`lifeprism/server/providers/report_provider.py`
- **方法**：`upsert_daily_report`
- **代码位置**：第 90-139 行
- **表配置**：`timestamps: True, update_at: True`（需 `created_at` + `updated_at`）
- **导入**：第 13 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **审查结论**：✅ 正确（upsert 路径）

```python
# INSERT 路径（第 129-131 行）
now_iso = get_utc_now_iso()
insert_data["created_at"] = now_iso   # ✅
insert_data["updated_at"] = now_iso   # ✅

# UPDATE 路径（第 113 行）
update_data["updated_at"] = get_utc_now_iso()  # ✅
```

**次要问题**：`update_report_state` 方法（第 141-164 行）通过 `db.update_by_id` 更新 `state` 字段时未写入 `updated_at`。此方法不在本次审查的 `upsert` 范围内，但属于遗留 P2 问题。

### 9. weekly_report

- **文件**：`lifeprism/server/providers/report_provider.py`
- **方法**：`upsert_weekly_report`
- **代码位置**：第 320-369 行
- **表配置**：`timestamps: True, update_at: True`
- **导入**：同 daily_report（第 13 行）✅
- **审查结论**：✅ 正确（upsert 路径）

```python
# INSERT 路径（第 359-361 行）
now_iso = get_utc_now_iso()
insert_data["created_at"] = now_iso   # ✅
insert_data["updated_at"] = now_iso   # ✅

# UPDATE 路径（第 343 行）
update_data["updated_at"] = get_utc_now_iso()  # ✅
```

**次要问题**：同 daily_report，`update_report_state` 未写 `updated_at`。

### 10. monthly_report

- **文件**：`lifeprism/server/providers/report_provider.py`
- **方法**：`upsert_monthly_report`
- **代码位置**：第 519-570 行
- **表配置**：`timestamps: True, update_at: True`
- **导入**：同 daily_report（第 13 行）✅
- **审查结论**：✅ 正确（upsert 路径）

```python
# INSERT 路径（第 560-562 行）
now_iso = get_utc_now_iso()
insert_data["created_at"] = now_iso   # ✅
insert_data["updated_at"] = now_iso   # ✅

# UPDATE 路径（第 544 行）
update_data["updated_at"] = get_utc_now_iso()  # ✅
```

**次要问题**：同 daily_report，`update_report_state` 未写 `updated_at`。

### 11. goal_stats

- **文件**：`lifeprism/repository/providers/goal_providers.py`
- **方法**：`upsert_stat`
- **代码位置**：第 633-693 行
- **表配置**：`timestamps: True`，无 `update_at` 配置（仅需 `created_at`）
- **导入**：第 18 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT
- **修复后**：INSERT 路径显式写入 `created_at`；UPDATE 路径正确地不写 `updated_at`
- **审查结论**：✅ 正确

```python
# INSERT 路径（第 675-683 行）
# 注释：插入（注入 created_at，goal_stats 无 update_at）
now_iso = get_utc_now_iso()
cursor.execute(
    """
    INSERT INTO goal_stats (goal_id, date, time_spent, completed_todo_count, created_at)
    VALUES (?, ?, ?, ?, ?)
    """,
    (goal_id, date, time_spent, todo_count, now_iso),  # ✅ 参数化绑定
)

# UPDATE 路径（第 664-672 行）
# 注释：更新（goal_stats 无 update_at 配置，不需写 updated_at）✅ 正确
```

### 12. multi_purpose_map_cache（批量插入路径）

- **文件**：`lifeprism/repository/providers/map_cache_providers.py`
- **方法**：`batch_insert_multi_purpose_map_cache`
- **代码位置**：第 223-282 行
- **表配置**：`timestamps: True, update_at: True`（需 `created_at` + `updated_at`）
- **导入**：第 14 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：依赖 DB DEFAULT
- **修复后**：循环外获取 `now_iso` 一次，循环内追加 `created_at` 和 `updated_at`
- **审查结论**：✅ 正确

```python
# 第 253-264 行
now_iso = get_utc_now_iso()  # ✅ 循环外获取一次
with self.db.get_connection() as conn:
    cursor = conn.cursor()
    for data in data_list:
        fields = list(data.keys()) + ["created_at", "updated_at"]  # ✅ 追加两字段
        placeholders = ",".join("?" * len(fields))
        fields_str = ",".join(fields)
        values = list(data.values()) + [now_iso, now_iso]  # ✅ 复用
        sql = f"INSERT INTO {self._TABLE_NAME} ({fields_str}) VALUES ({placeholders})"
        cursor.execute(sql, values)
```

**补充**：`lw_base_data_provider.py` 第 608-637 行的 `upsert_many` 调用路径也正确注入了时间戳：
```python
# 第 614-620 行
now_iso = get_utc_now_iso()
for record in single_purpose_data:
    record.setdefault("created_at", now_iso)  # ✅
    record.setdefault("updated_at", now_iso)  # ✅
for record in multi_purpose_data:
    record.setdefault("created_at", now_iso)  # ✅
    record.setdefault("updated_at", now_iso)  # ✅
```

### 13. single_purpose_map_cache（批量插入路径）

- **文件**：`lifeprism/repository/providers/map_cache_providers.py`
- **方法**：`batch_insert_single_purpose_map_cache`
- **代码位置**：第 585-644 行
- **表配置**：`timestamps: True, update_at: True`
- **导入**：第 14 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **审查结论**：✅ 正确（与 multi_purpose_map_cache 模式完全一致）

```python
# 第 615-627 行
now_iso = get_utc_now_iso()  # ✅ 循环外获取一次
with self.db.get_connection() as conn:
    cursor = conn.cursor()
    for data in data_list:
        fields = list(data.keys()) + ["created_at", "updated_at"]  # ✅
        placeholders = ",".join("?" * len(fields))
        fields_str = ",".join(fields)
        values = list(data.values()) + [now_iso, now_iso]  # ✅
        sql = f"INSERT INTO {self._TABLE_NAME} ({fields_str}) VALUES ({placeholders})"
        cursor.execute(sql, values)
```

### 14. database_manager.upsert / upsert_many

- **文件**：`lifeprism/repository/database_manager.py`
- **方法**：`upsert` (L356-422)、`upsert_many` (L424-500)
- **导入**：第 22 行 `from lifeprism.utils.time_utils import get_utc_now_iso` ✅
- **修复前**：使用 `CURRENT_TIMESTAMP`（格式 `YYYY-MM-DD HH:MM:SS`，非 ISO 8601）
- **修复后**：使用 `get_utc_now_iso()` 参数化绑定，无 `CURRENT_TIMESTAMP`
- **审查结论**：✅ 正确

```python
# upsert 方法（第 390-411 行）
now_iso = None
if need_update_at:
    now_iso = get_utc_now_iso()  # ✅
    if update_str:
        update_str += ", updated_at = ?"
    else:
        update_str = "updated_at = ?"
# ...
params = list(data.values())
if now_iso is not None:
    params.append(now_iso)  # ✅ 参数化绑定
cursor.execute(sql, params)

# upsert_many 方法（第 463-483 行）- 同样模式
now_iso = None
if need_update_at:
    now_iso = get_utc_now_iso()  # ✅
    # ...
values_list = [[row.get(col) for col in columns] for row in data_list]
if now_iso is not None:
    values_list = [row + [now_iso] for row in values_list]  # ✅ 参数化绑定
```

**设计说明**：`need_update_at` 逻辑仅对 `multi_purpose_map_cache` 和 `single_purpose_map_cache` 两张表生效（第 380-382、453-455 行硬编码判断）。其他表（如 `time_paradoxes`）通过 `db.upsert` 调用时，由调用方（如 `being_provider.py`）在 `data` 字典中预先设置 `created_at`/`updated_at`，因此时间戳仍能正确写入。

---

## 发现的问题

### ❌ 问题 1：behavior_analysis 批量插入缺少 `updated_at`（P1 级）

- **文件**：`lifeprism/repository/providers/behavior_analysis_provider.py`
- **位置**：第 315-317 行
- **问题描述**：
  - 表配置为 `timestamps: True, update_at: True`，需要同时写入 `created_at` 和 `updated_at`
  - 批量插入 SQL 的列列表仅包含 `created_at`，缺少 `updated_at`
  - `updated_at` 回退到 DB DEFAULT `datetime('now')`，输出格式为 `YYYY-MM-DD HH:MM:SS`（非 ISO 8601）
  - 导致同一行中 `created_at`（ISO 格式）与 `updated_at`（非 ISO 格式）格式不一致
- **影响**：
  - 时间戳格式不一致，不符合 ISO 8601 + UTC 规范
  - 可能影响同步 LWW 字符串比较的可靠性
  - behavior_analysis 是 AI 分析结果的核心表，影响行为分析展示和同步
- **建议修复**：在 SQL 列列表中添加 `updated_at`，并在 VALUES 中绑定 `now_iso`

### ⚠️ 问题 2：report_provider 的 `update_report_state` 未写入 `updated_at`（P2 级，次要）

- **文件**：`lifeprism/server/providers/report_provider.py`
- **位置**：第 141-164 行（daily）、第 371-394 行（weekly）、第 572-595 行（monthly）
- **问题描述**：`update_report_state` 方法通过 `db.update_by_id` 更新 `state` 字段时，未在 `update_data` 中添加 `updated_at`
- **影响**：报告状态更新后 `updated_at` 不变，可能影响同步 LWW 判断
- **说明**：此方法不在本次审查的 `upsert` 范围内，属于数据流报告中已记录的 P2 遗留问题

### ℹ️ 观察 1：map_cache batch_update 使用 `datetime.now(timezone.utc).isoformat()` 而非 `get_utc_now_iso()`（风格一致性）

- **文件**：`lifeprism/repository/providers/map_cache_providers.py`
- **位置**：第 310-313 行、第 672-675 行
- **描述**：`batch_update_multi_purpose_map_cache` 和 `batch_update_single_purpose_map_cache` 方法使用 `from datetime import datetime, timezone` + `datetime.now(timezone.utc).isoformat()`，而非统一的 `get_utc_now_iso()` 工具函数
- **影响**：功能上完全等价（`get_utc_now_iso()` 的实现就是 `datetime.now(timezone.utc).isoformat()`），但风格不一致
- **建议**：可选择性统一为 `get_utc_now_iso()` 以保持代码一致性（非阻塞性问题）

### ℹ️ 观察 2：database_manager.upsert 的 `need_update_at` 硬编码 map_cache 表名（设计限制）

- **文件**：`lifeprism/repository/database_manager.py`
- **位置**：第 380-382 行、第 453-455 行
- **描述**：`need_update_at` 逻辑通过 `table_name == "single_purpose_map_cache" or table_name == "multi_purpose_map_cache"` 硬编码判断，未泛化为根据 `TABLE_CONFIGS` 的 `update_at` 配置自动处理
- **影响**：其他表（如 `time_paradoxes`）通过 `db.upsert` 调用时不会自动设置 `updated_at`，需调用方自行处理。当前 `being_provider.py` 的 upsert 方法已在 `data` 字典中预设时间戳，功能正确
- **建议**：长期可泛化为根据 `TABLE_CONFIGS` 配置自动处理（非阻塞性问题）

---

## 总结

- **审查表数**：13 个审查对象（含 database_manager.upsert 通用方法）
- **通过**：12
- **未通过**：1（behavior_analysis 批量插入缺少 `updated_at`）
- **遗留问题**：
  - ❌ P1：behavior_analysis 批量插入需补充 `updated_at` 字段
  - ⚠️ P2：report_provider 的 `update_report_state` 未写 `updated_at`（已记录的遗留问题，非本次修复范围）
  - ℹ️ 风格：map_cache batch_update 可统一使用 `get_utc_now_iso()`
  - ℹ️ 设计：database_manager.upsert 的 `need_update_at` 可泛化为配置驱动

### 全局验证

- 已对 `lifeprism/monitor/`、`lifeprism/server/providers/`、`lifeprism/repository/providers/`、`lifeprism/repository/base_providers/` 目录执行全文搜索，确认无活跃的 `datetime('now')`、`CURRENT_TIMESTAMP`、`localtime` 使用（剩余匹配项均为注释或文档说明）
- 所有审查的文件均已正确导入 `from lifeprism.utils.time_utils import get_utc_now_iso`（顶层导入或局部导入）
- 所有批量插入路径均在循环外获取 `now_iso` 一次并在循环内复用，避免每行产生不同时间戳
- `database_manager.py` 的 `upsert`/`upsert_many` 已将 `CURRENT_TIMESTAMP` 替换为参数化绑定的 `get_utc_now_iso()`

### 报告生成信息

- 生成时间：2026-07-12
- 审查范围：UTC 时区迁移修复后的非 API 表数据链路代码
- 关联文档：
  - `.scratch/utc-timezone-migration/data-flow-audit-report.md`（修复前数据流审计报告）
  - `lifeprism/config/database.py`（TABLE_CONFIGS 表配置权威来源）
  - `lifeprism/utils/time_utils.py`（`get_utc_now_iso()` 工具函数）
