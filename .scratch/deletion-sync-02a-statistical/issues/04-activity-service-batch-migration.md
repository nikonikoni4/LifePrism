---
title: 迁移 activity_service 批量操作（3 个方法 + 业务逻辑上移）
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02a-statistical/prd.md`（同步删除 - 阶段 2a：StatisticalDataProviders 迁移 P5）

## What to build

将 `lifeprism/server/services/activity_service.py` 中 3 个批量操作的调用从 `server_lw_data_provider` 迁移到 `computer_usage_repository` 单例（Slice 02 新增的方法），同时将 2 类业务逻辑从 Provider 层上移到 Service 层。

**导入纪律**：本切片通过 `from lifeprism.repository import computer_usage_repository` 调用（`activity_service.py:8` 已有此导入，复用即可），**禁止**直接从 `lifeprism.repository.providers` 或 `lifeprism.repository.aggregators` 导入。

迁移清单：

1. **`batch_update_log_category`**（activity_service.py 约 line 187）：原调用 `server_lw_data_provider.batch_update_event_category(record_ids, category_id, sub_category_id)`，改为 `computer_usage_repository.batch_update_computer_usage(record_ids, {"category_id":..., "sub_category_id":...})`。

2. **`batch_delete_logs`**（activity_service.py 约 line 200）：原调用 `server_lw_data_provider.batch_delete_events(record_ids)`，改为 `computer_usage_repository.batch_delete_computer_usage(record_ids)`（走 `_generic_batch_delete` 写墓碑）。

3. **`update_logs_by_app_title`**（activity_service.py 的 `update_logs_by_app_title` 函数）：原调用 `server_lw_data_provider.update_logs_by_app_title(...)`，改为 `computer_usage_repository.update_by_filter(set_fields, where_conditions)`。**2 类业务逻辑上移到 Service 层**：

   **业务逻辑 1 — goal_id 三态语义**（原在 `statistical_data_providers.py` 的 `update_logs_by_app_title` 方法内 `if goal_id is not None: ...` 这一段，上移到 `activity_service.update_logs_by_app_title`）：
   - `goal_id is None` → 不修改（不加入 `set_fields`）
   - `goal_id == ""` → 清除（设为 NULL，`set_fields["link_to_goal_id"] = None`）
   - `goal_id == "goal-xxx"` → 设置（`set_fields["link_to_goal_id"] = "goal-xxx"`）

   **业务逻辑 2 — is_multipurpose_app 判断**（原在 `statistical_data_providers.py` 的 `update_logs_by_app_title` 方法内 `if is_multipurpose_app: ...` 这一段，上移到 `activity_service.update_logs_by_app_title`）：
   - `is_multipurpose_app=True` → 必须提供 title，`where_conditions["title"] = title`
   - `is_multipurpose_app=False` → 不加 title 条件

   迁移后 `activity_service.update_logs_by_app_title` 的实现应参照 PRD 中上移点 2 的代码示例：构建 `set_fields`（goal_id 三态）+ 构建 `where_conditions`（is_multipurpose_app + 时间范围）+ 调用 `computer_usage_repository.update_by_filter(set_fields, where_conditions)`。

迁移后 `server_lw_data_provider` 的导入暂不清理（留给 Slice 06 统一清理）。

## Acceptance criteria

- [ ] `activity_service.batch_update_log_category` 改用 `computer_usage_repository.batch_update_computer_usage`
- [ ] `activity_service.batch_delete_logs` 改用 `computer_usage_repository.batch_delete_computer_usage`
- [ ] `batch_delete_logs` 迁移后批量删除时写墓碑到 `deletion_log` 表（N 条记录对应 N 条墓碑）
- [ ] `activity_service.update_logs_by_app_title` 改用 `computer_usage_repository.update_by_filter`
- [ ] `update_logs_by_app_title` 的 goal_id 三态语义正确保留：None=不修改 / ""=清除为 NULL / "goal-xxx"=设置值
- [ ] `update_logs_by_app_title` 的 is_multipurpose_app 判断正确：True=加 title 条件 / False=不加
- [ ] 调用方通过 `computer_usage_repository.xxx(...)` 调用，未直接导入 `lifeprism.repository.providers` 或 `lifeprism.repository.aggregators`
- [ ] 单元测试覆盖 goal_id 三态语义（3 个用例）
- [ ] 单元测试覆盖 is_multipurpose_app 两种情况
- [ ] 现有测试全部通过（无回归）

## Blocked by

- `.scratch/deletion-sync-02a-statistical/issues/02-computer-usage-provider-gap-methods.md`（需新增的 `batch_update_computer_usage` / `batch_delete_computer_usage` / `update_by_filter`）
