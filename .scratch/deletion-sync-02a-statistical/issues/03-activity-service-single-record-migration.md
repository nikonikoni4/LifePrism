---
title: 迁移 activity_service 单记录操作（3 个方法）
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02a-statistical/prd.md`（同步删除 - 阶段 2a：StatisticalDataProviders 迁移 P5）

## What to build

将 `lifeprism/server/services/activity_service.py` 中 3 个单记录操作的调用从 `server_lw_data_provider` 迁移到 `computer_usage_repository` 单例，这 3 个方法均可使用**已存在**的 repository 方法，无需等待 Slice 02 的新增方法。无业务逻辑上移。

**导入纪律**：本切片通过 `from lifeprism.repository import computer_usage_repository` 调用（`activity_service.py:8` 已有此导入，复用即可），**禁止**直接从 `lifeprism.repository.providers` 或 `lifeprism.repository.aggregators` 导入。

迁移清单：

1. **`get_activity_log_detail`**（activity_service.py 约 line 161）：原调用 `server_lw_data_provider.get_activity_log_by_id(log_id)`，改为 `computer_usage_repository.get_computer_usage_by_id_with_names(log_id)`（含 category_name / sub_category_name 关联查询）。

2. **`update_log_category`**（activity_service.py 约 line 182）：原调用 `server_lw_data_provider.update_event_category(record_id, category_id, sub_category_id)`，改为 `computer_usage_repository.update_computer_usage(record_id, {"category_id":..., "sub_category_id":...})`。

   **注意 `updated_at` 行为变化（bug 修复）**：原方法用原生 SQL UPDATE 不更新 `updated_at`，迁移后 `update_computer_usage` 会自动更新 `updated_at`（因 `user_app_behavior_log` 在 `TABLE_CONFIGS` 中配置了 `update_at: true`）。这是 bug 修复——修改分类应触发云端 LWW 同步，原方法不更新 `updated_at` 会导致云端同步漏掉这次修改。迁移后行为正确。

3. **`delete_log`**（activity_service.py 约 line 194）：原调用 `server_lw_data_provider.delete_event(record_id)`，改为 `computer_usage_repository.delete_computer_usage(record_id)`（走 `_generic_delete` 写墓碑到 `deletion_log`）。

迁移后 `server_lw_data_provider` 的导入暂不清理（留给 Slice 06 统一清理）。

## Acceptance criteria

- [ ] `activity_service.get_activity_log_detail` 改用 `computer_usage_repository.get_computer_usage_by_id_with_names`，返回字段一致（含 `category_name` / `sub_category_name`）
- [ ] `activity_service.update_log_category` 改用 `computer_usage_repository.update_computer_usage`
- [ ] `update_log_category` 迁移后 `updated_at` 字段被自动更新（回归验证：修改记录后 `updated_at` 变化）
- [ ] `activity_service.delete_log` 改用 `computer_usage_repository.delete_computer_usage`
- [ ] `delete_log` 迁移后删除时写墓碑到 `deletion_log` 表
- [ ] 调用方通过 `computer_usage_repository.xxx(...)` 调用，未直接导入 `lifeprism.repository.providers` 或 `lifeprism.repository.aggregators`
- [ ] 现有测试全部通过（无回归）
- [ ] API 端点 `/activity/logs/{id}` GET / PATCH / DELETE 行为等价

## Blocked by

None - can start immediately（使用已存在的 repository 方法，不依赖 Slice 02）
