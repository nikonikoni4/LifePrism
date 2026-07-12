# Issue #29: 定时任务时区从 UTC 改为本地时区

## Parent

`.scratch/utc-timezone-migration/prd.md`

## 背景

**架构原则（最终决策）**：
- **内部时间**：UTC ISO 8601
- **对外时间**（面向 AI）：本地 `YYYY-MM-DD HH:MM:SS`
- **工具函数**：只接收 UTC ISO（#28 重构后）
- **dreaming 调用工具函数时**：硬编码本地时间后马上就地转 UTC ISO，然后传给工具函数

当前定时任务存在"巧合性正确"问题：

1. **CronTrigger 使用 UTC 时区**：`AsyncIOScheduler(timezone=pytz.UTC)`
2. **cron 表达式 `"0 2 * * *"` 是 UTC 02:00**：注释说"= 北京时间 10:00"，硬编码假设
3. **日期计算用 UTC**：`_dreaming()`、`_should_execute_cron_today` 等用 `datetime.now(timezone.utc)`
4. **`process_session_message` 日期标签用 UTC**：behavior.md 日期标签应该是本地日期

## What to build

### Part 1: `schedule_service.py` CronTrigger 时区修复

1. **调度器时区**：
   - `AsyncIOScheduler(timezone=pytz.UTC)` → `AsyncIOScheduler(timezone=pytz.timezone(get_user_timezone()))`

2. **Cron 表达式语义改为本地时间**：
   - `_SYSTEM_CRON_JOB_TIME = "0 2 * * *"` → `"0 10 * * *"`（本地 10:00）
   - 更新注释：从"UTC 02:00 = 北京时间 10:00"改为"本地 10:00"
   - `IntervalTrigger` 的 `timezone=pytz.UTC` 同步改为本地时区
   - `CronTrigger.from_crontab(cron_expr, timezone=pytz.UTC)` 同步改为本地时区

3. **TEST_MODE 的 cron 表达式**：
   - `target_time = datetime.now(timezone.utc)` → `datetime.now(local_tz)`
   - 注释更新

### Part 2: `schedule_service.py` 日期计算改本地时区

4. **`_dreaming()` 函数**：
   - `yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")` → 用本地时区计算昨天
   - 可使用 `time_utils.get_local_today()` 减 1 天
   - 更新注释说明"基于本地时区获取昨天"

5. **`_should_execute_cron_today` 方法**：
   - `today = datetime.now(timezone.utc).strftime("%Y-%m-%d")` → 用本地时区计算今天
   - 可使用 `time_utils.get_local_today().isoformat()`

6. **`_execute_cron_with_state` 方法**：
   - `today = datetime.now(timezone.utc).strftime("%Y-%m-%d")` → 用本地时区计算今天

7. **`_add_system_jobs` 方法**：
   - `now = datetime.now(timezone.utc)` → 用本地时区判断是否过触发时间
   - 注释更新："使用本地时间判断是否过触发时间（Cron 表达式基于本地时区）"

8. **`add_cron_job` 方法的 `wrapped_func`**：
   - `today = datetime.now(timezone.utc).strftime("%Y-%m-%d")` → 用本地时区计算今天

### Part 3: `agent_schedule_job.py` 时间构造改为 UTC ISO

9. **`dreaming()` 函数的时间构造**：
   - **硬编码本地时间后马上就地转 UTC ISO**
   - 当前：`start_time = f"{date} {DAILY_START_HOUR}"` → `2026-07-12 04:00:00`（本地）
   - 改为：`start_time = local_to_utc_iso(build_local_datetime(date, DAILY_START_HOUR))` → `2026-07-11T20:00:00+00:00`（UTC ISO）
   - 原因：#28 重构后，工具函数只接收 UTC ISO，dreaming 传给工具函数的必须是 UTC ISO
   - 用 #27 的 `build_local_datetime` 构造本地时间，再用 `local_to_utc_iso` 转 UTC ISO

10. **`update_memory()` 函数的时间构造**：
    - 同上，用 `local_to_utc_iso(build_local_datetime(...))` 构造 UTC ISO
    - 传给 `query_user_activity_summary`

11. **`process_session_message` 函数的日期标签**：
    - `datetime.now(timezone.utc).strftime("%Y-%m-%d")` → 用本地时区计算日期标签
    - 可使用 `time_utils.get_local_today().isoformat()`

### Part 4: 验证

12. **定时任务触发时间验证**：
    - 任务在本地 10:00 触发（非 UTC 10:00）
    - 用户时区改为洛杉矶后，任务在洛杉矶时间 10:00 触发

13. **数据范围验证**：
    - `dreaming()` 传给工具函数的时间是 UTC ISO
    - 工具函数正确接收 UTC ISO 并查库

14. **日期标签验证**：
    - behavior.md 的日期标签是本地日期（非 UTC 日期）

## Acceptance criteria

### Part 1
- [ ] `AsyncIOScheduler` 使用 `get_user_timezone()` 对应的 pytz 时区
- [ ] `IntervalTrigger` 和 `CronTrigger` 使用本地时区
- [ ] `_SYSTEM_CRON_JOB_TIME` 改为 `"0 10 * * *"`（本地 10:00）
- [ ] 注释更新为"本地 10:00"

### Part 2
- [ ] `_dreaming()` 用本地时区计算昨天
- [ ] `_should_execute_cron_today` 用本地时区计算今天
- [ ] `_execute_cron_with_state` 用本地时区计算今天
- [ ] `_add_system_jobs` 用本地时区判断是否过触发时间
- [ ] `add_cron_job` 的 `wrapped_func` 用本地时区计算今天

### Part 3
- [ ] `dreaming()` 的时间参数用 `local_to_utc_iso(build_local_datetime(...))` 构造 UTC ISO
- [ ] `update_memory()` 的时间参数用同样方式构造 UTC ISO
- [ ] `process_session_message` 的日期标签用本地时区计算
- [ ] `DAILY_START_HOUR` 常量保留为 `"04:00:00"`（纯时间，通过 `build_local_datetime` 组装）

### Part 4
- [ ] 单元测试：定时任务在本地 10:00 触发（mock 不同时区验证）
- [ ] 单元测试：`dreaming()` 构造的时间范围是 UTC ISO 格式
- [ ] 单元测试：日期标签是本地日期
- [ ] `ruff check` 和 `ruff format` 全部通过
- [ ] 现有测试全部通过（无回归）

## Blocked by

- Issue #27 - 后端本地时间转 UTC 工具函数（需要 `build_local_datetime` 和 `local_to_utc_iso` 函数）
- Issue #28 - LLM 工具时间转换职责上移（工具函数改为接收 UTC ISO）

## 注意事项

1. **CronTrigger 时区与 cron 表达式语义必须一致**：CronTrigger 使用本地时区后，cron 表达式 `"0 10 * * *"` 就是本地 10:00
2. **日期计算必须用本地时区**：`_dreaming` 查询"昨天"的数据，"昨天"是用户本地时区的昨天
3. **dreaming 传给工具函数的是 UTC ISO**：#28 重构后工具函数只接收 UTC ISO
4. **硬编码本地时间后马上转 UTC ISO**：`build_local_datetime` → `local_to_utc_iso`，就地转换
5. **`DAILY_START_HOUR` 常量不改**：保留为 `"04:00:00"`（纯时间，无日期），通过 `build_local_datetime` 组装
6. **TEST_MODE 同步修改**：TEST_MODE 下的 cron 表达式生成也要用本地时区
7. **依赖 #27 和 #28**：#27 提供转换函数，#28 重构工具函数接收 UTC ISO
