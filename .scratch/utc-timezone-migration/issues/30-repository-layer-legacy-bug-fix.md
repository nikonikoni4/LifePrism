# Issue #30: Repository 层时间查询遗留 bug 修复

## Parent

`.scratch/utc-timezone-migration/prd.md`

## 背景

代码审查发现 5 处遗留 bug，未被现有 issue（#21-#29）覆盖：

1. **behavior_analysis_provider** 用本地时间字符串查 UTC 时间戳字段
2. **raw_behavior_analysis_provider** 同上
3. **screenshot_analysis** 写库时 `replace("T", " ")` 降级格式
4. **statistical_data_providers** 用 `DATE(created_at)` 分组 UTC 时间戳
5. **session_query** 向 AI 显示 UTC 时间未转本地

这些 bug 导致：
- UTC+8 用户查询"今天"的数据会错位 8 小时
- 数据库存储格式不一致（部分 ISO，部分 `YYYY-MM-DD HH:MM:SS`）
- AI 看到的时间是 UTC 而非本地时间

## What to build

### Bug 1: behavior_analysis_provider 用本地时间查 UTC 时间戳

**文件**：`lifeprism/repository/providers/behavior_analysis_provider.py`

**问题**：
- 第 110-111 行 `get_behaviors_by_date()`：
  ```python
  start_datetime = f"{date} 00:00:00"  # 本地时间！
  end_datetime = f"{date} 23:59:59"
  sql = "SELECT * FROM behavior_analysis WHERE start_time >= ? AND start_time <= ?"
  ```
- 第 139-140 行 `get_behaviors_by_date_range()`：同上
- 第 251-252 行 `delete_behaviors_by_date_range()`：同上

**修复**：使用 Issue #27 的 `build_utc_time_range(local_date)` 将本地日期转为 UTC 时间范围：
```python
from lifeprism.utils.time_utils import build_utc_time_range

start_utc, end_utc = build_utc_time_range(date)
sql = "SELECT * FROM behavior_analysis WHERE start_time >= ? AND start_time <= ?"
# 参数用 start_utc, end_utc
```

### Bug 2: raw_behavior_analysis_provider 同上

**文件**：`lifeprism/repository/providers/raw_behavior_analysis_provider.py`

**问题**：
- 第 96-97 行 `get_raw_behaviors_by_date_range()`：同 Bug 1 模式
- 第 248-249 行 `delete_raw_behaviors_by_date_range()`：同上

**修复**：同 Bug 1，使用 `build_utc_time_range` 转换

### Bug 3: screenshot_analysis 写库时降级格式

**文件**：`lifeprism/llm/function/screenshot_analysis.py`

**问题**：第 397-398 行：
```python
start_time_db = chunk["start"].replace("T", " ")  # 降级为 YYYY-MM-DD HH:MM:SS
end_time_db = chunk["end"].replace("T", " ")
```
写入 `raw_behavior_analysis` 表前，将 ISO 格式（带 T）通过字符串替换转为 `YYYY-MM-DD HH:MM:SS`（无时区），违反 UTC ISO 8601 规范。

**修复**：移除 `replace("T", " ")`，保留 ISO 格式写入数据库。如果 `chunk["start"]`/`chunk["end"]` 已经是 ISO 格式，直接使用：
```python
start_time_db = chunk["start"]  # 保持 ISO 格式
end_time_db = chunk["end"]
```

如果 `chunk["start"]` 格式不确定，用 `parse_iso_to_aware` 规范化后再 `.isoformat()` 输出。

### Bug 4: statistical_data_providers 用 DATE() 分组 UTC 时间戳

**文件**：`lifeprism/server/providers/statistical_data_providers.py`

**问题**：第 548-555 行：
```sql
SELECT DATE(created_at) as usage_date, SUM(input_tokens), ...
FROM tokens_usage_log
WHERE created_at >= ? AND created_at <= ?
GROUP BY DATE(created_at)
```
`DATE(created_at)` 对 UTC 时间戳取日期得到 UTC 日期，对 UTC+8 用户在午夜前后分组错位。

