---
version: 1.0
created_at: 2026-07-12
updated_at: 2026-07-12
last_updated: 创建文档初稿，基于 UTC 时区迁移（ADR 2026-07-12）落地后的统一时间处理规范
abstract: 全栈时间处理规范，明确 UTC 存储 + ISO 8601 格式 + 展示层本地化的核心原则，区分时间戳字段与日期字段，约束后端时间生成/序列化/解析/定时任务和前端日期格式化行为
---

# 时间处理规范

## 1. 核心原则

系统统一遵循 **UTC 存储 + ISO 8601 格式 + 展示层本地化** 的业界最佳实践：

| 层级 | 时区 | 格式 | 说明 |
|------|------|------|------|
| **数据层**（数据库、API 传输） | UTC | ISO 8601（带时区标识） | `2026-07-11T16:29:54.123456+00:00` |
| **逻辑层**（后端计算、前端计算） | aware datetime / Date 对象 | - | Python 用 `timezone.utc` aware datetime；JS 用 `Date` 对象 |
| **展示层**（前端 UI） | 用户本地时区 | 本地化字符串 | 浏览器 `Date` 自动处理时区转换 |

**设计依据**：`docs/adr/2026-07-12-migrate-to-utc-timezone.md`

---

## 2. 字段分类（关键区分）

时间字段分为两类，**时区处理方式不同**，编写代码前必须先确认字段类型。

### 2.1 时间戳字段（UTC 存储）

记录"某个时刻"，必须使用 UTC + ISO 8601 格式存储和传输。

| 字段名 | 说明 |
|--------|------|
| `created_at` | 记录创建时间 |
| `updated_at` | 记录更新时间 |
| `captured_at` | 截图捕获时间 |
| `finished_at` | 任务/挑战完成时间 |
| `paused_at` | 暂停时间 |
| `start_time` / `end_time` | 行为事件起止时间（监控数据） |
| `timestamp` | 通用时间戳（如消息、日志） |
| `last_sync_time` | 最后同步时间 |

**格式示例**：`2026-07-11T16:29:54.123456+00:00`

### 2.2 日期字段（本地时区，YYYY-MM-DD）

记录"用户语义的某一天"，保持用户本地时区日期，**不使用 UTC 日期**。

| 字段名 | 说明 |
|--------|------|
| `date` | 习惯打卡日期、日报日期等 |
| `start_date` | 目标开始日期 |
| `expected_finished_at`（日期部分） | 目标预期完成日期 |
| `actual_finished_at` | Todo 实际完成日期 |
| `finish_time`（里程碑，日期部分） | 里程碑完成日期 |

**格式示例**：`2026-07-12`

**为什么日期字段不用 UTC**：用户在 UTC+8 的 00:30 打卡，UTC 日期是"昨天"，但用户认为是"今天"。如果存 UTC 日期，用户查看"今日打卡"时看不到刚打的卡。

---

## 3. 后端规则

### 3.1 时间生成（强制）

```python
# ✅ 正确：使用 timezone.utc 生成 aware datetime
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
timestamp = datetime.now(timezone.utc).isoformat()

# ❌ 禁止：datetime.now() 返回 naive datetime（无时区信息）
now = datetime.now()
timestamp = datetime.now().isoformat()

# ❌ 禁止：strftime 生成无时区字符串
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

**规则**：
- 所有时间戳生成必须使用 `datetime.now(timezone.utc)`
- 禁止使用 `datetime.now()`（无时区参数）
- 禁止使用 `datetime.today()`、`date.today()` 生成时间戳（仅日期字段可用，见 3.5）

### 3.2 时间序列化（强制）

```python
# ✅ 正确：统一使用 .isoformat()，返回带时区的 ISO 8601 字符串
timestamp = datetime.now(timezone.utc).isoformat()
# 结果: "2026-07-11T16:29:54.123456+00:00"

# ❌ 禁止：strftime 生成无时区或不一致格式
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
```

**规则**：
- 所有时间戳序列化必须使用 `.isoformat()`
- 禁止使用 `.strftime()` 序列化时间戳字段
- 统一格式为 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`（带 T 分隔符、微秒、时区标识）

### 3.3 时间解析

```python
from datetime import datetime, timezone

# ✅ 正确：解析后确认是 aware datetime，naive 字符串补充 UTC 时区
dt = datetime.fromisoformat(iso_string)
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)  # 假设无时区字符串为 UTC

# ⚠️ 注意：历史数据迁移后，所有新数据都应带时区标识
# 仅在解析外部输入（API 参数、文件读取）时需要处理 naive 字符串
```

### 3.4 数据库 DEFAULT（强制）

```python
# ✅ 正确：SQLite datetime('now') 返回 UTC
"created_at TIMESTAMP DEFAULT (datetime('now'))"

# ❌ 禁止：datetime('now', 'localtime') 返回本地时间
"created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))"

# ❌ 禁止：CURRENT_TIMESTAMP 在部分 SQLite 版本行为不一致
"created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
```

**规则**：
- 所有表 DEFAULT 使用 `datetime('now')`（SQLite 的 `datetime('now')` 返回 UTC）
- 禁止使用 `datetime('now', 'localtime')`
- 新建表遵循 `docs/coding-rules/create-table-rules.md`

### 3.5 日期字段生成（本地时区）

