# generated 文档索引

## ruff-lint-report
- updated_at: 2026-07-06
- path: `docs/generated/001/ruff-lint-report.md`
- 触发规则：运行 `ruff check lifeprism` 后查看
- 内容摘要：lifeprism 项目 ruff check 检测结果报告，包含 336 个错误分类统计、模块分布和修复优先级建议

## code-review-2026-07-07
- updated_at: 2026-07-07
- path: `docs/generated/002/code-review-2026-07-07.md`
- 触发规则：自定义记录模块 S1-S3 代码审查
- 内容摘要：自定义记录模块三个切片（S1 类型管理+LLM、S2 数据录入+查询、S3 Service+API）的初始代码审查报告，发现 2 个问题（Repository 层 except Exception、delete_entry 未校验存在性）并已修复

## code-review-2026-07-07-2145
- updated_at: 2026-07-07
- path: `docs/generated/003/code-review-2026-07-07-2145.md`
- 触发规则：自定义记录模块 issue 04-06 代码审查
- 内容摘要：自定义记录模块 issue 04-06（前端+后端+测试，22 个文件）的代码审查报告

## code-review-2026-07-08
- updated_at: 2026-07-08
- path: `docs/generated/003/code-review-2026-07-08.md`
- 触发规则：自定义记录模块 issue 01-03 补充审查
- 内容摘要：自定义记录模块 S1-S3 补充代码审查报告，聚焦前次审查未覆盖的问题（LLM Tools SUCCESS 前缀不一致、_query_one/_query_all 错误处理、N+1 查询等），发现 4 个问题

## code-review-2026-07-09
- updated_at: 2026-07-09
- path: `docs/generated/005/code-review-2026-07-09.md`
- 触发规则：P2 数据同步方案 issue01~issue10 文档审查
- 内容摘要：P2 数据同步方案 10 个 Issue 文档的审查报告，覆盖安全、性能、架构、代码质量、最佳实践、测试、文档一致性 7 个维度，发现 19 个问题（置信度 >= 80），其中 4 个阻断性问题（API 契约不一致、时间戳格式不统一、阻塞事件循环）、4 个安全/架构隐患、11 个文档/质量问题

## utc-migration-audit-report
- updated_at: 2026-07-12
- path: `docs/generated/utc-migration-audit-report.md`
- 触发规则：UTC 时区迁移项目 Issue #19 审核时查看
- 内容摘要：UTC 时区迁移项目（Issue #1-#16）的迁移结果审核报告。代码迁移和测试全部通过（199 个测试通过），但 m008/m009 迁移脚本存在 4 个 bug（PRIMARY KEY、CHECK 约束、空名表、带引号表名），且测试数据库未实际应用迁移。审核结论为"审核失败（附条件通过）"，暂不批准进入生产环境迁移。
