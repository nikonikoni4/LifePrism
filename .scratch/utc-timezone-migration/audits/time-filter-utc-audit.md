# 时间筛选功能 UTC 时区转换审查报告

> **审查日期**：2026-07-12
> **审查范围**：LifeWatch-AI 项目所有时间筛选功能（前端、后端 API、服务层、Repository、LLM Tool）
> **审查性质**：只读审查，未修改任何代码
> **架构基线**：
> - 数据库存储：UTC ISO 8601（`YYYY-MM-DDTHH:MM:SS.ffffff+00:00` 或 `YYYY-MM-DD HH:MM:SS`）
> - 前端显示：本地时区 `YYYY-MM-DD HH:MM:SS`
> - AI Tool：接收本地时区输入，内部转 UTC 查询
> - API：应接收本地时区或 UTC，本次审查需确认实际行为

---

## 1. 审查概述

### 1.1 审查目标
1. 确认前端所有时间筛选组件在筛选后提交的时间格式是否为 UTC
2. 确认后端 API 接收的时间筛选参数是否处理本地时区到 UTC 的转换
3. 确认 LLM Tool 的时间参数是否正确转换为 UTC 查询数据库

### 1.2 总体结论
**存在系统性时区不匹配问题**：前端、后端 API、服务层、Repository 在时间筛选链路中普遍未进行本地时区到 UTC 的转换，导致数据库查询使用本地时间字符串与 UTC 存储的时间进行比较，会产生跨时区边界的数据错位。

**唯一正面案例**：LLM Tool 模块（`lifeprismsystem.py`）正确实现了 `_parse_local_time` 和 `_utc_to_local`，完整支持本地时区到 UTC 的双向转换。

### 1.3 关键发现概览

| 层级 | 文件/模块 | 是否转 UTC | 严重程度 | 说明 |
|------|-----------|------------|----------|------|
| 前端组件 | `Timeline.tsx` | ❌ 否 | 高 | 直接发送本地时间字符串 |
| 前端组件 | `ActivitySummaryHeader.tsx` | ❌ 否 | 高 | 同步对话框未转 UTC |
| 前端 API 层 | 所有 `api.ts` 文件 | ❌ 否 | 高 | 直接传递本地时间字符串 |
| 后端 API | `activity_api.py` | ❌ 否 | 高 | 只做格式验证，无时区转换 |
| 后端 API | `timeline_api.py` | ❌ 否 | 高 | 同上 |
| 后端 API | `sync.py` | ❌ 否 | 高 | 同上 |
| 服务层 | `report_service.py` | ❌ 否 | 高 | 定义了辅助函数但未使用 |
| 服务层 | `activity_stats_builder.py` | ❌ 否 | 高 | 定义了辅助函数但未使用 |
| 服务层 | `timeline_builder.py` | ❌ 否 | 高 | 直接使用本地日期字符串 |
| 服务层 | `timeline_service.py` | ❌ 否 | 高 | 直接使用本地时间构造 |
| 服务层 | `activity_service.py` | ❌ 否 | 高 | 透传时间参数 |
| 服务层 | `mood_service.py` | ❌ 否 | 中 | 透传日期参数 |
| 服务层 | `diary_service.py` | ❌ 否 | 中 | 透传日期参数 |
| 服务层 | `sync_service.py` | ⚠️ 部分 | 中 | `screen_behavior_anlysis` 视为 UTC，`sync_by_time_range` 未转 |
| Repository | `lw_base_data_provider.py` | ❌ 否 | 高 | 字符串比较，无时区感知 |
| Repository | `mood_providers.py` | ❌ 否 | 中 | 直接 SQL 字符串比较 |
| Repository | `custom_block_provider.py` | ❌ 否 | 中 | 直接使用本地日期字符串 |
| Repository | `behavior_analysis_provider.py` | ❌ 否 | 中 | 直接使用本地日期字符串 |
| Repository | `diary_provider.py` | ❌ 否 | 低 | date 字段为日期，无时间，影响较小 |
| LLM Tool | `lifeprismsystem.py` | ✅ 是 | - | 正确实现本地→UTC 转换 |

---

## 2. 前端时间筛选组件审查

### 2.1 前端时间工具函数（基线）
**文件**：`frontend/core/utils/dateUtils.ts`

