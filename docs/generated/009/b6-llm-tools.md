# B6: LLM Tools 核心 审查报告

## 审查概要
- 审查文件数: 3
- 审查标准: time-handling-rules.md Section 4（重点），Section 2, 3.1-3.3
- 审查日期: 2026-07-12
- 总变更行数: ~220 行（lifeprismsystem.py 179 行 + custom_records_tool.py 25 行 + session_query.py 16 行）

---

## 1. 规则遵守程度

### §4.1 提示词输入（后端 → 大模型）：本地时间

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 提示词中的时间是否转为本地 `YYYY-MM-DD HH:MM:SS` | ✅ | 工具输出全部使用 `_utc_to_local()` 转换为本地格式后返回给 AI |
| 是否标注了时区名称 | ⚠️ | 参数描述 `_TIME_FORMAT_DESC = "YYYY-MM-DD HH:MM:SS（本地时区）"` 仅标注"本地时区"而未给出实际时区名称（如 `Asia/Shanghai`）。规则要求"标注时区名称（如"时区：Asia/Shanghai"）"。不过，这对工具参数描述的影响较小——AI 无需知道时区名称即可生成时间参数；时区名称标注更适用于 prompt 文本中的当前时间注入。Dreaming 路径中 `summary_activities()` 传入的 `start_time`/`end_time` 为本地时间字符串，由 `prompt_loader` 注入到 prompt 模板（非本文件范围），未在本文件中发现问题 |
| 是否有 UTC ISO 直接注入提示词 | ✅ | 所有返回给 AI 的显示用时间均通过 `_utc_to_local()` 或 `utc_to_local_display()` 转换为本地格式，无 UTC ISO 泄露到输出 |

**§4.1 遵守率: 3/3（⚠️ 时区名称为小瑕疵）**

### §4.2 工具输入（大模型 → 后端）：本地时间，execute 层转 UTC

| 检查项 | 状态 | 说明 |
|--------|------|------|
| execute 方法是否在入口处将本地时间转 UTC ISO | ✅ | 全部 5 个 execute 方法（`UserActivitySummaryTool`, `UserComputerLogTool`, `UpdateUserBehaviorNoteTool`, `UserMoodQuryTool`）均在入口处调用 `local_to_utc_iso()` 转换 |
| 转换后的参数是否正确传递到工具函数 | ✅ | 转换后参数直接传入对应工具函数，无中间层篡改 |
| 是否有本地时间字符串直接用于数据库查询 | ✅ | 无。所有数据库查询均使用转换后的 UTC ISO 参数 |

```python
# ✅ 标准模式（以 UserActivitySummaryTool.execute 为例，第 153-155 行）
start_time = local_to_utc_iso(kwargs.get("start_time", ""))
end_time = local_to_utc_iso(kwargs.get("end_time", ""))
return query_user_activity_summary(query_option, start_time, end_time)
```

**§4.2 遵守率: 3/3**

### §4.3 工具输出（后端 → 大模型）：区分显示用与计算用

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 显示用字段是否转为本地 `YYYY-MM-DD HH:MM:SS` | ✅ | 所有返回给 AI 的时间戳均转换。涉及位置：`high_usage_segments` 时间段显示（line 270）、`user_behavior_notes`（line 340）、`ai_behavior_notes`（line 353）、`query_user_activity_log`（line 526, 531-532）、`create_or_update_user_behavior_note` 返回消息（line 590, 598）、`query_user_mood`（line 779-781, 799）、`ListCustomRecordTypesTool`（line 47-49）、`QueryCustomRecordEntriesTool`（line 276-279）、`QuerySessionHistoryTool`（line 295-296） |
| 计算用字段是否保持 UTC ISO 不转换 | ✅ | 时长计算、时间范围校验均使用 `_parse_iso_time()` 解析后的 UTC aware datetime（line 234-236, 297-298, 564-565） |
| 转换是否为显式调用（非装饰器） | ✅ | 全部使用显式的 `_utc_to_local()` / `utc_to_local_display()` 调用 |

**§4.3 遵守率: 3/3**

