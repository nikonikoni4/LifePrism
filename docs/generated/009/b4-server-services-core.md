# B4: Server Services 核心 审查报告

## 审查概要
- 审查文件数: 6
- 审查标准: time-handling-rules.md Section 2, 3.1-3.3, 3.6, 6
- 审查日期: 2026-07-12
- 变更总量: 约 388 行（6 个文件）
- 严重程度: **发现 1 个严重 Bug（数据查询错位）和 4 个中等问题**

---

## 1. 规则遵守程度

### 1.1 report_service.py (122行变更) -- 部分遵守，存在严重 Bug

**新增辅助函数：**

| 函数 | 状态 | 说明 |
|------|------|------|
| `_get_local_today_str()` (L:51) | ✅ | 基于 `get_local_today()` 获取本地时区日期，正确 (§3.5) |
| `_normalize_timestamp()` (L:63) | ✅ | 正确处理 ISO 和传统两种格式 |
| `_utc_timestamp_to_local_date()` (L:78) | ⚠️ | 实现正确但**从未被调用**，死代码 |
| `_add_local_date_column()` (L:103) | ⚠️ | 实现正确但**从未被调用**，死代码 |
| `_build_utc_time_range()` (L:131) | 🔴 | 实现正确但**从未被调用**，死代码；且输出使用 `.strftime()` 违反 §3.2 |

**已修改的调用点：**

| 位置 | 变更 | 状态 |
|------|------|------|
| L:247 `get_daily_report` | `datetime.now().strftime()` → `_get_local_today_str()` | ✅ 正确，基于本地时区判断"今天" |
| L:342 `get_weekly_report` | 同上 | ✅ |
| L:445 `get_monthly_report` | 同上 | ✅ |

**未修改的关键缺陷：**

🔴 **严重 Bug**：以下 6 个数据查询函数（共 12 处）仍使用迁移前的 `f"{date} 00:00:00"` 模式构造时间范围，直接传给 SQL `WHERE start_time >= ?` 进行**字符串比较**。这些字符串是**本地时间**，但数据库 `user_app_behavior_log.start_time` 已被 m009 迁移为 **UTC ISO 8601 格式**（`2026-07-11T16:00:00+00:00`）。

```python
# ❌ L:578-579 _calc_sunburst_data() — 本地时间字符串，未转 UTC
start_time = f"{start_date} 00:00:00"     # "2026-07-12 00:00:00"
end_time = f"{end_date} 23:59:59"         # "2026-07-12 23:59:59"
df = server_lw_data_provider.load_user_app_behavior_log(
    start_time=start_time, end_time=end_time
)
```

| 函数 | 受影响行号 | 调用 `load_user_app_behavior_log` |
|------|-----------|----------------------------------|
| `_calc_sunburst_data()` | L:578-579 | 旭日图数据，日报/周报/月报共用 |
| `_calc_daily_trend()` | L:792-793, L:833-834 | 日报趋势图 |
| `_calc_weekly_trend()` | L:899-900 | 周报趋势图 |
| `_calc_monthly_trend()` | L:965-966 | 月报趋势图 |
| `_calc_heatmap_data()` | L:1032-1033 | 热力图数据 |

同样模式出现在 `_calc_comparison_data()` 的调用点（L:222, L:242, L:310-311, L:335-336, L:409-410, L:438-439），这些参数最终进入 `report_provider._calc_category_comparison()` 和 `_calc_goal_comparison()` 的 SQL `WHERE start_time >= ?` 子句（`report_provider.py` L:699, L:711, L:773, L:785）。

**影响分析（UTC+8 用户为例）：**
- 用户本地 `2026-07-12 00:00 ~ 07:59` 的数据，存储在 DB 为 UTC `2026-07-11T16:00:00 ~ 2026-07-11T23:59:59`
- 查询 `start_time >= "2026-07-12 00:00:00"` → 字符串比较 `"2026-07-11..." < "2026-07-12..."` → **这些记录被排除**
- 反之，UTC `2026-07-12T16:00:00 ~ 2026-07-12T23:59:59`（本地 7月13日 00:00-07:59）会被**错误包含**进 7月12日 的报表

**严重程度**: 所有日报、周报、月报的旭日图/趋势图/热力图/环比对比数据会在每天前 8 小时（UTC+8 用户）出现数据错位或缺失。

---

### 1.2 usage_service.py (114行变更) -- ✅ 良好遵守