| 函数 | 功能 | 输出格式 |
|------|------|----------|
| `toLocalDateString(date)` | 转 UTC ISO 为本地日期 | `YYYY-MM-DD` |
| `toLocalDateTimeString(date)` | 转 UTC ISO 为本地日期时间 | `YYYY-MM-DDTHH:MM:SS` |
| `toISOStringUTC(date)` | 转 Date 为 UTC ISO 8601 | `YYYY-MM-DDTHH:MM:SS.fffZ` |
| `parseISOString(isoString)` | 解析后端 ISO 字符串 | Date 对象 |
| `getUserTimezone()` | 获取用户时区 | `Asia/Shanghai`（默认） |

**关键问题**：虽然前端有 `toISOStringUTC` 函数可用于将本地时间转 UTC，但**所有时间筛选组件都未调用该函数**，直接传递本地时间字符串给后端。

### 2.2 Timeline 页面（严重）
**文件**：`frontend/apps/lifewatch/pages/timeline/Timeline.tsx`

```typescript
const startTime = `${currentDate} 00:00:00`;
const endTime = `${currentDate} 23:59:59`;
const response = await ActivityLogsAPI.getLogs({
    start_time: startTime,
    end_time: endTime,
    ...
});
```

**问题**：构造本地日期字符串 `YYYY-MM-DD 00:00:00` ~ `YYYY-MM-DD 23:59:59`，**未调用 `toISOStringUTC` 转换为 UTC**。

**影响**：当用户时区为 UTC+8 时，查询本地 2026-07-12 实际应该对应 UTC 2026-07-11 16:00:00 ~ 2026-07-12 15:59:59，但前端发送的是 `2026-07-12 00:00:00`，导致数据库查询错位 8 小时。

### 2.3 首页活动摘要同步对话框（严重）
**文件**：`frontend/apps/lifewatch/pages/home/components/ActivitySummaryHeader.tsx`

```typescript
const startDateTime = `${syncStartDate} 00:00:00`;
const endDateTime = `${syncEndDate} 23:59:59`;
await SyncAPI.syncByTimeRange({
    start_time: startDateTime,
    end_time: endDateTime,
    auto_classify: true,
});
```

**问题**：同步对话框构造本地时间字符串传给 `/sync/by-time-range` API，**未转 UTC**。

### 2.4 使用页面（中等）
**文件**：`frontend/apps/lifewatch/pages/usage/UsagePage.tsx`

使用 `toLocalDateString(today)` 获取本地日期传给 API。该场景仅传日期（无时间），影响相对较小，但仍存在跨时区日期边界问题。

### 2.5 其他前端组件
- **报告页面**：`getDailyReport(date)`、`getWeeklyReport(weekStartDate)`、`getMonthlyReport(month)` 等仅传日期参数，由后端处理时间范围
- **心情/日记**：`getEntries(startDate, endDate)` 等仅传日期参数

---

## 3. 前端 API 调用层审查

### 3.1 通用问题
所有前端 API 调用层都**直接传递本地时间字符串**给后端，未进行 UTC 转换。

### 3.2 具体文件清单

| 文件 | 方法 | 参数 | 格式 | 是否转 UTC |
|------|------|------|------|------------|
| `frontend/apps/lifewatch/pages/home/api.ts` | `getStats(params)` | `date` | `YYYY-MM-DD` | ❌ |
| 同上 | `syncByTimeRange(params)` | `start_time`/`end_time` | `YYYY-MM-DD HH:MM:SS` | ❌ |
| `frontend/apps/lifewatch/pages/reports/api.ts` | `getDailyReport(date)` | `date` | `YYYY-MM-DD` | ❌ |
| 同上 | `getWeeklyReport(weekStartDate)` | `week_start_date` | `YYYY-MM-DD` | ❌ |
| 同上 | `getMonthlyReport(month)` | `month` | `YYYY-MM` | ❌ |
| 同上 | `getCompletedReportDates(startDate, endDate)` | `start_date`/`end_date` | `YYYY-MM-DD` | ❌ |
| `frontend/apps/custom-records/api.ts` | `getEntries(typeId, params)` | `start_date`/`end_date` | `YYYY-MM-DD` | ❌ |
| `frontend/apps/lifewatch/pages/category/api.ts` | `updateLogsByCache` | `start_date`/`end_date` | `YYYY-MM-DD` | ❌ |
| `frontend/apps/mindspace/components/mood/moodApi.ts` | `getEntries(startDate, endDate)` | `start_date`/`end_date` | `YYYY-MM-DD` | ❌ |
| `frontend/apps/mindspace/components/journal/diaryApi.ts` | `getList(startDate, endDate)` | `start_date`/`end_date` | `YYYY-MM-DD` | ❌ |
| `frontend/core/services/commonApi.ts` | `getLogs(params)` | `start_time`/`end_time` | `YYYY-MM-DD HH:MM:SS` | ❌ |