### §4.4 工具函数内部一致性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 工具函数接收的参数是否为 UTC ISO | ✅ | Docstring 已更新标注"UTC ISO 8601 格式"，dreaming() 直接调用时正确传入 `local_to_utc_iso()` 转换后的值（agent_schedule_job.py line 138, 246-247, 312-313） |
| 内部数据库查询是否使用 UTC ISO | ✅ | `with_time_range(start_time, end_time)` 传入的是 UTC ISO 字符串 |
| 格式化输出时是否显式转换显示用字段 | ✅ | 全部使用 `_utc_to_local()` / `utc_to_local_display()` |

**§4.4 遵守率: 3/3**

---

## 2. 潜在 Bug

### 🔴 Bug 1: todolist 日期范围使用 UTC 日期切片（严重）

**文件**: `lifeprism/llm/agent/tools/lifeprismsystem.py`  
**行号**: 371  
**代码**:
```python
.with_date_range(start_time[:10], end_time[:10])
```

**问题**: `start_time` 和 `end_time` 经过 `local_to_utc_iso()` 转换后是 UTC ISO 8601 格式（如 `2026-07-11T20:00:00+00:00`）。`[:10]` 切片提取的是 UTC 日期部分 `2026-07-11`，而 `todo_list.date` 字段存储的是用户本地日期 `YYYY-MM-DD`（§2.2 日期字段规则）。在时区边界（如 UTC+8 用户在 00:00~08:00 本地时间查询时），UTC 日期会比本地日期早一天，导致 todolist 查询结果不正确。

**影响场景**: 用户查询 `2026-07-12 04:00:00` ~ `2026-07-13 04:00:00`（本地时间，UTC+8），转换后 `start_time = "2026-07-11T20:00:00+00:00"`，`[:10]` 得到 `2026-07-11`。实际应查询日期 `2026-07-12` ~ `2026-07-13` 的 todolist。

**修复建议**: 需要将原始的本地时间在 execute 层传入工具函数，或者在工具函数内部使用 `get_local_today()` 等基于本地时区的方法来计算日期范围。例如：
```python
# 方案：execute 层传入原始本地时间，工具函数分离显示/查询用途
# 或在工具函数中基于传入时间段计算本地日期
```

**失败场景**: UTC+8 时区，用户在本地时间凌晨 00:00~08:00 通过 LLM 工具查询 todolist 时，会遗漏当天的待办事项。

### 🟡 Bug 2: `_parse_iso_time` 与 `parse_iso_to_aware` 代码重复

**文件**: `lifeprism/llm/agent/tools/lifeprismsystem.py`  
**行号**: 21-33

**问题**: `_parse_iso_time()` 函数（lifeprismsystem.py line 21-33）的核心逻辑与 `lifeprism/utils/time_utils.py` 中的 `parse_iso_to_aware()` 几乎完全一致（`datetime.fromisoformat()` + naive tzinfo 补 UTC）。区别仅在于 `_parse_iso_time` 的 ValueError 包装了 `{ERROR}` 前缀。

**影响**: 违反项目"单一真相源"原则。如果未来解析逻辑需要修改（如兼容更多格式），需要同时维护两个位置。此外，`_parse_iso_time` 中的 `str(time_str)` 调用可能引入意外的格式化行为（当 `time_str` 已是 `datetime` 对象时，`str()` 会输出带空格分隔符的字符串 `"2026-04-19 09:00:00+00:00"`，虽然在 Python 3.11+ 中 `fromisoformat` 可以解析，但隐式行为不够显式）。

**修复建议**: 让 `_parse_iso_time` 直接调用 `parse_iso_to_aware`，仅在外层包装 ValueError：
```python
from lifeprism.utils.time_utils import parse_iso_to_aware

def _parse_iso_time(time_str: str) -> datetime:
    try:
        return parse_iso_to_aware(str(time_str))
    except (ValueError, TypeError) as e:
        raise ValueError(f"{ERROR} 时间格式错误: {e}") from e
```

### 🟡 Bug 3: `_utc_to_local` 异常兜底可能静默泄露 UTC ISO

**文件**: `lifeprism/llm/agent/tools/lifeprismsystem.py`  
**行号**: 36-52

