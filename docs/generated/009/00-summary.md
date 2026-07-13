# UTC 时区迁移 代码审查综合报告

## 审查概况

- **审查日期**: 2026-07-12
- **审查标准**: `docs/coding-rules/time-handling-rules.md`（版本 3.0）
- **审查范围**: 10 个 Agent，覆盖 ~85 个源文件 + 28 个测试文件
- **审查维度**: 规则遵守 / 潜在 Bug / 功能缺失 / 安全隐患

## 审查结果总览

| 严重度 | 数量 | 需在合入前修复 |
|--------|------|--------------|
| 🔴 严重 Bug | 2 | ✅ 必须修复 |
| 🟡 中等问题 | 7 | 建议修复 |
| 🟢 轻微问题 | 15 | 择机修复 |

## 🔴 严重 Bug（必须修复）

### BUG-1: report_service.py — 报表查询时间范围未从本地时区转 UTC

- **文件**: `lifeprism/server/services/report_service.py`
- **影响**: 6 个查询函数共 **12 处**仍使用 `f"{date} 00:00:00"` 本地时间字符串直接查询数据库
- **根因**: `_build_utc_time_range()`、`_utc_timestamp_to_local_date()`、`_add_local_date_column()` 三个 UTC 转换辅助函数已正确定义，但**从未被调用**（死代码）
- **后果**: 数据库 `user_app_behavior_log.start_time` 已迁移为 UTC ISO 格式（`2026-07-11T16:00:00+00:00`），本地时间字符串 `"2026-07-12 00:00:00"` 与之字符串比较会漏掉 UTC+8 用户每天前 8 小时的记录
- **影响范围**: 旭日图、日报趋势、周报趋势、月报趋势、热力图、环比对比 — 全部受影响
- **受影响的函数和行号**:
  - `_calc_sunburst_data()` L578-579
  - `_calc_daily_trend()` L792-793, L833-834
  - `_calc_weekly_trend()` L919-920, L957-958
  - `_calc_monthly_trend()` L1017-1018, L1051-1052
  - `_calc_heatmap_data()` L1117-1118
  - `_calc_comparison_data()` L1193-1194, L1229-1230
- **修复方案**: 将 12 处 `f"{date} 00:00:00"` 替换为 `_build_utc_time_range(date)` 调用，并将 `_build_utc_time_range` 内部的 `.strftime()` 改为 `.isoformat()`（见 BUG-5）

### BUG-2: lifeprismsystem.py — todolist 日期范围用 UTC 日期匹配本地日期字段

- **文件**: `lifeprism/llm/agent/tools/lifeprismsystem.py` L371
- **影响**: `start_time[:10]` 从已转为 UTC ISO 的字符串中提取 UTC 日期，但 `todo_list.date` 是本地日期字段
- **后果**: UTC+8 用户在凌晨（00:00-07:59）查询待办事项时，会遗漏当天的待办（UTC 日期还在"昨天"）
- **修复方案**: 在切片前先转回本地日期，或使用 `get_local_today()` 代替 UTC 日期字符串切片

---

## 🟡 中等问题（建议修复）

### BUG-3: chatbot_service.py — 会话名称显示 UTC 时间

- **文件**: `lifeprism/server/services/chatbot_service.py` L123
- **问题**: `datetime.now(timezone.utc).strftime('%m-%d %H:%M')` 生成会话名称，用户看到 UTC 时间
- **后果**: UTC+8 用户 10:30 创建会话 → 显示 `新会话 02-12 02:30`
- **违反**: Rules §3.1（对外显示应用本地时间）
- **修复**: 使用 `get_local_now().strftime('%m-%d %H:%M')` 或等效方法

### BUG-4: m009 迁移脚本 — 微秒精度丢失

