# Code Review Report

**审查范围**: `.scratch/custom-records-module/PRD-P3.md` 对应实现（前端记录 CRUD — 新增/编辑记录）
**审查时间**: 2026-08-19
**变更文件**: 10 个（后端 4 + 前端 5 + 测试 1），+1101/-59 行

| 端 | 文件 | 变更 |
|---|------|------|
| 后端 | `lifeprism/repository/aggregators/custom_record_aggregator.py` | 新增 `update_entry`（+145 行） |
| 后端 | `lifeprism/server/api/custom_records_api.py` | 新增 `PATCH /{type_id}/entries/{entry_id}`（+25） |
| 后端 | `lifeprism/server/schemas/custom_records_schemas.py` | 新增 `UpdateCustomRecordEntryRequest`（+27） |
| 后端 | `lifeprism/server/services/custom_records_service.py` | 新增 `update_entry` 薄包装（+72） |
| 前端 | `frontend/apps/custom-records/components/EntryForm.tsx` | 新增 Modal 组件 |
| 前端 | `frontend/apps/custom-records/utils/entryFormPayload.ts` | 新增 payload 工具 |
| 前端 | `frontend/apps/custom-records/api.ts` | 新增 `updateEntry`（+15） |
| 前端 | `frontend/apps/custom-records/types.ts` | 新增 `UpdateCustomRecordEntryRequest`（+22） |
| 前端 | `frontend/apps/custom-records/components/EntryCard.tsx` | 新增 `onEdit` prop（+33） |
| 前端 | `frontend/apps/custom-records/components/TypeDetailView.tsx` | 添加/编辑按钮 + EntryForm 集成（+160/-59） |
| 测试 | `test/core/integration/repository/test_custom_records_repository.py` | 新增 `TestUpdateEntry` 18 用例（+661） |

## 架构上下文

### 相关 ADR
- [ADR 2026-07-06-custom-records-storage](../../adr/2026-07-06-custom-records-storage.md) (accepted) — 动态表 + meta 表存储方案
- [ADR 2026-07-13-custom-records-time-string-not-convert](../../adr/2026-07-13-custom-records-time-string-not-convert.md) (accepted) — 时间字符串不做时区转换（就地存储）

### 相关 Spec
- `docs/specs/custom-records-module.md` (v1.1) — 自定义记录模块技术契约
- `docs/coding-rules/backend-api-rules.md` — PATCH 三态语义（本次实现的核心对齐基准）

### 决策覆盖
- 5/5 变更文件有文档化决策关联（PRD 自述三态语义设计偏离见 PRD-P3.md 96-100 行）
- 实现严格遵循 PRD 的"前端 diff + 后端 Repository 三态"折中方案，无未记录架构决策

## 审查结果

Found 3 issues:

### Issue 1: update_entry 复制 create_entry 校验逻辑，未真正"复用"
- **类型**: Code Quality
- **置信度**: 80
- **位置**: `lifeprism/repository/aggregators/custom_record_aggregator.py:899-970`（update_entry）
- **详情**: PRD 系统行为 27 明确要求"`update_entry` 应复用 `create_entry` 的字段校验逻辑（field_key 校验 + 类型校验 + valid_fields 构造）"，但实现是把 `create_entry` 中约 45 行校验代码（invalid_keys 检查 + valid_fields 构造 + `_coerce_field_value` 循环 + INVALID_FIELD_VALUE 块）**原样复制**而非提取共享辅助方法。两处代码块逐行几乎一致。
- **依据**: 比对 `create_entry`（第 501-553 行）与 `update_entry`（第 899-970 行）——重复块包括 INVALID_FIELD_KEY 分支的 `valid_fields` 构造、INVALID_FIELD_VALUE 分支的 `invalid_fields` 构造。P2 曾给 create_entry 添加 `_coerce_field_value` 校验（变更 3c4ea2fb），本次直接拷贝，未来新增字段类型或调整校验行为需改动两处，存在分歧风险。

### Issue 2: update_entry 在 with 块内抛 EntityNotFoundError，与 delete_entry 既有模式不一致
- **类型**: Code Quality
- **置信度**: 80
- **位置**: `lifeprism/repository/aggregators/custom_record_aggregator.py:996-1000`
- **详情**: `delete_entry` 刻意将 `EntityNotFoundError` 在 with 块外抛出并注明"避免连接以未 commit/rollback 状态归还池"（第 843-845 行）。`update_entry` 则在 `with self.db.get_connection() as conn:` 块内直接 raise。`get_connection` 上下文管理器只在 `sqlite3.Error` 时 rollback，其他异常仅通过 finally 归还连接、不 commit/rollback（`database_manager.py:150-187`）。当前实际影响极低（raise 前仅执行 SELECT，SQLite 对 SELECT 不开启写事务），但偏离本文件自身记录的模式约定，若后续在存在性检查前增加写操作会变为真实隐患。
- **依据**: 同文件 `delete_entry` 843-845 行注释 + `get_connection` 异常路径实现。