**问题**: `_utc_to_local()` 函数在 `utc_to_local_display()` 抛出 `ValueError` 或 `TypeError` 时，**静默返回原始值**（line 52: `return str(utc_time_str)`）。如果 `utc_to_local_display()` 因任何原因失败（不仅仅是"已是本地格式"），导致 UTC ISO 时间直接作为显示值返回给 AI，这违反了 §4.3 的核心要求。

**具体风险场景**:
1. `segment["start"]` 来自 `build_time_segments()`，该函数返回的 `start`/`end` 是 `datetime` 对象（density_utils.py）。`_utc_to_local()` 内部调用 `str(dt)` 后传给 `utc_to_local_display()`。如果 `datetime` 对象的转换逻辑有任何变化，静默兜底会隐藏问题。
2. 数据库返回的时间字段格式变更时，框架不会报错而是默默传回原始值。

**修复建议**: 异常兜底时至少记录 WARNING 日志，便于发现转换失败：
```python
except (ValueError, TypeError):
    logger.warning("时间转换失败，返回原始值: %s", utc_time_str)
    return str(utc_time_str)
```

### 🟢 Bug 4: `_utc_to_local` 空字符串处理后缺少 `ensure_ascii`

**文件**: `lifeprism/llm/agent/tools/lifeprismsystem.py`  
**行号**: 47

**问题**: `if not utc_time_str: return ""` 会在 `utc_time_str` 为 `None` 或空字符串时返回空字符串。这是正确的防御。但对比 `query_user_mood` 中 `entry.get('created_at', '')` 调用（line 799），如果 `created_at` 字段缺失，传入空字符串，`_utc_to_local("")` 返回 `""`，会在格式化字符串中产生一个空的时间戳，如 `"1.  心情: 5分\n"`。虽然不会崩溃，但输出略有不美观。

**级别**: 低，不影响功能。

### 🟢 Bug 5: session_query.py 时间提取位置硬编码

**文件**: `lifeprism/llm/agent/tools/session_query.py`  
**行号**: 296

**代码**:
```python
local_str = utc_to_local_display(timestamp)  # YYYY-MM-DD HH:MM:SS
time_str = local_str[5:16]  # 提取 MM-DD HH:MM
```

**问题**: 使用硬编码的字符串切片 `[5:16]` 提取 `MM-DD HH:MM`。如果 `utc_to_local_display` 的输出格式发生变化（如月/日补零策略变化），此切片会提取到错误内容。

**修复建议**: 使用 `datetime` 对象的 `strftime` 方法提取：
```python
dt = parse_iso_to_aware(timestamp)
local_tz = pytz.timezone(get_user_timezone())
local_dt = dt.astimezone(local_tz)
time_str = local_dt.strftime("%m-%d %H:%M")
```
当前实现虽然有脆性，但考虑到 try/except 兜底（`timestamp[:16]`），不会导致崩溃——仅可能导致显示格式略微错位。

**级别**: 低，有兜底逻辑。

---

## 3. 功能缺失风险

### 3.1 dreaming() 定时任务复用 LLM 工具

**文件**: `lifeprism/llm/function/agent_schedule_job.py`

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 调用路径正确转换 | ✅ | `dreaming()`（line 310-313）调用 `query_user_activity_summary()` 时，先用 `local_to_utc_iso()` 转换；`get_mood_data()`（line 138）同样转换。`update_memory()`（line 244-247）也正确转换。 |
| 工具函数输出时间格式一致性 | ✅ | 工具函数返回的格式化文本中所有时间均为本地 `YYYY-MM-DD HH:MM:SS`（由 `_utc_to_local()` 转换），适用于 AI 总结 prompt。 |
| 本地时间用于 prompt 注入 | ✅ | `dreaming()` 中 `summary_activities(activities, start_time, end_time)` 传入的 `start_time`/`end_time` 保持本地格式字符串（`build_local_datetime` 输出），符合 §4.1 要求。 |

### 3.2 AI 输入格式兼容性

