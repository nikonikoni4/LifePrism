"""
LWBaseDataProvider 通用方法单元测试

测试基类的通用 CRUD 方法，确保边界情况和错误处理正确。
"""
import pytest
from typing import Set

from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions


# ==================== 测试用 Mock Provider ====================

class MockProvider(LWBaseDataProvider):
    """测试用的 Mock Provider"""

    _TABLE_NAME = "test_table"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "date"
    _TIME_FIELD = "time"

    _FILTER_FIELDS: Set[str] = {'id', 'name', 'status', 'date', 'time'}
    _ORDER_FIELDS: Set[str] = {'id', 'name', 'created_at'}
    _SELECT_FIELDS: Set[str] = {'id', 'name', 'status', 'date', 'time', 'created_at'}
    _UPDATE_FIELDS: Set[str] = {'name', 'status'}


class MockProviderNoWhitelist(LWBaseDataProvider):
    """没有定义白名单的 Mock Provider"""

    _TABLE_NAME = "test_table"


class MockProviderInvalidTableName(LWBaseDataProvider):
    """表名不合法的 Mock Provider"""

    _TABLE_NAME = "test-table; DROP TABLE users;"  # SQL 注入尝试


class MockProviderNoDateField(LWBaseDataProvider):
    """没有日期字段的 Mock Provider"""

    _TABLE_NAME = "test_table"
    _DATE_FIELD = None
    _FILTER_FIELDS: Set[str] = {'id', 'name'}
    _ORDER_FIELDS: Set[str] = {'id', 'name'}


# ==================== Fixtures ====================

@pytest.fixture
def mock_provider(test_data_path):
    """创建 MockProvider 实例并初始化测试表"""
    from lifeprism.config.settings_manager import settings
    settings._initialize()

    provider = MockProvider()

    # 创建测试表
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id TEXT PRIMARY KEY,
                name TEXT,
                status TEXT,
                date TEXT,
                time TEXT,
                order_index INTEGER,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()

    yield provider

    # 清理测试表
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS test_table")
        conn.commit()


# ==================== 表名验证测试 ====================

class TestTableNameValidation:
    """测试表名验证"""

    def test_valid_table_name(self, mock_provider):
        """测试合法的表名"""
        # 不应该抛出异常
        mock_provider._validate_table_name()

    def test_invalid_table_name_with_special_chars(self, test_data_path):
        """测试包含特殊字符的表名"""
        from lifeprism.config.settings_manager import settings
        settings._initialize()

        provider = MockProviderInvalidTableName()
        with pytest.raises(ValueError, match="Invalid table name"):
            provider._validate_table_name()

    def test_missing_table_name(self, test_data_path):
        """测试未定义表名"""
        from lifeprism.config.settings_manager import settings
        settings._initialize()

        provider = LWBaseDataProvider()
        with pytest.raises(NotImplementedError, match="必须定义 _TABLE_NAME"):
            provider._validate_table_name()


# ==================== 查询方法测试 ====================

class TestGenericQuery:
    """测试 _generic_query() 方法"""

    def test_query_with_invalid_filter_field(self, mock_provider):
        """测试使用无效的筛选字段"""
        options = QueryOptions(filters={'invalid_field': 'value'})
        with pytest.raises(ValueError, match="Invalid filter field"):
            mock_provider._generic_query(options)

    def test_query_with_invalid_order_field(self, mock_provider):
        """测试使用无效的排序字段"""
        options = QueryOptions(order_by='invalid_field')
        with pytest.raises(ValueError, match="Invalid order_by field"):
            mock_provider._generic_query(options)

    def test_query_with_invalid_select_field(self, mock_provider):
        """测试使用无效的查询字段"""
        options = QueryOptions(fields=['invalid_field'])
        with pytest.raises(ValueError, match="Invalid select fields"):
            mock_provider._generic_query(options)

    def test_query_without_whitelist_definition(self, test_data_path):
        """测试未定义白名单时使用 filters"""
        from lifeprism.config.settings_manager import settings
        settings._initialize()

        provider = MockProviderNoWhitelist()
        options = QueryOptions(filters={'name': 'test'})
        with pytest.raises(NotImplementedError, match="必须定义 _FILTER_FIELDS"):
            provider._generic_query(options)

    def test_query_date_range_without_date_field(self, test_data_path):
        """测试在没有日期字段的表上使用日期范围查询"""
        from lifeprism.config.settings_manager import settings
        settings._initialize()

        provider = MockProviderNoDateField()
        options = QueryOptions(date_range=("2026-01-01", "2026-12-31"))
        with pytest.raises(ValueError, match="不支持日期范围查询"):
            provider._generic_query(options)

    def test_query_time_range_without_time_field(self, test_data_path):
        """测试在没有时间字段的表上使用时间范围查询"""
        from lifeprism.config.settings_manager import settings
        settings._initialize()

        provider = MockProviderNoDateField()
        options = QueryOptions(time_range=("08:00:00", "18:00:00"))
        with pytest.raises(ValueError, match="不支持时间范围查询"):
            provider._generic_query(options)

    def test_query_with_order_by_none(self, mock_provider):
        """测试 order_by=None 时不生成 ORDER BY 子句"""
        # 插入测试数据
        with mock_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO test_table (id, name, status) VALUES ('1', 'test1', 'active')")
            cursor.execute("INSERT INTO test_table (id, name, status) VALUES ('2', 'test2', 'active')")
            conn.commit()

        # 测试 order_by=None
        options = QueryOptions(order_by=None)
        results, total = mock_provider._generic_query(options)
        assert len(results) == 2
        assert total == 2

    def test_build_order_clause_with_none(self, mock_provider):
        """测试 _build_order_clause() 处理 None 的情况"""
        options = QueryOptions(order_by=None)
        order_clause = mock_provider._build_order_clause(options)
        assert order_clause == "", "order_by=None should return empty string"

    def test_build_order_clause_with_valid_field(self, mock_provider):
        """测试 _build_order_clause() 生成正确的 ORDER BY 子句"""
        # 测试升序
        options = QueryOptions(order_by='id', order_desc=False)
        order_clause = mock_provider._build_order_clause(options)
        assert order_clause == "ORDER BY id ASC"

        # 测试降序
        options = QueryOptions(order_by='name', order_desc=True)
        order_clause = mock_provider._build_order_clause(options)
        assert order_clause == "ORDER BY name DESC"


