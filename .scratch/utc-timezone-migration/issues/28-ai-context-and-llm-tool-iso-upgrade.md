# Issue #28: LLM 工具时间转换职责上移到 execute 层

## Parent

`.scratch/utc-timezone-migration/prd.md`

## 背景

**架构原则（最终决策）**：
- **数据层（Repository）**：只返回 UTC ISO，不转换
- **工具函数**：接收 UTC ISO，返回结果（内部一致性）
- **execute 方法**：负责输入转换（本地→UTC）和输出转换（UTC→本地给 AI）
- **dreaming**：硬编码本地时间后马上就地转 UTC ISO，调用工具函数

**方案选择**：采用"工具内部显式转换"方案，不采用装饰器方案。理由：
- 时间字段不仅用于显示，还用于计算（如 `_category_stats` 用 `start_time`/`end_time` 做区间截断）
- 装饰器会静默失败（字段改名时不报错），显式调用会 `KeyError` 立即暴露
- 返回类型多样（`list[dict]`、`tuple(list[dict], int)`、JSONL 文件等），装饰器难以统一覆盖
- 转换逻辑在显式调用处，便于调试

**当前问题**：
1. `lifeprismsystem.py` 的工具在内部做时间转换（`_parse_local_time`、`_utc_to_local`），职责不清晰
2. `custom_records_tool.py` 的 `QueryCustomRecordEntriesTool` 输出未转本地时间
3. `session_query.py` 的时间输出未转本地时间（[session_query.py:295-296](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/session_query.py#L295-L296) 用 `fromisoformat` 未做时区转换）

## What to build

### Part 1: `lifeprismsystem.py` 工具函数重构

#### 1.1 工具函数改为只接收 UTC ISO

**当前**：`query_user_activity_summary(query_option, start_time, end_time)`
- `start_time`/`end_time` 是本地 `YYYY-MM-DD HH:MM:SS`
- 内部用 `_parse_local_time` 转 UTC 查库

**改为**：
- `start_time`/`end_time` 改为 UTC ISO 8601
- 内部直接用 UTC ISO 查库，不做转换
- 移除内部对 `_parse_local_time` 的调用

同样修改其他时间相关工具函数：
- `query_user_activity_log`
- `create_or_update_user_behavior_note`
- `query_user_mood`

#### 1.2 execute 方法负责输入转换

在每个工具的 `execute` 方法开头，将 AI 输入的本地时间转 UTC ISO：

```python
async def execute(self, **kwargs: Any) -> Any:
    try:
        query_option = set(kwargs.get("query_option", []))
        # 输入转换：本地时间 → UTC ISO
        start_time = local_to_utc_iso(kwargs.get("start_time", ""))
        end_time = local_to_utc_iso(kwargs.get("end_time", ""))
        return query_user_activity_summary(query_option, start_time, end_time)
    except ValueError as e:
        return f"{ERROR}参数错误: {str(e)}"
```

**兜底处理**：AI 输入格式不固定，`local_to_utc_iso`（#27 提供）需兼容多种格式。

#### 1.3 输出转换用公共函数

工具函数内部结果中的时间字段，用 #27 的 `utc_to_local_display` 公共函数转换：

```python
# 工具函数内部
content += f"### 时间段 {idx}: {utc_to_local_display(segment['start'])} ~ {utc_to_local_display(segment['end'])}\n"
```

**注意**：只有用于**显示**的时间字段才转。用于**计算**的时间字段（如 `_category_stats` 中的 `start_time`/`end_time`）保持 UTC ISO，不转。

#### 1.4 移除/改造 `_parse_local_time` 和 `_utc_to_local`

- `_parse_local_time`：移除，输入转换由 execute 方法调用 `local_to_utc_iso` 完成
- `_utc_to_local`：改为调用 #27 的 `utc_to_local_display` 公共函数，或直接内联使用
- `_parse_iso_time`：保留，用于内部计算（解析 UTC ISO 为 datetime 对象）

#### 1.5 保持不变的部分

- `_build_run_context`：输出 `YYYY-MM-DD HH:MM:SS`（本地时间），符合"面向 AI 的时间用本地格式"原则
- `_TIME_FORMAT_DESC`：保持 `YYYY-MM-DD HH:MM:SS（本地时区）`，AI 仍输入本地时间

### Part 2: `custom_records_tool.py` 修复

#### 2.1 `QueryCustomRecordEntriesTool` 输出转换

**当前问题**：[custom_records_tool.py:266](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/custom_records_tool.py#L266) 直接 `json.dumps(entries)` 返回，`created_at` 字段是 UTC ISO，AI 看到的是 UTC 时间。

**修复**：在 `execute` 方法中，对返回的 entries 做时间字段转换：

```python
async def execute(self, **kwargs: Any) -> str:
    # ... 查询逻辑 ...
    entries = custom_record_repository.query_entries(...)
    
    # 输出转换：UTC ISO → 本地 YYYY-MM-DD HH:MM:SS
    for entry in entries:
        if "created_at" in entry:
            entry["created_at"] = utc_to_local_display(entry["created_at"])
        if "updated_at" in entry:
            entry["updated_at"] = utc_to_local_display(entry["updated_at"])
    
    return f"{SUCCESS}{json.dumps(entries, ensure_ascii=False)}"
```

#### 2.2 `QueryCustomRecordEntriesTool` 输入转换

**当前**：`date_range` 参数是 `YYYY-MM-DD` 格式（日期字段，非时间戳）。

**处理**：日期字段保持本地 `YYYY-MM-DD`，不转 UTC（符合"日期字段保持本地"原则）。但需要在 Repository 层确保查询逻辑正确（见 #30 的 Bug 1/Bug 2）。

### Part 3: `session_query.py` 修复

#### 3.1 `QuerySessionHistoryTool` 时间输出转换

**当前问题**：[session_query.py:295-296](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/session_query.py#L295-L296)：
```python
dt = datetime.fromisoformat(timestamp)
time_str = dt.strftime("%m-%d %H:%M")
```
解析后未做时区转换，AI 看到的是 UTC 时间。

**修复**：用 `utc_to_local_display` 转换后再格式化：

```python
from lifeprism.utils.time_utils import utc_to_local_display

# 在格式化时间戳处
try:
    local_str = utc_to_local_display(timestamp)  # YYYY-MM-DD HH:MM:SS
    time_str = local_str[5:16]  # 提取 MM-DD HH:MM
except Exception:
    time_str = timestamp[:16] if len(timestamp) >= 16 else timestamp
```

#### 3.2 `QuerySessionListTool` 时间输出转换

检查 `QuerySessionListTool` 的输出，如果有时间字段（如 `created_at`、`last_message_time`），同样用 `utc_to_local_display` 转换。

### Part 4: `UserMoodCreateTool` 确认

当前 `UserMoodCreateTool` 的输出已通过 `_utc_to_local` 转换 `created_at`，符合要求。本 issue 中改为调用公共 `utc_to_local_display` 函数即可。

## Acceptance criteria

### Part 1: lifeprismsystem.py
- [ ] `query_user_activity_summary` 工具函数改为接收 UTC ISO 参数
- [ ] `query_user_activity_log` 工具函数改为接收 UTC ISO 参数
- [ ] `create_or_update_user_behavior_note` 工具函数改为接收 UTC ISO 参数
- [ ] `query_user_mood` 工具函数改为接收 UTC ISO 参数
- [ ] 每个工具的 `execute` 方法开头调用 `local_to_utc_iso` 转换时间参数
- [ ] 工具函数内部显示用的时间字段用 `utc_to_local_display` 转换
- [ ] 工具函数内部计算用的时间字段保持 UTC ISO（如 `_category_stats`）
- [ ] `_parse_local_time` 移除
- [ ] `_utc_to_local` 改为调用 #27 公共函数
- [ ] `_parse_iso_time` 保留（用于内部计算）
- [ ] `_build_run_context` 保持不变（输出 `YYYY-MM-DD HH:MM:SS`）
- [ ] `_TIME_FORMAT_DESC` 保持不变

### Part 2: custom_records_tool.py
- [ ] `QueryCustomRecordEntriesTool` 输出的 `created_at`/`updated_at` 转为本地时间
- [ ] `QueryCustomRecordEntriesTool` 的 `date_range` 输入保持本地日期（不转 UTC）

### Part 3: session_query.py
- [ ] `QuerySessionHistoryTool` 的时间输出转为本地时间
- [ ] `QuerySessionListTool` 的时间输出转为本地时间（如有）

### Part 4: 通用
- [ ] 单元测试：execute 方法正确转换输入参数
- [ ] 单元测试：工具函数接收 UTC ISO 正确查询
- [ ] 单元测试：结果显示用时间字段转为本地格式
- [ ] 单元测试：计算用时间字段保持 UTC ISO
- [ ] `ruff check` 和 `ruff format` 全部通过
- [ ] 现有测试全部通过（无回归）

## Blocked by

- Issue #27 - 后端本地时间转 UTC 工具函数（需要 `local_to_utc_iso` 和 `utc_to_local_display` 函数）

## 注意事项

1. **不采用装饰器方案**：审查报告认为装饰器有静默失败、字段用途差异、返回类型多样等风险
2. **显示用 vs 计算用**：时间字段用于显示时转本地，用于计算时保持 UTC ISO。只有工具函数知道字段用途，所以转换在工具函数内部
3. **execute 方法负责输入转换**：每个工具的 execute 开头调用 `local_to_utc_iso`
4. **输出转换用公共函数**：工具函数内部用 `utc_to_local_display` 转换结果显示
5. **AI 仍输入本地时间**：`_TIME_FORMAT_DESC` 不变，execute 层负责转换
6. **dreaming 调用工具函数时**：硬编码本地时间后马上转 UTC ISO（见 #29），然后调用工具函数
7. **兜底处理**：AI 输入格式不固定，`local_to_utc_iso` 需要兼容多种格式
8. **这是重构**：涉及多个工具函数的参数类型变更，需要仔细测试
9. **日期字段保持本地**：`QueryCustomRecordEntriesTool` 的 `date_range` 是日期字段，不转 UTC
10. **覆盖 3 个文件**：`lifeprismsystem.py`、`custom_records_tool.py`、`session_query.py`
