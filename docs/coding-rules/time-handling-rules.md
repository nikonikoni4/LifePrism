---
version: 4.0
created_at: 2026-07-12
updated_at: 2026-07-13
last_updated: 新增日期查询 datetime 字段表的前端/后端规则
abstract: 时间处理规则，明确"内部 UTC + ISO 8601，对外本地时区 + YYYY-MM-DD HH:MM:SS"的内外分离原则，所有转换在边界处就地完成。新增前端组件内转换 date → UTC 时间范围、后端直接使用 UTC 参数的规则
---

# 时间处理规则

## 1. 核心原则：内外分离 + 就地转换

| 分类 | 时区 | 格式 | 适用场景 |
|------|------|------|---------|
| **内部**（存储、模块间传输、后端计算） | UTC | ISO 8601（带时区标识） | 数据库、API 响应、后端逻辑 |
| **对外**（面向用户、面向 AI） | 本地时区 | `YYYY-MM-DD HH:MM:SS` | 前端显示、大模型提示词、大模型工具参数 |
| **日期字段**（例外） | 本地时区 | `YYYY-MM-DD` | 打卡日期、日报日期等"某一天"语义 |

**就地转换规则**：
- 组件/模块**内部**使用本地时区时，在**传出去的那一刻**就地转为 UTC ISO
- 组件/模块**接收**外部本地时间时，在**入口处**就地转为 UTC ISO 再内部使用
- **禁止**将本地时间字符串透传到内部层（数据库查询、API 传输、后端计算）

**本地时区来源**：统一通过配置动态获取，禁止硬编码时区字符串用于业务逻辑。

**设计依据**：`docs/adr/2026-07-12-migrate-to-utc-timezone.md`、`docs/adr/2026-07-12-time-conversion-layering.md`

---

## 2. 字段分类规则

时间字段分为两类，**时区处理方式不同**，编写代码前必须先确认字段类型。

### 2.1 时间戳字段（UTC 存储）

记录"某个时刻"，必须使用 UTC + ISO 8601 格式。

**字段示例**：`created_at`、`updated_at`、`start_time`/`end_time`（监控数据）、`timestamp`、`last_sync_time` 等。

**格式示例**：`2026-07-11T16:29:54.123456+00:00`

### 2.2 日期字段（本地时区，YYYY-MM-DD）

记录"用户语义的某一天"，保持用户本地时区日期，**不使用 UTC 日期**。

**字段示例**：`date`（打卡日期）、`start_date`、`actual_finished_at` 等。

**格式示例**：`2026-07-12`

**理由**：用户在 UTC+8 的 00:30 打卡，UTC 日期是"昨天"，但用户认为是"今天"。存 UTC 日期会导致"今日打卡"看不到刚打的卡。

---

## 3. 后端规则

### 3.1 时间生成

- 所有时间戳必须生成 UTC aware datetime（示例：`datetime.now(timezone.utc)` 或项目时间工具函数）
- **禁止** `datetime.now()`（无时区参数）
- **禁止** `datetime.today()`、`date.today()` 生成时间戳（仅日期字段可用）

### 3.2 时间序列化

- 所有时间戳序列化必须使用 `.isoformat()`
- **禁止** `.strftime()` 序列化时间戳字段
- 统一格式为 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`

```python
# ✅
datetime.now(timezone.utc).isoformat()

# ❌
datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```

### 3.3 时间解析

- 解析 ISO 字符串必须确保返回 aware datetime
- **禁止** `datetime.fromisoformat()` 后不做 tzinfo 检查

### 3.4 数据库 DEFAULT

- 所有表 DEFAULT 使用 `datetime('now')`（SQLite 返回 UTC）
- **禁止** `datetime('now', 'localtime')`
- **禁止** `CURRENT_TIMESTAMP`

### 3.5 日期字段生成

- 日期字段基于用户本地时区（示例：`get_local_today()` 或等效方法）
- 时间戳字段基于 UTC
- 编写代码前必须先确认字段属于哪一类

### 3.6 定时任务

**Cron 表达式**：写本地时间，`CronTrigger` 的 `timezone` 参数设为用户本地时区。

```python
# ✅ Cron 表达式写本地时间，timezone 设为本地时区
trigger = CronTrigger.from_crontab("0 10 * * *", timezone=local_tz)

# ❌ Cron 表达式写 UTC 时间，硬编码换算
trigger = CronTrigger.from_crontab("0 2 * * *", timezone=pytz.UTC)
```

**硬编码本地时间常量**：保留为纯时间字符串（如 `"04:00:00"`），**使用时立即就地转 UTC ISO**。

```python
# ✅ 常量保留，使用时转 UTC ISO
start_time = local_to_utc(build_local_datetime(date, DAILY_START_HOUR))