| 函数/位置 | 状态 | 说明 |
|-----------|------|------|
| `_normalize_created_at()` (L:28) | ✅ | 兼容两种时间格式 |
| `_to_time_range()` (L:38) | ✅ | 本地日期正确转为 UTC 范围，使用 `astimezone(timezone.utc)` |
| `_is_in_time_range()` (L:46) | ✅ | 先归一化再字符串比较 |
| `_utc_created_at_to_local_date()` (L:126) | ✅ | UTC 转本地日期用于分组，正确 |
| `_aggregate_tokens_usage_by_date()` (L:155) | ✅ | 用 `_utc_created_at_to_local_date` 分组 |
| `get_usage_stats_7days()` (L:234) | ✅ | 本地日期范围正确通过 `_to_time_range` 转 UTC 后查询 |

**微小问题：**
- L:110 `_normalize_created_at` 返回值是 `.strftime()` 格式 `YYYY-MM-DD HH:MM:SS`，违反 §3.2 的 `.isoformat()` 规则。但此处是用于 SQL 字符串比较的内部中间格式，实际影响不大。

---

### 1.3 category_service.py (57行变更) -- ✅ 良好遵守

| 位置 | 变更 | 状态 |
|------|------|------|
| L:169-175 | 输入 `start_time`/`end_time` 统一归一化为 UTC aware | ✅ 符合 §3.3 |
| L:177 | `datetime.now()` → `datetime.now(timezone.utc)` | ✅ 符合 §3.1 |
| L:942, L:957, L:980, L:995 | `CURRENT_TIMESTAMP` → `get_utc_now_iso()` | ✅ 符合 §3.4，禁止 `CURRENT_TIMESTAMP` |
| L:1032, L:1065, L:1103, L:1136, L:1177, L:1211 | 同上 | ✅ |
| L:1507 测试代码 | `datetime.now()` → `datetime.now(timezone.utc)` | ✅ |

全部修改符合规则要求。`updated_at` 使用 `get_utc_now_iso()` 返回 `.isoformat()` 格式，同时满足 §3.2 和 §3.4。

---

### 1.4 schedule_service.py (38行变更) -- ✅ 良好遵守，重点审查通过

| 位置 | 变更 | 状态 |
|------|------|------|
| L:36 `_dreaming()` | `datetime.now()` → `get_local_today()` 计算"昨天" | ✅ §3.5/§3.6，基于本地时区 |
| L:206 `start()` | `AsyncIOScheduler()` → `AsyncIOScheduler(timezone=local_tz)` | ✅ 调度器整体使用本地时区 |
| L:210 `_add_system_jobs()` | `datetime.now()` → `datetime.now(local_tz)` | ✅ 用本地时间判断触发点 |
| L:222 `_add_cron_job()` | `CronTrigger.from_crontab(cron_expr)` → `CronTrigger.from_crontab(cron_expr, timezone=local_tz)` | ✅ **§3.6 关键要求** |
| L:335 `_add_interval_job()` | `IntervalTrigger(**interval_kwargs)` → `IntervalTrigger(**interval_kwargs, timezone=local_tz)` | ✅ APScheduler 3.11.2 支持 `timezone` 参数 |
| L:191, L:277, L:377 | `datetime.now().strftime()` → `get_local_today().isoformat()` | ✅ 状态记录使用本地日期 |
| L:76 | `_SYSTEM_CRON_JOB_TIME = "0 10 * * *"` | ✅ Cron 表达式写本地时间（10:00 本地） |

**CronTrigger `timezone` 验证 (Rules §3.6):**
```python
# L:222 — ✅ Cron 表达式写本地时间 "0 10 * * *"，timezone=local_tz
local_tz = pytz.timezone(get_user_timezone())
trigger = CronTrigger.from_crontab(cron_expr, timezone=local_tz)
```
这正是 §3.6 要求的模式：Cron 表达式写本地时间，timezone 参数设为用户本地时区。当用户切换时区后，`get_user_timezone()` 返回新的时区，定时任务会在新的本地 10:00 触发。

**TEST_MODE 处理：**
```python
# L:106-109 — TEST_MODE 下基于 UTC 时间生成 cron 表达式（与 CronTrigger 的 UTC 时区一致）
target_time = datetime.now(timezone.utc) + timedelta(minutes=TEST_CRON_AFTER_MINUTES)
cron_expr = f"{target_time.minute} {target_time.hour} * * *"
```
注释说明了 TEST_MODE 使用 UTC 的原因是当时未启用 `timezone=local_tz`，但现在 L:217 已启用。不过 TEST_MODE 仅用于开发测试，实际生产路径不受影响。**不构成 Bug**。

