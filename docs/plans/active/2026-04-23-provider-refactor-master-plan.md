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
- [x] tokens_usage_provider（tokens_usage_log表）
- [x] multi_purpose_map_cache_provider（multi_purpose_map_cache表）
- [x] single_purpose_map_cache_provider（single_purpose_map_cache表）

5. 写在基类的provider
- [ ] app_behavior_log_provider（user_app_behavior_log表）



## 编写聚合类，将同一个模块的provider聚合
 'DiaryProvider',
    'QueryOptions',
    'diary_provider',
    'MoodTypeProvider',
    'MoodEntryProvider',
    'MoodImpactProvider',
    'mood_type_provider',
    'mood_entry_provider',
    'mood_impact_provider',
    'HabitProvider',
    'HabitChallengeProvider',
    'HabitCheckinProvider',
    'habit_provider',
    'habit_challenge_provider',
    'habit_checkin_provider',
    'HabitChainProvider',
    'HabitChainNodeProvider',
    'habit_chain_provider',
    'habit_chain_node_provider',
    'GoalProvider',
    'GoalStatsProvider',
    'goal_provider',
    'goal_stats_provider',
    'TodoProvider',
    'todo_provider',
    'TimelineProvider',
    'timeline_provider',
    'PlanDocProvider',
    'plan_doc_provider',
    'CategoryProvider',
    'SubCategoryProvider',
    'category_provider',
    'sub_category_provider',
    'TokensUsageProvider',
    'tokens_usage_provider',
    'MultiPurposeMapCacheProvider',
    'SinglePurposeMapCacheProvider',
    'multi_purpose_map_cache_provider',
    'single_purpose_map_cache_provider',
依据docs\temp\Investigation\2026-04-24-provider-aggregator-architecture-research.md 进行聚合类的构建
需要聚合的对象（对应表）：
1. habit_aggregator : habit_provider(habits表), habit_challenge_provider(habit_challenges表), habit_checkin_provider(habit_checkins表)
2. mood_aggregator : mood_type_provider(mood_types表), mood_entry_provider(mood_entries表), mood_impact_provider(mood_impacts表)
3. goal_aggregator : goal_provider(goals表), goal_stats_provider(goal_stats表)
4. habit_chain_aggregator : habit_chain_provider(habit_chains表), habit_chain_node_provider(habit_chain_nodes表)
5. category_aggregator : category_provider(categories表), sub_category_provider(sub_categories表)
6. map_cache_aggregator : multi_purpose_map_cache_provider(multi_purpose_map_cache表), single_purpose_map_cache_provider(single_purpose_map_cache表)




## 重构lwbaseprovider

 1. 背景：我最近正在重构provider，原因：docs\temp\refactor-repository-architecture-draft\reason-and-new-archi
  ecture.md 。我已经重构了比较简单的内容，已经完成的内容在lifeprism/repository/provder内。现在我想打算重构lwbased
    atabaseprovider，使其仅仅保留通用内容。需要你整理出非

1. 需要移除的函数
   1. get_activity_logs
   2. load_category_map_cache_V2
   3. save_category_map_cache_V2
   4. load_categories
   5. load_sub_categories
   6. get_latest_end_time
   7. load_user_app_behavior_log
   8. save_user_app_behavior_log
   9. save_tokens_usage
   10. get_session_tokens_usage
   11. upsert_session_tokens_usage
2. 创建

1. 确认影响范围
2. 判断是否需要将其内容移出

# 聚合层

新增聚合层，将聚合类的provider移动至聚合类
调用流向 provider -> aggregater(可选) ->service/llm