### 3.3 关键证据
前端 API 层未调用 `toISOStringUTC`，而是直接将组件构造的本地时间字符串通过 `URLSearchParams` 拼接到请求 URL。

---

## 4. 后端 API 层审查

### 4.1 通用问题
FastAPI 路由层接收时间参数时**仅做格式验证（正则 pattern）**，**不做时区转换**，直接透传给 Service 层。

### 4.2 Activity API（严重）
**文件**：`lifeprism/server/api/activity_api.py`

```python
start_time: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
end_time: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
```

**问题**：正则只验证 `YYYY-MM-DD HH:MM:SS` 格式，不验证时区。前端传入的本地时间字符串直接传递给 `activity_service.get_activity_logs`。

### 4.3 Timeline API
**文件**：`lifeprism/server/api/timeline_api.py`

接收 `date` 参数（`YYYY-MM-DD` 格式），直接传递给 `timeline_service`。无时区转换。

### 4.4 Sync API
**文件**：`lifeprism/server/api/sync.py`

```python
start_time: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
end_time: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
```

**问题**：接收 `YYYY-MM-DD HH:MM:SS` 格式参数，直接传递给 `sync_service.sync_by_time_range`，无时区转换。

### 4.5 其他 API
- `report_api.py`：接收 `date`/`week_start_date`/`month` 参数，透传
- `mood_api.py`：接收 `start_date`/`end_date`，透传
- `diary_api.py`：接收 `start_date`/`end_date`，透传

---

## 5. 后端服务层审查

### 5.1 核心问题
服务层普遍直接使用本地日期字符串 `f"{date} 00:00:00"` 构造时间范围查询数据库，**未将本地时间转换为 UTC**。

### 5.2 report_service.py（严重）
**文件**：`lifeprism/server/services/report_service.py`

**问题 1：辅助函数定义但未使用**

定义了完整的 UTC 转换辅助函数：
- `_build_utc_time_range(start_date, end_date)` - 本地日期转 UTC 时间范围
- `_utc_timestamp_to_local_date(timestamp)` - UTC 时间戳转本地日期
- `_add_local_date_column(df, time_col)` - 为 DataFrame 添加本地日期列
- `_normalize_timestamp(value)` - 规范化时间戳格式

**但所有计算函数都未使用 `_build_utc_time_range`**，而是直接使用本地时间字符串：

```python
def _calc_sunburst_data(start_date, end_date, title, total_range_minutes):
    start_time = f"{start_date} 00:00:00"  # 本地时间！
    end_time = f"{end_date} 23:59:59"
    df = server_lw_data_provider.load_user_app_behavior_log(
        start_time=start_time, end_time=end_time
    )
```

**受影响函数列表**：
- `_calc_sunburst_data` - 旭日图数据计算
- `_calc_goal_time_invested` - 目标时间投入计算
- `_calc_hourly_trend` - 24小时趋势（日报）
- `_calc_weekly_trend` - 周趋势
- `_calc_monthly_trend` - 月趋势
- `_calc_heatmap_data` - 热力图数据
- `_calc_comparison_data` - 环比对比数据

**问题 2：缓存命中路径也未转 UTC**
```python
comparison_data = _calc_comparison_data(
    current_start=f"{date} 00:00:00",  # 本地时间
    current_end=f"{date} 23:59:59",
    period_type="daily"
)
```

### 5.3 activity_stats_builder.py（严重）
**文件**：`lifeprism/server/services/activity_stats_builder.py`

