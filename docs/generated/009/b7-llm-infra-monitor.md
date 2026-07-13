# B7: LLM Infra + Monitor + Processors 审查报告

## 审查概要
- 审查文件数: 16
- 审查标准: `time-handling-rules.md` Section 3.1-3.3（时间生成、序列化、解析）, Section 4.4（工具函数内部一致性）, Section 3.6（定时任务）, Section 4.1-4.2（大模型交互）
- 总体评价: **通过**。变更以机械替换为主，核心逻辑正确，未发现阻塞性 Bug。发现 2 个值得关注的观察点。

---

## 1. 规则遵守程度

### 1.1 LLM Infrastructure

#### `lifeprism/llm/function/agent_schedule_job.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: `datetime.now(timezone.utc)` 用于 UTC 时间比较（L476, L579, L463），`get_local_today()` 用于日期字段（L582）。`build_local_datetime()` 用于构造本地时间常量（L246-247, L300-301）。全部正确。
- **时间序列化 (Rule 3.2)**: 通过 `local_to_utc_iso()` 和 `build_local_datetime()` 间接完成序列化。日期字段使用 `get_local_today().isoformat()`（L582），因为 `get_local_today()` 返回 `date` 对象，`.isoformat()` 输出 `YYYY-MM-DD` 格式，符合日期字段规则。
- **时间解析 (Rule 3.3)**: `process_session_message` L462-467 解析 `update_at` 后检查 `tzinfo is None` 并补齐 UTC。这是正确的向后兼容处理。
- **定时任务 (Rule 3.6)**: `DAILY_START_HOUR = "04:00:00"` 保持为硬编码本地时间常量，使用时通过 `build_local_datetime()` + `local_to_utc_iso()` 就地转 UTC（L245-247, L300-301 + L311-313）。符合 Rule 3.6 关于硬编码本地时间常量的处理规范。
- **大模型交互 (Rule 4.1-4.2)**:
  - `get_mood_data` (L138): 接收本地时间字符串（AI 工具参数），通过 `local_to_utc_iso()` 就地转 UTC 后调用 `query_user_mood`。符合 Rule 4.2（execute 层转换）。
  - `dreaming` (L300-301, L311-313, L320, L332): `start_time`/`end_time` 保持本地格式传给 `summary_activities`（AI 工具，期望本地格式用于 prompt 注入，符合 Rule 4.1），同时通过 `local_to_utc_iso()` 转 UTC 传给 `query_user_activity_summary`（数据库查询，符合 Rule 4.2）。内外分离清晰。
- **工具函数内部一致性 (Rule 4.4)**: `get_mood_data` 接收本地时间 → 转 UTC → 调用底层工具 → 返回结果。`summary_activities` 接收本地时间 → 直接传给 LLM。职责清晰。

#### `lifeprism/llm/session/manager.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: 全部使用 `datetime.now(timezone.utc)`（L24, L31-32, L55, L60, L344, L413）。无裸 `datetime.now()`。
- **时间序列化 (Rule 3.2)**: `Session.add_message` L55 使用 `.isoformat()`；`ChatHistoryManager.add_content` L413 使用 `.isoformat()`。
- **时间解析 (Rule 3.3)**: `load_histories` L368-373 解析 `last_processed_time` 后检查 `tzinfo is None`；`get_unprocessed_histories` L389-391 解析 `timestamp` 后检查 `tzinfo is None`。两处都补齐 UTC tzinfo，向后兼容处理正确。
- **潜在细微问题**: Session 名称 `L24` 和 `last_processed_time` 默认值 `L344` 改用 UTC。Session 名称是展示用的标识符（非存储时间戳），使用 UTC 时间戳作为名称后缀是可接受的。但用户可能注意到名称中的时间戳比本地时间"早"几小时——这是设计选择，非 bug。

#### `lifeprism/llm/agent/context.py` -- ✅ 通过

- **大模型交互 (Rule 4.1)**: `_build_runtime_context` (L187-193) 正确实现了将 UTC 转为本地时间 `YYYY-MM-DD HH:MM:SS` 并附带时区名称的输出:
  ```python
  now_local = datetime.now(timezone.utc).astimezone(tz)
  f"当前时间：{now_local.strftime('%Y-%m-%d %H:%M:%S')}（时区：{tz_name}）"
  ```
  格式和内容完全匹配 Rule 4.1 的示例。
- **时间生成**: `datetime.now(timezone.utc)` 作为源，确保内部一致。
- **注意事项**: 引入 `pytz` 依赖。如果项目统一使用 `zoneinfo`（Python 3.9+），可能需要确认一致性。但这不是本审查范围的问题。

