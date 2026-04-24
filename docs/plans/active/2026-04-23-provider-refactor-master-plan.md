---
version: 1.1
created_at: 2026-04-23
updated_at: 2026-04-24
last_updated: 精简为仅保留 provider 重构顺序清单
abstract: Provider 重构顺序清单（仅保留待办项）
title: Provider 重构总计划
status: active
related_spec:
---

# Provider 重构总计划

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 provider 重构总计划 |
| 1.1 | 删除多余内容，仅保留 provider 重构顺序待办清单 |

## Provider 重构顺序

- [x] diary_provider
- [x] mood_provider
- [x] habit_provider
- [x] habit_checkin_provider
- [x] habit_stats_provider
- [x] goal_provider
- [x] todo_provider
- [x] timeline_provider
- [x] plan_doc_provider

说明：timeline service涉及到多个聚合，当前编写内容还未真实替换service，状态：待替换（当替换完成之后修改这个状态，修改位置lifeprism\server\services\timeline_builder.py lifeprism\server\services\usage_service.py）


## 剩下还未重构的内容

1. 功能未完全确认的

- [ ] value_provider
- [ ] commitment_provider
- [ ] (goal)jounral_provider
- [ ] being_provider

2. 聚合类的(业务类)，不应该直接写在provider

- [ ] statistical_data_providers
- [ ] report_provider
- [ ] category_color_privder

3. 废弃的
- [ ] focus_provider
- [ ] chat_session_provider

4. 直接写在statistical_data_providers内部，没有单独编写的provider（一个表对应一个provider）

- [x] category_provider（category表）
- [x] sub_category_provider（sub_category表）
- [x] app_behavior_log_provider（user_app_behavior_log表）
- [x] tokens_usage_provider（tokens_usage_log表）
- [x] multi_purpose_map_cache_provider（multi_purpose_map_cache表）
- [x] single_purpose_map_cache_provider（single_purpose_map_cache表）

# 聚合层

新增聚合层，将聚合类的provider移动至聚合类
调用流向 provider -> aggregater(可选) ->service/llm