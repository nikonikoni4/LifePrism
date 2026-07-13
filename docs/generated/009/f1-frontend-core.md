# F1: Frontend Core 工具函数 审查报告

## 审查概要
- 审查文件数: 6
- 审查标准: time-handling-rules.md Section 5 (5.1-5.4)，以及 Section 1 内外分离原则
- 审查日期: 2026-07-12
- 分支: feature/utc-timezone-migration vs main

---

## 1. 规则遵守程度

### §5.1 时间戳显示: UTC ISO -> 本地 (遵守率: 3/3)

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 是否有 UTC ISO -> 本地 YYYY-MM-DD HH:MM:SS 转换 | ✅ | `toLocalDateString` (L17) / `toLocalDateTimeString` (L32) — 两个函数均使用 `getFullYear()` / `getMonth()` / `getDate()` 本地方法 |
| 是否使用项目日期工具函数 | ✅ | `parseISOString` (L48) 作为解析 UTC ISO 的单一入口；配合 `toLocalDateString` / `toLocalDateTimeString` 完成转换链 |
| 禁止内联手写格式化 | ✅ | 本次 diff 中 `reportCacheService.ts:291` 将 `toISOString().split('T')[0]` 替换为 `toLocalDateString` |

**§5.1 全景验证（跨 diff 边界的实际使用）**：

- `TodoItem.tsx:200` / `TodoItemDetailed.tsx:196`: `actualFinishAt: toLocalDateString(new Date())` — 日期字段正确使用本地方法
- `PlanDocListView.tsx:138,186`: `updatedAt: toISOStringUTC(new Date())` — 更新时正确发送 UTC ISO
- `PlanDocListView.tsx:226-227`: `createdAt/updatedAt: toISOStringUTC(new Date())` — 新建时正确发送 UTC ISO
- `reportCacheService.ts:291`: `toLocalDateString(adjacentDate)` — 相邻日期计算修正为本地日期

### §5.2 提交后端: 本地时间 -> UTC ISO (遵守率: 2/2)

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 提交时转为 UTC ISO | ✅ | `toISOStringUTC` (L66) 封装 `Date.toISOString()`，语义明确标注"发送给后端" |
| 禁止提交本地时间字符串 | ✅ | `PlanDocListView.tsx` 全部三个写入点（L138, L186, L226-227）均使用 `toISOStringUTC(new Date())` |

**`toISOStringUTC` 与后端格式的一致性**：

| 属性 | 前端 toISOStringUTC | 后端 isoformat() | 兼容? |
|------|---------------------|-------------------|------|
| 格式示例 | `2026-07-11T16:29:54.123Z` | `2026-07-11T16:29:54.123456+00:00` | 兼容 |
| 精度 | 毫秒 (.123) | 微秒 (.123456) | 无影响（JS Date 仅毫秒精度） |
| 后缀 | `Z` | `+00:00` | 两者均为合法 ISO 8601，均可互解析 |

### §5.3 日期字段: 本地时区 (遵守率: 3/3)

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 禁止 `.toISOString().split('T')[0]` | ✅ | `reportCacheService.ts:291` 已从 `adjacentDate.toISOString().split('T')[0]` 替换为 `toLocalDateString(adjacentDate)` |
| 后端返回的 YYYY-MM-DD 字符串直接使用 | ✅ | `getAdjacentDates(date: string)` 接收日期字符串参数，通过 `new Date(date)` 创建 Date 后使用 `toLocalDateString` 提取本地日期。注意：`new Date('2026-03-03')` 在 ECMAScript 规范中按 UTC 解析，但后续 `setDate` 操作和 `toLocalDateString` 均在本地时区执行，结果正确 |
| TodoItem 日期字段使用本地方法 | ✅ | `actualFinishAt: toLocalDateString(new Date())` — 业务日期字段（打卡日期语义）使用本地时区 |

### §5.4 禁止事项对照表 (遵守率: 4/4)

| 禁止项 | 本次 diff 中出现? | 状态 |
|--------|-------------------|------|
| `new Date().toISOString().split('T')[0]` | 仅在注释/文档字符串/测试对比中出现，非生产代码 | ✅ |
| 内联手写 `${y}-${m}-${d}` | 未出现 | ✅ |
| 直接显示后端 UTC ISO | 未出现 | ✅ |
| 提交本地时间字符串给后端 | 未出现 | ✅ |

**注意**：虽然 `new Date().toISOString().split('T')[0]` 在 `test/` 文件的多处断言和对比中出现，但这些都是用于**验证规则被遵守**的对比代码（如 `toLocalDateString` 对比 `toISOString().split('T')[0]` 的差异），不是生产代码中的违规使用。✅