日期字段（YYYY-MM-DD）基于用户本地时区，不基于 UTC：

```python
# ✅ 正确：基于用户本地时区获取"今天"
from datetime import datetime
import pytz
from lifeprism.config import LOCAL_TIMEZONE

def get_local_today() -> str:
    """获取用户本地时区的今天日期 YYYY-MM-DD"""
    return datetime.now(pytz.timezone(LOCAL_TIMEZONE)).strftime("%Y-%m-%d")

today = get_local_today()

# ❌ 错误：基于 UTC 的"今天"，UTC+8 午夜前后日期错误
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

**规则**：
- `date`、`start_date` 等业务日期字段基于用户本地时区
- 时间戳字段（`created_at`、`updated_at`）基于 UTC
- 编写时间相关代码前，先确认字段属于哪一类（见第 2 节）

### 3.6 定时任务时区

```python
# ✅ 正确：APScheduler 显式设置 UTC 时区
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone=pytz.UTC)
trigger = CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)

# ❌ 禁止：未设置 timezone，依赖系统本地时区
scheduler = AsyncIOScheduler()
trigger = CronTrigger.from_crontab(cron_expr)
```

**Cron 表达式规则**：
- Cron 表达式基于 **UTC 时间**
- 若需保持用户感知的"本地时间触发"，需转换：本地 10:00（UTC+8）= UTC 02:00
- 示例：`_SYSTEM_CRON_JOB_TIME = "0 2 * * *"`（UTC 02:00 = 北京时间 10:00）

**"今天"/"昨天"语义**：
- 定时任务中"今天"/"昨天"的语义基于**用户本地时区**（用户感知的日期）
- 存储到数据库的时间戳仍使用 UTC
- 示例：`_dreaming()` 处理"昨天的日记"，日期范围用本地时区计算，执行时间戳用 UTC

---

## 4. 前端规则

### 4.1 时间戳字段（UTC）

发送给后端的时间戳字段使用 UTC ISO 8601 格式：

```typescript
import { toISOStringUTC, parseISOString } from '@core/utils/dateUtils';

// ✅ 正确：发送 UTC 时间给后端
const timestamp = toISOStringUTC(new Date());
// 结果: "2026-07-11T16:29:54.123Z"

// ✅ 正确：解析后端返回的 ISO 字符串
const date = parseISOString('2026-07-11T16:29:54.123456+00:00');
```

### 4.2 日期字段（本地时区，YYYY-MM-DD）

日期字段必须使用本地时区方法，**禁止 `.toISOString().split('T')[0]`**：

```typescript
import { toLocalDateString } from '@core/utils/dateUtils';

// ✅ 正确：本地日期字符串
const today = toLocalDateString(new Date());
// 结果: "2026-07-12"（基于浏览器本地时区）

// ❌ 禁止：toISOString 返回 UTC，UTC+ 午夜会导致日期减一天
const today = new Date().toISOString().split('T')[0];
// UTC+8 的 00:30 → "2026-07-11"（错误，应是 07-12）
```

**详细规则见**：`docs/coding-rules/frontend-date-handling.md`

### 4.3 后端返回的 YYYY-MM-DD 字符串

后端返回的日期字符串（如 `2026-07-12`）直接使用，**不要转 `Date` 再格式化**：

```typescript
// ✅ 直接用
challenge.startDate;

// ❌ 多余且引入时区风险
toLocalDateString(new Date(challenge.startDate));
```

### 4.4 禁止事项

| 禁止项 | 说明 | 正确做法 |
|--------|------|---------|
| ❌ `new Date().toISOString().split('T')[0]` | UTC 日期，午夜错位 | `toLocalDateString(date)` |
| ❌ 内联手写 `${y}-${m}-${d}` | 违反 SSOT | `toLocalDateString(date)` |
| ❌ 对日期字段用 `toISOString()` | 返回 UTC | `toLocalDateString(date)` |

**例外**：时间戳字段发送给后端时，`toISOString()`（即 `toISOStringUTC`）是正确做法。

---

## 5. 数据同步规则

LWW（Last-Write-Wins）冲突解决依赖字符串比较，**格式和时区必须完全一致**：

- 所有 `updated_at` 统一为 UTC ISO 8601 格式
- 字符串比较在相同时区、相同格式下与时间顺序一致
- `last_sync_time` 使用 UTC ISO 格式存储
- 迁移后 `last_sync_time` 需重置，触发全量同步

---

## 6. 暂停机制

遇到以下情况**必须暂停，与用户讨论后再编码**：

- 不确定字段属于"时间戳字段"还是"日期字段"
- 需要跨时区比较或传递给要求特定时区的外部 API
- 需要新增日期格式化函数（应统一在 `dateUtils.ts` / 后端时间工具中）
- 历史数据迁移涉及时区假设不确定
- 定时任务的 Cron 表达式需要调整时区转换

---

## 7. 相关文档

- `docs/adr/2026-07-12-migrate-to-utc-timezone.md` - UTC 迁移决策
- `docs/coding-rules/frontend-date-handling.md` - 前端日期格式化详细规则
- `docs/coding-rules/create-table-rules.md` - 建表规范（含 DEFAULT 时间戳）
- `docs/guides/utc-migration-hidden-dependencies.md` - 迁移隐性依赖排查清单
- `frontend/core/utils/dateUtils.ts` - 前端日期工具函数（单一真相源）