- **文件**: `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py`
- **问题**: 迁移用 `strftime('%Y-%m-%dT%H:%M:%S', ...) || '+00:00'`，丢失微秒 `.ffffff`
- **后果**: 历史数据格式为 `2026-07-11T16:00:00+00:00`（无微秒），新数据格式为 `2026-07-11T16:00:00.123456+00:00`（有微秒）。违反 Rules §3.2 统一格式要求，可能在 LWW 同步时字符串比较出现边界问题
- **修复**: 改为 `strftime('%Y-%m-%dT%H:%M:%f', ...) || '+00:00'`

### BUG-5: report_service.py — _build_utc_time_range 使用 .strftime()

- **文件**: `lifeprism/server/services/report_service.py` L131
- **问题**: 已定义的 `_build_utc_time_range()` 内部使用 `.strftime()` 而非 `.isoformat()`
- **违反**: Rules §3.2
- **修复**: 将 `.strftime()` 改为 `.isoformat()`，或直接复用 `lifeprism/utils/time_utils.py` 中的 `build_utc_time_range()`

### BUG-6: sync_service.py — 仍使用 .strftime() 序列化时间戳

- **文件**: `lifeprism/server/services/sync_service.py` L142, L147
- **问题**: `created_at.strftime("%Y-%m-%d %H:%M:%S")` 序列化时间戳
- **违反**: Rules §3.2
- **后果**: 下游有 tzinfo 容错逻辑暂时兜底，但流程脆弱
- **修复**: 改为 `.isoformat()`

### BUG-7: m009 docstring — 与代码不一致

- **文件**: `lifeprism/repository/migrations/scripts/m009_migrate_history_to_utc.py`
- **问题**: docstring 声称 `todo_list.created_at` 被排除（"已经是 UTC"），但 commit `27a2e04` 已将其加入 `_MIGRATION_FIELDS`
- **后果**: 误导后续维护者
- **修复**: 更新 docstring

### BUG-8: time_utils.py — local_to_utc_iso() DST 间隙异常

- **文件**: `lifeprism/utils/time_utils.py`
- **问题**: DST 过渡间隙（如 `02:30` 在 spring-forward 时不存在），`localize()` 会抛异常
- **影响**: 仅影响非 Asia/Shanghai 用户（中国无 DST），但需为国际化预留
- **修复**: 添加 `is_dst=None` 策略或 try/except 兜底

### BUG-9: DateGrid.tsx — YYYY-MM-DD 字符串被解析为 UTC

- **文件**: `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx` L85
- **问题**: `new Date(date)` 将 `YYYY-MM-DD` 字符串解析为 UTC（ECMAScript 规范行为）
- **后果**: UTC-5 等西向时区用户可能看到错误日期（预存问题，非本次引入）
- **修复**: 使用本地时间解析方法

---

## 🟢 轻微问题（择机修复）

| ID | Agent | 文件 | 问题 |
|----|-------|------|------|
| L1 | B1 | `time_utils.py` | `get_user_timezone()` 异常捕获过于宽泛（catch-all Exception）且静默回退 |
| L2 | B1 | `time_utils.py` | `build_local_datetime()` 用 strptime 做校验丢弃结果，效率低 |
| L3 | B2 | `database_manager.py` | `need_update_at` 条件硬编码表名 `"single_purpose_map_cache"` |
| L4 | B3 | `map_cache_providers.py` | `batch_insert` 盲追加 `created_at`/`updated_at` 列，与调用方约定隐式依赖 |
| L5 | B5 | `activity_stats_builder.py` | 4 个辅助函数定义后无调用方，与 report_service.py 存在代码重复 |
| L6 | B6 | `lifeprismsystem.py` | `_parse_iso_time` 与 `time_utils.parse_iso_to_aware` 功能重复 |
| L7 | B6 | `lifeprismsystem.py` | `_utc_to_local` 异常兜底静默返回 UTC ISO，未打 WARNING 日志 |
| L8 | B6 | `session_query.py` | 时间字符串切片硬编码位置，较为脆性 |
| L9 | B7 | `llm_call_logger.py` L334 | 日志按 UTC 日期分桶，UTC+8 用户 08:00 切换日志文件 |
| L10 | B7 | `session/manager.py` L24 | Session 名称时间戳使用 UTC |
| L11 | F1 | `dateUtils.ts` L48 | `parseISOString` 未校验输入格式，非法字符串返回 `Invalid Date` |
| L12 | F1 | `dateUtils.ts` L88 | `getUserTimezone` fallback 硬编码 `'Asia/Shanghai'` |
| L13 | F1 | `reportCacheService.ts` L248 | `isToday` 混用 UTC 解析和本地日期比较 |
| L14 | F1 | `dateUtils.test.ts` L60 | 测试用例使用相同的输入和操作做期望值（恒为真） |
| L15 | F3 | `SettingsApp.tsx` | `TIMEZONE_OPTIONS` 仅 15 个时区，建议扩展或动态获取 |

