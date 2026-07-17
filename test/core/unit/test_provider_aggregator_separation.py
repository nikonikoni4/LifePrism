"""测试 Provider 和 Aggregator 的职责分离"""

import io
import sys
from pathlib import Path

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lifeprism.repository.aggregators.plan_doc_aggregator import PlanDocAggregator
from lifeprism.repository.aggregators.todo_aggregator import TodoAggregator
from lifeprism.repository.providers.plan_doc_provider import PlanDocProvider
from lifeprism.repository.providers.todo_provider import TodoProvider
from lifeprism.utils.exceptions import ValidationError


def test_todo_provider_requires_order_index():
    """测试 TodoProvider 必须传入 order_index"""
    print("=" * 60)
    print("测试 TodoProvider 必须传入 order_index")
    print("=" * 60)

    provider = TodoProvider()

    # 测试 1: 不传 order_index 应该报错
    print("\n[测试 1] 不传 order_index 应该报错")
    try:
        data = {"content": "测试任务", "date": "2026-04-25", "state": "pool"}
        provider.create_todo(data)
        print("✗ 应该抛出 ValidationError")
        raise AssertionError("应该抛出 ValidationError")
    except ValidationError as e:
        print(f"✓ 正确抛出 ValidationError: {e}")

    # 测试 2: 传入 order_index 应该成功
    print("\n[测试 2] 传入 order_index 应该成功")
    try:
        data = {"content": "测试任务", "date": "2026-04-25", "state": "pool", "order_index": 0}
        todo_id = provider.create_todo(data)
        print(f"✓ 创建成功: {todo_id}")

        todo = provider.get_todo_by_id(todo_id)
        assert todo["order_index"] == 0
        print("✓ order_index 正确")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    print("\n" + "=" * 60)
    print("✓ TodoProvider 测试通过！")
    print("=" * 60)


def test_plan_doc_provider_requires_order_index():
    """测试 PlanDocProvider 必须传入 order_index"""
    print("\n" + "=" * 60)
    print("测试 PlanDocProvider 必须传入 order_index")
    print("=" * 60)

    provider = PlanDocProvider()

    # 测试 1: 不传 order_index 应该报错
    print("\n[测试 1] 不传 order_index 应该报错")
    try:
        data = {"id": "plandoc-test-provider-001", "goal_id": "goal-test-001", "status": "active"}
        provider.create_plan_doc(data)
        print("✗ 应该抛出 ValidationError")
        raise AssertionError("应该抛出 ValidationError")
    except ValidationError as e:
        print(f"✓ 正确抛出 ValidationError: {e}")

    # 测试 2: 传入 order_index 应该成功
    print("\n[测试 2] 传入 order_index 应该成功")
    try:
        data = {
            "id": "plandoc-test-provider-002",
            "goal_id": "goal-test-001",
            "status": "active",
            "order_index": 0,
        }
        doc_id = provider.create_plan_doc(data)
        print(f"✓ 创建成功: {doc_id}")

        doc = provider.get_plan_doc_by_id(doc_id)
        assert doc["order_index"] == 0
        print("✓ order_index 正确")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    print("\n" + "=" * 60)
    print("✓ PlanDocProvider 测试通过！")
    print("=" * 60)