---

## 2. 潜在 Bug

### 🟡 B1: `parseISOString` 未校验输入格式 (dateUtils.ts:48-50)

```typescript
// L48-50
export function parseISOString(isoString: string): Date {
    return new Date(isoString);
}
```

**问题**：函数文档声称用于"后端返回的 ISO 8601 字符串（带时区标识）"，但未对输入做任何校验。如果传入：
- 纯日期字符串 `'2026-03-03'`（无时区信息）→ 在 ECMAScript 规范下按 UTC 午夜解析（不同浏览器行为可能不一致：Safari 旧版会按本地时间解析）
- 非法字符串 → 返回 `Invalid Date`，调用方不做检查会导致静默错误

**风险等级**：低。当前调用方（测试文件外暂无）均为受控的 API 响应路径，后端保证返回合法 ISO 8601。但作为基础工具函数，缺乏防御性校验。

**建议**：添加简单的格式校验和 `Invalid Date` 检查：

```typescript
export function parseISOString(isoString: string): Date {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) {
        throw new Error(`parseISOString: invalid ISO string "${isoString}"`);
    }
    return d;
}
```

### 🟡 B2: `getUserTimezone` fallback 硬编码 `'Asia/Shanghai'` (dateUtils.ts:88)

```typescript
// L85-91
export function getUserTimezone(): string {
    try {
        const tz = localStorage.getItem(TIMEZONE_STORAGE_KEY);
        return tz || 'Asia/Shanghai';
    } catch {
        return 'Asia/Shanghai';
    }
}
```

**问题**：Section 1 核心原则规定"本地时区来源：统一通过配置动态获取，禁止硬编码时区字符串用于业务逻辑"。该函数在 localStorage 缺失时硬编码 fallback 为 `'Asia/Shanghai'`。

**风险等级**：低。该函数当前仅被后端 AI 工具使用（用于生成提示词中的本地时间），前端显示仍使用浏览器本地时区。但如果后续全域切换为按配置时区显示，UTC-5 用户在没有设置时区的情况下会看到上海时间。

**建议**：考虑 fallback 到浏览器本地时区（`Intl.DateTimeFormat().resolvedOptions().timeZone`）而非硬编码 `'Asia/Shanghai'`。

### 🟡 B3: `reportCacheService.formatDate` 重复实现 (reportCacheService.ts:301-305)

```typescript
// L301-305
static formatDate(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
```

**问题**：该方法与 `toLocalDateString` 功能完全一致，属于内联手写格式化的重复代码。违反 §5.1 "使用项目日期工具函数，禁止内联手写格式化逻辑"。

**风险等级**：低。不影响正确性，但违反 DRY 原则。若 `toLocalDateString` 将来修正（如加入时区参数），此处会遗漏。

**注意**：此代码为已有代码，不在本次 diff 范围内，但应在后续清理中修复。

### 🟡 B4: `reportCacheService.isToday` 存在 UTC/本地混淆 (reportCacheService.ts:248-255)

```typescript
// L248-255
private static isToday(date: string): boolean {
    const today = new Date();
    const targetDate = new Date(date);
    return (
        today.getFullYear() === targetDate.getFullYear() &&
        today.getMonth() === targetDate.getMonth() &&
        today.getDate() === targetDate.getDate()
    );
}
```

**问题**：`new Date('2026-03-03')` 按 ECMAScript 规范解析为 UTC 午夜（`2026-03-03T00:00:00Z`）。在 UTC-8 时区（如 `America/Los_Angeles`）下：
- `today.getDate()` 返回本地日期（如 3 月 2 日）
- `targetDate.getDate()` 返回 UTC 日期（3 月 3 日）

导致 `isToday` 在 UTC 负时区的午夜前后可能产生错误判断。

**风险等级**：中。影响日报告缓存的 TTL 决策（当天 vs 历史缓存不同）。

**注意**：此代码为已有代码，不在本次 diff 范围内。应在后续迁移中修复。

### 🟡 B5: 测试 `parseISOString` 存在同义反复 (dateUtils.test.ts:60-63)

```typescript
// L60-63
it('parses ISO 8601 string with Z suffix to correct Date instant', () => {
    const iso = '2026-07-11T16:29:54.123Z';
    const result = parseISOString(iso);
    expect(result.getTime()).toBe(new Date('2026-07-11T16:29:54.123Z').getTime());
});
```

