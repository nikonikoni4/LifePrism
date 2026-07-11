使用 tdd skill 完成任务

# Issue #14: 前端 LifeWatch 模块迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

修复前端 LifeWatch 模块中所有违规的时间处理代码。

**修改范围**：
- `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx:38, 119, 168, 187` - 日报告日期选择
- `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx:36-37, 118, 122` - 周报告日期范围
- `frontend/apps/lifewatch/pages/usage/UsagePage.tsx:28` - 使用统计页面
- `frontend/apps/lifewatch/pages/reports/mockData.ts:66` - Mock 数据生成

**修改模式**：
- 所有 `toISOString().split('T')[0]` 改为 `toLocalDateString(date)`
- `getWeekRange()` 函数改用 `toLocalDateString()`
- 确保周报告的日期范围计算正确

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 周报告的日期范围计算需要特别注意（周一到周日）
- Mock 数据生成也需要使用正确的时间方法

## Acceptance criteria

- [ ] 所有 `toISOString().split('T')[0]` 已改为 `toLocalDateString()`
- [ ] `getWeekRange()` 函数已修复
- [ ] 已新增单元测试：验证周报告日期范围计算正确
- [ ] 手动测试：日报告和周报告显示正确
- [ ] 所有现有前端测试仍然通过

## Blocked by

- Issue #12 - 前端工具函数扩展
