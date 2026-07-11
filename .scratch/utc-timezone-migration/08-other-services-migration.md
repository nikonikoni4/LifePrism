使用 tdd skill 完成任务

# Issue #8: 其他服务迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移其他服务模块的时间处理逻辑。

**修改范围**：
- `lifeprism/server/services/chatbot_service.py`
- `lifeprism/server/services/timeline_builder.py`
- `lifeprism/server/services/data_processing_service.py`
- `lifeprism/server/services/add_on_service.py`
- `lifeprism/server/services/category_service.py`
- 其他 `lifeprism/server/services/` 下涉及时间处理的服务

**修改模式**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 所有 `.strftime()` 改为 `.isoformat()`
- 所有时间参数解析确保返回 aware datetime

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 检查是否有时间轴构建逻辑（`timeline_builder.py`）
- 检查是否有数据处理的时间戳记录（`data_processing_service.py`）
- 检查是否有聊天消息的时间戳（`chatbot_service.py`）

## Acceptance criteria

- [ ] 所有服务中的 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 所有服务中的 `.strftime()` 已改为 `.isoformat()`
- [ ] 已审查并修复所有时间相关逻辑
- [ ] 已新增单元测试验证时间字段格式
- [ ] 所有现有服务测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
