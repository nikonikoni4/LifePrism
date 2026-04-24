"""
SinglePurposeMapCacheProvider 单元测试

测试 single_purpose_map_cache 表的所有 CRUD 操作。
"""
import pytest
import uuid
from lifeprism.repository.providers import single_purpose_map_cache_provider
from lifeprism.repository.providers.common_query_options import QueryOptions


# ==================== 测试辅助函数 ====================

def generate_test_id():
    """生成测试用的 ID"""
    return f"s-{uuid.uuid4().hex[:8]}"


def create_test_record(cache_id=None, **kwargs):
    """创建测试记录"""
    if cache_id is None:
        cache_id = generate_test_id()

    # 使用 cache_id 作为唯一标识，避免 UNIQUE 约束冲突
    unique_suffix = cache_id.split('-')[1] if '-' in cache_id else cache_id[:8]

    record = {
        'id': cache_id,
        'app': kwargs.get('app', f'test-{unique_suffix}.exe'),
        'title': kwargs.get('title', f'Test Title {unique_suffix}'),
        'app_description': kwargs.get('app_description', 'Test app description'),
        'category_id': kwargs.get('category_id', 'test_category'),
        'sub_category_id': kwargs.get('sub_category_id', 'test_sub_category'),
        'state': kwargs.get('state', 1),
        'link_to_goal_id': kwargs.get('link_to_goal_id', None),
    }
    return record


# ==================== 测试类 ====================

class TestInsertSinglePurposeMapCache:
    """测试插入操作"""

    def test_insert_success(self):
        """测试成功插入记录"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id)

        result = single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)
        assert result is True

        # 验证插入成功
        record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
        assert record is not None
        assert record['id'] == cache_id
        assert record['app'] == data['app']
        assert record['title'] == data['title']

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)

    def test_insert_with_optional_fields(self):
        """测试插入带可选字段的记录"""
        cache_id = generate_test_id()
        data = create_test_record(
            cache_id,
            app='pycharm.exe',
            title='PyCharm',
            app_description='PyCharm IDE',
            category_id='work',
            sub_category_id='coding',
            link_to_goal_id='goal-456'
        )

        result = single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)
        assert result is True

        # 验证字段
        record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
        assert record['app_description'] == 'PyCharm IDE'
        assert record['category_id'] == 'work'
        assert record['sub_category_id'] == 'coding'
        assert record['link_to_goal_id'] == 'goal-456'

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)

    def test_insert_missing_required_fields(self):
        """测试缺少必需字段时插入失败"""
        cache_id = generate_test_id()

        # 缺少 app 字段
        data = {'id': cache_id, 'title': 'Test'}
        result = single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)
        assert result is False

    def test_insert_invalid_fields(self):
        """测试包含非法字段时插入失败"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id)
        data['invalid_field'] = 'invalid'

        result = single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)
        assert result is False


class TestQuerySinglePurposeMapCache:
    """测试查询操作"""

    def test_query_all(self):
        """测试查询所有记录"""
        # 插入测试数据
        cache_id1 = generate_test_id()
        cache_id2 = generate_test_id()
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(create_test_record(cache_id1))
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(create_test_record(cache_id2))

        # 查询
        results, total = single_purpose_map_cache_provider.query_single_purpose_map_cache()
        assert total >= 2
        assert len(results) >= 2

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id1)
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id2)

    def test_query_with_filters(self):
        """测试带过滤条件的查询"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id, app='unique_single_app.exe', title='Unique Single Title')
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)

        # 按 app 过滤
        options = QueryOptions(filters={'app': 'unique_single_app.exe'}, order_by='id')
        results, total = single_purpose_map_cache_provider.query_single_purpose_map_cache(options)
        assert total >= 1
        assert any(r['id'] == cache_id for r in results)

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)

    def test_query_with_pagination(self):
        """测试分页查询"""
        # 插入多条测试数据
        cache_ids = [generate_test_id() for _ in range(5)]
        for cache_id in cache_ids:
            single_purpose_map_cache_provider.insert_single_purpose_map_cache(create_test_record(cache_id))

        # 分页查询
        options = QueryOptions(page=1, page_size=2, order_by='id')
        results, total = single_purpose_map_cache_provider.query_single_purpose_map_cache(options)
        assert len(results) <= 2
        assert total >= 5

        # 清理
        for cache_id in cache_ids:
            single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)

    def test_get_by_id(self):
        """测试按 ID 获取记录"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id)
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)

        # 获取记录
        record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
        assert record is not None
        assert record['id'] == cache_id

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)


