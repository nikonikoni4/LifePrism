---
version: 1.0
created_at: 2026-07-12
updated_at: 2026-07-12
last_updated: 创建文档初稿，全面排查前后端隐性时区依赖
abstract: UTC 时区迁移项目的隐性依赖排查清单和修改指导文档，供后续 18 个 issues 参考
---

# UTC 时区迁移隐性依赖排查与修改指导

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿，完成全面排查 |

## 1. 文档说明

### 1.1 目的

本文档是 UTC 时区迁移项目（Issue #1）的产出，全面排查系统中所有可能受时区变化影响的代码和逻辑，为后续 18 个 issues 提供修改指导。

### 1.2 排查范围

- 后端 Python 代码：59 个文件包含 `datetime.now()`
- 前端 TypeScript 代码：27 处违规使用 `.toISOString()`
- 数据库 schema：80+ 张表的时间字段
- 数据同步逻辑：LWW 冲突解决、增量查询
- 定时任务：APScheduler 配置、Cron 表达式
- 数据管道：ActivityWatch → 本地 DB 的时区转换

### 1.3 停止条件评估

**结论：未触发停止条件，迁移可行。**

- 核心功能不会完全失效（所有问题都有已知解决方案）
- 历史数据可迁移（假设 UTC+8，统一减 8 小时）
- 用户体验不受严重影响（前端 Date 对象自动处理时区转换）
- 主要风险可通过分阶段发布和测试缓解

### 1.4 风险等级定义

| 等级 | 定义 | 修改时机 |
| ---- | ---- | -------- |
| **高** | 不修改会导致数据错误、同步失败、核心功能异常 | 必须在同一次迁移中修改 |
| **中** | 不修改会导致部分功能异常或显示错误 | 应在同一次迁移中修改，可分批 |
| **低** | 不修改不影响功能正确性，仅影响可读性或日志 | 可后续优化 |

---

## 2. 隐性依赖清单

### 2.1 数据库 Schema 层（高风险）

#### 2.1.1 表 DEFAULT 时间戳生成

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/repository/lw_table_manager.py:81` | `datetime('now', 'localtime')` | 高 | 所有 `timestamps=True` 的表（48 张）的 `created_at` DEFAULT |
| `lifeprism/repository/lw_table_manager.py:83-85` | `datetime('now', 'localtime')` | 高 | 所有 `update_at=True` 的表（35 张）的 `updated_at` DEFAULT |
| `lifeprism/config/database.py` (CHAT_SESSION_CONFIG) | `timestamps: False` | 中 | `chat_session` 表手动写入时间戳，无 DEFAULT |
| `lifeprism/config/database.py` (TIMELINE_CUSTOM_BLOCK_CONFIG) | `CURRENT_TIMESTAMP` | 高 | 旧迁移遗留，3 张表使用 UTC（`todo_list.created_at`、`timeline_custom_block.created_at/updated_at`） |

**修复策略**：
- `lw_table_manager.py:81,83-85`：将 `datetime('now', 'localtime')` 改为 `datetime('now')`（SQLite 的 `datetime('now')` 返回 UTC）
- 旧迁移遗留的 3 张表：需要用 `ALTER TABLE` 修改 DEFAULT，并迁移历史数据
- `chat_session` 表：手动写入逻辑需要改为 UTC（见 2.5 节）

**注意事项**：
- SQLite 的 `ALTER TABLE` 不支持直接修改 DEFAULT 子句，需要重建表或创建新迁移脚本
- 已有表的 DEFAULT 修改不会影响现有数据，只影响新插入的数据
- 需要确保新建表和已有表使用相同的 DEFAULT 策略

#### 2.1.2 迁移脚本中的时间生成

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/repository/migrations/scripts/m006_add_updated_at.py:61` | `datetime('now', 'localtime')` | 中 | backfill 现有行的 `updated_at` |
| `lifeprism/repository/migrations/migration_runner.py:78` | `datetime.now().strftime("%Y%m%d%H%M%S")` | 低 | 数据库备份文件名，不影响数据 |

**修复策略**：
- `m006` 已执行完毕，历史数据已按本地时间 backfill，需要在 UTC 迁移脚本中一并转换
- 新的 `m008` 迁移脚本应使用 `datetime('now')`（UTC）

---

### 2.2 数据访问层（高风险）

#### 2.2.1 通用 updated_at 自动更新

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/repository/base_providers/lw_base_data_provider.py:1184` | `datetime.now().isoformat()` | 高 | 影响 35+ 张表的 `_generic_update` 方法，生成 naive 本地时间 ISO 格式 |

**当前行为**：
- 生成 `2026-07-12T00:29:54.123456`（本地时间，带 T，带微秒，无时区后缀）
- 与 SQLite DEFAULT 的 `2026-07-12 00:29:54`（本地时间，空格分隔，秒级）格式不一致

**修复策略**：
```python
# 改为
from datetime import datetime, timezone
data["updated_at"] = datetime.now(timezone.utc).isoformat()
# 生成: 2026-07-11T16:29:54.123456+00:00
```

**注意事项**：
- 这是影响面最广的修改点，所有通过 `_generic_update` 更新的记录都受影响
- 修改后格式与 SQLite DEFAULT（改为 UTC 后）仍不一致（T 分隔符 vs 空格），但 ISO 8601 字符串比较在同时区下是正确的
- 建议在后续优化中将 SQLite DEFAULT 也改为 ISO 格式，或统一使用 Python 生成时间戳

#### 2.2.2 Provider 层手动时间写入

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/repository/providers/map_cache_providers.py:311` | `datetime.now().isoformat()` | 高 | 批量更新 `multi_purpose_map_cache` |
| `lifeprism/repository/providers/map_cache_providers.py:672` | `datetime.now().isoformat()` | 高 | 批量更新 `single_purpose_map_cache` |
| `lifeprism/repository/providers/habit_providers.py:403` | `datetime.now().isoformat()` | 高 | 习惯更新（带 T 格式） |
| `lifeprism/repository/providers/habit_providers.py:404` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 高 | 习惯更新（空格格式，与 403 行不一致） |
| `lifeprism/repository/providers/habit_providers.py:558` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 高 | 习惯操作时间戳 |
| `lifeprism/repository/providers/habit_chain_providers.py:376` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 高 | 习惯链更新时间戳 |
| `lifeprism/repository/providers/goal_providers.py:490` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 高 | 目标 `time_invested_updated_at` |

