"""测试 LifePrism 数据查询工具"""
import pytest
from lifeprism.llm.agent.tools.lifeprismsystem import query_data
from lifeprism.repository.aggregators import computer_usage_aggregator, todo_aggregator
from lifeprism.repository.providers import custom_block_provider, behavior_analysis_provider


@pytest.fixture
def test_data():
    """创建测试数据"""
    created_ids = []

    # 创建电脑使用数据
    usage_data = {
        'id': 'test-usage-001',
        'start_time': '2026-04-28 10:00:00',
        'end_time': '2026-04-28 10:30:00',
        'duration': 1800,
        'app': 'test.exe',
        'title': 'Test App',
        'category_id': 'cat-001'
    }
    computer_usage_aggregator.create_computer_usage(usage_data)
    created_ids.append(('computer_usage', 'test-usage-001'))

    # 创建用户自定义备注
    custom_block_data = {
        'start_time': '2026-04-28 11:00:00',
        'end_time': '2026-04-28 11:30:00',
        'duration': 1800,
        'content': 'Test custom block',
        'color': '#FF0000'
    }
    block = custom_block_provider.create_custom_block(custom_block_data)
    created_ids.append(('custom_block', block['id']))

    # 创建 AI 行为分析
    behavior_data = {
        'start_time': '2026-04-28 12:00:00',
        'end_time': '2026-04-28 12:30:00',
        'behavior': 'working',
        'behavior_summary': 'Test behavior analysis',
        'screen_count': 1
    }
    behavior = behavior_analysis_provider.create_behavior(behavior_data)
    created_ids.append(('behavior', behavior['start_time']))

    # 创建待办事项
    todo_data = {
        'content': 'Test todo',
        'date': '2026-04-28',
        'state': 'active',
        'order_index': 0
    }
    todo_id = todo_aggregator.create_todo(todo_data)
    created_ids.append(('todo', todo_id))

    yield

    # 清理测试数据
    for data_type, data_id in created_ids:
        try:
            if data_type == 'computer_usage':
                computer_usage_aggregator.delete_computer_usage(data_id)
            elif data_type == 'custom_block':
                custom_block_provider.delete_custom_block(data_id)
            elif data_type == 'behavior':
                behavior_analysis_provider.delete_behavior(data_id)
            elif data_type == 'todo':
                todo_aggregator.delete_todo(data_id)
        except Exception:
            pass


@pytest.mark.core
def test_query_computer_usage_stats(test_data):
    """测试查询电脑使用统计"""
    result = query_data(
        query_option={'computer_usage_stats'},
        start_time='2026-04-28 00:00:00',
        end_time='2026-04-28 23:59:59'
    )

    assert isinstance(result, str)
    assert '电脑使用统计' in result
    assert '没有电脑使用记录' not in result


@pytest.mark.core
def test_query_user_behavior_notes(test_data):
    """测试查询用户自定义行为备注"""
    result = query_data(
        query_option={'user_behavior_notes'},
        start_time='2026-04-28 00:00:00',
        end_time='2026-04-28 23:59:59'
    )

    assert isinstance(result, str)
    assert '用户自定义行为备注' in result
    assert '用户自定义行为备注为空' not in result
    assert 'Test custom block' in result


@pytest.mark.core
def test_query_ai_behavior_notes(test_data):
    """测试查询 AI 行为分析"""
    result = query_data(
        query_option={'ai_behavior_notes'},
        start_time='2026-04-28 00:00:00',
        end_time='2026-04-28 23:59:59'
    )

    assert isinstance(result, str)
    assert 'AI分析行为备注' in result
    assert 'AI分析行为备注为空' not in result
    assert 'Test behavior analysis' in result


@pytest.mark.core
def test_query_todolist(test_data):
    """测试查询待办事项"""
    result = query_data(
        query_option={'todolist'},
        start_time='2026-04-28 00:00:00',
        end_time='2026-04-28 23:59:59'
    )

    assert isinstance(result, str)
    assert '用户待办事项' in result
    assert '用户待办事项为空' not in result
    assert 'Test todo' in result


@pytest.mark.core
def test_query_multiple_options(test_data):
    """测试查询多个选项"""
    result = query_data(
        query_option={'computer_usage_stats', 'user_behavior_notes', 'todolist'},
        start_time='2026-04-28 00:00:00',
        end_time='2026-04-28 23:59:59'
    )

    assert isinstance(result, str)
    assert '电脑使用统计' in result
    assert '用户自定义行为备注' in result
    assert '用户待办事项' in result
    assert '没有电脑使用记录' not in result


@pytest.mark.core
def test_invalid_query_option():
    """测试无效的查询选项"""
    with pytest.raises(ValueError, match="Invalid query options"):
        query_data(
            query_option={'invalid_option'},
            start_time='2026-04-28 00:00:00',
            end_time='2026-04-28 23:59:59'
        )


@pytest.mark.core
def test_invalid_time_format():
    """测试无效的时间格式"""
    with pytest.raises(ValueError, match="Invalid time format"):
        query_data(
            query_option={'goals'},
            start_time='2026-04-28',
            end_time='2026-04-28 23:59:59'
        )


@pytest.mark.core
def test_invalid_time_range():
    """测试无效的时间范围"""
    with pytest.raises(ValueError, match="start_time must be before end_time"):
        query_data(
            query_option={'goals'},
            start_time='2026-04-28 23:59:59',
            end_time='2026-04-28 00:00:00'
        )