同样定义了 `_build_utc_time_range`、`_utc_timestamp_to_local_date`、`_add_local_date_column` 等辅助函数，但**未在查询中使用**：

```python
def build_time_overview(date: str) -> TimeOverviewData:
    start_time = f"{date} 00:00:00"  # 本地时间！
    end_time = f"{date} 23:59:59"
    df = server_lw_data_provider.load_user_app_behavior_log(
        start_time=start_time, end_time=end_time
    )
```

### 5.4 timeline_builder.py（严重）
**文件**：`lifeprism/server/services/timeline_builder.py`

```python
def load_day_events(date: str) -> pd.DataFrame:
    start_time = f"{date} 00:00:00"  # 本地时间！
    end_time = f"{date} 23:59:59"
    df = custom_block_repository.load_user_app_behavior_log(
        start_time=start_time, end_time=end_time
    )
```

`_calculate_block_stats` 也使用 `datetime.strptime(f"{date} {start_hour:02d}:00:00", ...)` 构造本地时间范围（虽然这里用于切片 DataFrame，但数据源查询已经错位）。

### 5.5 timeline_service.py（严重）
**文件**：`lifeprism/server/services/timeline_service.py`

```python
range_start = datetime.strptime(f"{date} {start_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
# 未做时区转换
```

### 5.6 activity_service.py（严重）
**文件**：`lifeprism/server/services/activity_service.py`

`get_activity_logs` 直接透传 `start_time`/`end_time` 给 provider，无时区转换。

### 5.7 mood_service.py（中等）
**文件**：`lifeprism/server/services/mood_service.py`

```python
def get_mood_entries(start_date, end_date):
    items = mood_repository.get_mood_entries(start_date, end_date)
```

直接传递日期参数给 repository。注意：mood_entries 表使用 `created_at` 字段查询，存储为 UTC，但传入的 `start_date`/`end_date` 是本地日期。

### 5.8 diary_service.py（低）
**文件**：`lifeprism/server/services/diary_service.py`

```python
def get_diary_list(start_date, end_date):
    items = diary_repository.get_diaries_by_date_range(start_date, end_date)
```

diary 表使用 `date` 字段（`YYYY-MM-DD`）查询，不是时间戳，因此时区影响较小（日记按日期组织）。

### 5.9 sync_service.py（部分正确）
**文件**：`lifeprism/server/services/sync_service.py`

**`screen_behavior_anlysis` 函数**（部分正确）：
```python
start_time = start_time.replace("T", " ")
requested_start_time = datetime.fromisoformat(start_time)
# 迁移后输入字符串视为 UTC 时间：若 naive 则补充 UTC tzinfo
if requested_start_time.tzinfo is None:
    requested_start_time = requested_start_time.replace(tzinfo=timezone.utc)
```

**问题**：将 naive 时间视为 UTC（而非本地时区），如果前端传入本地时间会导致 8 小时偏移。

**`sync_by_time_range` 方法**（未转换）：
```python
start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
# 未做时区转换
```

**`incremental_sync` 方法**（正确）：
```python
analysis_end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```
使用 UTC 时间，正确。

---

## 6. LLM Tool 时间参数审查（正面案例）

### 6.1 文件
**文件**：`lifeprism/llm/agent/tools/lifeprismsystem.py`

### 6.2 时间转换函数（正确实现）

#### `_parse_local_time(time_str)` - 本地时间转 UTC
```python
def _parse_local_time(time_str: str) -> datetime:
    # 解析时间字符串
    if "T" in time_str:
        dt = datetime.fromisoformat(time_str)
    else:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    
    # 如果 naive，附加用户时区
    if dt.tzinfo is None:
        tz = pytz.timezone(get_user_timezone())
        dt = tz.localize(dt)
    
    # 转换为 UTC
    return dt.astimezone(timezone.utc)
```

**正确性分析**：
- ✅ 支持 `YYYY-MM-DD HH:MM:SS` 和 `YYYY-MM-DDTHH:MM:SS` 两种格式
- ✅ 正确处理 naive 时间（附加用户时区）
- ✅ 正确处理 aware 时间（直接转 UTC）
- ✅ 使用 `pytz.timezone(get_user_timezone())` 获取用户配置时区

