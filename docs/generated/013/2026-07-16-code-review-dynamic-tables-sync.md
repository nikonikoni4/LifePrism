# Code Review Report

**审查范围**: 本次会话修改的 4 个文件（动态表同步定义对比方案实现）
**审查时间**: 2026-07-16
**变更文件**:
- `lifeprism/server/api/sync_cloud_api.py` (+24)
- `lifeprism/sync/sync_client.py` (+191 改动)
- `test/core/integration/sync/test_sync_client.py` (+8)
- `test/core/integration/sync/test_sync_table_expansion.py` (-148)

## 架构上下文

### 相关 ADR
- `docs/ADR/2026-07-16-dynamic-tables-sync-definition-comparison.md` (decided) — 本次变更的主 ADR，决策采用"拉取云端定义 → 本地 slug 对比 → 双向建表"方案
- `docs/ADR/2026-07-14-file-sync-conflict-resolution.md` (decided) — 前提 2 主备模式继承自此
- `docs/ADR/2026-07-09-lww-conflict-resolution.md` (decided) — pull 阶段 LWW 逻辑
- `docs/ADR/2026-07-14-sync-full-sync-strategy.md` (decided) — 全量同步策略

### 相关 Spec
- `docs/specs/2026-07-11-data-sync-spec.md` (draft) — 数据同步规格，**需同步更新**（见观察项 O1, O2）
- `docs/specs/custom-records-module.md` (v1.1) — 自定义记录模块规格

### 决策覆盖
- 4/4 变更文件有 ADR 关联
- ADR 决策（新增端点、删除 get_all_sync_tables、流程顺序、不写 meta、全量发送）在代码中均正确落地

## 审查结果

按 skill 规则过滤分数 < 80 的问题后，**无 High 级问题达到报告阈值**。但存在 3 个 75 分的观察项值得记录（接近阈值且是本次 diff 引入的真实问题），以及若干 70 分的低优先级改进项。

### 观察项（75 分，接近阈值，建议关注）

#### O1: `_rebuild_remote_dynamic_tables` docstring 与实际调用时机不符（75 分）
- **类型**: Documentation
- **位置**: `lifeprism/sync/sync_client.py:426-427`
- **详情**: docstring 写"pull 后检测到 custom_record_types meta 表有变更时调用"，但实际调用时机已改为 **pull 之前**——由 `_sync_dynamic_tables_definitions`（在 sync_once 中 pull 之前调用）的步骤 3b 触发。docstring 描述的"pull 后"与实际"pull 前"相反，且"检测到 meta 表有变更"的描述也已过时（实际是 slug 集合差集判定）。
- **依据**: 本次 diff 修改了 `_rebuild_remote_dynamic_tables` 的调用上下文（从 pull 后移到 pull 前），但未同步更新该方法的 docstring

#### O2: `_create_local_dynamic_tables` 违反导入纪律（75 分）
- **类型**: Architecture
- **位置**: `lifeprism/sync/sync_client.py:392-394`
- **详情**: `from lifeprism.repository.aggregators.custom_record_aggregator import CustomRecordRepository` 违反 `docs/coding-rules/repository-module-rules.md` §2.2"外部调用方只能从 `lifeprism.repository` 导入"。`lifeprism/repository/__init__.py` 已导出相关 repository，应通过统一出口调用。
- **依据**: `docs/coding-rules/repository-module-rules.md` §2.2 明确规定；本次 diff 新增的代码违反此规则

#### O3: `_create_local_dynamic_tables` 完全无测试（75 分）
- **类型**: Testing
- **位置**: `lifeprism/sync/sync_client.py:372-422`（实现）；测试文件中无任何调用
- **详情**: 该方法是本次修复的核心新增能力之一（云端有本地没有时本地建表），但无任何测试覆盖。关键路径未覆盖：多个 slug 批量建表、slug → fields 映射查找、sqlite3.Error 异常包装、"只执行 DDL 不写 meta"的契约验证。
- **依据**: AGENTS.md 核心规则 5"Bug 先测试：修 bug 先写复现测试"；本次 diff 是 bug 修复，但无对应的复现测试和新增方法测试

### 低优先级改进项（70 分，可选处理）

#### L1: `_sync_dynamic_tables_definitions` 核心方法缺少单元测试（70 分）
- **类型**: Testing
- **位置**: `lifeprism/sync/sync_client.py:295-370`
- **详情**: 仅有 `test_sync_once_uses_default_tables_when_none` 间接覆盖（mock 空_types），未覆盖 slug 集合对比、双向建表触发、返回值正确性

#### L2: "云端有本地没有"和"本地有云端没有"两个方向均无测试覆盖（70 分）
- **类型**: Testing
- **位置**: `lifeprism/sync/sync_client.py:354-366`（双向建表分支）
- **详情**: ADR 明确要求双向建表，但两个方向的分支均无测试覆盖

#### L3: spec 中 `get_all_sync_tables` 已删除但仍列在 key_function 中（70 分）
- **类型**: Documentation
- **位置**: `docs/specs/2026-07-11-data-sync-spec.md:159`
- **详情**: spec 第 159 行仍列 `sync_client.SyncClient.get_all_sync_tables:178`，但该方法已按 ADR 决策删除

#### L4: spec 中未列出新增的 `GET /api/sync/dynamic-tables-definitions` 端点（70 分）
- **类型**: Documentation
- **位置**: `docs/specs/2026-07-11-data-sync-spec.md:185-191`（API 端点表）
- **详情**: spec 的 API 端点表缺少新增的 `GET /api/sync/dynamic-tables-definitions`

#### L5: ADR 中端点返回结构与实际代码不符（55 分）
- **类型**: Documentation
- **位置**: `docs/ADR/2026-07-16-dynamic-tables-sync-definition-comparison.md:135`
- **详情**: ADR 写"返回 `{types: [...], fields: [...]}`"，但实际代码返回 `{"types": types}`（types 内嵌 fields）

#### L6: `_create_local_dynamic_tables` 在 sync_client 中直接执行 SQL（70 分）
- **类型**: Architecture
- **位置**: `lifeprism/sync/sync_client.py:400-411`
- **详情**: 违反 `sync_client.py` 模块 docstring"不直接执行 SQL，所有数据库操作通过 SyncRepository"。建议将 DDL 执行下沉到 Repository 层
- **注意**: 该问题与 O2 关联，若重构 O2 时一并处理可解决此问题

## 变更摘要

本次变更实现了 ADR `2026-07-16-dynamic-tables-sync-definition-comparison.md` 的决策：采用"拉取云端定义 → 本地 slug 对比 → 双向建表"方案替代原"pull 前后快照对比"方案，修复了动态表同步每次都触发无意义重建请求的 bug。

核心改动：
1. 新增 `GET /api/sync/dynamic-tables-definitions` 端点（云端返回动态表定义）
2. 新增 `_sync_dynamic_tables_definitions` 方法（拉取云端定义 + 本地 slug 对比 + 双向建表 + 产出动态表列表）
3. 新增 `_create_local_dynamic_tables` 方法（本地建表只执行 DDL，不写 meta）
4. 修改 `sync_once` 主流程（动态表对比前置到 pull 之前）
5. 删除 `get_all_sync_tables` 方法（动态表列表由建表步骤产出）
6. 更新测试（mock 新端点、删除已废弃方法的测试）

测试结果：44 个相关测试全部通过，ruff 检查全部通过。
