使用 tdd skill 完成任务

# Issue #11: Monitor 模块时间处理迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移 Monitor 模块的时间处理逻辑。

**修改范围**：
- `lifeprism/monitor/windows_monitor/monitor.py` - 活动记录的时间戳
- `lifeprism/monitor/screenshot/store.py` - 截图存储的时间戳
- `lifeprism/monitor/windows_monitor/runtime.py` - 如果涉及时间处理
- `lifeprism/processors/` - 如果涉及时间处理

**修改模式**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 所有 `.strftime()` 改为 `.isoformat()`
- 活动记录的时间戳使用 UTC

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 活动记录的时间戳影响数据同步和统计报表
- 截图存储的时间戳影响文件命名和检索
- 检查是否有时间相关的数据清理逻辑（如"删除 7 天前的截图"）

## Acceptance criteria

- [ ] 所有 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 所有 `.strftime()` 已改为 `.isoformat()`
- [ ] 活动记录的时间戳格式已统一
- [ ] 截图存储的时间戳逻辑已验证
- [ ] 已新增单元测试验证时间字段格式
- [ ] 所有现有 Monitor 模块测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
