# Issue #22: 活动日志时间筛选端到端修复（Tracer Bullet）

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

以"查询某天活动日志"为 tracer bullet，打通前端筛选 → 后端查询 → 前端显示的完整链路，验证"组件就地转换"架构。

**架构原则**：
- 前端组件：筛选时就地转换为 UTC ISO 8601 提交，显示时就地将 UTC 转为本地时区
- 后端 API：透传 UTC ISO 8601，不做转换
- 后端 Service/Repository：接收 UTC ISO 8601，直接查库

**需要修复的链路**：

### 前端筛选提交（就地转换）
1. `Timeline.tsx` 构造 `${date} 00:00:00` 本地时间字符串 → 改为调用 `buildUtcTimeRange(date)` 转换为 UTC ISO 提交
2. `ActivitySummaryHeader.tsx` 同步对话框的时间筛选 → 同上
3. 相关 API 调用层（`api.ts` / hooks）→ 确保提交的是 UTC ISO 8601

### 后端 Service 修复（内部逻辑）
4. `timeline_builder.py` 的 `load_day_events` 直接使用本地日期字符串查库 → 改为使用 API 传入的 UTC 时间范围
5. `timeline_service.py` 直接使用本地时间构造 → 改为透传 API 传入的 UTC 时间
6. `activity_service.py` 透传时间参数 → 确认透传的是 UTC ISO 8601

### 前端显示（就地转换）
7. Timeline 相关组件显示时间时，调用 `utcToLocalDisplay()` 转换为本地时区显示
8. 活动日志列表显示时间时，同上

### E2E 验证
9. 选择"今天"筛选 → 返回今天的数据（不错位 8 小时）
10. 时间轴上事件块出现在正确的时刻（不偏移 8 小时）

## Acceptance criteria

- [ ] `Timeline.tsx` 筛选提交 UTC ISO 8601 格式
- [ ] `ActivitySummaryHeader.tsx` 筛选提交 UTC ISO 8601 格式
- [ ] `timeline_builder.py` 使用 UTC 时间范围查库
- [ ] `timeline_service.py` 透传 UTC 时间
- [ ] 前端显示使用 `utcToLocalDisplay()` 转换
- [ ] E2E 验证：筛选"今天"返回今天的数据，不错位
- [ ] E2E 验证：时间轴事件块出现在正确时刻
- [ ] 相关测试通过

## Blocked by

- Issue #21 - 前端时间转换工具完善（需要 `buildUtcTimeRange` 和 `utcToLocalDisplay` 函数）

## 注意事项

1. **后端 API 不做转换**：API 层只透传 UTC ISO 8601
2. **Service 层修复是修复 bug**：Service 错误地用本地时间查 UTC 存储的字段，这是 bug 修复，不是"对外接口转换"
3. **这是 tracer bullet**：打通后，后续 slice（#23-#26）可复用此模式
4. **参考 LLM tool**：`lifeprismsystem.py` 的 `_parse_local_time` 和 `_utc_to_local` 已正确实现此架构
