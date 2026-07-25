---
title: 清理 activity_service.py 和 activity_stats_builder.py 的 server_lw_data_provider 导入
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02a-statistical/prd.md`（同步删除 - 阶段 2a：StatisticalDataProviders 迁移 P5）

## What to build

在所有调用方迁移完毕（Slice 03/04/05）后，清理 `activity_service.py` 和 `activity_stats_builder.py` 中已不再使用的 `server_lw_data_provider` 导入。

**清理范围严格限定**（重要：不要扩大范围）：

仅清理以下 2 个文件中的 `server_lw_data_provider` 导入：
1. `lifeprism/server/services/activity_service.py`
2. `lifeprism/server/services/activity_stats_builder.py`

**不在本切片范围内的事项**（属于另一个故事——基类 11 个遗留方法迁移）：
- ❌ 不删除 `lifeprism/server/providers/statistical_data_providers.py` 文件本身
- ❌ 不清理 `lifeprism/server/providers/__init__.py` 中 `server_lw_data_provider` 的导入和导出
- ❌ 不要求全仓 grep 无 `server_lw_data_provider` 残留引用

**原因**：`category_service.py` 和 `data_processing_service.py` 仍依赖 `server_lw_data_provider` 调用基类遗留方法（`load_categories`、`load_sub_categories`、`load_category_map_cache_V2` 等），这些方法属于 PRD 的 "Out of Scope"（基类 11 个遗留方法属于另一个故事）。若本切片删除文件或清理 `__init__.py` 导出，将立即导致这两个 service ImportError / AttributeError，后端启动失败。

## Acceptance criteria

- [ ] `activity_service.py` 中 `server_lw_data_provider` 的导入已移除
- [ ] `activity_stats_builder.py` 中 `server_lw_data_provider` 的导入已移除
- [ ] grep 验证：`activity_service.py` 中无 `server_lw_data_provider` 残留引用
- [ ] grep 验证：`activity_stats_builder.py` 中无 `server_lw_data_provider` 残留引用
- [ ] **不要求**全仓 grep 无残留（`category_service.py` / `data_processing_service.py` / `server/providers/__init__.py` 仍有合法引用）
- [ ] 现有测试全部通过（无回归）
- [ ] 后端服务可正常启动（无 ImportError）
- [ ] P5 中本 PRD 范围内的 User Story（22-24 中的"清理调用方导入"部分）已完成

## Blocked by

- `.scratch/deletion-sync-02a-statistical/issues/01-delete-dead-code.md`
- `.scratch/deletion-sync-02a-statistical/issues/02-computer-usage-provider-gap-methods.md`
- `.scratch/deletion-sync-02a-statistical/issues/03-activity-service-single-record-migration.md`
- `.scratch/deletion-sync-02a-statistical/issues/04-activity-service-batch-migration.md`
- `.scratch/deletion-sync-02a-statistical/issues/05-activity-stats-builder-migration.md`

## Notes

PRD 阶段 4 验收标准中的"删除 `statistical_data_providers.py` 文件"和"清理 `server/providers/__init__.py` 中 `server_lw_data_provider`"两项**不在本 PRD 范围内**，推迟到基类 11 个遗留方法迁移完成后执行（另一个故事）。本切片仅完成"清理 `activity_service.py` / `activity_stats_builder.py` 的导入"这一项。
