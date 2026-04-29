"""测试 ComputerUsageAggregator 的所有功能"""
import pytest
from lifeprism.repository.aggregators.computer_usage_aggregator import ComputerUsageAggregator
from lifeprism.repository.providers.common_query_options import QueryOptions


@pytest.fixture
def aggregator():
    """创建 aggregator 实例"""
    return ComputerUsageAggregator()


@pytest.mark.core
def test_query_computer_usage(aggregator):
    """测试通用查询接口"""
    options = QueryOptions(
        time_range=("2026-04-28 00:00:00", "2026-04-28 23:59:59"),
        page=1,
        page_size=10
    )
    records, total = aggregator.query_computer_usage(options)

    assert isinstance(records, list)
    assert isinstance(total, int)
    assert total > 0
    assert len(records) > 0
    assert 'id' in records[0]
    assert 'app' in records[0]


@pytest.mark.core
def test_query_computer_usage_with_names(aggregator):
    """测试查询并附加分类名称"""
    options = QueryOptions(
        time_range=("2026-04-28 00:00:00", "2026-04-28 23:59:59"),
        page=1,
        page_size=10
    )
    records, total = aggregator.query_computer_usage_with_names(options)

    assert isinstance(records, list)
    assert isinstance(total, int)
    assert len(records) > 0

    # 检查是否附加了分类名称
    for record in records:
        if record.get('category_id'):
            assert 'category_name' in record
        if record.get('sub_category_id'):
            assert 'sub_category_name' in record


@pytest.mark.core
def test_get_computer_usage_by_id(aggregator):
    """测试根据 ID 获取记录"""
    # 先查询获取一个 ID
    options = QueryOptions(
        time_range=("2026-04-28 00:00:00", "2026-04-28 23:59:59"),
        page=1,
        page_size=1
    )
    records, _ = aggregator.query_computer_usage(options)
    assert len(records) > 0

    record_id = records[0]['id']
    record = aggregator.get_computer_usage_by_id(record_id)

    assert record is not None
    assert record['id'] == record_id
    assert 'app' in record


@pytest.mark.core
def test_get_computer_usage_by_id_with_names(aggregator):
    """测试根据 ID 获取记录并附加分类名称"""
    # 先查询获取一个记录
    options = QueryOptions(
        time_range=("2026-04-28 00:00:00", "2026-04-28 23:59:59"),
        page=1,
        page_size=10
    )
    records, _ = aggregator.query_computer_usage(options)

    # 找一个有 category_id 的记录
    record_with_category = None
    for r in records:
        if r.get('category_id'):
            record_with_category = r
            break

    if record_with_category:
        record_id = record_with_category['id']
        record = aggregator.get_computer_usage_by_id_with_names(record_id)

        assert record is not None
        assert record['id'] == record_id
        assert 'category_name' in record


@pytest.mark.core
def test_create_and_delete_computer_usage(aggregator):
    """测试创建和删除记录"""
    # 创建测试数据
    test_data = {
        'id': 'test-record-001',
        'start_time': '2026-04-28 10:00:00',
        'end_time': '2026-04-28 10:05:00',
        'duration': 300,
        'app': 'test.exe',
        'title': 'Test Application'
    }

    created = aggregator.create_computer_usage(test_data)
    assert created is not None
    assert created['id'] == 'test-record-001'
    assert created['app'] == 'test.exe'

    # 删除测试数据
    deleted = aggregator.delete_computer_usage('test-record-001')
    assert deleted is True

    # 验证已删除
    record = aggregator.get_computer_usage_by_id('test-record-001')
    assert record is None


@pytest.mark.core
def test_update_computer_usage(aggregator):
    """测试更新记录"""
    # 创建测试数据
    test_data = {
        'id': 'test-record-002',
        'start_time': '2026-04-28 11:00:00',
        'end_time': '2026-04-28 11:05:00',
        'duration': 300,
        'app': 'test2.exe',
        'title': 'Test Application 2'
    }

    created = aggregator.create_computer_usage(test_data)
    assert created is not None

    # 更新数据
    update_data = {
        'title': 'Updated Test Application'
    }
    updated = aggregator.update_computer_usage('test-record-002', update_data)

    assert updated is not None
    assert updated['title'] == 'Updated Test Application'
    assert updated['app'] == 'test2.exe'

    # 清理测试数据
    aggregator.delete_computer_usage('test-record-002')