---

### 1.5 habit_service.py (35行变更) -- ✅ 良好遵守

| 位置 | 变更 | 状态 |
|------|------|------|
| L:104, L:155, L:190, L:226, L:360, L:416, L:433, L:500, L:530, L:591, L:657, L:700, L:705, L:792, L:846 | `date.today()` → `get_local_today()` | ✅ §3.5，日期字段使用本地时区 |
| L:225, L:360, L:433, L:463 | `datetime.now().isoformat()` → `get_utc_now_iso()` | ✅ §3.1，时间戳字段使用 UTC ISO |
| L:540 | `datetime.now().isoformat()` → `get_utc_now_iso()` | ✅ |
| L:846 `check_settlements()` | `date.today().isoformat()` → `get_local_today().isoformat()` | ✅ 到期判断基于本地日期 |

日期字段 (`finished_at`, `paused_at`, `end_date`, `start_date`) 与时间戳字段 (`created_at`, `updated_at`) 的时区处理正确区分。

---

### 1.6 goal_service.py (22行变更) -- ✅ 良好遵守

| 位置 | 变更 | 状态 |
|------|------|------|
| L:113-114 | `datetime.strptime(start_date, "%Y-%m-%d")` + `datetime.now()` → `.date()` + `get_local_today()` | ✅ 日期字段比较使用本地时区 |
| L:209-216 | `updated_at` 解析兼容旧格式 + 阈值比较使用 UTC | ✅ `datetime.now(timezone.utc)` |
| L:242 | `datetime.now().strftime()` → `get_utc_now_iso()` | ✅ 时间戳字段使用 UTC ISO |
| L:521 | `datetime.now().strftime("%Y-%m-%d")` → `get_local_today().isoformat()` | ✅ `finish_time` 是日期字段 |

---

## 2. 潜在 Bug

### 🔴 严重：report_service.py 报表查询时间范围未从本地时区转 UTC

**文件**: `lifeprism/server/services/report_service.py`
**影响行**: L:222, 242, 310-311, 335-336, 409-410, 438-439, 578-579, 792-793, 833-834, 899-900, 965-966, 1032-1033 (共 12 处)
**相关 provider 行**: `report_provider.py` L:699, 711, 773, 785; `lw_base_data_provider.py` L:762-766

**问题描述**：
`_calc_sunburst_data`、`_calc_daily_trend`、`_calc_weekly_trend`、`_calc_monthly_trend`、`_calc_heatmap_data`、`_calc_comparison_data` 这 6 个函数使用 `f"{local_date} 00:00:00"` 和 `f"{local_date} 23:59:59"` 构造时间范围字符串，直接作为 SQL `WHERE start_time >= ?` 的参数。但 `user_app_behavior_log.start_time` 已被 m009 迁移为 UTC ISO 8601 格式 `YYYY-MM-DDTHH:MM:SS+00:00`。

**复现步骤**（UTC+8 用户）：
1. 在本地时间 2026-07-12 凌晨 02:00 产生一条使用记录
2. DB 存储: `start_time = "2026-07-11T18:00:00+00:00"`
3. 查看 2026-07-12 日报
4. 查询条件: `start_time >= "2026-07-12 00:00:00"`
5. 字符串比较: `"2026-07-11..." < "2026-07-12..."` → **记录被排除，不在报表中**

**修复方向**：将 12 处 `f"{date} 00:00:00"` / `f"{date} 23:59:59"` 替换为 `_build_utc_time_range(date)` 调用（该辅助函数已实现但未被调用）。

---

### 🟡 中等：report_service.py 三个 UTC 辅助函数为死代码

**文件**: `lifeprism/server/services/report_service.py`
**行号**: L:78-100 (`_utc_timestamp_to_local_date`), L:103-127 (`_add_local_date_column`), L:131-157 (`_build_utc_time_range`)

三个函数定义正确但**不存在任何调用点**。代码意图清晰，但未完成接线。函数实现本身需修正 `.strftime()` → `.isoformat()`（见下一条）。

---

### 🟡 中等：`_build_utc_time_range` 使用 `.strftime()` 违反 §3.2

