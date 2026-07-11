使用 tdd skill 完成任务

# Issue #9: API 层时间参数解析和响应序列化

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移 API 层的时间参数解析和响应序列化逻辑，确保前后端协议使用 ISO 8601 格式。

**修改范围**：
- `lifeprism/server/api/` - 所有 API endpoint
- 所有接收时间参数的 API
- 所有返回时间字段的 API

**核心修改**：
- 时间参数解析：使用 `datetime.fromisoformat()` 或 Pydantic 的时间类型
- 时间参数验证：确保解析后是 aware datetime
- 响应序列化：确保时间字段返回 ISO 8601 格式（Service 层已处理，API 层只需验证）

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 检查是否有硬编码的时间格式假设
- 检查是否有时间字符串直接传递给 Service 层（需要先解析）
- 前端发送的时间参数可能是 `YYYY-MM-DD` 或 `YYYY-MM-DDTHH:MM:SS` 格式

## Acceptance criteria

- [ ] 所有 API 的时间参数解析已统一使用 `datetime.fromisoformat()` 或 Pydantic
- [ ] 所有 API 的时间参数已验证是 aware datetime
- [ ] 已审查所有 API 响应，确认时间字段是 ISO 8601 格式
- [ ] 已新增 API 集成测试验证时间参数和响应格式
- [ ] 所有现有 API 测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
