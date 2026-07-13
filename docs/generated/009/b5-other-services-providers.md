# B5: Server Services 其他 + Providers + API 审查报告

## 审查概要
- 审查文件数: 16
- 审查标准: time-handling-rules.md Section 2, 3.1-3.3, 3.5, 6
- 审查日期: 2026-07-12
- 分支: feature/utc-timezone-migration

## 1. 规则遵守程度

### 1.1 sync_service.py -- 部分遵守

- L38-42: 新增 `tzinfo` 检查逻辑，为 naive datetime 补充 UTC tzinfo。符合 Rule 3.3（解析后确保 aware）。
  ```python
  if requested_start_time.tzinfo is None:
      requested_start_time = requested_start_time.replace(tzinfo=timezone.utc)
  ```
- L41: `datetime.now(timezone.utc)` 符合 Rule 3.1（时间生成必须 UTC aware）。**已修复。**
- L142, L147: **违反 Rule 3.2**，使用 `.strftime("%Y-%m-%d %H:%M:%S")` 序列化时间戳，应使用 `.isoformat()`。
  ```python
  # L142 - 违规
  analysis_start_time = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
      "%Y-%m-%d %H:%M:%S"
  )
  # L147 - 违规
  analysis_end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
  ```
  虽然下游 `screen_behavior_anlysis()` 通过 `fromisoformat` + tzinfo 补充能容错（L38-42），但这种"生成时丢失 tzinfo、解析时再补充"的流程是脆弱的。如果将来移除 tzinfo 补充逻辑，naive datetime 会导致比较异常。

### 1.2 chatbot_service.py -- 部分遵守

- L88-89, L144, L146: `get_utc_now_iso()` 用于 `created_at`/`updated_at` 默认值。符合 Rule 3.1 + 3.2。
- L123: **存在 Bug**（见 Section 2.1）。`datetime.now(timezone.utc).strftime('%m-%d %H:%M')` 将 UTC 时间直接用于面向用户的会话名称，用户会看到错误的时间。

### 1.3 timeline_builder.py -- 遵守（有注意事项）

- L598-601: `datetime.now(timezone.utc)` 替代了无时区 `datetime.now()`。符合 Rule 3.1。
- **注意事项**：默认 `range_start` 从本地当天 00:00 变为 UTC 当天 00:00。该函数的所有现有调用方（L445, L538）均传递显式的 `range_start`/`range_end` 参数，因此默认值仅在调用方未传参时生效。低风险，但语义变化值得记录。

### 1.4 add_on_service.py -- 遵守

- L180, L239: `datetime.now().isoformat()` 替换为 `get_utc_now_iso()`。符合 Rule 3.1 + 3.2。
- `created_at` fallback L239 使用 `get_utc_now_iso()`，即使旧数据缺少此字段也能生成正确格式。

### 1.5 plandoc_sync_service.py -- 遵守

- L578, L607: `datetime.now().strftime("%Y-%m-%d")` 替换为 `get_local_today().isoformat()`。
- `actual_finished_at` 是日期字段（Rule 2.2），使用用户本地时区日期正确。符合 Rule 3.5。

### 1.6 taskpool_service.py -- 遵守

- L180: 同上，`actual_finished_at` 日期字段使用 `get_local_today().isoformat()`。符合 Rule 3.5。

### 1.7 data_processing_service.py -- 遵守

- L66, L168: `strftime()` 替换为 `.isoformat()`，符合 Rule 3.2。
- L260-293: `_get_incremental_time_range()` 从 `local_tz.localize()` 改为 `datetime.now(timezone.utc)` + `_parse_latest_end_time()`，返回 UTC aware datetime。
- L260-318: 新增 `_parse_latest_end_time()` 方法，正确处理三种情况：
  1. 新格式 ISO 8601 带时区：直接解析
  2. 新格式 ISO 8601 无时区（旧数据迁移中间态）：假设本地时间转 UTC
  3. 旧格式 `%Y-%m-%d %H:%M:%S`：假设本地时间转 UTC
  4. 解析失败：回退到 24 小时前
- L822: `datetime.now().strftime("%Y-%m-%d")` 替换为 `get_local_today().isoformat()`。session_id 使用日期字段，符合 Rule 3.5。
- L873-874: `__main__` 测试代码也修复为 `datetime.now(timezone.utc)`。

### 1.8 activity_stats_builder.py -- 部分遵守（有冗余代码）

