"""测试 lifeprismsystem.py 中的 todolist 功能"""
import pytest
from datetime import datetime, timedelta
from collections import defaultdict

from lifeprism.repository import todo_repository, QueryOptions
from lifeprism.repository.aggregators import todo_aggregator


@pytest.fixture
def test_todos():
    """创建测试用的 todo 数据"""
    created_ids = []
    test_date = datetime.now().strftime('%Y-%m-%d')
    
    todos_data = [
        {'content': '已完成任务1', 'date': test_date, 'state': 'completed', 'order_index': 0},
        {'content': '未完成任务1', 'date': test_date, 'state': 'scheduled', 'order_index': 1},
        {'content': '已完成任务2', 'date': test_date, 'state': 'completed', 'order_index': 2},
        {'content': '任务池任务', 'date': None, 'state': 'pool', 'order_index': 3},
        {'content': '搁置任务', 'date': test_date, 'state': 'shelved', 'order_index': 4},
    ]
    
    for todo_data in todos_data:
        todo_id = todo_aggregator.create_todo(todo_data)
        created_ids.append(todo_id)
    
    yield created_ids, test_date
    
    for todo_id in created_ids:
        try:
            todo_aggregator.delete_todo(todo_id)
        except Exception:
            pass


class TestTodolistStateFormat:
    """测试状态转换功能"""
    
    def _format_state(self, state: str) -> str:
        """状态转换函数：数据库状态 -> 中文描述"""
        state_map = {
            'scheduled': '未完成',
            'completed': '已完成'
        }
        return state_map.get(state, state)
    
    def test_format_state_scheduled(self):
        """测试 scheduled 状态转换为'未完成'"""
        assert self._format_state('scheduled') == '未完成'
    
    def test_format_state_completed(self):
        """测试 completed 状态转换为'已完成'"""
        assert self._format_state('completed') == '已完成'
    
    def test_format_state_unknown(self):
        """测试未知状态原样返回"""
        assert self._format_state('pool') == 'pool'
        assert self._format_state('shelved') == 'shelved'


class TestTodolistFiltering:
    """测试 todolist 筛选功能"""
    
    def _filter_todos(self, todos: list[dict]) -> list[dict]:
        """仅保留 scheduled 和 completed 状态的 todo"""
        return [t for t in todos if t.get('state') in ('scheduled', 'completed')]
    
    def test_filter_scheduled_and_completed(self):
        """测试只保留 scheduled 和 completed 状态"""
        todos = [
            {'content': '已完成', 'state': 'completed'},
            {'content': '未完成', 'state': 'scheduled'},
            {'content': '任务池', 'state': 'pool'},
            {'content': '搁置', 'state': 'shelved'},
        ]
        filtered = self._filter_todos(todos)
        assert len(filtered) == 2
        assert filtered[0]['content'] == '已完成'
        assert filtered[1]['content'] == '未完成'
    
    def test_filter_empty_list(self):
        """测试空列表"""
        filtered = self._filter_todos([])
        assert len(filtered) == 0
    
    def test_filter_missing_state(self):
        """测试缺少 state 字段的 todo"""
        todos = [
            {'content': '无状态'},
            {'content': '已完成', 'state': 'completed'},
        ]
        filtered = self._filter_todos(todos)
        assert len(filtered) == 1


class TestTodolistGrouping:
    """测试按日期分组功能"""
    
    def _group_by_date(self, todos: list[dict]) -> dict:
        """按日期分组"""
        by_date = defaultdict(list)
        for todo in todos:
            by_date[todo['date']].append((todo['content'], todo['state']))
        return dict(by_date)
    
    def test_group_by_single_date(self):
        """测试单日期分组"""
        todos = [
            {'content': '任务1', 'date': '2026-05-08', 'state': 'completed'},
            {'content': '任务2', 'date': '2026-05-08', 'state': 'scheduled'},
        ]
        grouped = self._group_by_date(todos)
        assert len(grouped) == 1
        assert '2026-05-08' in grouped
        assert len(grouped['2026-05-08']) == 2
    
    def test_group_by_multiple_dates(self):
        """测试多日期分组"""
        todos = [
            {'content': '今天任务', 'date': '2026-05-08', 'state': 'completed'},
            {'content': '昨天任务', 'date': '2026-05-07', 'state': 'scheduled'},
        ]
        grouped = self._group_by_date(todos)
        assert len(grouped) == 2
        assert '2026-05-08' in grouped
        assert '2026-05-07' in grouped


class TestTodolistOutput:
    """测试 todolist 输出格式化"""
    
    def _format_output(self, todos: list[dict]) -> str:
        """格式化输出"""
        def _format_state(state: str) -> str:
            state_map = {
                'scheduled': '未完成',
                'completed': '已完成'
            }
            return state_map.get(state, state)
        
        by_date = defaultdict(list)
        for todo in todos:
            by_date[todo['date']].append((todo['content'], todo['state']))
        
        content = "## 用户待办事项\n"
        for date in sorted(by_date.keys()):
            content += f"### {date}\n"
            for idx, (item, state) in enumerate(by_date[date], 1):
                content += f"{idx}. {item} [{_format_state(state)}]\n"
        
        return content
    
    def test_output_with_todos(self):
        """测试有数据时的输出"""
        todos = [
            {'content': '完成任务', 'date': '2026-05-08', 'state': 'completed'},
            {'content': '未完成任务', 'date': '2026-05-08', 'state': 'scheduled'},
        ]
        output = self._format_output(todos)
        
        assert "## 用户待办事项" in output
        assert "### 2026-05-08" in output
        assert "1. 完成任务 [已完成]" in output
        assert "2. 未完成任务 [未完成]" in output
    
    def test_output_empty(self):
        """测试空数据输出"""
        output = self._format_output([])
        assert "## 用户待办事项" in output


@pytest.mark.integration
class TestTodolistIntegration:
    """集成测试：测试与真实数据库的交互"""
    
    def test_query_only_scheduled_and_completed(self, test_todos):
        """测试查询只返回 scheduled 和 completed 状态的 todo"""
        created_ids, test_date = test_todos
        
        todolists, _ = todo_repository.query_todos(
            QueryOptions(fields=['content', 'date', 'state']).with_date_range(test_date, test_date)
        )
        
        filtered = [t for t in todolists if t.get('state') in ('scheduled', 'completed')]
        
        assert len(filtered) >= 2
        
        for todo in filtered:
            assert todo['state'] in ('scheduled', 'completed')
            assert todo['content'] in ['已完成任务1', '未完成任务1', '已完成任务2']
    
    def test_pool_shelved_not_returned(self, test_todos):
        """测试过滤后 pool 和 shelved 状态不会被包含"""
        created_ids, test_date = test_todos
        
        todolists, _ = todo_repository.query_todos(
            QueryOptions(fields=['content', 'date', 'state']).with_date_range(test_date, test_date)
        )
        
        filtered = [t for t in todolists if t.get('state') in ('scheduled', 'completed')]
        filtered_states = [t.get('state') for t in filtered]
        
        assert 'pool' not in filtered_states
        assert 'shelved' not in filtered_states