**修复**：使用本地时区日期分组。SQLite 方案：
```sql
SELECT DATE(datetime(created_at, 'localtime')) as usage_date, ...
GROUP BY DATE(datetime(created_at, 'localtime'))
```

或者：在 Python 层用 `_utc_timestamp_to_local_date()` 函数分组（参考 `activity_stats_builder.py` 的 `_add_local_date_column` 模式）。

注意：SQLite 的 `datetime(created_at, 'localtime')` 依赖服务器时区设置，可能与 `get_user_timezone()` 不一致。推荐用 Python 层转换。

### Bug 5: session_query 向 AI 显示 UTC 时间未转本地

**文件**：`lifeprism/llm/agent/tools/session_query.py`

**问题**：第 293-298 行：
```python
dt = datetime.fromisoformat(timestamp)
time_str = dt.strftime("%m-%d %H:%M")
```
将聊天历史时间戳格式化为 `MM-DD HH:MM` 显示给 AI，但未做时区转换，AI 看到的是 UTC 时间而非本地时间。

**修复**：使用 Issue #27 的 `utc_to_local_display` 函数转换后再格式化：
```python
from lifeprism.utils.time_utils import utc_to_local_display

local_str = utc_to_local_display(timestamp)  # YYYY-MM-DD HH:MM:SS
# 提取 MM-DD HH:MM 部分
time_str = local_str[5:16]  # 从 "2026-07-12 10:00:00" 提取 "07-12 10:00"
```

或者直接用 `_utc_to_local`（`lifeprismsystem.py` 已有，#28 会提取到公共层）。

## Acceptance criteria

### Bug 1
- [ ] `behavior_analysis_provider.py` 的 3 个方法使用 `build_utc_time_range` 转换
- [ ] 单元测试：UTC+8 用户查询"今天"返回正确数据范围

### Bug 2
- [ ] `raw_behavior_analysis_provider.py` 的 2 个方法使用 `build_utc_time_range` 转换
- [ ] 单元测试：UTC+8 用户查询"今天"返回正确数据范围

### Bug 3
- [ ] `screenshot_analysis.py` 移除 `replace("T", " ")` 降级代码
- [ ] 写入 `raw_behavior_analysis` 的时间字段是 ISO 8601 格式
- [ ] 单元测试：写入数据库的时间格式正确

### Bug 4
- [ ] `statistical_data_providers.py` 的 `DATE(created_at)` 分组改为本地时区日期
- [ ] 单元测试：UTC+8 用户在午夜前后的 token 使用量分组到正确的本地日期

### Bug 5
- [ ] `session_query.py` 的时间显示使用 `utc_to_local_display` 转换
- [ ] 单元测试：AI 看到的时间是本地时间而非 UTC

### 通用
- [ ] `ruff check` 和 `ruff format` 全部通过
- [ ] 现有测试全部通过（无回归）

## Blocked by

- Issue #27 - 后端本地时间转 UTC 工具函数（需要 `build_utc_time_range` 和 `utc_to_local_display` 函数）

## 注意事项

1. **日期字段 vs 时间戳字段**：本 issue 修复的都是**时间戳字段**（start_time, end_time, created_at, timestamp）的查询问题，不是日期字段（date, start_date）。日期字段保持本地 `YYYY-MM-DD` 直接查询是正确的。
2. **build_utc_time_range 的用途**：将本地日期转为 UTC 时间范围，用于查询时间戳字段
3. **utc_to_local_display 的用途**：将 UTC ISO 转为本地 `YYYY-MM-DD HH:MM:SS`，用于面向 AI/用户显示
4. **screenshot_analysis 的 chunk 格式**：需确认 `chunk["start"]`/`chunk["end"]` 的来源格式，如果是 `build_time_segments` 输出，应已是 ISO 格式
5. **SQLite localtime 的陷阱**：`datetime(created_at, 'localtime')` 依赖服务器时区设置，可能与 `get_user_timezone()` 不一致。推荐用 Python 层转换。
6. **审查报告参考**：`.scratch/utc-timezone-migration/audits/time-filter-utc-audit.md` 和 `.scratch/utc-timezone-migration/audits/api-test-and-code-review.md`