**文件**: `lifeprism/server/services/report_service.py` L:156-157
```python
# ❌ 违反 §3.2：时间戳序列化必须使用 .isoformat()
return utc_start.strftime("%Y-%m-%d %H:%M:%S"), utc_end.strftime("%Y-%m-%d %H:%M:%S")
```

规则 §3.2 明确要求"所有时间戳序列化必须使用 `.isoformat()`"。`time_utils.py` 中已有的 `build_utc_time_range()` 返回 ISO 格式，此处应与之保持一致。若数据库查询需要传统格式，应在 provider 层做转换，而非在 service 层产出非标准格式。

虽然当前此函数是死代码，但修复后接入时必须同步修正。

---

### 🟡 中等：`usage_service._normalize_created_at` 使用 `.strftime()` 格式

**文件**: `lifeprism/server/services/usage_service.py` L:44
```python
return value[:19]  # 返回 "YYYY-MM-DD HH:MM:SS" 格式
```

`_normalize_created_at` 的输出是 `YYYY-MM-DD HH:MM:SS` 格式（截断到前 19 字符），违反 §3.2。虽然这是 SQL 查询的内部中间格式，但根据规则要求，时间戳序列化应统一为 ISO 格式。

---

## 3. 功能缺失风险

### 3.1 报表数据准确性受损（严重）

详见 Bug #1。日报/周报/月报的旭日图、趋势图、热力图、环比对比数据在跨时区边界（每天前 N 小时，N = UTC 偏移量）会丢失或错位数据。对于 UTC+8 用户，每天前 8 小时的记录会缺失。**所有报表功能均受影响**。

### 3.2 功能未受影响的部分

| 模块 | 状态 | 说明 |
|------|------|------|
| 定时任务触发 | ✅ 正常 | schedule_service 正确配置了 CronTrigger timezone |
| Token 使用统计 | ✅ 正常 | usage_service 正确转换了时间范围 |
| 分类统计 | ✅ 正常 | category_service 正确处理了时间参数 |
| 习惯打卡/挑战 | ✅ 正常 | habit_service 正确区分了日期字段和时间戳字段 |
| 目标时间投入 | ✅ 正常 | goal_service 正确处理了日期字段和时间戳字段 |
| 报告状态判断 | ✅ 正常 | "今天是否晚于报告日期"使用本地时区 |

---

## 4. 安全隐患

### 🟢 无严重安全隐患

- ✅ 所有时区配置通过 `get_user_timezone()` 动态获取，未发现硬编码时区字符串用于业务逻辑
- ✅ schedule_service 的 Cron 表达式为静态配置（`"0 10 * * *"`），不受外部输入影响
- ✅ `_build_utc_time_range` 虽使用 `.strftime()`，但输入日期经过 `datetime.strptime` 验证，无注入风险
- ⚠️ `habit_service.check_settlements()` (L:846) 将 `get_local_today().isoformat()` 传入 `habit_repository.get_expired_in_progress_challenges(today)`，Repository 层使用 SQL `WHERE end_date < ?`。`end_date` 是日期字段（`YYYY-MM-DD`，本地时区），`today` 也是本地时区日期。这种比较是正确的，因为两个值在同一时区。无风险。

---

## 总结

| 维度 | 评级 | 关键问题 |
|------|------|---------|
| 规则遵守 | ⚠️ 部分 | schedule_service、habit_service、goal_service 完全遵守；report_service 有未完成的接线 |
| 潜在 Bug | 🔴 1 严重 | 报表查询时间范围未从本地时区转 UTC，导致数据错位/缺失 |
| 功能缺失 | 🔴 高风险 | 所有报表视觉化（旭日图、趋势图、热力图、环比）受影响 |
| 安全隐患 | 🟢 低 | 无外部注入路径，时区来源可信 |

**建议修复优先级**：
1. 🔴 **P0**: 修复 `report_service.py` 12 处时间范围构造，接入 `_build_utc_time_range`（需同步修正其 `.strftime()` 为 `.isoformat()` 或与 `time_utils.build_utc_time_range()` 统一）
2. 🟡 **P1**: 将 `usage_service._normalize_created_at` 的输出统一为 ISO 格式（需同步修改 `_to_time_range` 和 `_is_in_time_range` 的比较逻辑）
3. 🟢 **P2**: 删除 report_service.py 中未使用的 `_add_local_date_column` 和 `_utc_timestamp_to_local_date`（或完成接线）
