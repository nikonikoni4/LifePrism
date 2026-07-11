使用 tdd skill 完成任务

# Issue #6: 报表和统计服务迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移报表和统计服务的时间处理逻辑，确保时间分组和范围查询在 UTC 时区下正确。

**修改范围**：
- `lifeprism/server/services/report_service.py` - 时间分组逻辑
- `lifeprism/server/services/activity_stats_builder.py` - 时间范围查询
- `lifeprism/server/services/usage_service.py` - 如果涉及时间处理

**核心修改**：
- 所有时间生成改为 `datetime.now(timezone.utc)`
- 按天分组统计需要将 UTC 时间转回本地时区：`datetime(created_at, '+8 hours')`
- 时间范围查询需要显式处理时区转换

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 统计按"天"分组时，需要基于用户本地时区的"天"，而非 UTC 的"天"
- 例如：本地 2026-01-01 00:00 ~ 23:59 对应 UTC 2025-12-31 16:00 ~ 2026-01-01 15:59
- 需要在 SQL 查询中使用 `datetime(created_at, '+8 hours')` 进行时区转换

## Acceptance criteria

- [ ] 所有 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 按天分组统计已正确处理时区转换
- [ ] 时间范围查询已验证在 UTC 时区下正确
- [ ] 已新增单元测试验证统计结果在跨时区下正确
- [ ] 所有现有报表和统计测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