**修复策略**：
- 统一改为 `datetime.now(timezone.utc).isoformat()`
- `habit_providers.py:403-404` 的格式不一致问题在迁移后自动解决

---

### 2.3 数据同步层（高风险）

#### 2.3.1 LWW 冲突解决 - 字符串比较

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/repository/sync_repository.py:637` | `existing_updated_at > incoming_updated_at` | 高 | LWW 核心逻辑，Python 字符串比较 |
| `lifeprism/repository/sync_repository.py:249` | `WHERE updated_at > ?` | 高 | 增量查询，SQLite 字符串比较 |
| `lifeprism/sync/sync_client.py:322` | `str(local_updated_at) <= str(last_sync_time)` | 高 | Pull 时判断本地是否修改 |
| `lifeprism/sync/sync_client.py:325` | `str(remote_row.get("updated_at", "")) > str(local_updated_at)` | 高 | Pull 时比较云端和本地 |

**当前问题**：
- `last_sync_time` 已经使用 UTC ISO 格式存储（`sync_client.py:230`：`datetime.now(timezone.utc).isoformat()`）
- 但数据库中的 `updated_at` 是本地时间 naive 格式
- 字符串比较 `2026-07-12 00:29:54`（本地）> `2026-07-11T16:29:54+00:00`（UTC）的结果是 True（因为 `1` < `2`），但实际上它们是同一时刻
- 导致所有本地记录都被认为"比 last_sync_time 新"，每次同步都会推送全部数据

**修复策略**：
- 迁移后所有 `updated_at` 统一为 UTC ISO 8601 格式（`2026-07-11T16:29:54.123456+00:00`）
- 字符串比较在相同时区、相同格式下是正确的
- 不需要修改比较逻辑本身，只需要确保两边格式一致

**注意事项**：
- **前后端必须同时迁移**：如果只有一端迁移，格式不一致会导致比较更加错误
- `last_sync_time` 在迁移后需要重置（设为空字符串或一个早于所有数据的时间），避免遗漏数据
- 3 张旧表（`todo_list`、`timeline_custom_block`）已经是 UTC，迁移后与其他表一致，不需要特殊处理

#### 2.3.2 云端同步 API 时间戳

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/api/sync_cloud_api.py:185` | `datetime.now(timezone.utc).isoformat()` | 低 | sync_time 返回值，已经是 UTC |
| `lifeprism/server/api/sync_cloud_api.py:220` | `datetime.now(timezone.utc).isoformat()` | 低 | sync_time 返回值，已经是 UTC |
| `lifeprism/server/api/sync_cloud_api.py:262` | `datetime.now(timezone.utc).isoformat()` | 低 | server_time 返回值，已经是 UTC |
| `lifeprism/sync/sync_client.py:230` | `datetime.now(timezone.utc).isoformat()` | 低 | last_sync_time 存储，已经是 UTC |
| `lifeprism/sync/sync_client.py:572` | `datetime.fromtimestamp(..., tz=timezone.utc).isoformat()` | 低 | 文件 mtime，已经是 UTC |
| `lifeprism/server/api/sync_cloud_api.py:300,356,366` | `datetime.fromtimestamp(..., tz=timezone.utc)` | 低 | 文件 mtime，已经是 UTC |

**修复策略**：无需修改，这些位置已经正确使用 UTC。

---

### 2.4 定时任务层（高风险）

#### 2.4.1 APScheduler 时区配置

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/schedule_service.py:213` | `AsyncIOScheduler()` | 高 | 未设置 timezone，使用系统本地时区 |
| `lifeprism/server/services/schedule_service.py:359` | `CronTrigger.from_crontab(cron_expr)` | 高 | 未设置 timezone，使用系统本地时区 |
| `lifeprism/server/services/schedule_service.py:324` | `IntervalTrigger(**interval_kwargs)` | 高 | 未设置 timezone，使用系统本地时区 |
| `lifeprism/server/services/schedule_service.py:75` | `_SYSTEM_CRON_JOB_TIME = "0 10 * * *"` | 高 | Cron 表达式，语义为"本地时间 10:00" |

**修复策略**：

```python
# 1. 调度器初始化时设置 UTC 时区
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

self._scheduler = AsyncIOScheduler(timezone=pytz.UTC)

# 2. Cron 表达式需要调整：本地 10:00 (UTC+8) = UTC 02:00
_SYSTEM_CRON_JOB_TIME = "0 2 * * *"  # UTC 02:00 = 北京时间 10:00

# 3. CronTrigger 显式设置时区
from apscheduler.triggers.cron import CronTrigger
trigger = CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)

# 4. IntervalTrigger 不受时区影响（间隔执行），但建议显式设置
trigger = IntervalTrigger(**interval_kwargs, timezone=pytz.UTC)
```

**注意事项**：
- Cron 表达式调整必须与调度器时区设置同时发布，否则任务触发时间会错
- 如果用户自定义了 Cron 任务（通过 API），需要记录用户输入的是本地时间还是 UTC，并提供转换
- `TEST_MODE` 下的 Cron 表达式（`schedule_service.py:102-103`）也需要调整

#### 2.4.2 "今天"/"昨天"语义

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/schedule_service.py:34` | `datetime.now() - timedelta(days=1)` | 高 | `_dreaming()` 获取"昨天"日期 |
| `lifeprism/server/services/schedule_service.py:184` | `datetime.now().strftime("%Y-%m-%d")` | 高 | `_should_execute_cron_today()` 获取"今天" |
| `lifeprism/server/services/schedule_service.py:222` | `now = datetime.now()` | 高 | `_add_system_jobs()` 判断是否过触发时间 |
| `lifeprism/server/services/schedule_service.py:267` | `datetime.now().strftime("%Y-%m-%d")` | 高 | `_execute_cron_with_state()` 记录执行日期 |
| `lifeprism/server/services/schedule_service.py:365` | `datetime.now().strftime("%Y-%m-%d")` | 高 | `add_cron_job()` 包装函数记录执行日期 |

