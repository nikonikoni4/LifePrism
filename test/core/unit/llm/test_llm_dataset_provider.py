"""测试 LLMDatasetProvider 的 TodoList 查询功能"""

from datetime import datetime, timedelta

import pytest
from lifeprism.llm.providers.dataset_providers.llm_dataset_provider import (
    LLMDatasetProvider,
    llm_dataset_provider,
)


@pytest.mark.core
class TestLLMDatasetProvider:
    """测试 LLMDatasetProvider 基础功能"""

    def test_provider_initialization(self):
        """测试 provider 初始化"""
        provider = LLMDatasetProvider()
        assert provider is not None
        assert provider.db is not None

    def test_singleton_instance(self):
        """测试单例模式"""
        provider1 = llm_dataset_provider
        provider2 = llm_dataset_provider
        assert provider1 is provider2


@pytest.mark.core
class TestQueryTodos:
    """测试 query_todos 接口"""

    def test_query_empty_date_range(self):
        """测试查询空日期范围"""
        provider = LLMDatasetProvider()

        # 查询未来日期（应该没有数据）
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        todos = provider.query_todos(start_date=future_date, end_date=future_date)

        assert isinstance(todos, list)

    def test_query_date_range(self):
        """测试日期范围查询"""
        provider = LLMDatasetProvider()

        # 查询最近7天
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        todos = provider.query_todos(start_date=start_date, end_date=end_date)

        assert isinstance(todos, list)

        # 验证返回的数据结构
        if todos:
            todo = todos[0]
            assert "id" in todo
            assert "content" in todo
            assert "date" in todo
            assert "state" in todo

    def test_query_single_date(self):
        """测试单日查询（不传 end_date）"""
        provider = LLMDatasetProvider()

        today = datetime.now().strftime("%Y-%m-%d")
        todos = provider.query_todos(start_date=today)

        assert isinstance(todos, list)

    def test_query_single_date_without_cross_day(self):
        """测试单日查询（不包含跨天任务）"""
        provider = LLMDatasetProvider()

        today = datetime.now().strftime("%Y-%m-%d")
        todos = provider.query_todos(start_date=today, include_cross_day=False)

        assert isinstance(todos, list)
        # 所有任务的日期应该都是今天
        for todo in todos:
            assert todo.get("date") == today

    def test_query_with_goal_filter(self):
        """测试带 goal_id 过滤的查询"""
        provider = LLMDatasetProvider()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # 使用一个不存在的 goal_id
        todos = provider.query_todos(
            start_date=start_date, end_date=end_date, goal_id="goal-nonexistent"
        )

        assert isinstance(todos, list)
        # 所有返回的 todo 应该都有这个 goal_id
        for todo in todos:
            assert todo.get("link_to_goal_id") == "goal-nonexistent"

    def test_query_with_plandoc_filter(self):
        """测试带 plandoc_id 过滤的查询"""
        provider = LLMDatasetProvider()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        todos = provider.query_todos(
            start_date=start_date, end_date=end_date, plandoc_id="plandoc-test"
        )

        assert isinstance(todos, list)
        for todo in todos:
            assert todo.get("plan_doc_id") == "plandoc-test"

    def test_query_with_state_filter(self):
        """测试带状态过滤的查询"""
        provider = LLMDatasetProvider()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # 查询已完成的任务
        todos = provider.query_todos(start_date=start_date, end_date=end_date, state="completed")

        assert isinstance(todos, list)
        for todo in todos:
            assert todo.get("state") == "completed"

    def test_query_with_multiple_filters(self):
        """测试多个过滤条件组合"""
        provider = LLMDatasetProvider()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        todos = provider.query_todos(
            start_date=start_date,
            end_date=end_date,
            goal_id="goal-test",
            plandoc_id="plandoc-test",
            state="active",
        )

        assert isinstance(todos, list)
        for todo in todos:
            assert todo.get("link_to_goal_id") == "goal-test"
            assert todo.get("plan_doc_id") == "plandoc-test"
            assert todo.get("state") == "active"

    def test_single_date_with_filters(self):
        """测试单日查询带过滤条件"""
        provider = LLMDatasetProvider()

        today = datetime.now().strftime("%Y-%m-%d")
        todos = provider.query_todos(start_date=today, goal_id="goal-test", state="active")

        assert isinstance(todos, list)
        for todo in todos:
            assert todo.get("link_to_goal_id") == "goal-test"
            assert todo.get("state") == "active"


@pytest.mark.core
class TestDataStructure:
    """测试返回数据结构的完整性"""

    def test_todo_fields(self):
        """测试 todo 数据包含必要字段"""
        provider = LLMDatasetProvider()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        todos = provider.query_todos(start_date=start_date, end_date=end_date)

        if todos:
            todo = todos[0]

            # 验证必要字段存在
            required_fields = [
                "id",
                "content",
                "date",
                "state",
                "order_index",
                "link_to_goal_id",
                "plan_doc_id",
                "parent_id",
                "cross_day",
                "color",
            ]

            for field in required_fields:
                assert field in todo, f"缺少字段: {field}"

    def test_todos_sorted_by_date_and_order(self):
        """测试返回的 todos 按日期和 order_index 排序"""
        provider = LLMDatasetProvider()

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        todos = provider.query_todos(start_date=start_date, end_date=end_date)

        if len(todos) > 1:
            # 验证排序：日期升序，同日期内 order_index 升序
            for i in range(len(todos) - 1):
                current = todos[i]
                next_todo = todos[i + 1]

                current_date = current.get("date", "")
                next_date = next_todo.get("date", "")

                # 日期应该是升序
                assert current_date <= next_date

                # 同一天内，order_index 应该是升序
                if current_date == next_date:
                    current_order = current.get("order_index", 0)
                    next_order = next_todo.get("order_index", 0)
                    assert current_order <= next_order

    def test_single_date_sorted_by_order(self):
        """测试单日查询返回的 todos 按 order_index 排序"""
        provider = LLMDatasetProvider()

        today = datetime.now().strftime("%Y-%m-%d")
        todos = provider.query_todos(start_date=today)

        if len(todos) > 1:
            # 验证排序：order_index 升序
            for i in range(len(todos) - 1):
                current_order = todos[i].get("order_index", 0)
                next_order = todos[i + 1].get("order_index", 0)
                assert current_order <= next_order