- L28-104: 新增四个辅助函数用于 UTC/本地时区转换。逻辑正确，与 `time_utils.py` 中的对应函数功能一致。
- **发现**：`_utc_timestamp_to_local_date`（L48）、`_add_local_date_column`（L73）、`_build_utc_time_range`（L99）三个函数**未被本文件内任何代码调用**，属于死代码。`_normalize_timestamp` 仅被 `_utc_timestamp_to_local_date` 调用，后者本身也是死代码。
- 这些函数与 `report_service.py` 中的同名函数存在代码重复。可能是从 `report_service.py` 复制过来作为预备工具，但未接入实际调用方。
- `_build_utc_time_range`（L99-121）返回值使用 `.strftime()` 格式（用于 SQL 查询参数）。技术上违反 Rule 3.2 的字面规定，但 SQLite `datetime('now')` DEFAULT 使用 `YYYY-MM-DD HH:MM:SS` 格式，SQL 字符串比较需要格式一致，属于合理例外。

### 1.9 journal_provider.py -- 遵守

- L99: `get_utc_now_iso()` 生成 UTC ISO 时间戳。
- L107-108: INSERT 新增 `created_at`、`updated_at` 列。数据使用 UTC ISO 格式。
- L172-173: UPDATE 追加 `updated_at = ?`，使用 `get_utc_now_iso()`。
- 符合 Rule 3.1 + 3.2。之前未写 `created_at`/`updated_at`，现在补全。

### 1.10 report_provider.py -- 遵守

- DailyReportProvider (L113, L129-130): INSERT/UPDATE 使用 `get_utc_now_iso()`。
- WeeklyReportProvider (L343, L359-360): INSERT/UPDATE 使用 `get_utc_now_iso()`。
- MonthlyReportProvider (L544, L561-562): INSERT/UPDATE 使用 `get_utc_now_iso()`。
- 符合 Rule 3.1 + 3.2。

### 1.11 being_provider.py -- 遵守

- L185-186: INSERT 新增 `created_at`、`updated_at`，使用 `get_utc_now_iso()`。
- L255: UPDATE 追加 `updated_at`，使用 `get_utc_now_iso()`。
- L284: 批量 UPDATE 追加 `updated_at`，使用 `get_utc_now_iso()`。
- L327, L336-337: upsert 新增 `created_at`、`updated_at`，使用 `get_utc_now_iso()`。
- 符合 Rule 3.1 + 3.2。

### 1.12 commitment_provider.py -- 遵守

- L151: `get_utc_now_iso()` 生成 UTC ISO 时间戳。
- L155-157: 原生 SQL INSERT 新增 `created_at`、`updated_at` 列和参数。
- 符合 Rule 3.1 + 3.2。

### 1.13 value_provider.py -- 遵守

- L85: `get_utc_now_iso()` 生成 UTC ISO 时间戳。
- L89-90: 原生 SQL INSERT 新增 `created_at`、`updated_at` 列和参数。
- 符合 Rule 3.1 + 3.2。

### 1.14 statistical_data_providers.py -- 遵守

- L534: 使用 `build_utc_time_range(date)` 替代旧的 `self.current_date` setter，返回 UTC ISO 格式的时间范围用于查询。符合 Rule 3.5（本地日期转 UTC 范围）。
- L540-557: 移除 SQL 中的 `DATE(created_at)` 分组，改为 Python 侧按 `utc_to_local_display(created_at)[:10]` 本地日期分组。避免了 UTC 日期跨时区分组错位的问题。
- L559: 结果按日期排序，保证输出稳定。
- 符合 Rule 2.1（created_at 是时间戳字段，UTC 存储）和 Rule 3.5（日期分组基于本地时区）。

### 1.15 sync_cloud_api.py -- 遵守

- L342: `datetime.fromisoformat()` 替换为 `parse_iso_to_aware()`。符合 Rule 3.3（解析后确保 aware）和 Rule 6（LWW 字符串比较需要一致格式）。
- L429: 同上。
- 符合 Rule 6（`last_sync_time` 使用 UTC ISO 格式，LWW 冲突解决依赖字符串比较）。

### 1.16 setting_schemas.py -- 遵守

- L63: 新增 `timezone` 字段，默认 `Asia/Shanghai`。IANA 标识符格式正确。
- L99: UpdateSettingsRequest 新增可选的 `timezone` 字段。
- 为系统提供用户可配置时区能力，符合 Rule 1（本地时区来源统一通过配置动态获取）。

---

## 2. 潜在 Bug

### 2.1 chatbot_service.py L123: 会话名称显示 UTC 时间而非本地时间

**严重程度**: 中（功能 Bug，影响用户体验）

**代码位置**: `lifeprism/server/services/chatbot_service.py` L123

```python
# 变更后（UTC 时间，错误）
session.name = name or f"新会话 {datetime.now(timezone.utc).strftime('%m-%d %H:%M')}"

# 变更前（本地时间，正确）
session.name = name or f"新会话 {datetime.now().strftime('%m-%d %H:%M')}"
```

