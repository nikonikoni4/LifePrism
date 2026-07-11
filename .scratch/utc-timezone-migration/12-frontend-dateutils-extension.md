使用 tdd skill 完成任务

# Issue #12: 前端核心工具函数扩展

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

扩展前端核心时间工具函数，为后续前端模块迁移提供基础。

**修改范围**：
- `frontend/core/utils/dateUtils.ts` - 新增工具函数
- `frontend/core/utils/dateUtils.test.ts` - 扩展单元测试

**新增工具函数**：
```typescript
// 解析后端返回的 ISO 8601 字符串为 Date 对象
function parseISOString(isoString: string): Date;

// 将 Date 对象转为 ISO 8601 字符串发送给后端
function toISOStringUTC(date: Date): string;
```

**扩展单元测试**：
- 测试 `toLocalDateString()` 在 UTC 午夜前后返回正确日期
- 测试 `toLocalDateTimeString()` 在不同时区下正确
- 测试新增的 `parseISOString()` 和 `toISOStringUTC()`

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- `toLocalDateString()` 已正确实现，无需修改
- 新增的工具函数需要与后端 ISO 8601 格式一致
- 测试用例需要覆盖 UTC+ 时区的边界场景

## Acceptance criteria

- [ ] 已新增 `parseISOString()` 工具函数
- [ ] 已新增 `toISOStringUTC()` 工具函数
- [ ] 已扩展单元测试覆盖 UTC 时区场景
- [ ] 已新增测试用例：验证午夜前后日期正确
- [ ] 所有现有测试仍然通过

## Blocked by

- Issue #1 - 排查隐性依赖