def test_todo_aggregator_auto_calculates_order_index():
    """测试 TodoAggregator 自动计算 order_index"""
    print("\n" + "=" * 60)
    print("测试 TodoAggregator 自动计算 order_index")
    print("=" * 60)

    aggregator = TodoAggregator()
    test_date = "2026-04-26"

    # 测试 1: get_next_order_index 方法
    print("\n[测试 1] get_next_order_index 方法")
    try:
        next_order = aggregator.get_next_order_index(test_date)
        print(f"✓ 获取下一个 order_index: {next_order}")
        assert isinstance(next_order, int)
        print("✓ 返回类型正确")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    # 测试 2: create_todo 不传 order_index（自动计算）
    print("\n[测试 2] create_todo 不传 order_index（自动计算）")
    try:
        data = {"content": "测试任务 1", "date": test_date, "state": "pool"}
        todo_id = aggregator.create_todo(data)
        print(f"✓ 创建成功: {todo_id}")

        todo = aggregator.get_todo_by_id(todo_id)
        print(f"✓ order_index = {todo['order_index']}")
        assert todo["order_index"] == next_order
        print("✓ order_index 自动计算正确")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    # 测试 3: create_todo 传入自定义 order_index
    print("\n[测试 3] create_todo 传入自定义 order_index")
    try:
        custom_order = 999
        data = {
            "content": "测试任务 2",
            "date": test_date,
            "state": "pool",
            "order_index": custom_order,
        }
        todo_id = aggregator.create_todo(data)
        print(f"✓ 创建成功: {todo_id}")

        todo = aggregator.get_todo_by_id(todo_id)
        print(f"✓ order_index = {todo['order_index']}")
        assert todo["order_index"] == custom_order
        print("✓ 自定义 order_index 生效")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    print("\n" + "=" * 60)
    print("✓ TodoAggregator 测试通过！")
    print("=" * 60)


def test_plan_doc_aggregator_auto_calculates_order_index():
    """测试 PlanDocAggregator 自动计算 order_index"""
    print("\n" + "=" * 60)
    print("测试 PlanDocAggregator 自动计算 order_index")
    print("=" * 60)

    aggregator = PlanDocAggregator()
    test_goal_id = "goal-test-002"

    # 测试 1: get_next_order_index 方法
    print("\n[测试 1] get_next_order_index 方法")
    try:
        next_order = aggregator.get_next_order_index(test_goal_id)
        print(f"✓ 获取下一个 order_index: {next_order}")
        assert isinstance(next_order, int)
        print("✓ 返回类型正确")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    # 测试 2: create_plan_doc 不传 order_index（自动计算）
    print("\n[测试 2] create_plan_doc 不传 order_index（自动计算）")
    try:
        data = {"id": "plandoc-test-agg-001", "goal_id": test_goal_id, "status": "active"}
        doc_id = aggregator.create_plan_doc(data)
        print(f"✓ 创建成功: {doc_id}")

        doc = aggregator.get_plan_doc_by_id(doc_id)
        print(f"✓ order_index = {doc['order_index']}")
        assert doc["order_index"] == next_order
        print("✓ order_index 自动计算正确")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    # 测试 3: create_plan_doc 传入自定义 order_index
    print("\n[测试 3] create_plan_doc 传入自定义 order_index")
    try:
        custom_order = 888
        data = {
            "id": "plandoc-test-agg-002",
            "goal_id": test_goal_id,
            "status": "active",
            "order_index": custom_order,
        }
        doc_id = aggregator.create_plan_doc(data)
        print(f"✓ 创建成功: {doc_id}")

        doc = aggregator.get_plan_doc_by_id(doc_id)
        print(f"✓ order_index = {doc['order_index']}")
        assert doc["order_index"] == custom_order
        print("✓ 自定义 order_index 生效")
    except Exception as e:
        print(f"✗ 失败: {e}")
        raise

    print("\n" + "=" * 60)
    print("✓ PlanDocAggregator 测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("Provider 和 Aggregator 职责分离测试")
    print("=" * 60)

    try:
        test_todo_provider_requires_order_index()
        test_plan_doc_provider_requires_order_index()
        test_todo_aggregator_auto_calculates_order_index()
        test_plan_doc_aggregator_auto_calculates_order_index()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        print("\n架构总结：")
        print("- Provider 层：纯数据访问，必须传入 order_index")
        print("- Aggregator 层：包含业务逻辑，自动计算 order_index")
        print("- Service 层：应该使用 Aggregator 而不是 Provider")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ 测试失败: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        sys.exit(1)
