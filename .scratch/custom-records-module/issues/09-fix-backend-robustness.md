# 后端 API 健壮性修复 — None 处理 + 枚举校验 + 时间戳 + 冗余查询

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Code Review**: `docs/generated/002/code-review-2026-07-07-2145.md` Issues 3, 6, 10, 11（置信度 85-95）

## What to build

修复后端 4 个健壮性问题，使 API 层返回正确的 HTTP 状态码和数据。

端到端行为：
1. `get_type` 在类型不存在时抛出 `EntityNotFoundError`（404），而非 `TypeError`（500）
2. Service 层移除冗余的 `get_type_fields` 调用，直接使用 `get_type_by_id` 返回的 `t["fields"]`
3. Schema 层 `card_template` 和 `display_role` 使用 `Literal` 类型做枚举校验，拒绝非法值
4. `update_type_config` 的 UPDATE SQL 包含 `updated_at = ?` 设置当前时间

## Acceptance criteria

- [ ] `GET /types/crt-nonexist` 返回 404 而非 500
- [ ] `get_type`、`create_type`、`update_type_config`、`update_field_role` 不再调用 `get_type_fields`
- [ ] `PATCH /types/{id}` 传入 `card_template="invalid"` 返回 422 校验错误
- [ ] `PATCH /types/{id}/fields/{field_id}` 传入 `display_role="invalid"` 返回 422
- [ ] `update_type_config` 后 `updated_at` 字段更新为当前时间
- [ ] `card_template` 枚举值：clean / paper / minimal / bold / metric
- [ ] `display_role` 枚举值：auto / title / main / chip / hidden
- [ ] 已有的 31 个后端测试无回归

## Blocked by

None - can start immediately