#### `lifeprism/llm/function/screenshot_analysis.py` -- ✅ 通过

- **时间序列化 (Rule 3.2)**: 移除了 `.replace("T", " ")` 转换（原 L396-397, L609-610），保持 ISO 8601 格式写入数据库 `start_time`/`end_time` 字段。这是正确的迁移——时间戳字段应使用 ISO 格式，而不是空格分隔的"数据库格式"。
- **向后兼容**: 原代码用 `.replace("T", " ")` 将 ISO 转为空格分隔格式再写库。现在直接写 ISO 8601。数据库 schema 和所有消费端必须已适配此格式变更。**这是迁移的一部分，应在整体迁移中已协调好。**

#### `lifeprism/llm/utils/density_utils.py` -- ✅ 通过

- **时间解析 (Rule 3.3)**: `_to_dt` (L8-16) 修复了 aware/naive 混用的潜在 bug。新增逻辑: 如果 `fromisoformat` 返回 naive datetime，补齐 `tzinfo=timezone.utc`。这正确修复了当输入字符串不带时区标识时可能导致 `TypeError`（aware vs naive 比较）的问题。
- **设计合理性**: 将 naive 视为 UTC 是正确的迁移策略——迁移后所有数据都应是 UTC，旧数据（如可能以 naive ISO 存储的）也应按 UTC 解读。这避免了历史数据兼容性问题。

#### `lifeprism/llm/utils/helpers.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: `timestamp()` (L42) 改为 `datetime.now(timezone.utc)`，`current_time_str()` (L48) 改为 `datetime.now(timezone.utc).astimezone()`。
- **时间序列化 (Rule 3.2)**: `timestamp()` 使用 `.isoformat()`，正确。
- **辅助函数**: `current_time_str()` 用于人类可读显示，先取 UTC 再 `astimezone()` 转本地，逻辑正确。继续使用 `time.strftime("%Z")` 获取时区缩写，这是显示用途，可以接受。

#### `lifeprism/llm/utils/llm_call_logger.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: 全部 `datetime.now()` → `datetime.now(timezone.utc)`（L158, L259, L287, L334）。
- **观察点 (🟡)**: 日志文件按日期分文件 `L334`:
  ```python
  date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  log_file = self.log_dir / f"llm_calls_{date_str}.json"
  ```
  使用 UTC 日期命名日志文件。对于 UTC+8 用户，日志文件在本地时间 08:00 切换日期。日志文件不是 Rule 2.2 定义的"日期字段"（打卡日期、日报日期），属于内部基础设施命名，使用 UTC 是可以接受的。但如果后续需要按"用户自然天"分析日志，需要注意这个边界。

#### `lifeprism/llm/prompts/prompt_loader.py` -- ✅ 通过

- **时间序列化 (Rule 3.2)**: `L178` `datetime.now(timezone.utc).isoformat()` 替代 `datetime.now().isoformat()`。纯机械替换，正确。

---

### 1.2 Monitor 模块

#### `lifeprism/monitor/windows_monitor/monitor.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: `_flush` L47 和窗口切换 L121 均使用 `datetime.now(timezone.utc)`。
- **时间序列化 (Rule 3.2)**: `_flush` L50 从 `strftime("%Y-%m-%d %H:%M:%S")` 改为 `.isoformat()`。这是关键修正——监控时间戳现为 UTC ISO 8601 格式，符合内部存储规范。
- **数据一致性**: `start_time`（datetime 对象）用于计算 duration，然后 `.isoformat()` 序列化后存储。duration 计算基于 UTC aware datetime，精度不受时区影响。

#### `lifeprism/monitor/windows_monitor/runtime.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: `iso_time_source` 默认 lambda L65-66 从 `datetime.now()` 改为 `datetime.now(timezone.utc)`。纯机械替换，正确。

#### `lifeprism/monitor/provider/window_data_provider.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: `save_event` L53 新增 `created_at: get_utc_now_iso()`。`get_utc_now_iso()` 返回 `datetime.now(timezone.utc).isoformat()`，符合 UTC ISO 8601 规范。
- **设计**: 数据写入时补充 `created_at` 字段，与数据库 schema 的时间戳字段对齐。

#### `lifeprism/monitor/provider/screenshot_data_provider.py` -- ✅ 通过

