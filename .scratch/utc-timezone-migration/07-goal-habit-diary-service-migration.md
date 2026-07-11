使用 tdd skill 完成任务

# Issue #7: 目标/习惯/日记服务迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移目标、习惯、日记、任务池服务的时间处理逻辑。

**修改范围**：
- `lifeprism/server/services/goal_service.py`
- `lifeprism/server/services/habit_service.py`
- `lifeprism/server/services/diary_service.py`
- `lifeprism/server/services/taskpool_service.py`

**修改模式**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 所有 `.strftime()` 改为 `.isoformat()`
- 所有时间参数解析确保返回 aware datetime

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 检查是否有日期范围过滤逻辑（如"本周目标"、"今日任务"）
- 检查是否有时间排序逻辑
- 检查是否有时间计算逻辑（如"已过期 X 天"）

## Acceptance criteria

- [ ] 所有服务中的 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 所有服务中的 `.strftime()` 已改为 `.isoformat()`
- [ ] 已审查并修复所有日期范围过滤逻辑
- [ ] 已审查并修复所有时间计算逻辑
- [ ] 已新增单元测试验证时间字段格式
- [ ] 所有现有服务测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
