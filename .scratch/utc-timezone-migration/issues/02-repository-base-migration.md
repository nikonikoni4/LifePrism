使用 tdd skill 完成任务

# Issue #2: Repository 层基础时间处理迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移 Repository 层的基础时间处理逻辑，包括 base provider、数据库配置、migration scripts。这是所有后端模块迁移的基础。

**修改范围**：
- `lifeprism/repository/base_providers/lw_base_data_provider.py` - 所有时间生成改为 `datetime.now(timezone.utc)`，时间序列化改为 `.isoformat()`
- `lifeprism/config/database.py` - 所有表 DEFAULT 从 `datetime('now', 'localtime')` 改为 `datetime('now')`
- `lifeprism/repository/migrations/` - 所有 migration scripts 中的时间处理

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 数据库 DEFAULT 修改需要生成新的 migration script
- 确保所有时间字段返回的是 aware datetime（`tzinfo` 不为 None）
- 时间比较逻辑需要确保两边都是 aware datetime

## Acceptance criteria

- [ ] `lw_base_data_provider.py` 中所有 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] `lw_base_data_provider.py` 中所有 `.strftime()` 已改为 `.isoformat()` 或 `.date().isoformat()`
- [ ] `database.py` 中所有表 DEFAULT 已改为 `datetime('now')`（SQLite UTC）
- [ ] 已生成新的 migration script 修改已有表的 DEFAULT
- [ ] 已新增单元测试验证时间字段带时区信息
- [ ] 已新增单元测试验证时间序列化为 ISO 8601 格式
- [ ] 所有现有 repository 测试仍然通过

## Blocked by

- Issue #1 - 排查隐性依赖