#### `_parse_iso_time(time_str)` - ISO 时间解析
用于解析数据库返回的时间字段，兼容带时区和不带时区（默认 UTC）的输入。

#### `_utc_to_local(utc_time_str)` - UTC 转本地时间
```python
def _utc_to_local(utc_time_str: str) -> str:
    # 解析 UTC 时间
    if "T" not in time_str:
        dt = datetime.strptime(time_str[:19], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(time_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    # 转本地时区
    tz = pytz.timezone(get_user_timezone())
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")
```

**正确性分析**：
- ✅ 正确将 UTC 时间转换为本地时区显示
- ✅ 兼容 SQLite DEFAULT 输出和 ISO 8601 格式

### 6.3 工具调用链路（正确）

所有 LLM 工具的时间参数处理流程：

1. **接收本地时间字符串**（来自 LLM）
2. **调用 `_parse_local_time`** 转换为 UTC aware datetime
3. **调用 `.isoformat()`** 转换为 ISO 8601 + UTC 字符串
4. **传给 Repository 查询数据库**

```python
# 示例：UserComputerLogTool
start_time = _parse_local_time(start_time).isoformat()
end_time = _parse_local_time(end_time).isoformat()

app_log, _ = computer_usage_repository.query_computer_usage_with_names(
    QueryOptions(...).with_time_range(start_time, end_time)
)
```

**受影响工具**：
- `UserActivitySummaryTool` - 用户活动摘要查询
- `UserComputerLogTool` - 电脑使用日志查询
- `UserMoodQuryTool` - 心情记录查询
- `CreateTimelineCustomBlockTool` - 创建自定义时间块

### 6.4 LLM Tool 结论
**LLM Tool 是项目中的正面案例**，完整实现了本地时区到 UTC 的双向转换，可作为其他模块的参考实现。

---

## 7. Repository 层时间查询审查

### 7.1 通用查询基类
**文件**：`lifeprism/repository/base_providers/lw_base_data_provider.py`

**`_build_where_clause` 方法**：
```python
# 时间范围（只有当表有时间字段时才处理）
if options.time_range:
    start_time, end_time = options.time_range
    if start_time:
        conditions.append(f"{self._TIME_FIELD} >= ?")
        params.append(start_time)
    if end_time:
        conditions.append(f"{self._TIME_FIELD} <= ?")
        params.append(end_time)
```

**问题**：
- 使用 SQL 字符串比较（字典序）
- **无时区感知**，假设调用方传入的字符串与数据库存储格式一致
- 字符串比较对于相同格式的 UTC 时间是正确的，但如果调用方传入本地时间会导致错位

### 7.2 QueryOptions 数据类
**文件**：`lifeprism/repository/providers/common_query_options.py`

```python
@dataclass(frozen=True)
class QueryOptions:
    date_range: tuple[str, str] | None = None
    time_range: tuple[str, str] | None = None
```

**设计假设**：输入格式由调用方决定，无时区假设。这要求所有调用方必须确保传入 UTC 时间，但实际调用方（如 `report_service`、`timeline_builder`）传入的是本地时间。

### 7.3 mood_providers.py
**文件**：`lifeprism/repository/providers/mood_providers.py`

```python
def get_mood_entries(self, start_time=None, end_time=None):
    conditions = []
    params = []
    if start_time:
        conditions.append("created_at >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("created_at < ?")
        params.append(end_time)
```

**问题**：直接使用字符串比较，无时区处理。`created_at` 存储为 UTC，但 LLM Tool 传入的是 ISO 8601 UTC 格式（正确），而 `mood_service` 传入的是本地日期（错误）。

### 7.4 custom_block_provider.py
**文件**：`lifeprism/repository/providers/custom_block_provider.py`

```python
def get_custom_blocks_by_date(self, date: str):
    start_of_day = f"{date} 00:00:00"  # 本地时间！
    end_of_day = f"{date} 23:59:59"
    sql = """
    SELECT * FROM timeline_custom_block
    WHERE start_time >= ? AND start_time <= ?
    ORDER BY start_time ASC
    """
```

**问题**：直接使用本地日期字符串查询 UTC 存储的时间字段。

同样的问题出现在：
- `get_duration_by_todo(todo_id, date)` - 使用 `f"{date} 00:00:00"`
- `batch_get_duration_by_todos(todo_ids, date)` - 使用 `f"{date} 00:00:00"`

