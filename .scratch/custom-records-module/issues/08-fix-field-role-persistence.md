# 字段角色持久化修复 — 前后端契约打通

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Code Review**: `docs/generated/002/code-review-2026-07-07-2145.md` Issue 2（置信度 100）

## What to build

修复字段角色配置功能的端到端持久化。当前后端 `FieldDefinition` Schema 缺少 `id` 字段，前端无法获取 `field_id` 来调用 `PATCH /types/{type_id}/fields/{field_id}` 端点，导致用户在 FieldRoleModal 中配置的角色刷新后丢失。

端到端行为：
1. 后端 `FieldDefinition` Schema 增加 `id` 字段
2. Service 层 `_convert_to_field_definition` 转换时保留 `item["id"]`
3. 前端 `types.ts` 的 `FieldDefinition` 接口增加 `id` 字段
4. `TypeDetailView` 的 `handleFieldRoleChange` 通过 `field.id` 调用 `CustomRecordsAPI.updateFieldRole` 持久化
5. 用户在 FieldRoleModal 修改角色后，刷新页面配置仍然生效

## Acceptance criteria

- [ ] 后端 `FieldDefinition` Schema 包含 `id: str` 字段
- [ ] Service `_convert_to_field_definition` 传递 `id` 字段
- [ ] API `GET /types` 和 `GET /types/{id}` 响应中每个 field 都包含 `id`
- [ ] 前端 `FieldDefinition` 接口包含 `id` 字段
- [ ] `handleFieldRoleChange` 调用 `updateFieldRole` API 持久化，移除 TODO 注释
- [ ] 用户修改字段角色后刷新页面，角色配置仍然生效
- [ ] 已有的 31 个后端测试 + 64 个前端测试无回归

## Blocked by

None - can start immediately