**修复策略**：

```python
# 所有 datetime.now() 改为 datetime.now(timezone.utc)
# 但需要注意："今天"和"昨天"的语义需要基于用户本地时区，而非 UTC

# 方案 A（推荐）：内部使用 UTC 日期，但"昨天"的语义基于用户本地时区
from datetime import datetime, timezone, timedelta
import pytz

local_tz = pytz.timezone(LOCAL_TIMEZONE)  # 用户本地时区
now_local = datetime.now(local_tz)  # 获取本地时间
yesterday_local = now_local - timedelta(days=1)
yesterday_str = yesterday_local.strftime("%Y-%m-%d")  # 本地日期

# 方案 B：全部使用 UTC 日期（简单但语义变化）
yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
yesterday_str = yesterday_utc.strftime("%Y-%m-%d")  # UTC 日期
```

**注意事项**：
- `_dreaming()` 的"昨天"是用户语义上的"昨天"（本地时间的昨天），不能简单地改为 UTC 的昨天
- 如果 UTC 迁移后 `_dreaming()` 在 UTC 02:00 触发（本地 10:00），此时 UTC 日期是"今天"，但本地日期可能还是"昨天"（取决于 UTC 02:00 时本地是几号）
- **建议**：`_dreaming()` 中的"昨天"计算使用本地时区，但存储到数据库的时间戳使用 UTC
- `_should_execute_cron_today()` 的"今天"判断也需要基于本地时区，否则任务可能在 UTC 午夜重复执行

---

### 2.5 会话管理层（中风险）

#### 2.5.1 Session 时间戳

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/llm/session/manager.py:24` | `datetime.now().strftime('%Y%m%d%H%M')` | 中 | Session 名称生成 |
| `lifeprism/llm/session/manager.py:26` | `datetime.now()` | 中 | `created_at` 字段默认值 |
| `lifeprism/llm/session/manager.py:27` | `datetime.now()` | 中 | `updated_at` 字段默认值 |
| `lifeprism/llm/session/manager.py:51` | `datetime.now().isoformat()` | 中 | 消息 `timestamp` 字段 |
| `lifeprism/llm/session/manager.py:53` | `datetime.now()` | 中 | `updated_at` 更新 |
| `lifeprism/llm/agent/tools/session_query.py:154-158` | 字符串比较 `timestamp` | 中 | 比较消息时间戳 |

**修复策略**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- `datetime.now().isoformat()` 改为 `datetime.now(timezone.utc).isoformat()`
- Session 名称的格式化不影响数据正确性，但建议统一使用 UTC

**注意事项**：
- Session 数据存储在 JSONL 文件中（`settings.session_path / f"{session_id}.jsonl"`），时间戳格式变更需要考虑向后兼容
- 已有的 JSONL 文件中的 naive 时间戳需要能被正确解析（`datetime.fromisoformat()` 能解析 naive 和 aware 两种格式）
- `session_query.py` 的字符串比较在格式统一后是正确的

---

### 2.6 数据管道层（高风险）

#### 2.6.1 ActivityWatch 数据转换

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/processors/data_clean.py:54-87` | `convert_utc_to_local()` | 高 | 将 AW 的 UTC 时间戳转换为本地时间 |
| `lifeprism/processors/data_clean.py:205` | `convert_utc_to_local(event.get("timestamp", ""), LOCAL_TIMEZONE)` | 高 | 数据清洗时转换时间 |
| `lifeprism/processors/components/event_transformer.py:28` | `timezone: str = LOCAL_TIMEZONE` | 高 | EventTransformer 默认时区 |
| `lifeprism/processors/components/event_transformer.py:139-160` | `_convert_timestamp()` UTC → 本地 | 高 | 事件时间戳转换 |
| `lifeprism/processors/components/event_transformer.py:81,83` | `strftime("%Y-%m-%d %H:%M:%S")` | 高 | 事件时间格式化 |
| `lifeprism/processors/data_clean.py:81` | `dt_local.strftime("%Y-%m-%d %H:%M:%S")` | 高 | 本地时间格式化 |
| `lifeprism/processors/data_clean.py:209` | `local_end_time = ...` | 高 | 本地结束时间 |
| `lifeprism/processors/provider/processor_monitor_data_provider.py:47,52,59,64` | `strftime(...)` | 高 | 监控数据处理时间格式化 |

**当前行为**：
- ActivityWatch API 返回 UTC 时间戳（`2025-11-19T08:14:52.000000+00:00`）
- `convert_utc_to_local()` 将其转换为本地时间字符串（`2025-11-19 16:14:52`）
- 转换后的本地时间存入数据库的 `start_time`、`end_time` 字段

**修复策略**：
- **移除 UTC → 本地的转换**，直接保留 UTC 时间
- `convert_utc_to_local()` 函数可以保留但不再使用，或直接删除
- `EventTransformer._convert_timestamp()` 改为直接返回 UTC ISO 格式
- `data_clean.py:205` 不再调用 `convert_utc_to_local`，直接使用原始 UTC 时间戳

**注意事项**：
- 这是数据管道的核心变更，影响 `behavior_analysis`、`raw_behavior_analysis`、`window_events` 等表的数据
- 迁移后数据库中的行为分析时间将是 UTC，前端展示时需要转为本地时间
- 前端时间线（Timeline）展示需要验证：确保前端能正确解析 UTC 时间并转为本地显示
- `_get_incremental_time_range()`（`data_processing_service.py:262-279`）使用 `LOCAL_TIMEZONE` 查询 ActivityWatch API，迁移后应改为 UTC