### 7.5 behavior_analysis_provider.py
**文件**：`lifeprism/repository/providers/behavior_analysis_provider.py`

```python
def get_behaviors_by_date(self, date: str):
    start_datetime = f"{date} 00:00:00"  # 本地时间！
    end_datetime = f"{date} 23:59:59"
    sql = """
    SELECT * FROM behavior_analysis
    WHERE start_time >= ? AND start_time <= ?
    ORDER BY start_time ASC
    """
```

**问题**：同样直接使用本地日期字符串查询 UTC 存储的时间字段。

### 7.6 diary_provider.py（影响较小）
**文件**：`lifeprism/repository/providers/diary_provider.py`

```python
def get_diaries_by_date_range(self, start_date, end_date):
    options = QueryOptions(date_range=(start_date, end_date), order_by="date", order_desc=True)
```

**说明**：diary 表使用 `date` 字段（`YYYY-MM-DD` 格式日期，非时间戳），因此时区影响较小。日记按日期组织，不涉及时间部分。

### 7.7 Repository 层结论
Repository 层的设计假设是**调用方负责确保时间格式正确**。这种设计本身是合理的（保持 Repository 层简单），但要求所有调用方必须将本地时间转换为 UTC 后再传入。

**实际情况**：除了 LLM Tool 外，几乎所有调用方都未进行转换。

---

## 8. 不匹配情况汇总

### 8.1 前端假设 vs 后端实际

| 前端假设 | 后端实际 | 影响 |
|----------|----------|------|
| 前端发送本地时间字符串 `YYYY-MM-DD HH:MM:SS` | 后端 API 接收并透传给 Service 层 | Service 层收到本地时间字符串 |
| 前端假设后端会处理时区转换 | Service 层直接使用 `f"{date} 00:00:00"` 查询数据库 | 数据库查询使用本地时间，与 UTC 存储错位 |
| 前端 `dateUtils.ts` 提供了 `toISOStringUTC` 函数 | 前端组件未调用该函数 | 转换工具存在但未被使用 |

### 8.2 服务层辅助函数 vs 实际使用

| 文件 | 定义的辅助函数 | 是否被使用 | 实际查询使用 |
|------|----------------|------------|--------------|
| `report_service.py` | `_build_utc_time_range` | ❌ 未使用 | `f"{date} 00:00:00"` |
| `report_service.py` | `_utc_timestamp_to_local_date` | ❌ 未使用 | 直接使用 UTC 时间戳分组 |
| `report_service.py` | `_add_local_date_column` | ❌ 未使用 | 直接按 `start_dt.dt.date` 分组 |
| `activity_stats_builder.py` | `_build_utc_time_range` | ❌ 未使用 | `f"{date} 00:00:00"` |
| `activity_stats_builder.py` | `_utc_timestamp_to_local_date` | ❌ 未使用 | - |
| `activity_stats_builder.py` | `_add_local_date_column` | ❌ 未使用 | - |

### 8.3 LLM Tool vs 其他模块

| 对比项 | LLM Tool | 其他模块 |
|--------|----------|----------|
| 本地时间转 UTC | ✅ `_parse_local_time` | ❌ 未转换 |
| UTC 转本地时间 | ✅ `_utc_to_local` | ❌ 未转换 |
| 数据库查询格式 | ISO 8601 + UTC | 本地时间字符串 |
| 时区配置使用 | ✅ `get_user_timezone()` | ❌ 未使用 |

---

## 9. 修复建议

### 9.1 优先级 P0（严重影响数据准确性）

#### 9.1.1 服务层启用 UTC 转换
**涉及文件**：
- `lifeprism/server/services/report_service.py`
- `lifeprism/server/services/activity_stats_builder.py`
- `lifeprism/server/services/timeline_builder.py`

**修复方案**：将所有 `f"{date} 00:00:00"` 和 `f"{date} 23:59:59"` 替换为调用已有的 `_build_utc_time_range(date)` 函数。

**示例**：
```python
# 修改前
start_time = f"{date} 00:00:00"
end_time = f"{date} 23:59:59"

# 修改后
start_time, end_time = _build_utc_time_range(date)
```

