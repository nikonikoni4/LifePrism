使用 tdd skill 完成任务

# Issue #3: Repository 层各 Provider 迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移 Repository 层所有具体 provider 和 aggregator 的时间处理逻辑。

**修改范围**：
- `lifeprism/repository/providers/` - 所有 provider（goal/habit/todo/diary/custom_record 等）
- `lifeprism/repository/aggregators/` - 所有 aggregator
- 所有继承自 `LWBaseDataProvider` 的类

**修改模式**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 所有 `.strftime()` 改为 `.isoformat()` 或 `.date().isoformat()`
- 所有时间字符串解析确保返回 aware datetime

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 检查是否有硬编码的时间格式字符串（如 `%Y-%m-%d %H:%M:%S`）
- 检查是否有时间字符串直接比较（需要改为 datetime 对象比较）
- 检查缓存中的时间数据是否需要更新

## Acceptance criteria

- [ ] 所有 provider 中的 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 所有 provider 中的 `.strftime()` 已改为 `.isoformat()`
- [ ] 所有 aggregator 中的时间处理已迁移
- [ ] 已审查并修复所有时间字符串比较逻辑
- [ ] 已新增单元测试验证时间字段格式
- [ ] 所有现有 provider 测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