### Issue 3: 添加/编辑记录成功后未重置页码，多页场景下新记录不可见
- **类型**: 与 PRD User Story 符合性
- **置信度**: 80
- **位置**: `frontend/apps/custom-records/components/TypeDetailView.tsx:78-80`（handleEntryFormSuccess）
- **详情**: PRD User Story 6 要求"提交表单后新记录出现在列表顶部（按 event_time 倒序）并刷新总数"。`handleEntryFormSuccess` 只调用 `loadData()`，未 `setPage(1)`；`loadData` 依赖当前 `page` 状态（第 99、133 行）。当列表超过 20 条（pageSize=20）且用户位于第 2+ 页时，新增记录排到第 1 页顶部，当前页刷新后看不到新记录。同理，编辑 event_time 使记录跨页移动时（User Story 18），记录可能从当前页消失。常见场景（第 1 页）不受影响。
- **依据**: `TypeDetailView.tsx:78-80` + `loadData` 依赖 `page`（第 99、133 行）+ pageSize=20（第 97 行）。

## 已验证但未达阈值的观察（低置信度，供参考）

- **create 模式显示"事件时间"控件但静默忽略**（~55）：EntryForm create 模式渲染 datetime-local 并标注"(可选，create 不生效)"，但提交时丢弃。这是 PRD Out of Scope 的**明确设计决策**（避免改 P1 schema），非缺陷；仅提示用户可能输入了不生效的时间。
- **编辑 event_time 秒级精度丢失**（~40）：datetime-local 仅分钟精度，用户显式修改 event_time 后 `toISOStringUTC(new Date(eventTime))` 将秒截断为 0（分钟级编辑的合理取舍）。
- **Service `else None` 潜在 500**（~50）：`update_entry` 返回 `_convert_to_entry_item(entry_dict) if entry_dict else None`，若并发删除导致 UPDATE 与 GET 之间记录消失，返回 None 会触发 response_model 校验 500；概率极低且无测试路径。

## 验证执行

- ✅ `pytest test/core/integration/repository/test_custom_records_repository.py -k UpdateEntry` → 18 passed
- ✅ 全文件 `pytest` → 84 passed（66 个 P1/P2 回归 + 18 个 P3，无破坏）
- ✅ 前端 `tsc --noEmit` → custom-records 文件 **0 错误**（其余 9 个错误均在未修改的 goals/category/timeline/floating 模块，为预先存在，超出范围）
- ✅ 三态语义链路核对：前端 diff（`entryFormPayload.ts` buildUpdatePayload）→ Service `model_dump(exclude_unset=True)` → Repository 按 key 进入 SET 子句，None 值跳过 `_coerce_field_value` 直接写 NULL——符合 PRD 96-100 行设计偏离说明
- ✅ 动态列名注入防护：SET 子句的列名均经 valid_keys 白名单校验（valid_keys 源自受 `_FIELD_KEY_PATTERN` 约束的字段定义），无注入面
- ✅ 错误分层：Repository 抛 `ValidationError`/`EntityNotFoundError`，API 层无 try/except（符合 lifeprism/CLAUDE.md 错误处理规则），全局异常处理器映射 422/404

## 变更摘要

P3 按 PRD 实现自定义记录前端"C"+"U"两环：后端 Repository 新增 `update_entry`（PATCH 三态语义，SELECT 存在性校验 + 动态 SET + 自动刷 updated_at），Service 薄包装（`model_dump(exclude_unset=True)` 区分顶层三态 + 显式拒绝 data/event_time 传 null），Schema 新增 `UpdateCustomRecordEntryRequest`，API 新增 `PATCH /{type_id}/entries/{entry_id}` 端点；前端新增 `EntryForm` Modal（create/edit 双模式、动态字段控件、datetime-local 事件时间）、`entryFormPayload.ts`（buildCreatePayload / buildUpdatePayload diff）、`EntryCard` 的 `onEdit` prop、`TypeDetailView` 的添加/编辑入口串联。测试按 PRD 测试表覆盖 18 个行为用例，全部通过。

整体实现与 PRD 高度一致：三态语义落地正确、无新增 LLM tool、字段定义不可改、P1/P2 无回归。3 个发现均为中低风险的质量/一致性/边界符合性问题，不阻塞合入，建议按优先级修复 Issue 3（一行 `setPage(1)`）与 Issue 1（提取共享校验方法），Issue 2 顺手对齐 delete_entry 模式。