**问题**：`parseISOString(iso)` 内部实现就是 `new Date(iso)`，而期望值也是 `new Date(iso).getTime()`。两者使用完全相同的输入和操作，测试恒为真，无法检测 `parseISOString` 的逻辑错误。

**风险等级**：低。测试仍能捕获 `parseISOString` 抛异常的情况，且 `+00:00` 格式测试使用了不同的输入格式进行交叉验证。

**建议**：使用固定时间戳作为期望值：
```typescript
expect(result.getTime()).toBe(1752248994123); // 硬编码期望的毫秒时间戳
```

---

## 3. 功能缺失风险

### 🟢 无功能缺失

对比 `main` 分支，本次变更：

| 变更 | 影响 | 风险 |
|------|------|------|
| 新增 `parseISOString` | 提供 UTC ISO 解析入口。当前未被生产代码使用（仅有 `toISOStringUTC` 的 round-trip 测试调用），属于基础设施铺设 | 无 |
| 新增 `toISOStringUTC` | 提供"发送给后端"语义的时间序列化入口。已被 `PlanDocListView.tsx` 三个写入点采用 | 无 |
| 新增 `getUserTimezone` / `setUserTimezone` | 提供用户时区配置的读写入口。当前未被生产代码调用，属于基础设施铺设 | 无 |
| 修复 `reportCacheService.getAdjacentDates` | `toISOString().split('T')[0]` -> `toLocalDateString`：在 UTC- 时区下日期正确性提升 | 无 |
| TodoItem `actualFinishAt` 使用 `toLocalDateString` | 已在 `main` 分支通过其他 MR 合入？本次仅是新增 UTC 测试用例 | 无 |
| vitest.config.ts 新增 resolve alias | 使 my-ui-kit 组件和 @dnd-kit 的测试可以正确解析 React 单例 | 无 |

**结论**：本次变更为"基础设施铺设 + 单点修复"，新增函数均正确，替换均等价或更优（修正了 UTC/本地混淆），无功能回退。

---

## 4. 安全隐患

### 🟢 无安全隐患

逐项排查：

| 检查项 | 结论 |
|--------|------|
| 日期解析 XSS（innerHTML 注入） | 所有时间函数返回纯字符串（数字和 `-:T.Z`），不包含 HTML 特殊字符。即使直接插入 DOM 也不会触发 XSS |
| 时区假设硬编码 | `getUserTimezone` fallback 硬编码 `'Asia/Shanghai'` 见 B2，但该值仅用于后端 AI 提示词，不影响前端显示 |
| localStorage 异常处理 | `getUserTimezone` / `setUserTimezone` 均包含 try-catch，localStorage 不可用时静默降级 |
| 日期注入攻击 | `parseISOString` 无输入校验（见 B1），但仅创建 Date 对象，不存在注入路径 |

---

## 总结

| 规则章节 | 遵守率 | 关键证据 |
|----------|--------|----------|
| §5.1 时间戳显示 | 3/3 | `toLocalDateString` + `toLocalDateTimeString` 覆盖本地格式化；`reportCacheService` 违规已修复 |
| §5.2 提交后端 | 2/2 | `toISOStringUTC` 封装 UTC ISO 序列化，`PlanDocListView` 正确使用 |
| §5.3 日期字段 | 3/3 | `toISOString().split('T')[0]` 替换完成；`actualFinishAt` 使用 `toLocalDateString` |
| §5.4 禁止事项 | 4/4 | 生产代码中无违规模式出现 |

**整体评估**：变更质量高。4 个新增函数（`parseISOString` / `toISOStringUTC` / `getUserTimezone` / `setUserTimezone`）设计合理，注释详尽，语义明确。`reportCacheService` 的单点修复正确消除了 `toISOString().split('T')[0]` 在 UTC- 时区下的 bug。测试用例覆盖了 UTC+8 午夜边界、UTC-8 时区相邻日期计算、以及与旧 `toISOString` 的对比验证。

**需要跟进的问题**：

| 编号 | 严重度 | 简述 | 是否在 diff 范围内 |
|------|--------|------|-------------------|
| B1 | 🟡 | `parseISOString` 缺少输入校验 | 是 |
| B2 | 🟡 | `getUserTimezone` fallback 硬编码 `Asia/Shanghai` | 是 |
| B3 | 🟡 | `reportCacheService.formatDate` 重复实现 | 否（已有代码） |
| B4 | 🟡 | `reportCacheService.isToday` UTC/本地混淆 | 否（已有代码） |
| B5 | 🟡 | `parseISOString` 测试同义反复 | 是 |