#### 2.6.2 监控数据采集

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/monitor/windows_monitor/monitor.py:47` | `datetime.now()` | 高 | WindowMonitor 事件时间戳 |
| `lifeprism/monitor/windows_monitor/monitor.py:51` | `self.start_time.strftime("%Y-%m-%d %H:%M:%S")` | 高 | 事件时间格式化 |
| `lifeprism/monitor/windows_monitor/runtime.py:65-66` | `datetime.now().replace(microsecond=0).isoformat()` | 高 | 截图 `captured_at` 时间源 |

**修复策略**：
- `monitor.py:47`：改为 `datetime.now(timezone.utc)`
- `monitor.py:51`：改为 `self.start_time.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")` 或使用 `.isoformat()`
- `runtime.py:65-66`：改为 `lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()`

**注意事项**：
- `window_events` 表不同步（`是否同步=否`），但被 `behavior_analysis` 引用
- 截图 `captured_at` 用于截图文件目录结构（`store.py:26`：`date_dir = request.captured_at[:10]`），UTC 迁移后目录名将是 UTC 日期
- 截图清理（`cleanup_worker.py:38`）基于 `captured_at` 计算过期，迁移后需确保 `now_iso` 也是 UTC

---

### 2.7 业务逻辑层 - "今天"/"本周"语义（中风险）

#### 2.7.1 习惯模块

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/habit_service.py:103` | `date.today()` | 中 | 习惯挑战日期 |
| `lifeprism/server/services/habit_service.py:154` | `date.today().isoformat()` | 中 | 今日打卡查询 |
| `lifeprism/server/services/habit_service.py:189` | `date.today()` | 中 | 习惯挑战完成 |
| `lifeprism/server/services/habit_service.py:225,359,432,462` | `datetime.now().isoformat()` | 中 | `finished_at`、`paused_at` |
| `lifeprism/server/services/habit_service.py:415,500,529,590,656,704,791,845` | `date.today()` / `datetime.now().isoformat()` | 中 | 习惯各类操作 |
| `lifeprism/repository/providers/habit_providers.py:687` | `date.today().isoformat()` | 中 | `get_today_checkins()` |
| `lifeprism/repository/providers/habit_providers.py:417` | `get_expired_in_progress_challenges(today)` | 中 | 过期挑战判断 |

**修复策略**：
- `date.today()` 的语义是"用户本地时区的今天"，迁移后仍应基于本地时区计算
- 建议封装一个 `get_local_today()` 工具函数：
  ```python
  from datetime import datetime, timezone
  import pytz
  from lifeprism.config import LOCAL_TIMEZONE

  def get_local_today() -> str:
      """获取用户本地时区的今天日期 YYYY-MM-DD"""
      return datetime.now(pytz.timezone(LOCAL_TIMEZONE)).strftime("%Y-%m-%d")
  ```
- `datetime.now().isoformat()`（用于 `finished_at`、`paused_at`）改为 `datetime.now(timezone.utc).isoformat()`

**注意事项**：
- 习惯打卡的 `date` 字段是 `YYYY-MM-DD` 格式的日期，不包含时间，时区敏感
- 如果用户在 UTC+8 的 00:30 打卡，UTC 日期是"昨天"，但用户认为是"今天"
- **关键决策**：`date` 字段应存储用户本地时区的日期还是 UTC 日期？
  - 建议存储用户本地时区日期（因为打卡是"用户行为"，应基于用户感知的日期）
  - 但 `finished_at`、`paused_at` 等时间戳字段应存储 UTC

#### 2.7.2 目标模块

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/goal_service.py:114` | `datetime.now()` | 中 | `_calculate_days_started` 计算已开始天数 |
| `lifeprism/server/services/goal_service.py:210` | `datetime.now() - timedelta(hours=...)` | 中 | `time_invested` 更新阈值 |
| `lifeprism/server/services/goal_service.py:234` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 中 | `time_invested_updated_at` |
| `lifeprism/server/services/goal_service.py:513` | `datetime.now().strftime("%Y-%m-%d")` | 中 | 里程碑 `finish_time` |
| `lifeprism/repository/providers/goal_providers.py:812,834,840,853,864` | `current.strftime("%Y-%m-%d")` | 中 | 日期范围同步 |
| `lifeprism/repository/providers/goal_providers.py:490` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 中 | `time_invested_updated_at` |

**修复策略**：
- `goal_service.py:114`：`today = datetime.now()` 用于计算天数差，应基于本地时区
- `goal_service.py:210`：时间阈值比较，应使用 UTC
- `goal_service.py:234,513`：时间戳写入，应使用 UTC
- `goal_providers.py:490`：时间戳写入，应使用 UTC

**注意事项**：
- `start_date`、`expected_finished_at` 是 `YYYY-MM-DD` 格式的日期字段，语义为用户本地日期
- `_calculate_days_started` 的"今天"应基于用户本地时区
- `goal_stats.date` 字段是 `YYYY-MM-DD` 格式，与 `habit_checkins.date` 同理

#### 2.7.3 报表模块

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/report_service.py:135` | `datetime.now().strftime("%Y-%m-%d")` | 中 | 日报"今天" |
| `lifeprism/server/services/report_service.py:230` | `datetime.now().strftime("%Y-%m-%d")` | 中 | 周报"今天" |
| `lifeprism/server/services/report_service.py:333` | `datetime.now().strftime("%Y-%m-%d")` | 中 | 月报"今天" |
| `lifeprism/server/services/activity_stats_builder.py:68-76` | `center_date - timedelta(...)` | 中 | 活动统计日期范围 |

**修复策略**：
- `report_service.py` 的"今天"应基于用户本地时区
- `activity_stats_builder.py` 的日期范围基于传入的 `date` 参数，不直接依赖 `datetime.now()`

**注意事项**：
- `daily_report.date`、`weekly_report.date`、`monthly_report.date` 是 `YYYY-MM-DD` 格式的 PRIMARY KEY
- 报表分组是按"用户本地天"分组的，不能简单地用 UTC 日期作为分组键
- **关键决策**：报表的 `date` 字段应保持用户本地日期，但报表的 `created_at`/`updated_at` 应使用 UTC

#### 2.7.4 计划书同步

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/plandoc_sync_service.py:578` | `datetime.now().strftime("%Y-%m-%d")` | 中 | Todo `actual_finished_at` |
| `lifeprism/server/services/plandoc_sync_service.py:607` | `datetime.now().strftime("%Y-%m-%d")` | 中 | Todo `actual_finished_at` |

