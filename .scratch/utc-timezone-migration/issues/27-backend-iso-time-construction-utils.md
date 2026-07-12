# Issue #27: 后端本地时间转 UTC 工具函数（Prefactor）

## Parent

`.scratch/utc-timezone-migration/prd.md`

## 背景

时区配置功能已实现（commit `e7d98ee`），`get_user_timezone()` 可动态读取用户配置的时区。

**架构原则（最终决策）**：
- **内部时间**（数据库存储、模块间传输）：UTC ISO 8601 格式
- **对外时间**（面向用户、面向 AI）：本地时间 `YYYY-MM-DD HH:MM:SS` 格式
- **就地转换**：组件/工具内部转换后传出，不在中间模块转换

当前问题：
- 定时任务（如 `dreaming()`）构造本地时间字符串 `f"{date} {DAILY_START_HOUR}"`（如 `2026-07-12 04:00:00`），传给 LLM 工具后需要转 UTC 查库
- LLM 工具的 `_parse_local_time` 已能处理本地时间转 UTC，但缺少统一的工具函数供其他场景使用
- Repository 层有多处用本地时间字符串直接查 UTC 时间戳字段，需要统一的转换函数

本 issue 建立"让后续修改变容易"的基础设施，**不修复具体业务问题**。

## What to build

### 新增辅助函数（`lifeprism/utils/time_utils.py`）

1. `local_to_utc_iso(local_str: str, format: str = "%Y-%m-%d %H:%M:%S") -> str`
   - 输入：本地时间字符串（如 `2026-07-12 04:00:00`）
   - 输出：UTC ISO 8601 字符串（如 `2026-07-11T20:00:00+00:00`）
   - 偏移量由 `get_user_timezone()` 动态决定
   - 实现要点：
     ```python
     tz = pytz.timezone(get_user_timezone())
     dt = datetime.strptime(local_str, format)
     dt = tz.localize(dt)
     return dt.astimezone(timezone.utc).isoformat()
     ```
   - 用于：定时任务构造本地时间后转 UTC 查库、Repository 层修复

2. `build_local_datetime(date_str: str, time_str: str = "00:00:00") -> str`
   - 输入：日期 `YYYY-MM-DD` + 时间 `HH:MM:SS`
   - 输出：本地时间字符串 `YYYY-MM-DD HH:MM:SS`（无时区标识，面向 AI/用户格式）
   - 示例：`build_local_datetime("2026-07-12", "04:00:00")` → `2026-07-12 04:00:00`
   - 用于：定时任务构造本地时间字符串（替代 `f"{date} {time}"` 硬拼接）

3. `utc_to_local_display(utc_iso: str) -> str`
   - 输入：UTC ISO 8601 字符串（如 `2026-07-11T20:00:00+00:00`）
   - 输出：本地时间字符串 `YYYY-MM-DD HH:MM:SS`（面向 AI/用户格式）
   - 偏移量由 `get_user_timezone()` 动态决定
   - 用于：后端将 UTC ISO 转为本地时间显示（AI 工具输出、日志等）
   - 注意：`lifeprismsystem.py` 已有 `_utc_to_local` 实现此功能，本函数将其提取到公共工具层供其他模块复用

4. `build_utc_time_range(local_date: str) -> tuple[str, str]`
   - 输入：本地日期 `YYYY-MM-DD`
   - 输出：`(utc_start_iso, utc_end_iso)`（当天 00:00:00 ~ 23:59:59 的 UTC 范围）
   - 用于：Repository 层按日期查询时间戳字段时，将本地日期转为 UTC 时间范围
   - 实现要点：调用 `local_to_utc_iso(f"{local_date} 00:00:00")` 和 `local_to_utc_iso(f"{local_date} 23:59:59")`

### 单元测试

为所有函数编写单元测试，覆盖：
- UTC+8 时区（默认 `Asia/Shanghai`）
- 其他时区（如 `America/Los_Angeles` UTC-8、`UTC` UTC+0）
- 跨日期边界：本地 00:30 → UTC 前一天 16:30
- `build_local_datetime` 默认时间参数（`time_str` 省略时为 `00:00:00`）
- `utc_to_local_display` 处理 `+00:00`、`Z` 后缀、带偏移输入
- `build_utc_time_range` 跨天场景
- 容错：无效输入抛 `ValueError`

## Acceptance criteria

- [ ] `lifeprism/utils/time_utils.py` 新增 `local_to_utc_iso`、`build_local_datetime`、`utc_to_local_display`、`build_utc_time_range` 四个函数
- [ ] 所有函数使用 `get_user_timezone()` 读取配置时区，偏移量动态决定
- [ ] 单元测试覆盖 UTC+8、UTC-8、UTC+0 三种时区
- [ ] 单元测试覆盖跨日期边界场景
- [ ] `utc_to_local_display` 能正确处理 `+00:00`、`Z`、带偏移三种输入
- [ ] `ruff check` 和 `ruff format` 全部通过
- [ ] 单元测试全部通过

## Blocked by

None - 可立即开始

## 注意事项

1. **这是 prefactor issue**：只建立工具函数，**不修改任何业务代码**
2. **后续 Issue #29、#30 将使用这些函数**：定时任务时区修复、Repository 层遗留 bug 修复
3. **对外格式是 `YYYY-MM-DD HH:MM:SS`**：面向 AI/用户的时间用此格式，不是 ISO 带偏移
4. **内部格式是 UTC ISO 8601**：数据库存储、模块间传输用此格式
5. **不修改 `get_utc_now_iso`**：该函数已正确返回 UTC ISO，保持不变
6. **不修改 `get_local_today`**：该函数已正确返回本地日期，保持不变
7. **`_utc_to_local` 提取**：从 `lifeprismsystem.py` 提取到 `time_utils.py` 后，`lifeprismsystem.py` 的 `_utc_to_local` 可改为调用公共函数（此修改在 #28 中处理）