class TestUpdateSinglePurposeMapCache:
    """测试更新操作"""

    def test_update_success(self):
        """测试成功更新记录"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id)
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)

        # 更新
        update_data = {'app_description': 'Updated description', 'state': 0}
        result = single_purpose_map_cache_provider.update_single_purpose_map_cache(cache_id, update_data)
        assert result is True

        # 验证更新
        record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
        assert record['app_description'] == 'Updated description'
        assert record['state'] == 0

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)

    def test_update_nonexistent_record(self):
        """测试更新不存在的记录"""
        cache_id = generate_test_id()
        update_data = {'app_description': 'Updated'}

        result = single_purpose_map_cache_provider.update_single_purpose_map_cache(cache_id, update_data)
        assert result is False

    def test_update_invalid_fields(self):
        """测试更新非法字段"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id)
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)

        # 尝试更新非法字段
        update_data = {'invalid_field': 'invalid'}
        result = single_purpose_map_cache_provider.update_single_purpose_map_cache(cache_id, update_data)
        assert result is False

        # 清理
        single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)


class TestDeleteSinglePurposeMapCache:
    """测试删除操作"""

    def test_delete_success(self):
        """测试成功删除记录"""
        cache_id = generate_test_id()
        data = create_test_record(cache_id)
        single_purpose_map_cache_provider.insert_single_purpose_map_cache(data)

        # 删除
        result = single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)
        assert result is True

        # 验证删除
        record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
        assert record is None

    def test_delete_nonexistent_record(self):
        """测试删除不存在的记录"""
        cache_id = generate_test_id()
        result = single_purpose_map_cache_provider.delete_single_purpose_map_cache(cache_id)
        assert result is False


class TestBatchOperations:
    """测试批量操作"""

    def test_batch_insert(self):
        """测试批量插入"""
        cache_ids = [generate_test_id() for _ in range(3)]
        data_list = [create_test_record(cache_id) for cache_id in cache_ids]

        count = single_purpose_map_cache_provider.batch_insert_single_purpose_map_cache(data_list)
        assert count == 3

        # 验证插入
        for cache_id in cache_ids:
            record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
            assert record is not None

        # 清理
        single_purpose_map_cache_provider.batch_delete_single_purpose_map_cache(cache_ids)

    def test_batch_update(self):
        """测试批量更新"""
        cache_ids = [generate_test_id() for _ in range(3)]
        for cache_id in cache_ids:
            single_purpose_map_cache_provider.insert_single_purpose_map_cache(create_test_record(cache_id))

        # 批量更新
        update_data = {'state': 0}
        count = single_purpose_map_cache_provider.batch_update_single_purpose_map_cache(cache_ids, update_data)
        assert count == 3

        # 验证更新
        for cache_id in cache_ids:
            record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
            assert record['state'] == 0

        # 清理
        single_purpose_map_cache_provider.batch_delete_single_purpose_map_cache(cache_ids)

    def test_batch_delete(self):
        """测试批量删除"""
        cache_ids = [generate_test_id() for _ in range(3)]
        for cache_id in cache_ids:
            single_purpose_map_cache_provider.insert_single_purpose_map_cache(create_test_record(cache_id))

        # 批量删除
        count = single_purpose_map_cache_provider.batch_delete_single_purpose_map_cache(cache_ids)
        assert count == 3

        # 验证删除
        for cache_id in cache_ids:
            record = single_purpose_map_cache_provider.get_single_purpose_map_cache_by_id(cache_id)
            assert record is None
