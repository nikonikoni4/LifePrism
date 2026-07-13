# F2: Frontend Goals App 审查报告

## 审查概要
- 审查文件数: 7
- 审查标准: time-handling-rules.md Section 5 (前端规则 5.1-5.4) + frontend-date-handling.md
- 审查日期: 2026-07-12

## 1. 规则遵守程度

### 1.1 DateGrid.tsx -- ✅ 完全合规

| 位置 | 变更内容 | 规则对照 |
|------|---------|---------|
| L7 | 新增 `import { toLocalDateString }` | -- |
| L22 | `current.toISOString().split('T')[0]` -> `toLocalDateString(current)` | §5.3 禁止 `.toISOString().split('T')[0]` |
| L67 | `today.toISOString().split('T')[0]` -> `toLocalDateString(today)` | §5.3 |
| L90 | `selectedDate.toISOString().split('T')[0]` -> `toLocalDateString(selectedDate)` | §5.3 |

共消灭 **3 处** `.toISOString().split('T')[0]` 违规。零残留。

L85 使用了本地时区方法 (`getDay()`, `getMonth()`, `getDate()`) 显示星期和日期，符合 §5.3 对日期字段的要求。L86-L87:

```typescript
const dayName = ['日', '一', '二', '三', '四', '五', '六'][dateObj.getDay()];
const monthDay = `${dateObj.getMonth() + 1}/${dateObj.getDate()}`;
```

无内联手写 YYYY-MM-DD 格式化 (§5.4)。✅

### 1.2 DateGrid.test.ts -- ✅ 测试覆盖充分

新增 4 个测试用例，覆盖 UTC+8 午夜边界的关键场景:
- 午夜 00:00 日期范围 (L34-L41)
- 23:59 深夜边界 (L44-L49)
- 单天范围 (L52-L57)
- 跨月边界 (L60-L65)

测试集直接验证 `generateDateRange` 不再依赖 UTC 日期。✅

**轻微注意事项 (🟡)**: L22-L32 通过 `process.env.TZ` 尝试设置时区。Node.js 在部分平台 (Windows) 上运行时修改此变量不会改变 `Date` 的时区行为 -- 时区在进程启动时已固化。如果 CI 运行在非 UTC+8 环境，测试可能表现不一致。建议后续引入时区 mock 库或使用 `vitest` 的 `TZ` 环境变量设置。

### 1.3 DailyTaskView.tsx -- ✅ 完全合规

| 位置 | 变更 | 规则 |
|------|------|------|
| L330 | `selectedDate.toISOString().split('T')[0]` -> `toLocalDateString(selectedDate)` | §5.3 |

`dateStr` 用于过滤任务的 `scheduledDate` 字段 (L337: `t.scheduledDate === dateStr`)。`scheduledDate` 是 YYYY-MM-DD 格式的日期字段，使用本地日期进行匹配可确保午夜前后 (UTC+8 00:30) 仍能正确过滤"今日任务"。✅

### 1.4 AddGoalModal.tsx -- ✅ 完全合规

| 位置 | 变更 | 规则 |
|------|------|------|
| L20-L22 | `new Date().toISOString().split('T')[0]` -> `toLocalDateString(today)` | §5.3 |

`startDate` 是日期字段 (Goal 实体的 `startDate: string`, 格式 YYYY-MM-DD)，使用 `toLocalDateString` 正确。表单中的 `<input type="date">` (L202-L207) 使用本地日期值，正确。✅

### 1.5 JournalEntryModal.tsx -- ✅ 完全合规

| 位置 | 变更 | 规则 |
|------|------|------|
| L22-L23 | `new Date().toISOString().split('T')[0]` -> `toLocalDateString(new Date())` | §5.3 |

JournalEntry 的 `date` 字段是日期字段 (YYYY-MM-DD)。`getCurrentTime()` (L27-L28) 使用 `toTimeString().slice(0, 5)` 获取本地 HH:MM，无问题。✅

### 1.6 PlanDocListView.tsx -- ✅ 完全合规

| 位置 | 变更 | 规则 |
|------|------|------|
| L138 | `new Date().toISOString()` -> `toISOStringUTC(new Date())` | §5.2 提交后端转 UTC ISO |
| L186 | `new Date().toISOString()` -> `toISOStringUTC(new Date())` | §5.2 |
| L226 | `new Date().toISOString()` -> `toISOStringUTC(new Date())` | §5.2 |
| L227 | `new Date().toISOString()` -> `toISOStringUTC(new Date())` | §5.2 |

共消灭 **4 处** 直接 `.toISOString()` 调用，全部替换为语义明确的 `toISOStringUTC()`。

PlanDoc 的 `createdAt` / `updatedAt` 是时间戳字段 (Entity 定义: `createdAt: string`, `updatedAt: string`)，需要 UTC ISO 格式提交给后端。使用 `toISOStringUTC()` 表达了"提交给后端"的意图，与 `toLocalDateString` (本地日期) 语义明确区分。✅

