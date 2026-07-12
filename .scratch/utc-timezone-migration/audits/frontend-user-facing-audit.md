# 前端面向用户时间数据审查报告

> 审查目标：核对前端所有面向用户展示的时间数据是否正确将后端返回的 UTC ISO 8601（如 `2026-07-11T16:29:54.123Z`）转换为本地时区显示。
> 审查范围：`frontend/` 目录下所有 `.tsx` / `.ts` 文件（不含 `node_modules`）。
> 审查方式：只读审查，未修改任何代码。

---

## 1. 时间显示工具审查

### 1.1 dateUtils.ts 函数清单

文件位置：`frontend/core/utils/dateUtils.ts`

该文件是前端时间转换的 SSOT（单一事实来源），核心原则已写入注释：
> 前端所有 Date → 日期字符串 的转换必须使用本地时区方法（getFullYear / getMonth / getDate），禁止使用 toISOString()（UTC）。

| 函数名 | 输入格式 | 输出格式 | 时区处理 | 是否正确 | 说明 |
|--------|----------|----------|----------|----------|------|
| `toLocalDateString(date: Date \| string)` | Date 对象 或 ISO 字符串 | `YYYY-MM-DD`（本地） | 使用 `getFullYear/getMonth/getDate` 本地方法 | ✅ 正确 | 推荐用于所有"只显示日期"场景 |
| `toLocalDateTimeString(date: Date \| string)` | Date 对象 或 ISO 字符串 | `YYYY-MM-DD HH:MM`（本地） | 使用本地方法 + 补零 | ✅ 正确 | 推荐用于"日期+时间"显示 |
| `parseISOString(iso: string)` | UTC ISO 8601 字符串 | Date 对象 | `new Date(iso)` 浏览器自动按本地时区解析 | ✅ 正确 | 统一入口，避免各处自行 `new Date()` |
| `toISOStringUTC(date: Date)` | Date 对象 | UTC ISO 8601 字符串 | `date.toISOString()` | ✅ 正确 | **仅用于向后端提交数据**，不用于显示 |
| `getUserTimezone()` | 无 | IANA 时区字符串（如 `Asia/Shanghai`） | 读取 localStorage `lifeprism_timezone`，fallback `Asia/Shanghai` | ✅ 正确 | **仅供后端 AI 工具使用**；前端显示仍使用浏览器本地时区 |
| `setUserTimezone(tz: string)` | IANA 时区字符串 | 无 | 写入 localStorage | ✅ 正确 | 配合 `getUserTimezone` 使用 |

**关键观察**：
- dateUtils.ts 提供的转换函数均已正确使用本地时区方法，是推荐的统一入口。
- `getUserTimezone()` 仅用于后端 AI 工具的时区上下文，前端显示不依赖该值，而是依赖浏览器本地时区（通过 `new Date()` + 本地方法）。
- 文件已明确禁止使用 `toISOString().split('T')[0]` 这种返回 UTC 日期的反模式。

### 1.2 其他时间处理方式

除 dateUtils.ts 外，前端代码中存在以下几类时间处理方式：

| 处理方式 | 说明 | 是否安全 |
|----------|------|----------|
| `new Date(isoString)` + `toLocaleString('zh-CN')` / `toLocaleDateString` / `toLocaleTimeString` | 浏览器原生 Intl API，自动按本地时区格式化 | ✅ 安全 |
| `new Date(isoString)` + `getFullYear()/getMonth()/getDate()/getHours()/getMinutes()` | 显式使用本地方法 | ✅ 安全 |
| `date-fns` 的 `format(d, 'yyyy-MM-dd')` | 对 Date 对象操作，时区无关 | ✅ 安全（前提是 `d` 已是正确的 Date 对象） |
| `dateStr.split('T')[0]` 直接作用于后端 UTC ISO 字符串 | 取 UTC 日期，未做时区转换 | ❌ 有 Bug（UTC+ 时区可能差一天） |
| `dateStr.replace('T', ' ').slice(0, 16)` 直接作用于后端 UTC ISO 字符串 | 显示 UTC 时间，未做时区转换 | ❌ 有 Bug |
| `date.toISOString().split('T')[0]` | 返回 UTC 日期，非本地日期 | ❌ 有 Bug（午夜差一天） |
| `dateStr.split(' ')[1]?.slice(0, 5)` | 假定空格分隔的本地时间格式 | ⚠️ 取决于后端是否返回本地时间（当前后端返回 UTC，有 Bug） |

---

## 2. 各模块时间显示位置

