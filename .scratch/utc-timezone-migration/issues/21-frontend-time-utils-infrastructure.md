# Issue #21: 前端时间转换工具完善（基础设施）

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

完善前端 `dateUtils.ts` 的时间转换工具函数，作为后续所有 slice 的基础设施。

**架构原则**：
- API 层保持 UTC ISO 8601 透传，不做转换
- 所有时间转换在**前端组件层就地进行**
- 前端提交给后端的时间筛选参数：本地时区 → UTC ISO 8601
- 前端显示后端返回的时间：UTC ISO 8601 → 本地时区 `YYYY-MM-DD HH:MM:SS`

**需要完善的函数**（在 `frontend/core/utils/dateUtils.ts`）：

1. `utcToLocalDisplay(utcStr: string): string`
   - 输入：UTC ISO 8601（如 `2026-07-12T07:08:57.529846+00:00`）
   - 输出：本地时区 `YYYY-MM-DD HH:MM:SS`
   - 使用 `getUserTimezone()` 获取配置的时区
   - 用于前端组件显示时间

2. `localToUtcISO(localStr: string): string`
   - 输入：本地时区时间（如 `2026-07-12 15:00:00` 或 `2026-07-12`）
   - 输出：UTC ISO 8601（如 `2026-07-12T07:00:00+00:00`）
   - 使用 `getUserTimezone()` 获取配置的时区
   - 用于前端组件提交筛选参数

3. `utcToLocalDate(utcStr: string): string`
   - 输入：UTC ISO 8601
   - 输出：本地时区日期 `YYYY-MM-DD`
   - 用于只显示日期的场景

4. `buildUtcTimeRange(localDate: string): [string, string]`
   - 输入：本地日期 `YYYY-MM-DD`
   - 输出：`[utcStartIso, utcEndIso]`（当天 00:00:00 ~ 23:59:59 的 UTC 范围）
   - 用于"查询某天数据"的筛选场景

**依赖库**：可使用 `date-fns-tz`（已安装 date-fns@4.1.0）或 `Intl.DateTimeFormat` 实现时区转换

**单元测试**：覆盖所有函数，包括：
- UTC+8 时区的转换
- 跨日期边界（本地 00:30 → UTC 前一天 16:30）
- 不同输入格式（带 T、不带 T、带毫秒、不带毫秒）
- 空字符串/无效输入的处理

## Acceptance criteria

- [ ] `dateUtils.ts` 新增 4 个转换函数
- [ ] 所有函数使用 `getUserTimezone()` 读取配置时区
- [ ] 单元测试覆盖所有函数，包括跨日期边界场景
- [ ] 测试通过
- [ ] ruff check / eslint 通过

## Blocked by

None - 可立即开始

## 注意事项

1. **不要修改后端 API 层**：API 保持 UTC ISO 8601 透传
2. **不要修改后端 Service 层**：Service 层的修复在后续 slice 中处理
3. **时区配置**：使用 `getUserTimezone()` 读取用户配置的时区（默认 `Asia/Shanghai`）
4. **向后兼容**：如果输入已经是本地格式或无效，应安全处理不抛异常
