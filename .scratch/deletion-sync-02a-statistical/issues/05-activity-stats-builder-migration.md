---
title: 迁移 activity_stats_builder 统计方法（4 个方法 + 业务逻辑上移）
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02a-statistical/prd.md`（同步删除 - 阶段 2a：StatisticalDataProviders 迁移 P5）

## What to build

将 `lifeprism/server/services/activity_stats_builder.py` 中 4 个统计方法的调用从 `server_lw_data_provider` 迁移到 `ComputerUsageProvider` 新增方法（Slice 2），同时将 3 类业务逻辑从 Provider 层上移到 Service 层。

迁移清单：

1. **`get_daily_active_time`**（activity_stats_builder.py 约 line 120-185，被 `build_activity_summary` 调用）：原调用 `server_lw_data_provider.get_daily_active_time(start_date, end_date)`，改为 `computer_usage_repository.load_user_app_behavior_log(start_time, end_time)` 取 DataFrame + Service 层 Python 聚合。

   **业务逻辑 1 — 时区转换**（原在 Provider 内部 `utc_to_local_display`）：上移到 `activity_stats_builder.build_activity_summary`，复用已有的 `_add_local_date_column`（activity_stats_builder.py line 75-98）。

   **业务逻辑 2 — 百分比计算**（原 `int(total_duration * 100 / 86400)`，statistical_data_providers.py line 263）：上移到 Service 层。迁移后流程：`load_user_app_behavior_log` → `_add_local_date_column` → `df.groupby("local_date")["duration"].sum()` → `int(total_duration * 100 / 86400)`。

2. **`get_active_time`**（activity_stats_builder.py 约 line 310, 340，被 `get_top_app` / `get_top_title` 调用）：原调用 `server_lw_data_provider.get_active_time(date)`，改为 `computer_usage_repository.get_total_duration(start_utc, end_utc)`。**时区转换上移**：`start_utc, end_utc = build_utc_time_range(date)`（`build_utc_time_range` 已在 activity_stats_builder.py line 204 导入并使用）。

3. **`get_top_applications`**（activity_stats_builder.py 约 line 339，被 `get_top_app` 调用）：原调用 `server_lw_data_provider.get_top_applications(date, top_n)`，改为 `computer_usage_repository.get_top_groups_by_duration("app", start_utc, end_utc, top_n)`。**时区转换 + 字段名映射上移**：Provider 返回 `list[tuple[str, int]]`，Service 层解包 tuple 构建 `TopAppData`。

4. **`get_top_title`**（activity_stats_builder.py 约 line 309，被 `get_top_title` 调用）：同上，`group_field` 传 `"title"`，返回类型 `TopTitleData`。

迁移后 `get_top_app` / `get_top_title` 的实现应参照 PRD 中上移点 5 的代码示例：`build_utc_time_range` → `get_top_groups_by_duration` + `get_total_duration` → tuple 解包 + 百分比计算 → `TopAppData` / `TopTitleData`。

迁移后 `server_lw_data_provider` 的导入暂不清理（留给 Slice 6 统一清理）。

## Acceptance criteria

- [ ] `build_activity_summary` 改用 `load_user_app_behavior_log` + Service 层 Python 聚合（复用 `_add_local_date_column`）
- [ ] `get_top_app` 改用 `get_top_groups_by_duration("app", ...)`
- [ ] `get_top_title` 改用 `get_top_groups_by_duration("title", ...)`
- [ ] `get_top_app` / `get_top_title` 中的 `get_active_time` 调用改用 `get_total_duration`
- [ ] 时区转换上移到 Service 层（`build_utc_time_range` 已导入复用）
- [ ] 百分比计算上移到 Service 层
- [ ] 字段名映射上移到 Service 层（tuple 解包替代 dict 访问）
- [ ] **跨时区测试通过**：UTC 20:00 的活动归属本地次日（必须包含此用例）
- [ ] `get_top_app` / `get_top_title` 百分比计算正确
- [ ] 现有测试全部通过（无回归）
- [ ] API 端点 `/activity/stats` 返回数据结构一致

## Blocked by

- `.scratch/deletion-sync-02a-statistical/issues/02-computer-usage-provider-gap-methods.md`（需新增的 `get_total_duration` / `get_top_groups_by_duration`）