### 2.1 习惯模块（habits）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/habits/components/views/overview/Heatmap.tsx` | — | 日期键 | `date-fns format(d, 'yyyy-MM-dd')` 对 Date 对象格式化 | 本地（Date 对象已本地化） | ✅ 正确 |
| `apps/habits/components/dialogs/HabitHistoryDialog.tsx` | — | `dateStr` | `new Date(dateStr)` + `getFullYear/getMonth/getDate` | 本地 | ✅ 正确 |

### 2.2 目标模块（goals）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/goals/components/views/CalendarView/components/DateGrid.tsx` | — | 日期键 | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |
| `apps/goals/components/views/DailyTaskView/DailyTaskView.tsx` | — | 当前日期 | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |
| `apps/goals/components/views/DailyTaskView/components/DailyTaskHeader.tsx` | — | `selectedDate` | `selectedDate.getMonth()/getDate()` 直接使用 | 本地（Date 对象本地方法） | ✅ 正确 |
| `apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx` | — | 日期 | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |
| `apps/goals/apis/goal.ts` | 58-65 | `dateStr` (YYYY-MM-DD) | `formatDateForDisplay` 纯字符串切分为 `MM.DD` | 不涉及（输入已是本地日期字符串） | ✅ 正确 |

### 2.3 日记模块（diary / mindspace/journal）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/mindspace/components/journal/journal.tsx` | — | 日期 | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |

### 2.4 心情模块（mood）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/mindspace/components/mood/EmotionRecord.tsx` | — | `entry.timestamp` | `new Date(entry.timestamp).toLocaleDateString` / `toLocaleTimeString('zh-CN')` | 本地（Intl API） | ✅ 正确 |
| `apps/mindspace/components/mood/DateSelect.tsx` | — | 选中日期 | 本地 YYYY-MM-DD 构造 | 本地 | ✅ 正确 |

### 2.5 报告模块（reports）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/lifewatch/pages/reports/components/DailyReviewTab.tsx` | — | 日期 | `toLocalDateString` + `toLocaleDateString('zh-CN')` | 本地（dateUtils + Intl） | ✅ 正确 |
| `apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx` | — | 日期 | `toLocalDateString` + `toLocaleDateString('zh-CN')` | 本地（dateUtils + Intl） | ✅ 正确 |
| `apps/lifewatch/pages/reports/components/MonthlyReviewTab.tsx` | — | 日期 | 本地 YYYY-MM-DD 拼装 | 本地 | ✅ 正确 |
| `apps/lifewatch/pages/reports/components/CalendarHeatmap.tsx` | — | 日期键 | 纯字符串比较 YYYY-MM-DD | 不涉及（已是日期键） | ✅ 正确 |
| `core/services/reportCacheService.ts` | — | `getAdjacentDates` | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |

### 2.6 时间线模块（timeline）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/lifewatch/pages/timeline/Timeline.tsx` (EventTooltip) | — | 事件时间 | `new Date()` + `toTimeString()` | 本地 | ✅ 正确 |
| `apps/lifewatch/pages/timeline/Timeline.tsx` | 1436-1438 | `selectedEvent.start_time` / `end_time` | `selectedEvent.start_time.split(' ')[1]?.slice(0, 5)` | ❌ 假定空格分隔的本地时间字符串，未做 UTC 转换 | ❌ 有 Bug |
| `apps/lifewatch/pages/timeline/components/CustomBlockPopover.tsx` | 46-50 | `timeStr` | `timeStr.includes('T') ? timeStr.split('T')[1] : timeStr.split(' ')[1]` + `slice(0, 5)` | ❌ 直接取 UTC ISO 中的时间部分，未做时区转换 | ❌ 有 Bug |
| `apps/lifewatch/pages/timeline/components/CustomBlockLayer.tsx` | 41-45 | `timeStr` | 同上 `timeToHour` 模式 | ❌ 直接取 UTC 时间部分 | ❌ 有 Bug |
| `apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx` | 26-32 | `timeStr` | 同上 `timeToHour` 模式 | ❌ 直接取 UTC 时间部分 | ❌ 有 Bug |
| `apps/lifewatch/pages/timeline/components/CustomBlockLabel.tsx` | 41-45 | `timeStr` | 同上 `timeToHour` 模式 | ❌ 直接取 UTC 时间部分 | ❌ 有 Bug |
| `apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx` | 42-57 | `timeStr` | `formatTime` / `formatDate` 均直接 `split('T')` | ❌ 直接取 UTC 日期/时间，未做时区转换 | ❌ 有 Bug |

### 2.7 待办模块（todos）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx` | — | 日期 | `toLocalDateString` + `toLocaleDateString('zh-CN')` | 本地（dateUtils + Intl） | ✅ 正确 |