# ❌ 直接拼接无时区字符串
start_time = f"{date} {DAILY_START_HOUR}"
```

**"今天"/"昨天"语义**：基于用户本地时区，**禁止**基于 UTC 计算业务日期。

### 3.7 日期查询 datetime 字段表：后端直接使用 UTC 参数

**场景**：前端传 UTC 时间范围查询只有 datetime 字段的表。

**规则**：后端直接使用 UTC 参数，**禁止**字符串拼接本地时间。

```python
# ✅ 正确：直接使用 UTC 参数
def get_timeline_stats(start_time: str, end_time: str):
    """
    Args:
        start_time: ISO 8601 UTC 格式（如 "2026-07-12T16:00:00.000Z"）
        end_time: ISO 8601 UTC 格式（如 "2026-07-13T15:59:59.999Z"）
    """
    df = repository.load_logs(start_time=start_time, end_time=end_time)
    # 直接传 UTC ISO 字符串给 Repository
    
# ❌ 错误：字符串拼接本地时间
def get_timeline_stats(date: str):
    start_time = f"{date} 00:00:00"  # 本地时间字符串，无时区标识
    end_time = f"{date} 23:59:59"
    df = repository.load_logs(start_time=start_time, end_time=end_time)
```

**Repository 层**：

```python
# ✅ 正确：直接使用 UTC 参数查询
def load_logs(start_time: str, end_time: str):
    cursor.execute(
        "SELECT * FROM logs WHERE start_time >= ? AND start_time <= ?",
        (start_time, end_time)
    )
    
# ❌ 错误：在 Repository 层拼接时间字符串
def load_logs(date: str):
    start_time = f"{date} 00:00:00"  # 违反"就近转换"原则
    cursor.execute("SELECT * FROM logs WHERE start_time >= ?", (start_time,))
```

**适用场景**：
- Timeline Stats API（查询 `user_app_behavior_log` 只有 `start_time/end_time`）
- Timeline Overview API（同上）
- Custom Block API（查询 `timeline_custom_block` 只有 `start_time/end_time`）

**不适用场景**：
- 查询有独立 `date` 字段的表（如 `todo_list.date`），接收 `date=YYYY-MM-DD` 参数
- 聚合查询（混合表），需同时接收 `date` + `start_time/end_time` 参数

**决策依据**：`docs/adr/2026-07-13-date-to-utc-conversion-boundary.md`

---

## 4. 大模型交互规则

大模型交互涉及两个方向的时间，**默认本地时区，就地转换**。

### 4.1 提示词输入（后端 → 大模型）：本地时间

- 提示词中的时间必须转换为本地时区 `YYYY-MM-DD HH:MM:SS` 格式
- 同时标注时区名称（如"时区：Asia/Shanghai"），让 AI 知道本地时区
- **禁止**把 UTC ISO 时间直接注入提示词

```python
# ✅ 本地时间格式
"当前时间：2026-07-12 10:30:00（时区：Asia/Shanghai）"

# ❌ UTC ISO 格式
"当前时间：2026-07-12T02:30:00+00:00"
```

### 4.2 工具输入（大模型 → 后端）：本地时间，execute 层转 UTC

- 大模型工具参数中的时间默认本地时区 `YYYY-MM-DD HH:MM:SS`
- **execute 方法层**负责输入转换：本地时间 → UTC ISO
- 转换后工具函数内部一致使用 UTC ISO（包括数据库查询）
- **禁止**把大模型输出的本地时间字符串直接用于数据库查询

```python
# ✅ execute 层转换
async def execute(self, **kwargs):
    start_utc = local_to_utc(kwargs["start_time"])
    return tool_func(start_utc, ...)

# ❌ 工具函数内部用本地时间查库
def tool_func(start_time):
    db.query("WHERE created_at >= ?", (start_time,))  # 本地时间查 UTC 数据
```

### 4.3 工具输出（后端 → 大模型）：区分显示用与计算用

工具函数返回结果中的时间字段，**必须区分用途**：

- **显示用字段**：转本地 `YYYY-MM-DD HH:MM:SS` 后返回给 AI
- **计算用字段**：保持 UTC ISO，不转（如用于时间区间截断、时长计算的字段）

```python
# ✅ 显示用字段转本地
content += f"时间: {utc_to_local(log['start_time'])}"

