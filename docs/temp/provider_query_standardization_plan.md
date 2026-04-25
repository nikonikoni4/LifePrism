# Provider Query 函数标准化计划

## 调查结果

### 已有 query 函数的 Provider（7个）

所有已有的 query 函数都符合标准：
- ✅ 返回类型：`Tuple[List[Dict[str, Any]], int]`
- ✅ 参数：`options: Optional[QueryOptions] = None`
- ✅ 实现：调用 `self._generic_query(options)`

| Provider | Query 函数名 | 文件 | 状态 |
|---------|------------|------|------|
| CategoryProvider | query_categories() | category_provider.py | ✅ 符合标准 |
| SubCategoryProvider | query_sub_categories() | category_provider.py | ✅ 符合标准 |
| DiaryProvider | query_diaries() | diary_provider.py | ✅ 符合标准 |
| MultiPurposeMapCacheProvider | query_multi_purpose_map_cache() | map_cache_providers.py | ✅ 符合标准 |
| SinglePurposeMapCacheProvider | query_single_purpose_map_cache() | map_cache_providers.py | ✅ 符合标准 |
| TodoProvider | query_todos() | todo_provider.py | ✅ 符合标准 |
| TokensUsageProvider | query_tokens_usage() | tokens_usage_provider.py | ✅ 符合标准 |

**结论：已有的 7 个 query 函数无需修改**

---

### 缺少 query 函数的 Provider（11个）

需要为以下 Provider 添加标准 query 函数：

| # | Provider | 表名 | 文件 | 需要添加的函数名 |
|---|---------|------|------|----------------|
| 1 | BehaviorAnalysisProvider | behavior_analysis | behavior_analysis_provider.py | query_behaviors() |
| 2 | RawBehaviorAnalysisProvider | raw_behavior_analysis | raw_behavior_analysis_provider.py | query_raw_behaviors() |
| 3 | TimelineProvider | timeline_custom_block | timeline_provider.py | query_custom_blocks() |
| 4 | PlanDocProvider | plan_doc | plan_doc_provider.py | query_plan_docs() |
| 5 | GoalProvider | goal | goal_providers.py | query_goals() |
| 6 | GoalStatsProvider | goal_stats | goal_providers.py | query_goal_stats() |
| 7 | HabitProvider | habits | habit_providers.py | query_habits() |
| 8 | HabitChallengeProvider | habit_challenges | habit_providers.py | query_habit_challenges() |
| 9 | HabitCheckinProvider | habit_checkins | habit_providers.py | query_habit_checkins() |
| 10 | HabitChainProvider | habit_chains | habit_chain_providers.py | query_habit_chains() |
| 11 | HabitChainNodeProvider | habit_chain_nodes | habit_chain_providers.py | query_habit_chain_nodes() |
| 12 | MoodTypeProvider | mood_types | mood_providers.py | query_mood_types() |
| 13 | MoodEntryProvider | mood_entries | mood_providers.py | query_mood_entries() |
| 14 | MoodImpactProvider | mood_impacts | mood_providers.py | query_mood_impacts() |

**总计：14 个 Provider 需要添加 query 函数**

---

## 实施计划

### 标准模板

每个 query 函数应遵循以下模板：

```python
def query_{table_name}(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用查询接口

    Args:
        options: 查询选项

    Returns:
        (记录列表, 总记录数)

    Examples:
        # 示例1：基本查询
        options = QueryOptions(filters={'status': 'active'})
        records, total = provider.query_{table_name}(options)

        # 示例2：分页查询
        options = QueryOptions(page=1, page_size=20)
        records, total = provider.query_{table_name}(options)
    """
    return self._generic_query(options)
```

### 分组实施

**组1：行为分析相关（2个文件，3个 Provider）**
- behavior_analysis_provider.py: BehaviorAnalysisProvider
- raw_behavior_analysis_provider.py: RawBehaviorAnalysisProvider
- timeline_provider.py: TimelineProvider

**组2：目标和计划相关（2个文件，3个 Provider）**
- plan_doc_provider.py: PlanDocProvider
- goal_providers.py: GoalProvider, GoalStatsProvider

**组3：习惯相关（2个文件，5个 Provider）**
- habit_providers.py: HabitProvider, HabitChallengeProvider, HabitCheckinProvider
- habit_chain_providers.py: HabitChainProvider, HabitChainNodeProvider

**组4：心情相关（1个文件，3个 Provider）**
- mood_providers.py: MoodTypeProvider, MoodEntryProvider, MoodImpactProvider

---

## 注意事项

1. **插入位置**：在每个 Provider 的"核心方法"部分的开头添加 query 函数
2. **命名规范**：函数名为 `query_{表名复数形式}`
3. **文档字符串**：必须包含 Args、Returns 和 Examples
4. **类型注解**：必须添加完整的类型注解
5. **实现方式**：直接调用 `self._generic_query(options)`，不需要额外逻辑
6. **特殊处理**：如果表没有 date/time 字段，query 函数仍然支持 filters 等其他查询选项
