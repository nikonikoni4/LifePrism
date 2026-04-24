# server_lw_data_provider 使用位置与表映射

本文档列出 `server_lw_data_provider`（来自 `statistical_data_providers.py`）的所有使用位置，以及对应的数据库表。

---

## 表与方法映射

### 1. user_app_behavior_log 表

| 方法名 | 功能 | 调用位置 |
|--------|------|----------|
| `get_activity_logs()` | 获取活动日志 | [activity_service.py#L120](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L120) |
| `get_activity_log_by_id()` | 获取单条活动日志 | [activity_service.py#L167](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L167) |
| `update_event_category()` | 更新事件分类 | [activity_service.py#L192](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L192) |
| `batch_update_event_category()` | 批量更新事件分类 | [activity_service.py#L201](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L201) |
| `delete_event()` | 删除事件 | [activity_service.py#L206](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L206) |
| `batch_delete_events()` | 批量删除事件 | [activity_service.py#L212](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L212) |
| `update_logs_by_app_title()` | 根据应用和标题批量更新日志 | [activity_service.py#L245](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_service.py#L245) |
| `load_user_app_behavior_log()` | 加载行为日志DataFrame | [report_service.py#L546](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L546), [L763](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L763), [L802](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L802), [L869](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L869), [L936](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L936), [L1004](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/report_service.py#L1004) |
| `load_user_app_behavior_log()` | 加载行为日志DataFrame | [data_processing_service.py#L116](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L116), [L215](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L215) |
| `load_user_app_behavior_log()` | 加载行为日志DataFrame | [activity_stats_builder.py#L130](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L130) |
| `load_user_app_behavior_log()` | 加载行为日志DataFrame | [category_service.py#L159](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L159) |
| `save_user_app_behavior_log()` | 保存行为日志 | [data_processing_service.py#L116](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L116), [L215](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L215) |

### 2. tokens_usage_log 表

| 方法名 | 功能 | 调用位置 |
|--------|------|----------|
| `get_tokens_usage()` | 获取指定日期token使用汇总 | [usage_service.py#L34](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L34), [L75](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L75), [L123](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L123) |
| `get_tokens_usage_by_mode()` | 获取按mode分组的token使用 | [usage_service.py#L37](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L37), [L178](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L178), [L245](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L245) |
| `get_all_tokens_usage()` | 获取全部token使用汇总 | [usage_service.py#L40](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L40), [L126](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L126) |
| `get_all_tokens_usage_by_mode()` | 获取全部token使用按mode分组 | [usage_service.py#L43](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L43), [L181](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L181), [L248](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/usage_service.py#L248) |
| `get_session_tokens_usage()` | 获取会话token使用 | [data_processing_service.py#L744](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L744) |
| `upsert_session_tokens_usage()` | 更新会话token使用 | [data_processing_service.py#L753](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L753) |

### 3. category / sub_category 表（元数据表）

| 方法名 | 功能 | 调用位置 |
|--------|------|----------|
| `load_categories()` | 加载分类数据 | [data_processing_service.py#L294](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L294), [L674](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L674) |
| `load_sub_categories()` | 加载子分类数据 | [data_processing_service.py#L295](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L295), [L675](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L675) |
| `load_categories()` | 加载分类数据 | [category_service.py#L36](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L36), [L386](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L386), [L387](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L387) |
| `load_sub_categories()` | 加载子分类数据 | [category_service.py#L37](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L37), [L386](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L386), [L387](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L387) |

### 4. multi_purpose_map_cache / single_purpose_map_cache 表

| 方法名 | 功能 | 调用位置 |
|--------|------|----------|
| `load_category_map_cache_V2()` | 加载分类映射缓存 | [data_processing_service.py#L71](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L71), [L172](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L172) |
| `save_category_map_cache_V2()` | 保存分类映射缓存 | [data_processing_service.py#L95](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L95), [L194](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L194) |
| `load_category_map_cache_V2()` | 加载分类映射缓存 | [category_service.py#L1135](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L1135) |
| `update_category_map_cache_by_id()` | 更新单条缓存记录 | [category_service.py#L1233](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L1233) |
| `batch_update_category_map_cache_by_ids()` | 批量更新缓存记录 | [category_service.py#L1273](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L1273) |
| `delete_category_map_cache_by_id()` | 删除单条缓存记录 | [category_service.py#L1296](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L1296) |
| `batch_delete_category_map_cache_by_ids()` | 批量删除缓存记录 | [category_service.py#L1320](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L1320) |

### 5. 其他方法（跨表或辅助方法）

| 方法名 | 功能 | 调用位置 |
|--------|------|----------|
| `get_latest_end_time()` | 获取最新结束时间 | [data_processing_service.py#L261](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/data_processing_service.py#L261) |
| `get_daily_active_time()` | 获取每日活跃时长 | [activity_stats_builder.py#L78](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L78) |
| `get_top_title()` | 获取Top窗口标题 | [activity_stats_builder.py#L230](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L230) |
| `get_active_time()` | 获取活跃时长 | [activity_stats_builder.py#L231](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L231), [L257](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L257) |
| `get_top_applications()` | 获取Top应用 | [activity_stats_builder.py#L256](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/activity_stats_builder.py#L256) |

---

## 按服务分类的使用情况

| 服务文件 | 使用的表 |
|----------|----------|
| `activity_service.py` | user_app_behavior_log |
| `report_service.py` | user_app_behavior_log |
| `data_processing_service.py` | user_app_behavior_log, category, sub_category, multi_purpose_map_cache, single_purpose_map_cache, tokens_usage_log |
| `activity_stats_builder.py` | user_app_behavior_log |
| `category_service.py` | user_app_behavior_log, category, sub_category, multi_purpose_map_cache, single_purpose_map_cache |
| `usage_service.py` | tokens_usage_log |

---

## 统计摘要

| 表名 | 方法数量 | 调用次数（约） |
|------|----------|----------------|
| user_app_behavior_log | 13 | 22 |
| tokens_usage_log | 6 | 11 |
| category | 2 | 6 |
| sub_category | 2 | 6 |
| multi_purpose_map_cache | 4 | 5 |
| single_purpose_map_cache | 4 | 5 |