**修复策略**：
- `actual_finished_at` 是 `YYYY-MM-DD` 格式的日期字段，应基于用户本地时区

#### 2.7.5 分类服务

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/category_service.py:168` | `datetime.now()` | 中 | 分类操作时间 |
| `lifeprism/server/services/category_service.py:1499` | `datetime.now()` | 中 | 分类操作时间 |
| `lifeprism/server/services/category_service.py:1041,1079,1152,1186` | `created_at > ?` | 中 | 时间范围查询 |

**修复策略**：
- `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 时间范围查询的参数需要确保也是 UTC 格式

#### 2.7.6 数据处理服务

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/data_processing_service.py:262-279` | `pytz.timezone(LOCAL_TIMEZONE)` | 高 | 增量同步时间范围 |
| `lifeprism/server/services/data_processing_service.py:786` | `datetime.now().strftime("%Y-%m-%d")` | 中 | "今天" |
| `lifeprism/server/services/data_processing_service.py:836-837` | `datetime.now()` | 中 | 时间计算 |

**修复策略**：
- `_get_incremental_time_range()` 改为使用 UTC：
  ```python
  # 改为
  start_time = datetime.now(timezone.utc) - timedelta(hours=24)
  end_time = datetime.now(timezone.utc)
  ```
- 但查询 ActivityWatch API 时，API 接受的是时间范围，需要确认 AW API 是否要求特定时区

#### 2.7.7 其他业务服务

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/server/services/sync_service.py:41` | `datetime.now().replace(microsecond=0)` | 中 | 截图保留期计算 |
| `lifeprism/server/services/sync_service.py:139` | `datetime.now() - timedelta(days=1)` | 中 | "1天前" |
| `lifeprism/server/services/sync_service.py:144` | `datetime.now()` | 中 | "现在" |
| `lifeprism/server/services/sync_service.py:209-210` | `datetime.strptime(...)` | 中 | 时间范围解析 |
| `lifeprism/llm/function/agent_schedule_job.py:225` | `start_time.strftime("%Y-%m-%d")` | 中 | 日期格式化 |
| `lifeprism/llm/function/agent_schedule_job.py:295` | `datetime.strptime(date, "%Y-%m-%d")` | 中 | 日期解析 |
| `lifeprism/llm/function/agent_schedule_job.py:569` | `datetime.now().strftime("%Y-%m-%d")` | 中 | behavior.md 日期 |
| `lifeprism/llm/function/agent_schedule_job.py:574` | `datetime.now()` | 中 | 历史记录时间 |
| `lifeprism/llm/tools/summary_tools.py:48-65` | `date.today()` | 中 | 日报/周报/月报默认日期 |
| `lifeprism/repository/aggregators/custom_record_aggregator.py:126,381,603` | `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 中 | 自定义记录时间 |

---

### 2.8 前端层（参考已有报告）

前端违规清单已在 `docs/generated/frontend-time-usage-report.md` 中详细记录，此处仅汇总关键信息。

#### 2.8.1 P0 级违规（数据库写入使用 UTC）

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:137,185,225,226` | `new Date().toISOString()` | 高 | 计划书 `updatedAt`/`createdAt` |
| `frontend/apps/addons/components/ExpandDirManager.tsx:49` | `new Date().toISOString()` | 中 | 扩展目录 `created_at`（临时显示，实际由后端生成） |

**修复策略**：
- UTC 迁移后，前端发送给后端的时间应为 UTC ISO 格式
- `new Date().toISOString()` 生成的是 UTC ISO 格式，**迁移后这实际上变成了正确做法**
- 但需要确保后端能正确解析带 `Z` 后缀的 ISO 字符串

**注意事项**：
- UTC 迁移后，前端的 `.toISOString()` 违规变为**正确做法**（因为后端需要 UTC）
- 但 `toLocalDateString()` 和 `toLocalDateTimeString()` 的语义变为"本地日期"（用于 `YYYY-MM-DD` 字段，如 `date`、`start_date`）
- 需要明确区分：
  - 时间戳字段（`created_at`、`updated_at`）：使用 `new Date().toISOString()`（UTC）
  - 日期字段（`date`、`start_date`、`actual_finished_at`）：使用 `toLocalDateString()`（本地日期）

#### 2.8.2 P1 级违规（日期字段使用 UTC）

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `frontend/my-ui-kit/ui-kit/todoItem/TodoItem.tsx:199` | `new Date().toISOString().split('T')[0]` | 高 | Todo 完成日期 |
| `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx:195` | `new Date().toISOString().split('T')[0]` | 高 | Todo 完成日期 |
| `frontend/apps/goals/hooks/useGoalStore.ts:204` | `new Date().toISOString().split('T')[0]` | 高 | 里程碑完成日期 |
| `frontend/apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx:22` | `new Date().toISOString().split('T')[0]` | 高 | 日记日期 |
| `frontend/apps/goals/components/views/GoalListView/components/AddGoalModal.tsx:21` | `new Date().toISOString().split('T')[0]` | 高 | 目标默认日期 |
| `frontend/apps/lifewatch/pages/usage/UsagePage.tsx:28` | `new Date().toISOString().split('T')[0]` | 高 | 使用情况页面日期 |
| `frontend/core/services/reportCacheService.ts:290` | `adjacentDate.toISOString().split('T')[0]` | 高 | 报表缓存日期 |

**修复策略**：
- 这些是 `YYYY-MM-DD` 格式的日期字段，语义为"用户本地日期"
- 迁移后仍应使用 `toLocalDateString()`（本地日期），而非 `.toISOString().split('T')[0]`（UTC 日期）
- **这些违规在 UTC 迁移后仍然是违规**，必须修复

#### 2.8.3 前端工具函数

