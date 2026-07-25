---
title: 删除 statistical_data_providers.py 中 11 个死代码方法
created_at: 2026-07-23
status: ready-for-agent
---

## Parent

`.scratch/deletion-sync-02a-statistical/prd.md`（同步删除 - 阶段 2a：StatisticalDataProviders 迁移 P5）

## What to build

删除 `lifeprism/server/providers/statistical_data_providers.py` 中 11 个无任何调用方的死代码方法，以及 `__main__` 测试块（调用了不存在的方法 `get_timeline_events_by_date`）。

11 个死代码方法清单：

| # | 方法名 | 死代码原因 |
|---|--------|-----------|
| 1 | `get_range_active_time` | 无调用方 |
| 2 | `get_category_stats` | 已被 `CategoryService.get_category_stats` 替代 |
| 3 | `get_app_usage_summary` | 无调用方 |
| 4 | `get_tokens_usage` | 无调用方 |
| 5 | `get_all_tokens_usage` | 无调用方 |
| 6 | `get_tokens_usage_by_mode` | 仅被 `get_all_tokens_usage_by_mode` 内部调用（也是死代码） |
| 7 | `get_all_tokens_usage_by_mode` | 无调用方 |
| 8 | `update_category_map_cache_by_id` | 已被 `map_cache_repository` 替代 |
| 9 | `batch_update_category_map_cache_by_ids` | 已被 `map_cache_repository` 替代 |
| 10 | `delete_category_map_cache_by_id` | 已被 `map_cache_repository` 替代 |
| 11 | `batch_delete_category_map_cache_by_ids` | 已被 `map_cache_repository` 替代 |

此切片为纯删除，不修改任何调用方，不碰业务使用的 10 个方法。删除后通过 grep 验证无残留引用。

**同时补基线测试**（PRD "Testing Decisions > 测试策略" 要求）：在删除死代码后，为保留的 10 个业务使用方法补基线测试，记录当前行为，作为后续 Slice 03/04/05 迁移后的行为等价性对比基准。

基线测试位置：`test/core/unit/services/test_statistical_data_providers_baseline.py`

10 个需补基线测试的方法：
1. `get_activity_log_by_id`
2. `update_event_category`
3. `delete_event`
4. `get_daily_active_time`
5. `batch_update_event_category`
6. `batch_delete_events`
7. `update_logs_by_app_title`
8. `get_active_time`
9. `get_top_applications`
10. `get_top_title`

## Acceptance criteria

- [ ] 11 个死代码方法已从 `statistical_data_providers.py` 中删除
- [ ] `__main__` 测试块已删除
- [ ] grep 验证：全仓无对这 11 个方法的残留引用
- [ ] `statistical_data_providers.py` 中仅保留 10 个业务使用方法
- [ ] **基线测试已补齐**：`test/core/unit/services/test_statistical_data_providers_baseline.py` 覆盖 10 个业务使用方法，记录当前行为作为迁移对比基准
- [ ] 基线测试包含跨时区用例（UTC 20:00 → 本地次日，验证 `get_daily_active_time` 时区分组正确性）
- [ ] 现有测试全部通过（无回归）

## Blocked by

None - can start immediately（纯删除，无依赖）