### 2.8 分类模块（categories）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/lifewatch/pages/category/components/DataReviewTab.tsx` | — | `timeStr` | `formatTime` = `new Date(timeStr)` + `getHours()/getMinutes()` | 本地（Date 本地方法） | ✅ 正确 |

### 2.9 设置模块（settings）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/settings/syncUtils.ts` | — | `timestamp` | `formatRelativeTime` = `new Date(timestamp).getTime()` 相对计算 | 本地（Date 对象） | ✅ 正确 |

### 2.10 LifeWatch 主模块（lifewatch）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/lifewatch/pages/usage/UsagePage.tsx` | — | 日期 | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |
| `apps/lifewatch/pages/home/components/ActivitySummaryHeader.tsx` | — | 日期 | 自定义 `parseLocalDate` / `formatDateToYYYYMMDD` 使用本地方法 | 本地 | ✅ 正确 |
| `dialogs/record-activity/RecordActivityDialog.tsx` | — | `isoString` | `new Date(isoString).toLocaleTimeString('zh-CN')` | 本地（Intl） | ✅ 正确 |

### 2.11 自定义记录模块（custom-records）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `apps/custom-records/components/TypeListView.tsx` | 117 | `type.created_at` | `type.created_at.split('T')[0]` | ❌ 直接取 UTC 日期，未做时区转换 | ❌ 有 Bug |
| `apps/custom-records/components/TypeDetailView.tsx` | 40 | `dateStr` | `getDateKey` = `dateStr.split('T')[0].split(' ')[0]` | ❌ 直接取 UTC 日期 | ❌ 有 Bug |
| `apps/custom-records/components/TypeDetailView.tsx` | 429 | `entry.created_at` | `entry.created_at.replace('T', ' ').slice(0, 16)` | ❌ 直接显示 UTC 日期+时间 | ❌ 有 Bug |
| `apps/custom-records/components/EntryCard.tsx` | 28-32 | `dateStr` | `dateStr.replace('T', ' ').slice(0, 16)` | ❌ 直接显示 UTC 日期+时间 | ❌ 有 Bug |

### 2.12 其他模块（chatbot / floating / commitment）

| 文件 | 行号 | 字段 | 格式化方法 | 时区处理 | 状态 |
|------|------|------|-----------|----------|------|
| `core/components/Chatbot/components/ChatPanel.tsx` | — | `dateStr` | `formatTime` = `new Date(dateStr)` 相对 `now` | 本地（Date 对象） | ✅ 正确 |
| `apps/mindspace/components/commitment/commitment.tsx` | 163-166 | `iso` | `formatDate` = `new Date(iso)` + `getMonth()/getDate()` | 本地（Date 本地方法） | ✅ 正确 |
| `floating/what-am-i-doing/utils/formatTime.ts` | — | 日期 | `toLocalDateString` | 本地（dateUtils） | ✅ 正确 |
| `floating/what-am-i-doing/WhatAmIDoingFloat.tsx` | — | 今日 | `getTodayStr()` 来自 formatTime.ts | 本地（dateUtils） | ✅ 正确 |

### 2.13 测试/示例文件（不面向用户，仅供参考）

| 文件 | 行号 | 字段 | 格式化方法 | 状态 |
|------|------|------|-----------|------|
| `my-ui-kit/test/src/test_component/DragDropTestPage.tsx` | 125, 132, 263-267, 466, 734 | `date` | `date.toISOString().split('T')[0]` | ⚠️ 测试文件，不面向用户，但使用了反模式 |
| `my-ui-kit/ui-kit/dragDrop/examples/TaskPoolCalendarExample.tsx` | 246 | `date` | `date.toISOString().split('T')[0]` | ⚠️ 示例文件，不面向用户，但使用了反模式 |

---

## 3. 时间筛选审查

### 3.1 时间筛选组件清单