| 位置 | 说明 | 风险 |
| ---- | ---- | ---- |
| `frontend/core/utils/dateUtils.ts:17-22` | `toLocalDateString()` - 已正确实现 | 低 |
| `frontend/core/utils/dateUtils.ts:32-35` | `toLocalDateTimeString()` - 已正确实现 | 低 |

**修复策略**：
- 迁移后需要新增 `toISOStringUTC(date: Date): string` 工具函数，用于发送 UTC 时间给后端
- 实际上 `new Date().toISOString()` 已经是 UTC，但封装一层更清晰
- 现有的 `toLocalDateString()` 和 `toLocalDateTimeString()` 语义不变，仍用于本地日期

---

### 2.9 日志与调试层（低风险）

| 位置 | 当前代码 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/llm/utils/llm_call_logger.py:334` | `datetime.now().strftime("%Y-%m-%d")` | 低 | 日志文件名日期 |
| `lifeprism/llm/agent/context.py:185` | `datetime.now().strftime('%Y-%m-%d %H:%M:%S')` | 低 | LLM 上下文中的当前时间 |
| `lifeprism/llm/utils/helpers.py:48` | `datetime.now().strftime("%Y-%m-%d %H:%M (%A)")` | 低 | 人类可读时间 |
| `lifeprism/utils/logger.py` | 日志格式配置 | 低 | 日志时间戳 |

**修复策略**：
- 日志时间戳建议保持本地时间（便于调试），或显式标注 UTC
- LLM 上下文中的时间（`context.py:185`）建议使用本地时间（LLM 需要知道用户的实际时间）
- 这些位置不影响数据正确性，可最后处理

---

### 2.10 时间范围查询清单（中风险）

以下 SQL 查询使用字符串比较进行时间范围过滤，迁移后需要确保比较双方时区一致：

| 位置 | 查询逻辑 | 风险 | 说明 |
| ---- | -------- | ---- | ---- |
| `lifeprism/repository/sync_repository.py:249` | `WHERE updated_at > ?` | 高 | 增量同步查询 |
| `lifeprism/server/providers/statistical_data_providers.py:554` | `WHERE created_at >= ? AND created_at <= ?` | 中 | 统计数据时间范围 |
| `lifeprism/server/providers/statistical_data_providers.py:639,642` | `created_at >= ? AND created_at <= ?` | 中 | 统计数据时间范围 |
| `lifeprism/repository/aggregators/custom_record_aggregator.py:443,446` | `created_at >= ?` / `created_at <= ?` | 中 | 自定义记录时间范围 |
| `lifeprism/server/services/category_service.py:1041,1079,1152,1186` | `WHERE created_at > ?` | 中 | 分类查询 |
| `lifeprism/repository/providers/mood_providers.py:297,300` | `created_at >= ?` / `created_at < ?` | 中 | 心情记录查询 |
| `lifeprism/repository/providers/habit_providers.py:693` | `WHERE date = ?` | 中 | 今日打卡查询 |

**修复策略**：
- 迁移后所有 `created_at`、`updated_at` 字段统一为 UTC ISO 格式
- 查询参数也需要使用 UTC ISO 格式
- 对于按"天"查询的场景（如 `WHERE date = ?`），`date` 字段保持用户本地日期，查询参数也使用本地日期

---

## 3. 功能失效清单

以下是 UTC 迁移后**可能暂时失效**或需要额外处理的功能，**只记录不修改**：

### 3.1 定时任务触发时间偏移

**功能**：`_dreaming()` 定时任务（每天 10:00 执行）

**失效场景**：
- 如果 Cron 表达式从 `"0 10 * * *"` 改为 UTC 但不调整时间，任务将在 UTC 10:00（北京时间 18:00）触发
- 用户预期是本地 10:00 触发

**处理方案**：将 Cron 表达式改为 `"0 2 * * *"`（UTC 02:00 = 北京时间 10:00）

### 3.2 报表日期分组错位

**功能**：每日活动统计、日报、周报、月报

**失效场景**：
- 如果数据库中 `behavior_analysis.start_time` 改为 UTC，但报表按 `date(start_time)` 分组
- UTC 16:00 ~ 24:00 的数据会被分到"今天"，但用户感知是"今天 00:00 ~ 08:00"
- 导致报表显示的"今天"数据不完整

**处理方案**：
- 报表分组查询需要使用 `datetime(start_time, '+8 hours')` 将 UTC 转回本地时间再分组
- 或在 Python 层面进行时区转换后再分组

### 3.3 习惯打卡日期错位

**功能**：习惯每日打卡

**失效场景**：
- 用户在本地时间 00:30 打卡
- 如果 `habit_checkins.date` 改为 UTC 日期，记录的是"昨天"
- 用户查看"今日打卡"时看不到刚打的卡

**处理方案**：`habit_checkins.date` 字段保持用户本地日期，不使用 UTC 日期

### 3.4 截图目录结构变化

**功能**：截图文件按日期存储（`screenshots/YYYY-MM-DD/`）

**失效场景**：
- `captured_at` 改为 UTC 后，目录名将是 UTC 日期
- 用户在本地 00:30 截图，文件存储在"昨天"的目录下

**处理方案**：
- 接受 UTC 日期目录（内部存储一致性）
- 或在存储时使用本地日期目录（但元数据时间戳使用 UTC）

### 3.5 历史数据时区假设

**功能**：历史数据迁移

**失效场景**：
- 假设所有历史数据都是 UTC+8，但可能有少量数据是其他时区生成的
- 迁移后这些数据的时间会偏差

**处理方案**：
- 当前用户都在中国，假设 UTC+8 是合理的
- 迁移后如果发现异常数据，可以单独修复

### 3.6 前后端版本不一致

**功能**：所有涉及时间交互的功能

**失效场景**：
- 如果前端已迁移但后端未迁移（或反之），时间格式不匹配
- 导致 LWW 比较错误、时间显示错误

**处理方案**：前后端必须同一版本发布

---

## 4. 修复策略与注意事项

### 4.1 修改优先级排序

**第一优先级（必须同时修改，否则数据错误）**：
1. `lw_table_manager.py` - 数据库 DEFAULT
2. `lw_base_data_provider.py:1184` - 通用 updated_at 生成
3. 所有 Provider 层手动时间写入（2.2.2 节）
4. `sync_repository.py` 和 `sync_client.py` 的 LWW 逻辑（格式一致性）
5. `schedule_service.py` 的 APScheduler 时区配置

**第二优先级（同一次迁移中修改，可分批）**：
6. 数据管道（`data_clean.py`、`event_transformer.py`、`data_processing_service.py`）
7. 监控数据采集（`monitor.py`、`runtime.py`）
8. 会话管理（`session/manager.py`）
9. 业务逻辑层的 `datetime.now()` 替换

**第三优先级（可后续优化）**：
10. 日志和调试时间戳
11. 前端 P2/P3 违规修复
12. LLM 上下文时间显示

### 4.2 修改模式

#### 4.2.1 时间戳生成（`created_at`、`updated_at`）

```python
# 修改前
from datetime import datetime
now = datetime.now()
timestamp = datetime.now().isoformat()
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 修改后
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
timestamp = datetime.now(timezone.utc).isoformat()
# 不再需要 strftime，统一使用 isoformat()
```

#### 4.2.2 日期字段（`date`、`start_date`）

```python
# 修改前
from datetime import date
today = date.today().isoformat()