---

## 各 Agent 审查质量概览

| Agent | 范围 | 文件数 | 规则遵守 | 严重发现 | 评级 |
|-------|------|--------|---------|---------|------|
| B1 | 时间工具+配置 | 5 | ✅ 100% | 0 | ⭐⭐⭐ |
| B2 | Repository 基础+迁移 | 7 | ✅ 良好 | 0 | ⭐⭐⭐ |
| B3 | Repository Providers | 12 | ✅ 优秀 | 0 | ⭐⭐⭐ |
| **B4** | **Server Services 核心** | 6 | ⚠️ 部分 | **1 严重** | ⭐ |
| B5 | 其他 Services+Providers | 16 | ⚠️ 良好 | 0 | ⭐⭐ |
| **B6** | **LLM Tools** | 3 | ✅ 良好 | **1 严重** | ⭐ |
| B7 | LLM Infra+Monitor | 16 | ✅ 优秀 | 0 | ⭐⭐⭐ |
| F1 | Frontend Core | 6 | ✅ 优秀 | 0 | ⭐⭐⭐ |
| F2 | Frontend Goals | 7 | ✅ 优秀 | 0 | ⭐⭐⭐ |
| F3 | Frontend Lifewatch+Settings | 7 | ✅ 优秀 | 0 | ⭐⭐⭐ |

---

## 结论

**整体评价：代码质量良好，规则遵守率高，但存在 2 个必须修复的严重 Bug。**

1. **report_service.py**（B4）：12 处查询仍用本地时间字符串查 UTC 数据库，旭日图/趋势图/热力图/环比对比全部受影响。修复方案明确（接线已定义的辅助函数）。
2. **lifeprismsystem.py**（B6）：todolist 日期范围比较语义错误（UTC 日期 vs 本地日期字段）。修复方案明确（切片前转回本地日期）。

建议在修复 2 个严重 Bug + 5 个中等问题后合入 main 分支。15 个轻微问题不阻塞合入，可后续迭代修复。

---

## 审查报告索引

| 文件 | Agent | 说明 |
|------|-------|------|
| [b1-time-utils-config.md](b1-time-utils-config.md) | B1 | 时间工具 + 配置基础设施 |
| [b2-repo-base-migration.md](b2-repo-base-migration.md) | B2 | Repository 基础层 + 迁移脚本 |
| [b3-repo-providers.md](b3-repo-providers.md) | B3 | Repository Providers 全部 |
| [b4-server-services-core.md](b4-server-services-core.md) | B4 | Server Services 核心（⚠️ 含严重 Bug） |
| [b5-other-services-providers.md](b5-other-services-providers.md) | B5 | Server Services 其他 + Providers + API |
| [b6-llm-tools.md](b6-llm-tools.md) | B6 | LLM Tools 核心（⚠️ 含严重 Bug） |
| [b7-llm-infra-monitor.md](b7-llm-infra-monitor.md) | B7 | LLM Infra + Monitor + Processors |
| [f1-frontend-core.md](f1-frontend-core.md) | F1 | Frontend Core 工具函数 |
| [f2-frontend-goals.md](f2-frontend-goals.md) | F2 | Frontend Goals App |
| [f3-lifewatch-settings.md](f3-lifewatch-settings.md) | F3 | Frontend Lifewatch + Settings |
