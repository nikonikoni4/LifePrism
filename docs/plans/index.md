
## Active Plans

### provider-crud-rename-fix

- updated_at: 2026-04-24
- path: `docs/plans/2026-04-24-provider-crud-rename-fix.md`
- 触发规则：当任务涉及 `lifeprism/storage/providers` 基础 CRUD 命名统一与调用修复时读取
- 内容摘要：统一 provider 基础 CRUD 方法命名到 create-table-rules 规范，并同步修复跨层调用与测试。

### usage-service-tokens-store-migration

- updated_at: 2026-04-24
- path: `docs/plans/2026-04-24-usage-service-tokens-store-migration.md`
- 触发规则：当任务涉及 usage_service 从 server_lw_data_provider 迁移到 tokens_usage_store 时读取
- 内容摘要：将 token 使用统计切换到 storage 层通用查询并在 service 层完成按日/按 mode 聚合适配，保持返回结构不变。

### docs-maintenance

- updated_at: 2026-04-10
- path: `docs/plans/active/2026-04-08-docs-maintenance.md`
- 触发规则：当任务涉及 `docs/` 分类、生命周期、冲突裁决或 CI 文档维护机制时读取
- 内容摘要：文档治理计划草案，整理 docs 目录分层、生命周期状态机以及 CI 维护目标。
