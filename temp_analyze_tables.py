#!/usr/bin/env python3
"""临时脚本：分析所有表的 updated_at 字段情况"""

# sync-solution.md 中提到的需要同步的表
sync_tables = [
    'window_events',
    'user_app_behavior_log',
    'behavior_analysis',
    'mood_entries',
    'timeline_custom_block',
    'diary',
    'todo_list',
    'category',
    'sub_category',
    'goal',
    'habits',
    # cache 表
    'category_map_cache',
    'multi_purpose_map_cache',
    'single_purpose_map_cache',
]

# 其他可能需要同步的表
other_tables = [
    'habit_challenges',
    'habit_checkins',
    'habit_chains',
    'habit_chain_nodes',
    'mood_types',
    'mood_impacts',
    'user_values',
    'commitments',
    'plan_doc',
    'goal_journal',
    'daily_focus',
    'weekly_focus',
    'daily_report',
    'weekly_report',
    'monthly_report',
    'time_paradoxes',
    'goal_stats',
    'raw_behavior_analysis',
    'screen_captures',
    'custom_record_types',
    'custom_record_fields',
]

# 从 database.py 手工提取的配置
table_configs = {
    'multi_purpose_map_cache': {'timestamps': True, 'update_at': True},
    'single_purpose_map_cache': {'timestamps': True, 'update_at': True},
    'category_map_cache': {'timestamps': True, 'update_at': False},
    'user_app_behavior_log': {'timestamps': True, 'update_at': False},
    'category': {'timestamps': True, 'update_at': False},
    'sub_category': {'timestamps': True, 'update_at': False},
    'tokens_usage_log': {'timestamps': True, 'update_at': False},
    'todo_list': {'timestamps': True, 'update_at': False},
    'daily_focus': {'timestamps': True, 'update_at': False},
    'weekly_focus': {'timestamps': True, 'update_at': False},
    'goal': {'timestamps': True, 'update_at': False},
    'goal_journal': {'timestamps': True, 'update_at': False},
    'plan_doc': {'timestamps': True, 'update_at': True},
    'chat_session': {'timestamps': False, 'update_at': False},  # 自定义时间戳
    'timeline_custom_block': {'timestamps': True, 'update_at': False},
    'goal_stats': {'timestamps': True, 'update_at': False},
    'daily_report': {'timestamps': True, 'update_at': True},
    'weekly_report': {'timestamps': True, 'update_at': True},
    'monthly_report': {'timestamps': True, 'update_at': True},
    'time_paradoxes': {'timestamps': True, 'update_at': True},
    'diary': {'timestamps': True, 'update_at': True},
    'mood_types': {'timestamps': True, 'update_at': False},
    'mood_entries': {'timestamps': True, 'update_at': False},
    'mood_impacts': {'timestamps': True, 'update_at': False},
    'user_values': {'timestamps': True, 'update_at': True},
    'commitments': {'timestamps': True, 'update_at': True},
    'schema_version': {'timestamps': False, 'update_at': False},
    'habits': {'timestamps': True, 'update_at': True},
    'habit_challenges': {'timestamps': True, 'update_at': True},
    'habit_checkins': {'timestamps': True, 'update_at': False},
    'habit_chains': {'timestamps': True, 'update_at': True},
    'habit_chain_nodes': {'timestamps': True, 'update_at': True},
    'screen_captures': {'timestamps': True, 'update_at': False},
    'window_events': {'timestamps': True, 'update_at': False},
    'raw_behavior_analysis': {'timestamps': True, 'update_at': False},
    'behavior_analysis': {'timestamps': True, 'update_at': False},
    'custom_record_types': {'timestamps': True, 'update_at': True},
    'custom_record_fields': {'timestamps': True, 'update_at': False},
}

has_updated_at = []
missing_updated_at = []

all_check_tables = sync_tables + other_tables

for table in all_check_tables:
    if table not in table_configs:
        print(f'⚠️  表不存在: {table}')
        continue

    config = table_configs[table]
    timestamps = config.get('timestamps', False)
    update_at = config.get('update_at', False)

    # timestamps=True 会自动添加 created_at
    # update_at=True 会自动添加 updated_at
    if timestamps and update_at:
        has_updated_at.append(table)
    else:
        missing_updated_at.append(table)

print('[OK] 有 updated_at 的表:')
for t in sorted(has_updated_at):
    print(f'  - {t}')

print(f'\n[MISSING] 缺少 updated_at 的表（需要添加）:')
for t in sorted(missing_updated_at):
    config = table_configs.get(t, {})
    ts = config.get('timestamps', False)
    ua = config.get('update_at', False)
    in_sync = '[NEED_SYNC]' if t in sync_tables else ''
    print(f'  - {t:30s} (timestamps={ts}, update_at={ua}) {in_sync}')