# ==================== 插入方法测试 ====================

class TestGenericInsert:
    """测试 _generic_insert() 方法"""

    def test_insert_with_id_prefix(self, mock_provider):
        """测试自动生成 ID"""
        data = {'name': 'test', 'status': 'active'}
        record_id = mock_provider._generic_insert(data, id_prefix='t-')

        # 验证 ID 格式
        assert record_id.startswith('t-')
        assert len(record_id) == 10  # t- + 8 位 hex

    def test_insert_with_auto_order_index(self, mock_provider):
        """测试自动计算 order_index"""
        # 第一次插入
        data1 = {'name': 'test1', 'status': 'active'}
        mock_provider._generic_insert(data1, id_prefix='t-', auto_order_index=True)

        # 第二次插入应该有更大的 order_index
        data2 = {'name': 'test2', 'status': 'active'}
        mock_provider._generic_insert(data2, id_prefix='t-', auto_order_index=True)

        # 验证 order_index 被设置（通过查询验证）
        # 注意：这里只是测试方法不抛出异常，实际值需要查询数据库验证


# ==================== 更新方法测试 ====================

class TestGenericUpdate:
    """测试 _generic_update() 方法"""

    def test_update_with_invalid_field(self, mock_provider):
        """测试使用无效的更新字段"""
        data = {'invalid_field': 'value'}
        with pytest.raises(ValueError, match="Invalid update fields"):
            mock_provider._generic_update('test-id', data)

    def test_update_with_empty_data(self, mock_provider):
        """测试空数据更新"""
        result = mock_provider._generic_update('test-id', {})
        assert result is True  # 空数据应该返回 True


# ==================== 删除方法测试 ====================

class TestGenericDelete:
    """测试 _generic_delete() 方法"""

    def test_delete_nonexistent_record(self, mock_provider):
        """测试删除不存在的记录"""
        # 删除不存在的记录应该返回 False
        result = mock_provider._generic_delete('nonexistent-id')
        assert result is False


# ==================== QueryOptions 测试 ====================

class TestQueryOptions:
    """测试 QueryOptions 类"""

    def test_immutability(self):
        """测试 QueryOptions 的不可变性"""
        options = QueryOptions(filters={'status': 'active'})

        # 尝试修改应该失败
        with pytest.raises(Exception):  # frozen dataclass 会抛出异常
            options.filters = {'status': 'inactive'}

    def test_with_date_range(self):
        """测试 with_date_range() 方法"""
        options = QueryOptions()
        new_options = options.with_date_range("2026-01-01", "2026-12-31")

        assert new_options.date_range == ("2026-01-01", "2026-12-31")
        assert options.date_range is None  # 原对象不变

    def test_with_time_range(self):
        """测试 with_time_range() 方法"""
        options = QueryOptions()
        new_options = options.with_time_range("08:00:00", "18:00:00")

        assert new_options.time_range == ("08:00:00", "18:00:00")
        assert options.time_range is None  # 原对象不变

    def test_with_filters(self):
        """测试 with_filters() 方法"""
        options = QueryOptions(filters={'status': 'active'})
        new_options = options.with_filters(name='test')

        assert new_options.filters == {'status': 'active', 'name': 'test'}
        assert options.filters == {'status': 'active'}  # 原对象不变

    def test_with_order(self):
        """测试 with_order() 方法"""
        options = QueryOptions()
        new_options = options.with_order('name', desc=False)

        assert new_options.order_by == 'name'
        assert new_options.order_desc is False

    def test_with_page(self):
        """测试 with_page() 方法"""
        options = QueryOptions()
        new_options = options.with_page(2, 50)

        assert new_options.page == 2
        assert new_options.page_size == 50

    def test_with_fields(self):
        """测试 with_fields() 方法"""
        options = QueryOptions()
        new_options = options.with_fields('id', 'name', 'status')

        assert new_options.fields == ['id', 'name', 'status']

    def test_page_validation(self):
        """测试页码验证"""
        with pytest.raises(ValueError, match="page must be >= 1"):
            QueryOptions(page=0, page_size=10)

    def test_page_size_validation(self):
        """测试页大小验证"""
        with pytest.raises(ValueError, match="page_size must be between 1 and 1000"):
            QueryOptions(page=1, page_size=0)

        with pytest.raises(ValueError, match="page_size must be between 1 and 1000"):
            QueryOptions(page=1, page_size=1001)
