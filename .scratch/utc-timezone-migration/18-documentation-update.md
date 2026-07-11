使用 tdd skill 完成任务

# Issue #18: 文档更新和开发规范

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

更新项目文档和开发规范，反映 UTC 时区迁移后的新要求。

**文档更新**：
- 更新 API 文档（如果存在 `docs/api/`），明确标注所有时间字段的格式和时区
  - 示例：`created_at: string (ISO 8601 format, UTC timezone, e.g., "2026-07-11T02:30:45.123456+00:00")`
- 更新 `docs/coding-rules/` 新增"时间处理规范"章节
  - 明确禁止使用 `datetime.now()`（无时区），必须使用 `datetime.now(timezone.utc)`
  - 明确禁止前端使用 `.toISOString().split('T')[0]`，必须使用 `toLocalDateString()`
- 删除 `docs/known-limitations/timezone-and-format-inconsistency.md`（问题已解决）

**开发规范**：
- 后端：所有时间生成必须使用 `datetime.now(timezone.utc)`
- 后端：所有时间序列化必须使用 `.isoformat()`
- 前端：所有日期格式化必须使用 `dateUtils` 工具函数
- 前端：禁止直接使用 `.toISOString()` 进行日期格式化

## Acceptance criteria

- [ ] API 文档已更新（如果存在）
- [ ] `docs/coding-rules/` 已新增时间处理规范章节
- [ ] `docs/known-limitations/timezone-and-format-inconsistency.md` 已删除
- [ ] 开发规范文档清晰易懂，新开发者可以直接遵循
- [ ] 已提交文档更新到 Git

## Blocked by

- Issue #17 - 集成测试和回归测试