| 文件 | 行号 | 筛选字段 | 提交格式 | 时区处理 | 状态 |
|------|------|----------|----------|----------|------|
| `apps/lifewatch/pages/timeline/Timeline.tsx` | 713-714 | `start_time` / `end_time` | `${currentDate} 00:00:00` / `${currentDate} 23:59:59`（本地 YYYY-MM-DD 拼接） | ⚠️ 提交本地日期时间的字符串字面量，**未转换为 UTC ISO 8601**。后端若按 UTC 解析会有时区偏移。 | ⚠️ 需确认后端处理 |
| `apps/lifewatch/pages/category/components/DataReviewTab.tsx` | 87-88 | `start` / `end` | `${dateRange.start} 00:00:00` / `${dateRange.end} 23:59:59` | ⚠️ 同上，提交本地字面量 | ⚠️ 需确认后端处理 |
| `apps/custom-records/components/TypeDetailView.tsx` | 68-73 | `start_date` / `end_date` | `YYYY-MM-DD` 字符串 | ✅ 业务日期（纯日期，非时间戳），后端按日期匹配 | ✅ 正确 |
| `apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx` | — | `date` / `time` | `YYYY-MM-DD` + `HH:MM` 分离提交 | ✅ 业务日期 + 业务时间 | ✅ 正确 |
| `apps/goals/components/views/CalendarView/components/DateGrid.tsx` | — | 日期键 | `toLocalDateString` 生成的 YYYY-MM-DD | ✅ 本地日期键 | ✅ 正确 |
| `apps/mindspace/components/mood/DateSelect.tsx` | — | 选中日期 | 本地 YYYY-MM-DD 构造 | ✅ 本地日期 | ✅ 正确 |

### 3.2 时间筛选审查说明

**关键风险**：`Timeline.tsx` 与 `DataReviewTab.tsx` 均采用"本地 YYYY-MM-DD + 00:00:00 / 23:59:59"的字面量拼接，未通过 `toISOStringUTC()` 转换为 UTC ISO 8601。

- 若后端将这些字符串按 UTC 解析（例如 `datetime.fromisoformat`），则查询范围会与用户期望的本地日期范围产生偏移：
  - `Asia/Shanghai`（UTC+8）用户查询 `2026-07-12 00:00:00`，后端按 UTC 解析后实际覆盖的是本地 `2026-07-12 08:00:00` 开始的范围，导致当天凌晨 0-8 点的数据被漏查。
- 建议统一改为：用本地 Date 对象构造起止时刻，再通过 `toISOStringUTC()` 转换为 UTC ISO 8601 提交。
- 但需与后端确认：若后端已将这些字段当作"本地时间字面量"处理（不进行时区转换），则当前实现可工作；不过这违反"全链路 UTC ISO 8601"的约束。

---

## 4. 问题汇总

### P0 - 严重（直接显示 UTC 时间，用户可见错误）

| 优先级 | 文件 | 行号 | 问题描述 | 修复建议 |
|--------|------|------|----------|----------|
| P0 | `apps/custom-records/components/TypeListView.tsx` | 117 | `type.created_at.split('T')[0]` 直接取 UTC 日期，UTC+ 时区用户在 0-8 点看到的日期比实际少一天 | 改用 `toLocalDateString(type.created_at)` |
| P0 | `apps/custom-records/components/TypeDetailView.tsx` | 40 | `getDateKey` = `dateStr.split('T')[0].split(' ')[0]` 直接取 UTC 日期用于分组，导致按日期分组错位 | 改用 `toLocalDateString(dateStr)` 作为分组键 |
| P0 | `apps/custom-records/components/TypeDetailView.tsx` | 429 | `entry.created_at.replace('T', ' ').slice(0, 16)` 直接显示 UTC 日期+时间，时区偏移全部错位 | 改用 `toLocalDateTimeString(entry.created_at)` |
| P0 | `apps/custom-records/components/EntryCard.tsx` | 28-32 | `dateStr.replace('T', ' ').slice(0, 16)` 直接显示 UTC 日期+时间 | 改用 `toLocalDateTimeString(dateStr)` |
| P0 | `apps/lifewatch/pages/timeline/Timeline.tsx` | 1436-1438 | `selectedEvent.start_time.split(' ')[1]?.slice(0, 5)` 假定空格分隔的本地时间，后端返回 UTC ISO 时取到的是 UTC 时间 | 先 `new Date(selectedEvent.start_time)` 再用 `toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })` 或 `toLocalDateTimeString` |
| P0 | `apps/lifewatch/pages/timeline/components/CustomBlockPopover.tsx` | 46-50 | `extractTime` 直接 `split('T')[1]` 取 UTC 时间部分 | 改用 `new Date(timeStr)` + `getHours()/getMinutes()` 或 `toLocalDateTimeString` |
| P0 | `apps/lifewatch/pages/timeline/components/CustomBlockLayer.tsx` | 41-45 | `timeToHour` 直接取 UTC 时间部分用于定位时间轴位置 | 同上 |
| P0 | `apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx` | 26-32 | 同上 `timeToHour` 模式 | 同上 |
| P0 | `apps/lifewatch/pages/timeline/components/CustomBlockLabel.tsx` | 41-45 | 同上 `timeToHour` 模式 | 同上 |
| P0 | `apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx` | 42-57 | `formatTime` / `formatDate` 均 `split('T')` 直接取 UTC 部分 | 改用 dateUtils 的 `toLocalDateString` / `toLocalDateTimeString` |

