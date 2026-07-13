# Known Limitations（已知限制）

本目录记录系统当前已知的限制、约束和未解决的问题。

## 索引

### 1. 时间格式不一致导致 SQL 字符串比对丢失数据

- **文件**: `time-format-iso-vs-space-in-db-queries.md`
- **状态**: `mitigating`（sync_service.py 已修复，screen_capture_provider / category_service 待修复）
- **严重程度**: 高
- **影响范围**: 截图分析、截图查询、分类统计
- **问题描述**: 部分代码将 UTC ISO 8601 格式（`T` 分隔符）转为空格格式后直接用于 SQL 查询，SQLite 字符串比对 `T(84) > 空格(32)` 导致数据被静默排除
- **修复计划**: `sync_service.py` 已修复，其余待排期

### 2. Mood Entries 和 Custom Records 日期查询问题

- **文件**: `mood-and-custom-records-date-query-issues.md`
- **状态**: `acknowledged`（已确认但尚未修复）
- **严重程度**: 中
- **影响范围**: Mood Entries API、Custom Records API
- **问题描述**: 表中缺少独立 `date` 字段，只有 `created_at/updated_at` datetime 字段，导致按日期查询需要后端时区转换，无法建立日期索引，查询效率低
- **触发条件**: 数据量超过 10 万条或查询响应时间超过 1 秒时需重构
- **临时方案**: 当前使用 `build_utc_time_range()` 转换，功能正确但效率低

> 时区和时间格式不一致问题已于 2026-07-12 通过 UTC 时区迁移解决，相关规范见 `docs/coding-rules/time-handling-rules.md`，决策见 `docs/adr/2026-07-12-migrate-to-utc-timezone.md`。

## 说明

已知限制文档用于：
1. **透明记录**：明确系统当前的技术债和设计约束
2. **风险管理**：帮助开发者了解潜在风险，避免引入新问题
3. **修复规划**：为未来的改进提供清晰的问题清单

## 文档格式

每个限制文档应包含：
- **问题描述**：清晰说明限制是什么
- **影响范围**：哪些功能受影响，严重程度如何
- **当前假设**：系统依赖的脆弱前提
- **相关文档**：指向调查报告、ADR 等
- **注意事项**：开发时需要注意的事项

## 状态说明

- `acknowledged`：已确认但尚未修复
- `mitigating`：正在实施缓解措施
- `planned`：已纳入修复计划
- `resolved`：已解决（归档到 history）