# 修改后（保持本地日期语义）
from datetime import datetime
import pytz
from lifeprism.config import LOCAL_TIMEZONE

def get_local_today() -> str:
    """获取用户本地时区的今天日期"""
    return datetime.now(pytz.timezone(LOCAL_TIMEZONE)).strftime("%Y-%m-%d")

today = get_local_today()
```

#### 4.2.3 SQLite DEFAULT

```python
# 修改前
column_definitions.append("created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))")

# 修改后
column_definitions.append("created_at TIMESTAMP DEFAULT (datetime('now'))")
```

#### 4.2.4 APScheduler 配置

```python
# 修改前
self._scheduler = AsyncIOScheduler()
trigger = CronTrigger.from_crontab(cron_expr)

# 修改后
import pytz
self._scheduler = AsyncIOScheduler(timezone=pytz.UTC)
trigger = CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)
```

### 4.3 关键注意事项

1. **前后端必须同时发布**：UTC 迁移是一个原子性变更，不能分端发布
2. **历史数据迁移必须在代码迁移之后**：先修改代码（新数据使用 UTC），再迁移历史数据
3. **`last_sync_time` 需要重置**：迁移后将 `sync.last_sync_time` 设为空字符串，触发全量同步
4. **3 张旧表不需要历史数据迁移**：`todo_list.created_at`、`timeline_custom_block.created_at/updated_at` 已经是 UTC
5. **`date` 字段保持本地日期**：所有 `YYYY-MM-DD` 格式的业务日期字段（如 `habit_checkins.date`、`daily_report.date`）保持用户本地时区日期
6. **时间戳字段使用 UTC**：所有 `created_at`、`updated_at`、`captured_at`、`finished_at`、`paused_at` 等时间戳字段使用 UTC
7. **Cron 表达式需要调整**：`"0 10 * * *"` → `"0 2 * * *"`（UTC 02:00 = 北京时间 10:00）
8. **测试必须覆盖跨时区场景**：模拟本地 UTC+8、服务器 UTC 的场景

---

## 5. 测试验证要点

### 5.1 单元测试

| 测试项 | 验证内容 | 优先级 |
| ------ | -------- | ------ |
| `datetime.now(timezone.utc)` 返回值 | `tzinfo` 不为 None，时区为 UTC | 高 |
| `datetime.now(timezone.utc).isoformat()` 格式 | 匹配 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}\+00:00$` | 高 |
| LWW 字符串比较 | UTC ISO 格式字符串比较结果正确 | 高 |
| `get_local_today()` | 返回用户本地时区的日期 | 高 |
| `toLocalDateString()` | UTC 午夜前后返回正确日期 | 高 |
| `toLocalDateTimeString()` | 不包含 Z 或 + 后缀 | 中 |

### 5.2 集成测试

| 测试场景 | 验证内容 | 优先级 |
| -------- | -------- | ------ |
| 跨时区数据同步 | 本地 UTC+8 ↔ 服务器 UTC，LWW 正确 | 高 |
| 前端午夜场景 | 本地 00:30 打卡，日期正确 | 高 |
| 定时任务触发 | UTC 02:00 触发 = 本地 10:00 触发 | 高 |
| 增量同步 | `WHERE updated_at > ?` 返回正确结果 | 高 |
| 报表日期分组 | 按用户本地日期分组，不跨天 | 中 |
| 截图清理 | 过期截图正确清理 | 中 |

### 5.3 手动测试清单

- [ ] 数据同步：本地修改 → 同步到云端 → 云端修改 → 同步回本地，时间戳正确
- [ ] 前端时间显示：目标创建时间、日记日期、习惯打卡时间显示正确
- [ ] 定时任务：`_dreaming()` 在本地 10:00 触发（非 18:00）
- [ ] 日历组件：在不同日期点击，日期选择正确
- [ ] 统计报表：每日/每周/每月统计数据正确
- [ ] 习惯打卡：本地 00:30 打卡显示在"今天"
- [ ] 截图功能：截图正确存储和清理
- [ ] 日记 AI 总结：`_dreaming()` 处理的是本地"昨天"的数据

### 5.4 回归测试

- 运行所有现有测试套件，确保无回归
- 特别关注时间相关测试：`test_schedule_service.py`、`test_llm_dataset_provider.py`
- 验证数据库迁移脚本（m008）在测试环境正确执行

---

## 6. 可能遗漏的风险点提示

### 6.1 未排查的区域

以下区域可能存在未发现的时区依赖，后续开发者需要注意：

1. **配置文件中的时间相关设置**：
   - `screenshot_retention_days`（截图保留天数）
   - `poll_time`（监控轮询间隔）
   - `afk_timeout`（AFK 超时）
   - 这些是时间间隔，不涉及时区，但需要确认没有隐含的时区假设

