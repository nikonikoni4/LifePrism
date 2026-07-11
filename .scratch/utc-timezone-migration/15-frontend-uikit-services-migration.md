使用 tdd skill 完成任务

# Issue #15: 前端 UI Kit 和 Core Services 迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

修复前端 UI Kit 和 Core Services 中所有违规的时间处理代码。

**修改范围**：
- `frontend/my-ui-kit/ui-kit/todoItem/TodoItem.tsx:199` - Todo 项完成时间
- `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx:195` - 详细 Todo 完成时间
- `frontend/core/services/reportCacheService.ts:290` - 报告缓存服务相邻日期获取

**修改模式**：
- 所有 `toISOString().split('T')[0]` 改为 `toLocalDateString(date)`
- 确保 Todo 完成时间显示正确

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- reportCacheService 的相邻日期获取逻辑需要验证
- Todo 完成时间可能影响统计和排序

## Acceptance criteria

- [ ] 所有 `toISOString().split('T')[0]` 已改为 `toLocalDateString()`
- [ ] reportCacheService 的日期计算已验证
- [ ] 已新增单元测试：验证 Todo 完成时间显示正确
- [ ] 手动测试：Todo 项完成时间显示正确
- [ ] 所有现有前端测试仍然通过

## Blocked by

- Issue #12 - 前端工具函数扩展