**问题**: 用户在 UTC+8 时区，10:30 创建新会话，会话名称会显示 `新会话 02:30` 而非 `新会话 10:30`。这是一个面向用户的显示 Bug，虽然不影响数据正确性，但会持续困扰用户。

**建议修复**: 使用 `get_local_today()` + 本地时间格式化，或引入 `get_local_now_display()` 工具函数。
```python
from lifeprism.utils.time_utils import get_local_today
from datetime import datetime
import pytz
from lifeprism.config import get_user_timezone

local_tz = pytz.timezone(get_user_timezone())
now_local = datetime.now(local_tz)
session.name = name or f"新会话 {now_local.strftime('%m-%d %H:%M')}"
```

### 2.2 sync_service.py L142, L147: strftime() 违反序列化规则

**严重程度**: 低（规则违反，但下游有容错逻辑）

**代码位置**: `lifeprism/server/services/sync_service.py` L142, L147

```python
# L142
analysis_start_time = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
    "%Y-%m-%d %H:%M:%S"
)
# L147
analysis_end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```

**问题**: Rule 3.2 明确禁止 `.strftime()` 序列化时间戳字段，应使用 `.isoformat()`。当前代码生成的时间字符串丢失了时区信息（naive 字符串），依赖下游 `screen_behavior_anlysis()` 的 tzinfo 补充逻辑（L38-42）来恢复。如果下游逻辑变更或被移除，会导致 aware/naive datetime 比较错误。

**建议修复**:
```python
analysis_start_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
analysis_end_time = datetime.now(timezone.utc).isoformat()
```

### 2.3 activity_stats_builder.py: 4 个辅助函数为死代码

**严重程度**: 低（不影响功能，但增加维护负担）

**代码位置**: `lifeprism/server/services/activity_stats_builder.py` L33-121

**问题**: `_normalize_timestamp`（L33）、`_utc_timestamp_to_local_date`（L48）、`_add_local_date_column`（L73）、`_build_utc_time_range`（L99）四个函数定义后未被本文件内任何代码调用。`_normalize_timestamp` 仅被 `_utc_timestamp_to_local_date` 调用，而后者本身就是死代码。

这些函数在 `report_service.py` 中有同名副本，推测是从 `report_service.py` 复制过来作为预备工具，但未完成接入。

**建议**: 
- 如果这些函数是计划中要用的，添加 TODO 注释并完成接入。
- 如果是误复制，应移除以避免代码重复。

---

## 3. 功能缺失风险

无功能缺失风险。所有 Provider 的 INSERT/UPDATE 操作都正确地补全或新增了 `created_at`/`updated_at` 字段，不会丢失任何数据。

`journal_provider.py` 的 INSERT 新增了 `created_at`/`updated_at` 列，表结构需要包含这些列（应由 migration 保证）。如果 migration 未添加这些列，INSERT 会因列数不匹配而失败 -- 这是 migration 的审查范围，不是本文件的代码问题。

---

## 4. 安全隐患

无安全隐患。所有时间生成均使用 UTC 时区，无硬编码时区偏移。时间序列化统一使用 `get_utc_now_iso()` 或 `.isoformat()`，LWW 冲突解决所需的字符串格式一致性得到保证。

`setting_schemas.py` 新增的 `timezone` 字段无输入验证（接受任意字符串）。虽然 `pytz.timezone()` 会在使用时对无效时区抛出 `UnknownTimeZoneError`，但建议在 Schema 层添加 IANA 时区校验器以提供更早的错误反馈。这属于增强建议，非阻塞问题。

---

## 5. 总结

| 维度 | 评估 |
|------|------|
| 规则遵守程度 | 14/16 文件完全或基本遵守。2 个文件存在规则违反（sync_service 的 strftime，chatbot_service 的 UTC 用户显示） |
| 潜在 Bug | 2 个真实问题：session 名称显示 UTC 时间（中）、sync_service strftime 违反规则（低） |
| 功能缺失 | 无 |
| 安全隐患 | 无。建议 Schema 层加时区校验（非阻塞） |
| 整体评价 | 变更质量良好。Provider 层的时间字段补全和 statistical_data_providers 的本地日期重分组逻辑设计合理。建议修复 chatbot_service 的显示 Bug 后合入 |

### 必须修复（阻塞合入）

无。但建议修复以下两项：

1. **chatbot_service.py L123**: 会话名称使用 UTC 时间（显示 Bug，中）
2. **sync_service.py L142, L147**: 使用 `.isoformat()` 替代 `.strftime()`（规则违反，低）

### 建议清理（非阻塞）

3. **activity_stats_builder.py L33-121**: 移除未使用的 4 个辅助函数，或完成接入
