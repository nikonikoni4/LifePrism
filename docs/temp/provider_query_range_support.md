# Provider Query 函数支持的查询范围类型

## 分类统计

### 支持 time_range（4个）
| Provider | Query 函数 | 文件 | _TIME_FIELD |
|---------|-----------|------|-------------|
| BehaviorAnalysisProvider | query_behaviors() | behavior_analysis_provider.py | start_time |
| RawBehaviorAnalysisProvider | query_raw_behaviors() | raw_behavior_analysis_provider.py | start_time |
| TimelineProvider | query_custom_blocks() | timeline_provider.py | start_time |

### 支持 date_range（5个）
| Provider | Query 函数 | 文件 | _DATE_FIELD |
|---------|-----------|------|-------------|
| DiaryProvider | query_diaries() | diary_provider.py | date |
| TodoProvider | query_todos() | todo_provider.py | date |
| GoalStatsProvider | query_goal_stats() | goal_providers.py | date |
| HabitChallengeProvider | query_habit_challenges() | habit_providers.py | start_date |
| HabitCheckinProvider | query_habit_checkins() | habit_providers.py | date |

### 不支持范围查询（12个）
| Provider | Query 函数 | 文件 | 说明 |
|---------|-----------|------|------|
| CategoryProvider | query_categories() | category_provider.py | 无日期/时间字段 |
| SubCategoryProvider | query_sub_categories() | category_provider.py | 无日期/时间字段 |
| MultiPurposeMapCacheProvider | query_multi_purpose_map_cache() | map_cache_providers.py | 无日期/时间字段 |
| SinglePurposeMapCacheProvider | query_single_purpose_map_cache() | map_cache_providers.py | 无日期/时间字段 |
| TokensUsageProvider | query_tokens_usage() | tokens_usage_provider.py | 无日期/时间字段 |
| PlanDocProvider | query_plan_docs() | plan_doc_provider.py | 无日期/时间字段 |
| GoalProvider | query_goals() | goal_providers.py | 无日期/时间字段 |
| HabitProvider | query_habits() | habit_providers.py | 无日期/时间字段 |
| HabitChainProvider | query_habit_chains() | habit_chain_providers.py | 无日期/时间字段 |
| HabitChainNodeProvider | query_habit_chain_nodes() | habit_chain_providers.py | 无日期/时间字段 |
| MoodTypeProvider | query_mood_types() | mood_providers.py | 无日期/时间字段 |
| MoodEntryProvider | query_mood_entries() | mood_providers.py | 无日期/时间字段 |
| MoodImpactProvider | query_mood_impacts() | mood_providers.py | 无日期/时间字段 |

## 注释模板

### 支持 time_range
```python
def query_xxx(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用查询接口

    Args:
        options: 查询选项
            - 支持 time_range: 时间范围查询（基于 start_time 字段）
            - 支持 filters: 字段过滤
            - 支持 order_by/order_desc: 排序
            - 支持 page/page_size: 分页

    Returns:
        (记录列表, 总记录数)
    """
```

### 支持 date_range
```python
def query_xxx(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用查询接口

    Args:
        options: 查询选项
            - 支持 date_range: 日期范围查询（基于 date 字段）
            - 支持 filters: 字段过滤
            - 支持 order_by/order_desc: 排序
            - 支持 page/page_size: 分页

    Returns:
        (记录列表, 总记录数)
    """
```

### 不支持范围查询
```python
def query_xxx(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用查询接口

    Args:
        options: 查询选项
            - 支持 filters: 字段过滤
            - 支持 order_by/order_desc: 排序
            - 支持 page/page_size: 分页

    Returns:
        (记录列表, 总记录数)
    """
```