### P1 - 中等（时间筛选提交格式不一致）

| 优先级 | 文件 | 行号 | 问题描述 | 修复建议 |
|--------|------|------|----------|----------|
| P1 | `apps/lifewatch/pages/timeline/Timeline.tsx` | 713-714 | 提交 `${currentDate} 00:00:00` / `23:59:59` 字面量，未转 UTC ISO | 改为构造本地 Date 后用 `toISOStringUTC()` 提交，或与后端确认按本地字面量解析 |
| P1 | `apps/lifewatch/pages/category/components/DataReviewTab.tsx` | 87-88 | 同上模式 | 同上 |

### P2 - 低（测试/示例文件使用了反模式）

| 优先级 | 文件 | 行号 | 问题描述 | 修复建议 |
|--------|------|------|----------|----------|
| P2 | `my-ui-kit/test/src/test_component/DragDropTestPage.tsx` | 125, 132, 263-267, 466, 734 | `date.toISOString().split('T')[0]` 取 UTC 日期 | 测试文件不面向用户，但建议改为 `toLocalDateString(date)` 以避免误导 |
| P2 | `my-ui-kit/ui-kit/dragDrop/examples/TaskPoolCalendarExample.tsx` | 246 | 同上 | 同上 |

---

## 5. 总结

### 5.1 审查统计

| 指标 | 数量 |
|------|------|
| 审查文件数 | 约 49 个 |
| 时间显示位置数 | 约 40+ 处 |
| 正确处理的位置 | 约 27 处 |
| 存在 Bug 的位置（P0） | 约 10 处 |
| 时间筛选需确认（P1） | 2 处 |
| 测试/示例反模式（P2） | 2 个文件 |

### 5.2 核心问题

1. **dateUtils.ts 工具齐全但未强制使用**：项目已提供 `toLocalDateString` / `toLocalDateTimeString` / `parseISOString` 等正确工具，且明确禁止 `toISOString().split('T')[0]`，但仍有大量组件直接对 UTC ISO 字符串做 `split('T')` / `replace('T', ' ')` 操作，绕开了 SSOT。

2. **问题集中在两个模块**：
   - **custom-records 模块**：`TypeListView.tsx` / `TypeDetailView.tsx` / `EntryCard.tsx` 全部使用字符串切分，是重灾区。
   - **timeline 模块**：`CustomBlockPopover` / `CustomBlockLayer` / `BehaviorBlockLayer` / `CustomBlockLabel` / `BehaviorDetailPanel` 以及 `Timeline.tsx` 第 1436-1438 行，均存在 `split('T')[1]` 或 `split(' ')[1]` 直接取时间的反模式。这些组件用于在时间轴上定位事件位置，时区错误会导致事件块出现在错误的时刻。

3. **时间筛选提交格式不统一**：`Timeline.tsx` 与 `DataReviewTab.tsx` 提交本地字面量时间字符串而非 UTC ISO 8601，与项目"全链路 UTC ISO 8601"约束不一致，需与后端确认解析逻辑。

4. **正确实践的典型代表**：
   - 报告模块（DailyReviewTab / WeeklyReviewTab / MonthlyReviewTab）全面采用 dateUtils + Intl API。
   - 目标模块（DateGrid / DailyTaskView / JournalEntryModal）统一使用 `toLocalDateString`。
   - 心情/日记模块使用 `new Date()` + `toLocaleString('zh-CN')`。

### 5.3 修复优先级建议

1. **优先修复 custom-records 模块**（3 个文件，影响记录创建时间显示）。
2. **其次修复 timeline 模块**（6 个文件，影响时间轴事件定位，用户感知最强）。
3. **统一时间筛选提交格式**（2 处，需与后端确认后批量改造）。
4. **清理测试/示例文件反模式**（可选，避免误导后续开发）。

### 5.4 统一修复策略建议

- 所有"显示日期"场景 → `toLocalDateString(input)`
- 所有"显示日期+时间"场景 → `toLocalDateTimeString(input)`
- 所有"解析 UTC ISO 为 Date 对象"场景 → `parseISOString(input)`
- 所有"向后端提交时间"场景 → `toISOStringUTC(localDate)`
- 禁止：`str.split('T')[0]`、`str.replace('T', ' ').slice(0, 16)`、`date.toISOString().split('T')[0]` 直接用于显示

---

*报告生成时间：2026-07-12*
*审查范围：`frontend/` 目录全量扫描*
*审查性质：只读审查，未修改任何代码*