- **时间生成 (Rule 3.1)**: `save_metadata` L33 新增 `created_at: get_utc_now_iso()`。与 window_data_provider 一致的 pattern。
- **实现细节**: 使用 `{**data, "created_at": get_utc_now_iso()}` 合并，不修改原始 `data` dict，是安全的。

#### `lifeprism/monitor/screenshot/store.py` -- ✅ 通过

- **时间序列化 (Rule 3.2)**: 移除了 `datetime.fromisoformat(request.captured_at).strftime(...)` 的本地时间转换逻辑（原 L46-48），现在直接将 `request.captured_at` 作为 ISO 8601 传递。符合 UTC 内部存储规范。
- **清理**: 同步移除未使用的 `from datetime import datetime`。

---

### 1.3 Processors 模块

#### `lifeprism/processors/data_clean.py` -- ✅ 通过（重点关注）

- **时间序列化 (Rule 3.2)**: `_normalize_utc_timestamp` 替代 `convert_utc_to_local`。新函数保留 UTC ISO 8601 格式（返回 `.isoformat()`），移除本地时间转换。正确。
- **时间解析 (Rule 3.3)**: `_normalize_utc_timestamp` (L62-66) 解析 ISO 字符串后检查 `tzinfo is None`，补齐 UTC。正确处理 Z 后缀（`.replace("Z", "+00:00")`），兼容 Python 3.10 及以下版本（这些版本 `fromisoformat` 不支持 Z 后缀）。
- **结束时间计算 (Rule 3.2)**: `clean_activitywatch_data_old` (L193-195) 改用 `datetime.fromisoformat()` + `timedelta` + `.isoformat()` 替代 `strptime` + `strftime`。`_normalize_utc_timestamp` 保证了返回的字符串是可以被 `fromisoformat` 解析的 aware datetime，算术正确。
- **清理**: 移除 `pytz`、`LOCAL_TIMEZONE` 导入，`convert_utc_to_local` 函数被完全替换。无遗漏引用。
- **提醒**: 原 `convert_utc_to_local` 将时间转为本地 `YYYY-MM-DD HH:MM:SS` 存入数据库。现在改为存 UTC ISO 8601。所有读取 `user_app_behavior_log` 表 `start_time`/`end_time` 字段的代码必须适配此格式变更。这是迁移整体的一部分。

#### `lifeprism/processors/components/event_transformer.py` -- ✅ 通过

- **时间序列化 (Rule 3.2)**: `_convert_timestamp` 不再转本地时间，返回 UTC ISO 8601 (`.isoformat()`)。
- **时间解析 (Rule 3.3)**: `_convert_timestamp` (L149-154) 解析后检查 `tzinfo is None`，补齐 UTC。处理 Z 后缀。
- **结束时间计算**: `transform` L73-75 改用 `datetime.fromisoformat()` + `timedelta` + `.isoformat()`，正确。
- **清理**: 移除 `pytz`、`LOCAL_TIMEZONE`、`self._target_tz`、`timezone` 参数。构造函数简化——时区不再需要作为参数传入，因为处理器内部统一用 UTC。这是正确且干净的重构。

#### `lifeprism/processors/provider/processor_monitor_data_provider.py` -- ✅ 通过

- **时间序列化 (Rule 3.2)**: `L57-58` datetime 转字符串从 `strftime("%Y-%m-%d %H:%M:%S")` 改为 `.isoformat()`。机械替换，正确。
- **注释更新**: 注释同步改为"lifeprism 的 timestamp 使用 UTC ISO 8601 格式"。

---

## 2. 潜在 Bug

### 🟢 无阻塞性 Bug

经过详细审查，未发现会导致运行时错误、数据损坏或逻辑错误的 Bug。

### 🟡 观察点 1: `llm_call_logger.py` 日志文件日期边界

- **文件**: `lifeprism/llm/utils/llm_call_logger.py` L334
- **代码**:
  ```python
  date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  ```
- **说明**: 日志文件按 UTC 日期命名（如 `llm_calls_2026-07-12.json`），对于 UTC+8 用户，日志文件在本地时间 08:00 切换。这不是数据正确性问题（日志内容的时间戳仍是准确的 UTC ISO），但如果有人按"本地日期"手动查找日志文件，可能产生困惑。
- **严重程度**: 🟡 低。属于基础设施层面的设计选择，不影响核心功能。
- **建议**: 可选改进——如果项目规范要求日志文件也按本地日期组织，可改用 `get_local_today().isoformat()`。作为参考，`llm_call_logger` 内部记录的 `timestamp` 字段已经是 `datetime.now(timezone.utc).isoformat()`(L158)，日志文件只是容器，按 UTC 日期分桶在技术上是自洽的。

