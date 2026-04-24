# test_repository_architecture.py
"""验证 repository 架构重构"""
from lifeprism.repository.providers import (
    DiaryProvider,
    TodoProvider,
    TimelineProvider,
    PlanDocProvider,
    TokensUsageProvider,
)
from lifeprism.repository.aggregators import (
    HabitAggregator,
    MoodAggregator,
    GoalAggregator,
    HabitChainAggregator,
    CategoryAggregator,
    MapCacheAggregator,
)

def test_single_table_stores():
    """测试单表 Store（Provider）"""
    print("Testing single-table Stores (Providers)...")

    # diary_store
    assert hasattr(DiaryProvider, 'query_diaries')
    assert hasattr(DiaryProvider, 'get_diary_by_id')
    print("[OK] DiaryProvider")

    # todo_store
    assert hasattr(TodoProvider, 'get_todos_by_date')
    assert hasattr(TodoProvider, 'get_todo_by_id')
    print("[OK] TodoProvider")

    # timeline_store
    assert hasattr(TimelineProvider, 'get_timeline_events_by_date')
    assert hasattr(TimelineProvider, 'get_custom_blocks_by_date')
    print("[OK] TimelineProvider")

    # plan_doc_store
    assert hasattr(PlanDocProvider, 'get_all_plan_docs')
    assert hasattr(PlanDocProvider, 'get_plan_doc_by_id')
    print("[OK] PlanDocProvider")

    # tokens_usage_store
    assert hasattr(TokensUsageProvider, 'query_tokens_usage')
    assert hasattr(TokensUsageProvider, 'get_tokens_usage_by_session_id')
    print("[OK] TokensUsageProvider")

def test_multi_table_stores():
    """测试多表 Store（Aggregator）"""
    print("\nTesting multi-table Stores (Aggregators)...")

    # habit_store
    assert hasattr(HabitAggregator, 'get_habit_with_challenge')
    assert hasattr(HabitAggregator, 'get_habits_with_challenges')
    print("[OK] HabitAggregator")

    # mood_store
    assert hasattr(MoodAggregator, 'get_mood_entry_with_type')
    assert hasattr(MoodAggregator, 'get_mood_entries_with_types')
    print("[OK] MoodAggregator")

    # goal_store
    assert hasattr(GoalAggregator, 'get_goal_with_stats')
    assert hasattr(GoalAggregator, 'get_goals_with_latest_stats')
    print("[OK] GoalAggregator")

    # habit_chain_store
    assert hasattr(HabitChainAggregator, 'get_chain_with_nodes')
    assert hasattr(HabitChainAggregator, 'get_chains_with_nodes')
    print("[OK] HabitChainAggregator")

    # category_store
    assert hasattr(CategoryAggregator, 'get_category_with_subs')
    assert hasattr(CategoryAggregator, 'get_category_tree')
    print("[OK] CategoryAggregator")

    # map_cache_store
    assert hasattr(MapCacheAggregator, 'get_all_caches')
    print("[OK] MapCacheAggregator")

def test_store_aliases():
    """测试 Store 别名导入"""
    print("\nTesting Store aliases...")

    from lifeprism.repository import (
        diary_store,
        todo_store,
        timeline_store,
        plan_doc_store,
        tokens_usage_store,
        habit_store,
        mood_store,
        goal_store,
        habit_chain_store,
        category_store,
        map_cache_store,
    )
    from lifeprism.repository.providers import (
        diary_provider,
        todo_provider,
        timeline_provider,
        plan_doc_provider,
        tokens_usage_provider,
    )
    from lifeprism.repository.aggregators import (
        habit_aggregator,
        mood_aggregator,
        goal_aggregator,
        habit_chain_aggregator,
        category_aggregator,
        map_cache_aggregator,
    )

    # 验证 store 是 provider/aggregator 的别名
    assert diary_store is diary_provider
    assert todo_store is todo_provider
    assert timeline_store is timeline_provider
    assert plan_doc_store is plan_doc_provider
    assert tokens_usage_store is tokens_usage_provider
    assert habit_store is habit_aggregator
    assert mood_store is mood_aggregator
    assert goal_store is goal_aggregator
    assert habit_chain_store is habit_chain_aggregator
    assert category_store is category_aggregator
    assert map_cache_store is map_cache_aggregator

    print("[OK] All store aliases verified")

if __name__ == '__main__':
    test_single_table_stores()
    test_multi_table_stores()
    test_store_aliases()
    print("\n[SUCCESS] All Store interfaces verified!")
