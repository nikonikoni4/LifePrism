# Issue #23: 报告统计模块时间筛选修复

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

修复报告统计模块的时间筛选问题，确保查询使用 UTC 时间范围。

**问题**：`report_service.py` 和 `activity_stats_builder.py` 已定义辅助函数（`_build_utc_time_range` 等），但 7 个计算函数都未使用，仍用 `f"{date} 00:00:00"` 本地时间字符串查询 UTC 存储的字段，导致 UTC+8 用户查询"今天"会错位 8 小时。

**架构原则**：
- 前端组件：筛选时就地转换为 UTC ISO 8601 提交
- 后端 API：透传 UTC ISO 8601
- 后端 Service：使用前端传入的 UTC 时间范围查库，不再自己用本地日期构造

**需要修复的文件**：

### 后端 Service 层（启用已有辅助函数）
1. `report_service.py`：
   - 7 个计算函数（`_calc_sunburst_data` 等）启用已有的 `_build_utc_time_range`、`_utc_timestamp_to_local_date`、`_add_local_date_column` 辅助函数
   - 移除 `f"{date} 00:00:00"` 等本地时间构造
   - 使用 API 传入的 UTC 时间范围

2. `activity_stats_builder.py`：
   - `build_time_overview` 启用已有辅助函数
   - 移除本地时间构造

3. `timeline_builder.py`（如 Issue #22 未完全覆盖）：
   - `load_day_events` 使用 UTC 时间范围

### 前端筛选提交（就地转换）
4. 报告页面筛选组件（日报/周报/月报日期选择器）：
   - 调用 `buildUtcTimeRange(date)` 转换为 UTC ISO 提交
   - 检查 `DataReviewTab.tsx` 的时间筛选

### 前端显示（就地转换）
5. 报告页面显示时间时，调用 `utcToLocalDisplay()` 转换

### E2E 验证
6. 日报查询"今天" → 返回今天的数据
7. 周报查询本周 → 返回正确周范围数据
8. 报告中的时间显示为本地时区

## Acceptance criteria

- [ ] `report_service.py` 7 个计算函数启用辅助函数
- [ ] `activity_stats_builder.py` `build_time_overview` 启用辅助函数
- [ ] `timeline_builder.py` 使用 UTC 时间范围
- [ ] 移除所有 `f"{date} 00:00:00"` 本地时间构造
- [ ] 前端报告筛选提交 UTC ISO 8601
- [ ] 前端报告显示使用 `utcToLocalDisplay()`
- [ ] E2E 验证：日报/周报查询返回正确数据
- [ ] 相关测试通过

## Blocked by

- Issue #21 - 前端时间转换工具完善
- Issue #22 - 活动日志 tracer bullet（参考模式）

## 注意事项

1. **辅助函数已存在**：`report_service.py` 已有 `_build_utc_time_range` 等函数，只需启用
2. **后端 API 不做转换**：API 层透传 UTC ISO 8601
3. **Service 层是修复 bug**：错误地用本地时间查 UTC 存储，这是 bug 修复