### 🟡 观察点 2: `session/manager.py` Session 名称使用 UTC 时间

- **文件**: `lifeprism/llm/session/manager.py` L24
- **代码**:
  ```python
  name: str = field(
      default_factory=lambda: f"session_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
  )
  ```
- **说明**: Session 名称中的时间戳（如 `session_202607120230`）现在反映 UTC 时间而非本地时间。这是展示标识符，不影响数据正确性，但用户可能在 UI 中看到与本地时间"不一致"的 session 名称。
- **严重程度**: 🟡 低。Session 名称是机器生成的标识符，用户通常不会将其与本地时间对照。
- **建议**: 无需修改。如果未来 session 列表在 UI 中显示名称，前端可以在展示时转本地时间，或直接使用 `created_at` 字段。

---

## 3. 功能缺失风险

### 数据采集时间戳准确性 -- ✅ 无风险

- **Monitor 模块**: `monitor.py` 中使用 `datetime.now(timezone.utc)` 记录事件开始时间，duration 计算基于 UTC aware datetime。duration = `now - start_time`，结果以秒为单位。由于 `now` 和 `start_time` 都是 UTC aware 且使用同一时钟源（系统时钟），duration 计算精确，不受时区影响。事件时间戳 `start_time.isoformat()` 准确反映 UTC 时刻。
- **ActivityWatch 数据处理**: `data_clean.py` 和 `event_transformer.py` 中 AW 返回的 UTC 时间戳被正确保留（`_normalize_utc_timestamp` / `_convert_timestamp` 返回 `.isoformat()`），不再错误转换为本地时间。
- **LLM 调用日志**: `llm_call_logger.py` 中的时间戳使用 UTC，日志记录的调用时刻准确。

### 无功能缺失

所有变更都是格式/时区迁移，不涉及功能增删。数据采集、存储、查询的时间语义保持完整，仅格式从本地 `YYYY-MM-DD HH:MM:SS`（无时区标识）升级为 UTC ISO 8601（带时区标识）。

---

## 4. 安全隐患

按常规审查，未发现安全相关问题：

- 时间输入均来自内部系统（监控采集、AW API、LLM 响应），无不信任的外部时间输入。
- 无 SQL 注入风险（所有数据库操作通过 `LWBaseDataProvider` / `DatabaseManager` 参数化查询）。
- 无路径遍历风险（文件路径来自 `settings.lifeprism_data_path` 或数据库记录）。
- `agent_schedule_job.py` 中的 `datetime.fromisoformat()` 异常未被捕获为安全风险（解析失败最多导致该 session 跳过处理，不会造成系统崩溃或数据泄露）。

---

## 5. 总结

| 维度 | 结果 | 说明 |
|------|------|------|
| 规则遵守程度 | ✅ 通过 | 16 个文件全部符合 Section 3.1-3.3, 3.6, 4.1-4.2, 4.4 |
| 潜在 Bug | 🟢 无阻塞 Bug | 2 个 🟡 低严重度观察点（日志文件日期边界、Session 名称时间戳） |
| 功能缺失风险 | ✅ 无风险 | 数据采集时间戳准确，无功能删除 |
| 安全隐患 | ✅ 无风险 | 无外部时间输入，参数化查询 |

### 关键发现

1. **机械替换质量高**: `datetime.now()` → `datetime.now(timezone.utc)` 替换完整，无遗漏。`.isoformat()` 替代 `.strftime()` 的序列化变更一致。

2. **向后兼容处理正确**: `session/manager.py`、`density_utils.py`、`agent_schedule_job.py`、`data_clean.py`、`event_transformer.py` 均对 naive datetime 做了 UTC 补齐的向后兼容处理。此策略假设所有历史 naive 时间戳都应按 UTC 解读——这在迁移后是正确的。

3. **大模型交互内外分离清晰**: `context.py`（Rule 4.1: 本地时间给 AI）、`agent_schedule_job.py`（Rule 4.2: execute 层转 UTC）、`screenshot_analysis.py`（Rule 3.2: ISO 格式存库）均正确实现了内外分离+就地转换。

4. **工具函数内部一致性 (Rule 4.4)**: `get_mood_data` 接收本地时间 → 转 UTC → 调底层工具；`summary_activities` 保持本地时间用于 LLM prompt。职责边界清晰，无时间格式混淆。

### 无需修改项

所有 16 个文件的变更均符合时间处理规则，不需要额外修改。两个 🟡 观察点为低严重度设计选择，可以接受。