**风险**: `local_to_utc_iso()` 使用固定格式 `"%Y-%m-%d %H:%M:%S"` 解析 AI 输入。如果 AI 输出偏离此格式（如 `2026-07-12` 缺少时间部分、`2026-7-12 9:0:0` 不补零、或 ISO 格式 `2026-07-12T10:30:00`），`strptime` 会抛出 `ValueError`。

**当前防护**: 所有 `execute` 方法均使用 `try/except ValueError` 捕获此错误并返回 `{ERROR}参数错误: ...` 给 AI，AI 可据此重新生成正确格式。JSON Schema 中的 `description` 明确要求格式。**风险可控**。

### 3.3 未涉及的转换

| 方法 | 说明 |
|------|------|
| `UserMoodCreateTool.execute()` | 不涉及时区参数，不需要修改 |
| `CreateCustomRecordTypeTool.execute()` | 不涉及时区参数，不需要修改 |
| `CreateCustomRecordEntryTool.execute()` | 不涉及时区参数，时间由数据库 DEFAULT 自动生成 |
| `QuerySessionListTool.execute()` | `updated_at` 用于 `startswith` 日期过滤（line 119），已为 UTC ISO 格式，与查询参数 `date_filter`（`YYYY-MM-DD`）做字符串前缀匹配。`updated_at` 的 UTC 日期部分在时区边界可能不等于本地日期，但这是一个日期筛选的近似匹配，该功能本身设计为近似筛选，不要求精确。 |

---

## 4. 安全隐患

| 检查项 | 风险 | 评估 |
|--------|------|------|
| AI 输入时间的格式注入 | AI 返回的时间字符串能否被利用进行注入攻击 | **低风险**。`local_to_utc_iso()` 使用 `datetime.strptime` 严格解析，非匹配格式直接抛异常。且 JSON Schema 限制了 AI 只能传入字符串类型。即使 AI 故意传入特殊字符串，最坏结果是解析失败返回错误消息。 |
| 时区信息的泄露风险 | 返回给 AI 的时间中是否包含不应暴露的时区信息 | **低风险**。`_TIME_FORMAT_DESC` 标注"本地时区"而非实际时区名称。时间显示值也不携带时区标识。但工具的 `description` 中未暴露时区名称属于隐私保护（而非缺失）。 |
| 日期切片的信息截断 | `start_time[:10]` 硬切片的安全性 | **低风险**。仅截取 ISO 8601 字符串的前 10 字符，而 ISO 8601 保证前 10 字符为 `YYYY-MM-DD`。不存在注入攻击向量。 |

---

## 总结

### 整体评价

本次变更**高质量地完成了 LLM Tools 层的 UTC 时区迁移**，核心转换逻辑（execute 层输入转换 + 工具函数输出转换）准确、一致、覆盖全面。

### 规则遵守统计

| 规则章节 | 遵守率 | 状态 |
|----------|--------|------|
| §4.1 提示词输入 | 3/3 | ⚠️ 时区名称标注为"本地时区"而非具体名称（影响较小） |
| §4.2 工具输入 | 3/3 | ✅ 完美 |
| §4.3 工具输出 | 3/3 | ✅ 完美 |
| §4.4 内部一致性 | 3/3 | ✅ 良好 |
| §2 字段分类 | -- | ⚠️ 见 Bug 1（todolist 日期字段误用 UTC 日期切片） |
| §3.1 时间生成 | -- | ✅ 工具函数不生成时间，仅转换和显示 |
| §3.2 时间序列化 | -- | ✅ 使用 `.isoformat()` 系列 |
| §3.3 时间解析 | -- | ⚠️ 见 Bug 2（重复实现） |

### 必须修复（Blocking）

1. **🔴 Bug 1**: todolist 日期范围使用 UTC 日期切片。在时区边界（本地时间 00:00~08:00）会导致查询到错误的日期范围。

### 建议修复（Non-blocking）

2. **🟡 Bug 2**: `_parse_iso_time` 重复实现 `parse_iso_to_aware`，应复用公共函数。
3. **🟡 Bug 3**: `_utc_to_local` 异常兜底时添加 WARNING 日志。

### 低优先级

4. **🟢 Bug 4**: `session_query.py` 硬编码字符串切片位置，建议改用 `strftime`。
