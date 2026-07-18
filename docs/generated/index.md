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

## code-review-2026-07-15-sync-jsonl-lww
- updated_at: 2026-07-15
- path: `docs/generated/012/code-review-2026-07-15-sync-jsonl-lww.md`
- 触发规则：sync_client.py JSONL LWW 分流逻辑变更审查时查看
- 内容摘要：sync_client.py Phase 2c-1 冲突解决分流逻辑（JSONL→LWW、MD→AI 合并）+ ADR v2.1→v2.2 的代码审查报告，覆盖 8 个维度，发现 4 个问题（置信度 ≥ 80）：ADR 决策 5 hash 规范化描述与代码冲突（85）、JSONL LWW 分流逻辑无测试覆盖（90）、md_conflicts 命名与实际语义不符（80）、混合冲突场景测试缺失（80）

## code-review-2026-07-16-graceful-shutdown

- updated_at: 2026-07-16
- path: `docs/generated/001/code-review-2026-07-16-graceful-shutdown.md`
- 触发规则：审查优雅关闭功能（打包环境退出、系统关机、睡眠唤醒）代码时查看
- 内容摘要：优雅关闭功能的 8 维度代码审查报告。审查 4 个文件（+493 -27 行），发现 9 个问题（置信度 ≥ 80）：1 个 P0 致命缺陷（`net.isOnline()` 不存在导致唤醒同步功能失效）、2 个 P1 架构问题（uvicorn 超时打断 sync_once、无认证端点）、6 个 P2 代码质量/竞态问题。设计核心：参考思源笔记的三场景区分（用户退出含同步、Windows 关机跳过同步、唤醒后触发同步）。

## 2026-07-16-code-review-dynamic-tables-sync

- updated_at: 2026-07-16
- path: `docs/generated/013/2026-07-16-code-review-dynamic-tables-sync.md`
- 触发规则：审查动态表同步定义对比方案实现（新增 GET /dynamic-tables-definitions 端点、_sync_dynamic_tables_definitions、_create_local_dynamic_tables、删除 get_all_sync_tables）时查看
- 内容摘要：动态表同步定义对比方案的 8 维度代码审查报告。审查 4 个文件（+196 -193 行），ADR 决策在代码中均正确落地。无 High 级问题达到 80 分阈值，但记录 3 个 75 分观察项（_rebuild_remote_dynamic_tables docstring 与实际调用时机不符、_create_local_dynamic_tables 违反导入纪律、_create_local_dynamic_tables 完全无测试）和 6 个 70 分低优先级改进项（核心方法缺少单元测试、双向建表分支无测试覆盖、spec 未同步更新、ADR 返回结构描述不符、sync_client 直接执行 SQL）。

## 2026-07-17-code-review-cloud-init-first-sync

- updated_at: 2026-07-17
- path: `docs/generated/014/2026-07-17-code-review-cloud-init-first-sync.md`
- 触发规则：审查云端首次同步全清覆盖方案实现（bootstrap agent_only 跳过、3 个新 API 端点、sync_once 首次同步分支、5 个首次同步方法、query_all/delete_all_rows）时查看
- 内容摘要：云端首次同步全清覆盖方案的 8 维度代码审查报告。审查 7 个文件（+594 -79 行），ADR 5 个阶段全部合规。发现 12 个问题（置信度 ≥ 50），其中 10 个已直接修复（2 个 P0：N+1 查询、重复扫描；5 个 P1：私有方法访问、RuntimeError、魔法数字、未告警、异常范围；3 个 P2：空目录清理、docstring 修正、注释修正），2 个需要用户决策（测试覆盖、类职责膨胀）。

## 2026-07-18-code-review-conflict-resolution-backup

- updated_at: 2026-07-18
- path: `docs/generated/015/2026-07-18-code-review-conflict-resolution-backup.md`
- 触发规则：审查文件冲突解决重设计 + BackupService 平铺备份方案（commit `11230c56`，40 文件 +11380/-449 行）时查看
- 内容摘要：文件冲突解决重设计 + BackupService 平铺备份方案的 8 维度代码审查报告。审查 10 个核心代码文件，4 个 ADR 完整覆盖。发现 10 个问题（置信度 ≥ 80）：1 个死代码（`_build_resolve_prompt` 未调用，90）、1 个架构不一致（BackupService 未用 LazySingleton，85）、1 个异常处理违规（`except Exception` 捕获标准库异常 + 缺 `exc_info`，85）、2 个测试缺口（`_fetch_remote_base_content` 无测试 + 多冲突块串行替换边界未覆盖，85）、1 个 ADR 引用错误（`agent_only` 不备份归因到错误 ADR，95）、2 个文档与代码不符（sync_conflict 清理机制 + 冲突降级范围描述错误，90）、1 个过时注释（diff3.py docstring 仍写"Issue 4 将扩展"但已实现，85）、1 个边界测试缺失（清理 `>` vs `>=` off-by-one，80）。

## 2026-07-18-code-review-scratch-specs

- updated_at: 2026-07-18
- path: `docs/generated/016/2026-07-18-code-review-scratch-specs.md`
- 触发规则：审查 `.scratch/file-conflict-resolution-redesign/` 中的 PRD + Issue 规格文档（9 个 spec 文件 + 实现对齐）时查看
- 内容摘要：File Sync Conflict Resolution Redesign 规格文档审查。检查 9 个 spec 文件与 20 个 PRD 决策的实现对齐。发现 5 个文档问题（置信度 >= 80）：PRD decision 19 代码示例与目录图自相矛盾（90）、Issue 5 Blocked by 遗漏 Issue 4 依赖标注（85）、file_path_str 推导规则未显式定义（80）、Issue 7 包结构决策未记录（80）、Issue 1 BOM 边界未讨论（80）。20/20 决策在实现中全部正确落地，无 spec-实现不一致。

## utc-migration-audit-report
- updated_at: 2026-07-12
- path: `docs/generated/utc-migration-audit-report.md`
- 触发规则：UTC 时区迁移项目 Issue #19 审核时查看
- 内容摘要：UTC 时区迁移项目（Issue #1-#16）的迁移结果审核报告。代码迁移和测试全部通过（199 个测试通过），但 m008/m009 迁移脚本存在 4 个 bug（PRIMARY KEY、CHECK 约束、空名表、带引号表名），且测试数据库未实际应用迁移。审核结论为"审核失败（附条件通过）"，暂不批准进入生产环境迁移。