### 1.7 useGoalStore.ts -- ✅ 完全合规

| 位置 | 变更 | 规则 |
|------|------|------|
| L205 | `new Date().toISOString().split('T')[0]` -> `toLocalDateString(new Date())` | §5.3 |

`finishTime` 是日期字段 (MilestoneItem 类型定义: `finishTime: string | null`, API 层经 `formatDateForApi` 期望 YYYY-MM-DD)。使用 `toLocalDateString` 正确。✅

### 违规统计

| 违规类型 | 修复前 | 修复后 | 残留 |
|----------|--------|--------|------|
| `.toISOString().split('T')[0]` | 6 处 | 0 处 | **0** |
| 直接 `.toISOString()` (应转 UTC) | 4 处 | 0 处 | **0** |
| 内联手写日期格式化 | 0 处 | 0 处 | **0** |
| 内联手写 `${y}-${m}-${d}` | 0 处 | 0 处 | **0** |

## 2. 潜在 Bug

### 🟡 DateGrid.tsx L85: `new Date(date)` 解析 YYYY-MM-DD 字符串为 UTC

```typescript
// L83: dates 数组元素是 "YYYY-MM-DD" 字符串
{dates.map(date => {
    const dateObj = new Date(date);  // L85
    const dayName = ['日', '一', '二', '三', '四', '五', '六'][dateObj.getDay()];  // L86
    const monthDay = `${dateObj.getMonth() + 1}/${dateObj.getDate()}`;  // L87
```

ECMAScript 规范规定 `new Date("YYYY-MM-DD")` 解析为 **UTC 午夜**。例如:
- `new Date("2026-03-03")` = `2026-03-03T00:00:00.000Z` = 本地 `2026-03-03 08:00:00` (UTC+8)

在 UTC+8 时区，`getMonth()+1` 返回 3、`getDate()` 返回 3，结果正确。但在 UTC-5 时区 (如美国东部时间夏令时): `new Date("2026-03-03")` = UTC 2026-03-03T00:00Z = 本地 2026-03-02T19:00。此时 `getMonth()+1` 返回 2 (二月)，`getDate()` 返回 2，**显示错误**。

**判定**: 此问题**预存于原代码** (原代码同样使用 `new Date(date)`)，非本次 diff 引入。本次改动修复了日期生成 (`generateDateRange`) 和日期比较 (`isToday` / `isSelected`)，使得日期字符串在 UTC+8 时区下一致。`new Date(date)` 对 UTC-5 时区的影响是后续改进项。建议后续统一替换为:

```typescript
const dateObj = parseLocalDate(date); // 解析 YYYY-MM-DD 为本地日期
```

### 🟢 无新引入的 Bug

本次变更对 UTC+8 用户 (项目主要用户群) 而言是**纯修复** -- 所有 `.toISOString().split('T')[0]` 替换为 `toLocalDateString` 消除了午夜前后的日期错位。

## 3. 功能缺失风险

- **无功能缺失**。所有功能逻辑等价替换，仅改变日期计算方式 (UTC -> 本地)。
- PlanDocListView 中的 `toISOStringUTC()` 与原来的 `toISOString()` 行为完全一致 (均为原生 `.toISOString()`)，无功能变化。
- Goal 创建/编辑的 `startDate` 和 Journal 的 `date` 字段均保持 YYYY-MM-DD 本地日期格式，提交逻辑未改变。

## 4. 安全隐患

无特殊安全问题。日期工具函数 (`toLocalDateString`, `toISOStringUTC`, `parseISOString`) 均为纯计算函数，无网络请求、无动态代码执行、无 user input 注入风险。

## 总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 规则遵守 | ⭐⭐⭐⭐⭐ | 10 处违规全部修复，零残留 |
| 新 Bug | ⭐⭐⭐⭐⭐ | 无新引入 Bug；预存的 `new Date(date)` 问题仅影响非 UTC+8 时区 |
| 功能完整 | ⭐⭐⭐⭐⭐ | 无功能丢失 |
| 安全性 | ⭐⭐⭐⭐⭐ | 无安全问题 |
| 测试覆盖 | ⭐⭐⭐⭐☆ | 新增 4 个 UTC+8 午夜边界测试；TZ mock 可靠性待改进 |

**结论**: 审查通过。7 个文件的所有变更严格遵循了 `time-handling-rules.md` Section 5 (5.1-5.4) 和 `frontend-date-handling.md` 规范。核心修复项 -- 将 `.toISOString().split('T')[0]` 替换为 `toLocalDateString()` -- 覆盖了日历、日视图、目标创建、日记、里程碑完成等全部用户交互路径。建议的后续改进: (1) DateGrid L85 `new Date(date)` 改为本地日期解析 (2) DateGrid 测试引入可靠的时区 mock 机制。
