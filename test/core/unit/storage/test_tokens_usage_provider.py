"""
TokensUsageProvider 单元测试

测试 TokensUsageProvider 的所有 CRUD 方法
"""
import pytest
from datetime import datetime

from lifeprism.storage.providers import tokens_usage_provider
from lifeprism.storage.providers.common_query_options import QueryOptions


# ==================== Fixtures ====================

@pytest.fixture
def sample_tokens_usage_data():
    """测试用的 token 使用数据"""
    return {
        'session_id': 'test-session-001',
        'input_tokens': 100,
        'output_tokens': 200,
        'total_tokens': 300,
        'search_count': 5,
        'result_items_count': 10,
        'mode': 'classification'
    }


@pytest.fixture
def cleanup_test_data():
    """清理测试数据"""
    yield
    # 测试后清理
    try:
        tokens_usage_provider.delete_tokens_usage('test-session-001')
        tokens_usage_provider.delete_tokens_usage('test-session-002')
        tokens_usage_provider.delete_tokens_usage('test-session-003')
    except:
        pass


# ==================== 插入测试 ====================

class TestInsertTokensUsage:
    """测试插入方法"""

    def test_insert_tokens_usage_success(self, sample_tokens_usage_data, cleanup_test_data):
        """测试成功插入记录"""
        result = tokens_usage_provider.insert_tokens_usage(sample_tokens_usage_data)
        assert result is True

        # 验证插入的数据
        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record is not None
        assert record['session_id'] == 'test-session-001'
        assert record['input_tokens'] == 100
        assert record['output_tokens'] == 200
        assert record['total_tokens'] == 300
        assert record['mode'] == 'classification'

    def test_insert_tokens_usage_with_defaults(self, cleanup_test_data):
        """测试插入时使用默认值"""
        data = {'session_id': 'test-session-002'}
        result = tokens_usage_provider.insert_tokens_usage(data)
        assert result is True

        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-002')
        assert record['input_tokens'] == 0
        assert record['output_tokens'] == 0
        assert record['total_tokens'] == 0
        assert record['search_count'] == 0
        assert record['result_items_count'] == 0
        assert record['mode'] == 'classification'

    def test_insert_tokens_usage_missing_session_id(self):
        """测试缺少 session_id 时插入失败"""
        data = {'input_tokens': 100}
        result = tokens_usage_provider.insert_tokens_usage(data)
        assert result is False

    def test_insert_tokens_usage_invalid_fields(self, cleanup_test_data):
        """测试包含无效字段时插入失败"""
        data = {
            'session_id': 'test-session-003',
            'invalid_field': 'value'
        }
        result = tokens_usage_provider.insert_tokens_usage(data)
        assert result is False


# ==================== 查询测试 ====================

class TestQueryTokensUsage:
    """测试查询方法"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, cleanup_test_data):
        """准备测试数据"""
        # 插入测试数据
        tokens_usage_provider.insert_tokens_usage({
            'session_id': 'test-session-001',
            'input_tokens': 100,
            'output_tokens': 200,
            'total_tokens': 300,
            'mode': 'classification'
        })
        tokens_usage_provider.insert_tokens_usage({
            'session_id': 'test-session-002',
            'input_tokens': 150,
            'output_tokens': 250,
            'total_tokens': 400,
            'mode': 'chatbot'
        })
        yield

    def test_get_tokens_usage_by_session_id(self):
        """测试按 session_id 获取记录"""
        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record is not None
        assert record['session_id'] == 'test-session-001'
        assert record['input_tokens'] == 100

    def test_get_tokens_usage_by_session_id_not_found(self):
        """测试获取不存在的记录"""
        record = tokens_usage_provider.get_tokens_usage_by_session_id('non-existent')
        assert record is None

    def test_query_tokens_usage_by_mode(self):
        """测试按 mode 查询"""
        options = QueryOptions(
            filters={'mode': 'classification'},
            order_by='session_id'
        )
        results, total = tokens_usage_provider.query_tokens_usage(options)
        assert total >= 1
        assert all(r['mode'] == 'classification' for r in results)

    def test_query_tokens_usage_all(self):
        """测试查询所有记录"""
        options = QueryOptions(order_by='session_id')
        results, total = tokens_usage_provider.query_tokens_usage(options)
        assert total >= 2


# ==================== 更新测试 ====================

class TestUpdateTokensUsage:
    """测试更新方法"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, cleanup_test_data):
        """准备测试数据"""
        tokens_usage_provider.insert_tokens_usage({
            'session_id': 'test-session-001',
            'input_tokens': 100,
            'output_tokens': 200,
            'total_tokens': 300,
            'mode': 'classification'
        })
        yield

    def test_update_tokens_usage_success(self):
        """测试成功更新记录"""
        update_data = {
            'input_tokens': 150,
            'output_tokens': 250,
            'total_tokens': 400
        }
        result = tokens_usage_provider.update_tokens_usage('test-session-001', update_data)
        assert result is True

        # 验证更新后的数据
        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record['input_tokens'] == 150
        assert record['output_tokens'] == 250
        assert record['total_tokens'] == 400

    def test_update_tokens_usage_empty_data(self):
        """测试更新空数据"""
        result = tokens_usage_provider.update_tokens_usage('test-session-001', {})
        assert result is True

    def test_update_tokens_usage_invalid_fields(self):
        """测试更新包含无效字段"""
        update_data = {'invalid_field': 'value'}
        result = tokens_usage_provider.update_tokens_usage('test-session-001', update_data)
        assert result is False