**受影响函数**：
- `report_service.py`: `_calc_sunburst_data`, `_calc_goal_time_invested`, `_calc_hourly_trend`, `_calc_weekly_trend`, `_calc_monthly_trend`, `_calc_heatmap_data`, `_calc_comparison_data`
- `activity_stats_builder.py`: `build_time_overview`
- `timeline_builder.py`: `load_day_events`

#### 9.1.2 Timeline 筛选 API 链路
**涉及文件**：
- 前端：`frontend/apps/lifewatch/pages/timeline/Timeline.tsx`
- 前端：`frontend/apps/lifewatch/pages/home/components/ActivitySummaryHeader.tsx`
- 后端 API：`lifeprism/server/api/activity_api.py`、`lifeprism/server/api/sync.py`
- 后端服务：`lifeprism/server/services/activity_service.py`、`lifeprism/server/services/sync_service.py`

**修复方案 A（推荐）**：后端 API 层接收本地时间，转换为 UTC 后传给 Service 层。
- 在 API 层增加时区转换中间件
- Service 层统一接收 UTC 时间

**修复方案 B**：前端在提交前转换为 UTC。
- 前端调用 `toISOStringUTC` 转换
- 后端 API 层明确要求 UTC 格式

### 9.2 优先级 P1（影响特定功能）

#### 9.2.1 Repository 层手写 SQL 查询
**涉及文件**：
- `lifeprism/repository/providers/custom_block_provider.py` - `get_custom_blocks_by_date`, `get_duration_by_todo`, `batch_get_duration_by_todos`
- `lifeprism/repository/providers/behavior_analysis_provider.py` - `get_behaviors_by_date`, `get_behaviors_by_date_range`
- `lifeprism/repository/providers/mood_providers.py` - `get_mood_entries`

**修复方案**：调用方（Service 层）负责将本地日期转换为 UTC 时间范围后传入。

#### 9.2.2 sync_service.py 时间处理
**涉及文件**：`lifeprism/server/services/sync_service.py`

**问题**：
- `screen_behavior_anlysis` 将 naive 时间视为 UTC（应视为本地时区）
- `sync_by_time_range` 未做时区转换

**修复方案**：统一使用 `_parse_local_time` 模式（参考 LLM Tool）。

### 9.3 优先级 P2（影响较小）

#### 9.3.1 日记和心情模块
- `diary_service.py`：日记按日期组织，影响较小
- `mood_service.py`：心情记录按 `created_at` 查询，需要转换

### 9.4 修复实施建议

#### 阶段一：服务层启用已有辅助函数
1. 在 `report_service.py` 和 `activity_stats_builder.py` 中启用已定义但未使用的 `_build_utc_time_range` 函数
2. 在 `timeline_builder.py` 中添加并使用 `_build_utc_time_range` 函数
3. 验证所有计算函数使用 UTC 时间范围查询数据库

#### 阶段二：API 层增加时区转换
1. 在 FastAPI 路由层增加时区转换逻辑（或中间件）
2. 明确 API 接收的是本地时间还是 UTC 时间
3. 统一 Service 层接口为 UTC 时间

#### 阶段三：前端清理
1. 如果 API 层接收本地时间，前端无需修改
2. 如果 API 层接收 UTC 时间，前端需调用 `toISOStringUTC` 转换

#### 阶段四：Repository 层手写 SQL 清理
1. 将 `get_custom_blocks_by_date`、`get_behaviors_by_date` 等方法的调用方改为传入 UTC 时间范围
2. 或在 Repository 层方法内部增加时区转换

---

## 10. 附录

### 10.1 审查文件清单

#### 前端文件
- `frontend/core/utils/dateUtils.ts`
- `frontend/apps/lifewatch/pages/home/api.ts`
- `frontend/apps/lifewatch/pages/home/components/ActivitySummaryHeader.tsx`
- `frontend/apps/lifewatch/pages/reports/api.ts`
- `frontend/apps/lifewatch/pages/timeline/Timeline.tsx`
- `frontend/apps/lifewatch/pages/usage/UsagePage.tsx`
- `frontend/apps/lifewatch/pages/category/api.ts`
- `frontend/apps/custom-records/api.ts`
- `frontend/apps/mindspace/components/mood/moodApi.ts`
- `frontend/apps/mindspace/components/journal/diaryApi.ts`
- `frontend/core/services/commonApi.ts`

