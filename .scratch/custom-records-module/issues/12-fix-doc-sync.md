# 文档同步 — ADR 更新 + Spec 编写

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Code Review**: `docs/generated/002/code-review-2026-07-07-2145.md` Issues 8, 12, 15（置信度 80-90）

## What to build

同步 3 个文档问题，使 ADR 和 spec 与实际实现保持一致。

端到端行为：
1. 更新 ADR `2026-07-06-custom-records-storage.md` 反映实际架构决策（放弃 LWBaseDataProvider 继承的原因 + Slice 6 新增字段）
2. 编写自定义记录模块 spec 文档，收录到 `docs/specs/index.md`
3. 更新 `docs/ARCHITECTURE.md` 增加自定义记录模块记录

## Acceptance criteria

- [ ] ADR "方案 B 优点"和"决策影响"章节移除"复用 LWBaseDataProvider 模式"描述
- [ ] ADR 新增"实现偏差说明"章节，解释为何 `CustomRecordRepository` 独立实现（动态表名运行时确定）
- [ ] ADR Meta 表结构更新：`custom_record_types` 增加 card_template/icon/accent_color 列
- [ ] ADR Meta 表结构更新：`custom_record_fields` 增加 display_role 列
- [ ] ADR 明确 `display_role` 属于展示配置可变，不违反"字段定义后不可变"约束
- [ ] `docs/specs/index.md` 新增自定义记录模块 spec 条目
- [ ] spec 文档包含模块概述、数据模型、API 端点、L1/L2/L3 布局引擎设计
- [ ] `docs/ARCHITECTURE.md` 新增自定义记录模块章节

## Blocked by

- `.scratch/custom-records-module/issues/08-fix-field-role-persistence.md`（ADR 需反映 FieldDefinition 含 id 字段的最终状态）
- `.scratch/custom-records-module/issues/09-fix-backend-robustness.md`（ADR 需反映枚举校验和 updated_at 修复后的最终状态）