# ==================== Upsert 测试 ====================

class TestUpsertTokensUsage:
    """测试 upsert 方法"""

    def test_upsert_insert_new_record(self, cleanup_test_data):
        """测试 upsert 插入新记录"""
        data = {
            'input_tokens': 100,
            'output_tokens': 200,
            'total_tokens': 300,
            'mode': 'classification'
        }
        result = tokens_usage_provider.upsert_tokens_usage('test-session-001', data)
        assert result is True

        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record is not None
        assert record['input_tokens'] == 100

    def test_upsert_update_existing_record(self, cleanup_test_data):
        """测试 upsert 更新已存在的记录"""
        # 先插入
        tokens_usage_provider.insert_tokens_usage({
            'session_id': 'test-session-001',
            'input_tokens': 100,
            'output_tokens': 200,
            'total_tokens': 300,
            'mode': 'classification'
        })

        # 再 upsert
        data = {
            'input_tokens': 150,
            'output_tokens': 250,
            'total_tokens': 400
        }
        result = tokens_usage_provider.upsert_tokens_usage('test-session-001', data)
        assert result is True

        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record['input_tokens'] == 150
        assert record['output_tokens'] == 250


# ==================== 删除测试 ====================

class TestDeleteTokensUsage:
    """测试删除方法"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, cleanup_test_data):
        """准备测试数据"""
        tokens_usage_provider.insert_tokens_usage({
            'session_id': 'test-session-001',
            'input_tokens': 100,
            'output_tokens': 200,
            'total_tokens': 300,
            'mode': 'classification'
        })
        yield

    def test_delete_tokens_usage_success(self):
        """测试成功删除记录"""
        result = tokens_usage_provider.delete_tokens_usage('test-session-001')
        assert result is True

        # 验证已删除
        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record is None

    def test_delete_tokens_usage_not_found(self):
        """测试删除不存在的记录"""
        result = tokens_usage_provider.delete_tokens_usage('non-existent')
        assert result is False


# ==================== 批量插入测试 ====================

class TestBatchInsertTokensUsage:
    """测试批量插入方法"""

    def test_batch_insert_tokens_usage_success(self, cleanup_test_data):
        """测试成功批量插入"""
        data_list = [
            {
                'session_id': 'test-session-001',
                'input_tokens': 100,
                'output_tokens': 200,
                'total_tokens': 300,
                'mode': 'classification'
            },
            {
                'session_id': 'test-session-002',
                'input_tokens': 150,
                'output_tokens': 250,
                'total_tokens': 400,
                'mode': 'chatbot'
            }
        ]
        affected = tokens_usage_provider.batch_insert_tokens_usage(data_list)
        assert affected == 2

        # 验证插入的数据
        record1 = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        record2 = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-002')
        assert record1 is not None
        assert record2 is not None

    def test_batch_insert_tokens_usage_with_defaults(self, cleanup_test_data):
        """测试批量插入时使用默认值"""
        data_list = [
            {'session_id': 'test-session-001'},
            {'session_id': 'test-session-002'}
        ]
        affected = tokens_usage_provider.batch_insert_tokens_usage(data_list)
        assert affected == 2

        record = tokens_usage_provider.get_tokens_usage_by_session_id('test-session-001')
        assert record['mode'] == 'classification'
        assert record['search_count'] == 0