#### 后端 API 文件
- `lifeprism/server/api/activity_api.py`
- `lifeprism/server/api/timeline_api.py`
- `lifeprism/server/api/sync.py`
- `lifeprism/server/api/report_api.py`
- `lifeprism/server/api/mood_api.py`
- `lifeprism/server/api/diary_api.py`

#### 后端服务文件
- `lifeprism/server/services/activity_service.py`
- `lifeprism/server/services/activity_stats_builder.py`
- `lifeprism/server/services/timeline_builder.py`
- `lifeprism/server/services/timeline_service.py`
- `lifeprism/server/services/report_service.py`
- `lifeprism/server/services/mood_service.py`
- `lifeprism/server/services/diary_service.py`
- `lifeprism/server/services/sync_service.py`

#### Repository 文件
- `lifeprism/repository/base_providers/lw_base_data_provider.py`
- `lifeprism/repository/providers/common_query_options.py`
- `lifeprism/repository/providers/custom_block_provider.py`
- `lifeprism/repository/providers/behavior_analysis_provider.py`
- `lifeprism/repository/providers/mood_providers.py`
- `lifeprism/repository/providers/diary_provider.py`
- `lifeprism/repository/providers/todo_provider.py`

#### LLM Tool 文件
- `lifeprism/llm/agent/tools/lifeprismsystem.py`

#### 配置文件
- `lifeprism/config/__init__.py`

### 10.2 时区架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端（本地时区显示）                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Timeline.tsx │  │ Home Header  │  │ Reports API  │          │
│  │  本地时间字符串 │  │  本地时间字符串 │  │  本地日期字符串 │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                     │
│                    URLSearchParams                              │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    后端 API 层（无时区转换）                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ activity_api │  │  sync_api    │  │ report_api   │          │
│  │  pattern验证  │  │  pattern验证  │  │  透传        │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                服务层（未转 UTC，直接使用本地时间）                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │activity_service│ │sync_service  │  │report_service│          │
│  │  透传         │  │  部分转 UTC   │  │  f"{date}..." │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                     │
│                    本地时间字符串                                  │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Repository 层（字符串比较，无时区感知）                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │_generic_query│  │mood_providers │  │custom_block  │          │
│  │  SQL 字符串比较│  │  SQL 字符串比较│  │  SQL 字符串比较│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    数据库（UTC ISO 8601 存储）                     │
│            ⚠️ 本地时间字符串与 UTC 时间比较 → 错位                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                LLM Tool（正面案例，正确转换）                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │_parse_local_ │  │_parse_iso_time│  │_utc_to_local │          │
│  │  time()      │  │  ()           │  │  ()          │          │
│  │ 本地→UTC ✅   │  │ ISO→UTC ✅    │  │ UTC→本地 ✅   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                     │
│                    UTC ISO 8601 字符串                            │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    数据库（UTC ISO 8601 存储）                     │
│            ✅ UTC 时间字符串与 UTC 时间比较 → 正确                   │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 修复优先级矩阵

| 模块 | 影响范围 | 修复难度 | 优先级 | 备注 |
|------|----------|----------|--------|------|
| `report_service.py` | 所有报告数据 | 低（启用已有函数） | P0 | 辅助函数已存在 |
| `activity_stats_builder.py` | 首页统计 | 低（启用已有函数） | P0 | 辅助函数已存在 |
| `timeline_builder.py` | Timeline 页面 | 低（添加辅助函数） | P0 | 需添加函数 |
| `activity_api.py` + 前端 | 活动日志查询 | 中（需确定方案） | P0 | 需确定 A/B 方案 |
| `sync.py` + 前端 | 数据同步 | 中（需确定方案） | P0 | 需确定 A/B 方案 |
| `sync_service.py` | 截图分析 | 中 | P1 | 部分已转 |
| Repository 手写 SQL | 多个模块 | 中 | P1 | 调用方转换 |
| `mood_service.py` | 心情记录 | 低 | P2 | 影响较小 |
| `diary_service.py` | 日记 | 低 | P2 | 按日期组织 |

---

**报告结束**