# ✅ 计算用字段保持 UTC ISO
segment_start = parse_iso(log['start_time'])  # 用于时间区间计算
```

**理由**：只有工具函数知道字段用途，所以转换必须在工具函数内部显式进行，不能用装饰器自动转换（装饰器无法区分显示用与计算用，会误转计算字段）。

### 4.4 工具函数内部一致性

- 工具函数接收 UTC ISO 参数（由 execute 层转换）
- 工具函数返回的原始数据是 UTC ISO
- 工具函数内部格式化输出时，显式转换显示用字段

---

## 5. 前端规则

### 5.1 时间戳显示：UTC ISO → 本地

- 组件接收 UTC ISO，**内部就地转换**为本地 `YYYY-MM-DD HH:MM:SS` 显示
- 使用项目日期工具函数转换，禁止内联手写格式化逻辑

```typescript
// ✅
const display = toLocalDateTimeString(parseISOString(isoString));

// ❌ 直接显示 UTC ISO
<p>{isoString}</p>
```

### 5.2 提交后端：本地时间 → UTC ISO

- 用户选择/输入的时间，**提交时就地转为 UTC ISO** 再传给后端
- **禁止**提交本地时间字符串给后端（无时区标识）

### 5.3 日期字段：本地时区

- 日期字段使用本地时区方法，**禁止** `.toISOString().split('T')[0]`
- 后端返回的 `YYYY-MM-DD` 字符串直接使用，不要转 `Date` 再格式化

### 5.4 日期查询 datetime 字段表：前端组件内转换

**场景**：查询只有 datetime 字段（无独立 date 字段）的表时，前端传日期参数。

**规则**：在 API 调用前（组件内），将本地日期转换为 UTC 时间范围再传给后端。

```typescript
// ✅ 正确：组件内转换 date → UTC 时间范围
import { toISOStringUTC } from '@core/utils/dateUtils';

async function getStats(date: string) {
    const startOfDay = new Date(`${date}T00:00:00`);
    const endOfDay = new Date(`${date}T23:59:59.999`);
    
    const params = {
        start_time: toISOStringUTC(startOfDay),  // "2026-07-12T16:00:00.000Z"
        end_time: toISOStringUTC(endOfDay)       // "2026-07-13T15:59:59.999Z"
    };
    
    return fetch(`/api/stats?start_time=${params.start_time}&end_time=${params.end_time}`);
}

// ❌ 错误：直接传本地日期字符串给后端
async function getStats(date: string) {
    return fetch(`/api/stats?date=${date}`);  // 后端会字符串拼接出错
}
```

**适用场景**：
- Timeline Stats API（查询 `user_app_behavior_log` 只有 `start_time/end_time`）
- Timeline Overview API（同上）
- Custom Block API（查询 `timeline_custom_block` 只有 `start_time/end_time`）

**不适用场景**：
- 查询有独立 `date` 字段的表（如 `todo_list.date`、`diary.date`），直接传 `date=YYYY-MM-DD`
- 聚合查询（混合有 date 字段和只有 datetime 的表），见后端规则 3.7

**决策依据**：`docs/adr/2026-07-13-date-to-utc-conversion-boundary.md`

### 5.5 禁止事项

| 禁止项 | 正确做法 |
|--------|---------|
| `new Date().toISOString().split('T')[0]` | 用本地日期工具函数 |
| 内联手写 `${y}-${m}-${d}` | 用本地日期工具函数 |
| 直接显示后端 UTC ISO | 转本地 `YYYY-MM-DD HH:MM:SS` |
| 提交本地时间字符串给后端 | 转 UTC ISO 后提交 |

---

## 6. 数据同步规则

- LWW 冲突解决依赖字符串比较，**格式和时区必须完全一致**
- 所有 `updated_at` 统一为 UTC ISO 8601
- `last_sync_time` 使用 UTC ISO 格式存储
- 迁移后 `last_sync_time` 需重置，触发全量同步

---

## 7. 暂停规则

遇到以下情况**必须暂停，与用户讨论后再编码**：

- 不确定字段属于"时间戳字段"还是"日期字段"
- 需要跨时区比较或传递给要求特定时区的外部 API
- 需要新增日期格式化函数（应统一在项目时间工具模块）
- 历史数据迁移涉及时区假设不确定
- 大模型工具参数格式不确定是本地时间还是 UTC
- 不确定时间字段是"显示用"还是"计算用"

---

## 8. 相关文档

- `docs/adr/2026-07-12-migrate-to-utc-timezone.md` - UTC 迁移决策
- `docs/adr/2026-07-12-time-conversion-layering.md` - 时间转换职责分层决策
- `docs/adr/2026-07-13-date-to-utc-conversion-boundary.md` - 日期到 UTC 转换边界决策
- `docs/coding-rules/frontend-date-handling.md` - 前端日期格式化详细规则
- `docs/coding-rules/create-table-rules.md` - 建表规范
- 项目时间工具模块（后端/前端各自单一真相源）