2. **Electron 主进程/渲染进程时区设置**：
   - 未排查 Electron 是否设置了 `process.env.TZ`
   - 未排查渲染进程的 `Intl.DateTimeFormat().resolvedOptions().timeZone`

3. **第三方库的时区行为**：
   - `pandas.to_datetime()` 的时区处理
   - `httpx` 请求/响应中的时间头
   - APScheduler 的 `misfire_grace_time` 是否涉及时区

4. **数据库索引**：
   - 时间字段上的索引在格式变更后是否仍然有效
   - SQLite TEXT 类型索引对 ISO 8601 字符串的排序行为

5. **数据导出/导入**：
   - 未排查是否有数据导出功能（CSV、JSON）包含时间字段
   - 导入数据时的时间格式解析

6. **LLM Prompt 中的时间**：
   - `agent/context.py:185` 中的当前时间用于 LLM 上下文
   - `summary_tools.py` 中的时区参数（默认 `Asia/Hong_Kong`）
   - LLM 生成的时间相关内容可能基于 prompt 中的时间

### 6.2 需要后续验证的假设

1. **ActivityWatch API 时区**：
   - 假设 AW API 返回的时间戳是 UTC
   - 需要验证 AW API 文档确认

2. **SQLite 字符串比较**：
   - 假设 SQLite TEXT 类型的字符串比较是按字典序
   - 需要验证 ISO 8601 格式的字典序与时间顺序一致

3. **前端 Date 对象自动时区转换**：
   - 假设 `new Date(isoString)` 能正确解析 UTC ISO 字符串
   - 假设 `Date.toLocaleString()` 能正确显示本地时间
   - 需要在不同时区的浏览器中验证

4. **历史数据时区**：
   - 假设所有历史数据都是 UTC+8
   - 如果有用户曾在中国以外地区使用，数据可能偏差

### 6.3 特殊注意事项

1. **`chat_session` 表**：
   - `timestamps: False`，手动写入时间戳
   - 时间戳来自 `Session` dataclass 的 `datetime.now()`
   - 迁移后需要确保 `Session` 使用 UTC

2. **`goal_journal.time` 字段**：
   - 格式为 `HH:MM`（仅时间，无日期）
   - 不涉及时区，但需要确认语义

3. **`habit_chain_nodes.trigger_time` 字段**：
   - 格式为 `HH:mm`（仅时间，无日期）
   - 不涉及时区，但需要确认语义

4. **`weekly_focus.year/month/week_num` 字段**：
   - 整数类型，表示年份/月份/周序号
   - 周序号的计算可能涉及时区（ISO 周还是本地周）

5. **`raw_behavior_analysis` 表**：
   - 不同步（`是否同步=否`）
   - 但被 `behavior_analysis` 引用
   - 迁移时需要一并处理

6. **文件系统时间戳**：
   - `sync_client.py:572` 和 `sync_cloud_api.py:300,356,366` 已使用 UTC
   - 但文件系统的 mtime 本身是 UTC，不需要迁移

---

## 7. 附录：关键文件清单

### 7.1 必须修改的后端文件

| 文件路径 | 修改点数量 | 风险 |
| -------- | ---------- | ---- |
| `lifeprism/repository/lw_table_manager.py` | 2 | 高 |
| `lifeprism/repository/base_providers/lw_base_data_provider.py` | 1 | 高 |
| `lifeprism/repository/providers/map_cache_providers.py` | 2 | 高 |
| `lifeprism/repository/providers/habit_providers.py` | 4 | 高 |
| `lifeprism/repository/providers/habit_chain_providers.py` | 1 | 高 |
| `lifeprism/repository/providers/goal_providers.py` | 2 | 高 |
| `lifeprism/server/services/schedule_service.py` | 7 | 高 |
| `lifeprism/server/services/data_processing_service.py` | 3 | 高 |
| `lifeprism/processors/data_clean.py` | 3 | 高 |
| `lifeprism/processors/components/event_transformer.py` | 4 | 高 |
| `lifeprism/processors/provider/processor_monitor_data_provider.py` | 4 | 高 |
| `lifeprism/monitor/windows_monitor/monitor.py` | 2 | 高 |
| `lifeprism/monitor/windows_monitor/runtime.py` | 1 | 高 |
| `lifeprism/llm/session/manager.py` | 5 | 中 |
| `lifeprism/server/services/habit_service.py` | 15+ | 中 |
| `lifeprism/server/services/goal_service.py` | 4 | 中 |
| `lifeprism/server/services/report_service.py` | 3 | 中 |
| `lifeprism/server/services/plandoc_sync_service.py` | 2 | 中 |
| `lifeprism/server/services/category_service.py` | 4 | 中 |
| `lifeprism/server/services/sync_service.py` | 3 | 中 |
| `lifeprism/llm/function/agent_schedule_job.py` | 4 | 中 |
| `lifeprism/llm/tools/summary_tools.py` | 3 | 中 |
| `lifeprism/repository/aggregators/custom_record_aggregator.py` | 3 | 中 |

### 7.2 必须修改的前端文件

详见 `docs/generated/frontend-time-usage-report.md`

### 7.3 需要新建的文件

| 文件路径 | 用途 |
| -------- | ---- |
| `lifeprism/repository/migrations/scripts/m008_migrate_to_utc.py` | 历史数据迁移脚本 |
| `lifeprism/utils/time_utils.py`（建议） | 统一时间工具函数（`get_local_today()` 等） |
| `frontend/core/utils/dateUtils.ts`（扩展） | 新增 `toISOStringUTC()` 函数 |

### 7.4 参考文档

- `docs/adr/2026-07-12-migrate-to-utc-timezone.md` - 迁移决策
- `.scratch/utc-timezone-migration/prd.md` - 产品需求文档
- `docs/known-limitations/timezone-and-format-inconsistency.md` - 当前问题详情
- `docs/generated/backend-time-fields-inventory.md` - 后端时间字段清单
- `docs/generated/frontend-time-usage-report.md` - 前端时间使用报告
- `docs/coding-rules/frontend-date-handling.md` - 前端时间处理规范
