使用 tdd skill 完成任务

# Issue #13: 前端 Goals 模块迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

修复前端 Goals 模块中所有违规的时间处理代码。

**修改范围**：
- `frontend/apps/goals/hooks/useGoalStore.ts:204` - 里程碑完成时间
- `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx:21, 66, 89` - 日历网格日期生成
- `frontend/apps/goals/components/views/GoalListView/components/AddGoalModal.tsx:21` - 目标新增对话框
- `frontend/apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx:22` - 日记输入对话框

**修改模式**：
- 所有 `toISOString().split('T')[0]` 改为 `toLocalDateString(date)`
- 日期范围生成函数改用 `toLocalDateString()`
- 确保所有日期选择使用本地时间方法

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- DateGrid 的日期范围生成需要特别注意
- 日期选择器传递给后端时需要使用正确格式

## Acceptance criteria

- [ ] 所有 `toISOString().split('T')[0]` 已改为 `toLocalDateString()`
- [ ] 日期范围生成函数已修复
- [ ] 已新增单元测试：验证午夜前后日期选择正确
- [ ] 手动测试：日历组件在不同日期点击显示正确
- [ ] 所有现有前端测试仍然通过

## Blocked by

- Issue #12 - 前端工具函数扩展
