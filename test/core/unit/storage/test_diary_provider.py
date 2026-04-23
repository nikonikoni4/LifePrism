"""
Diary Provider 单元测试

测试新 provider 的所有方法。
"""
import pytest
from lifeprism.storage.providers import DiaryProvider, QueryOptions


@pytest.fixture
def diary_provider(test_data_path):
    """创建 diary_provider 实例"""
    from lifeprism.config.settings_manager import settings
    settings._initialize()
    return DiaryProvider()


@pytest.fixture
def sample_diary_data():
    """测试用的日记数据"""
    return {
        'mood': 'happy',
        'importance': 'important',
        'custom_tags': '["测试", "单元测试"]',
        'word_count': 100,
    }


class TestDiaryProviderCore:
    """测试核心方法"""

    def test_insert_diary(self, diary_provider, sample_diary_data):
        """测试插入日记"""
        date = "2026-04-25"

        # 先删除可能存在的记录
        diary_provider.delete_diary(date)

        result = diary_provider.insert_diary(date, sample_diary_data)
        assert result is True

        # 验证插入成功
        diary = diary_provider.get_diary_by_id(date)
        assert diary is not None
        assert diary['date'] == date
        assert diary['mood'] == 'happy'

    def test_get_diary_by_id(self, diary_provider, sample_diary_data):
        """测试按 ID 获取日记"""
        date = "2026-04-26"
        diary_provider.insert_diary(date, sample_diary_data)

        diary = diary_provider.get_diary_by_id(date)
        assert diary is not None
        assert diary['date'] == date

        # 测试不存在的日记
        non_exist = diary_provider.get_diary_by_id("2099-12-31")
        assert non_exist is None

    def test_update_diary(self, diary_provider, sample_diary_data):
        """测试更新日记"""
        date = "2026-04-27"
        diary_provider.insert_diary(date, sample_diary_data)

        # 更新
        update_data = {'mood': 'very_happy', 'word_count': 200}
        result = diary_provider.update_diary(date, update_data)
        assert result is True

        # 验证更新成功
        diary = diary_provider.get_diary_by_id(date)
        assert diary['mood'] == 'very_happy'
        assert diary['word_count'] == 200

    def test_delete_diary(self, diary_provider, sample_diary_data):
        """测试删除日记"""
        date = "2026-04-28"
        diary_provider.insert_diary(date, sample_diary_data)

        # 删除
        result = diary_provider.delete_diary(date)
        assert result is True

        # 验证删除成功
        diary = diary_provider.get_diary_by_id(date)
        assert diary is None

    def test_query_diaries_basic(self, diary_provider):
        """测试基本查询"""
        # 插入测试数据
        for i in range(5):
            date = f"2026-05-{i+1:02d}"
            diary_provider.insert_diary(date, {'word_count': i * 10})

        # 查询所有
        results, total = diary_provider.query_diaries()
        assert total >= 5
        assert len(results) >= 5

    def test_query_diaries_with_date_range(self, diary_provider):
        """测试日期范围查询"""
        # 插入测试数据
        for i in range(10):
            date = f"2026-06-{i+1:02d}"
            diary_provider.insert_diary(date)

        # 查询日期范围
        options = QueryOptions(date_range=("2026-06-01", "2026-06-05"))
        results, total = diary_provider.query_diaries(options)
        assert total == 5
        assert len(results) == 5

    def test_query_diaries_with_filters(self, diary_provider):
        """测试筛选查询"""
        # 插入测试数据
        diary_provider.insert_diary("2026-07-01", {'mood': 'happy'})
        diary_provider.insert_diary("2026-07-02", {'mood': 'calm'})
        diary_provider.insert_diary("2026-07-03", {'mood': 'happy'})

        # 筛选 mood=happy
        options = QueryOptions(
            date_range=("2026-07-01", "2026-07-03"),
            filters={'mood': 'happy'}
        )
        results, total = diary_provider.query_diaries(options)
        assert total == 2
        assert all(r['mood'] == 'happy' for r in results)

    def test_query_diaries_with_pagination(self, diary_provider):
        """测试分页查询"""
        # 插入测试数据
        for i in range(20):
            date = f"2026-08-{i+1:02d}"
            diary_provider.insert_diary(date)

        # 第一页
        options = QueryOptions(
            date_range=("2026-08-01", "2026-08-20"),
            page=1,
            page_size=5
        )
        results, total = diary_provider.query_diaries(options)
        assert total == 20
        assert len(results) == 5

        # 第二页
        options = options.with_page(2, 5)
        results, total = diary_provider.query_diaries(options)
        assert total == 20
        assert len(results) == 5


class TestDiaryProviderSpecial:
    """测试特殊方法（兼容旧接口）"""

    def test_get_diary_by_date(self, diary_provider, sample_diary_data):
        """测试 get_diary_by_date（兼容方法）"""
        date = "2026-09-01"
        diary_provider.insert_diary(date, sample_diary_data)

        diary = diary_provider.get_diary_by_date(date)
        assert diary is not None
        assert diary['date'] == date

    def test_get_diaries_by_date_range(self, diary_provider):
        """测试 get_diaries_by_date_range（兼容方法）"""
        # 插入测试数据
        for i in range(5):
            date = f"2026-09-{i+10:02d}"
            diary_provider.insert_diary(date)

        results = diary_provider.get_diaries_by_date_range("2026-09-10", "2026-09-14")
        assert len(results) == 5
        # 验证降序排列
        assert results[0]['date'] > results[-1]['date']

    def test_create_diary(self, diary_provider):
        """测试 create_diary（兼容方法）"""
        date = "2026-09-20"

        # 先删除可能存在的记录
        diary_provider.delete_diary(date)

        result = diary_provider.create_diary(date)
        assert result is True

        diary = diary_provider.get_diary_by_date(date)
        assert diary is not None


class TestQueryOptionsImmutability:
    """测试 QueryOptions 不可变性"""

    def test_query_options_immutable(self):
        """测试 QueryOptions 是不可变的"""
        base = QueryOptions(filters={'mood': 'happy'})

        # 使用 with_* 方法不会修改原对象
        new_options = base.with_date_range("2026-01-01", "2026-01-31")

        assert base.date_range is None  # 原对象未改变
        assert new_options.date_range == ("2026-01-01", "2026-01-31")
        assert new_options.filters == {'mood': 'happy'}  # 保留原有 filters

    def test_query_options_with_filters_merge(self):
        """测试 with_filters 合并行为"""
        base = QueryOptions(filters={'mood': 'happy'})
        new_options = base.with_filters(importance='important')

        assert base.filters == {'mood': 'happy'}  # 原对象未改变
        assert new_options.filters == {'mood': 'happy', 'importance': 'important'}


class TestWhitelistValidation:
    """测试白名单验证"""

    def test_invalid_filter_field(self, diary_provider):
        """测试无效的筛选字段"""
        options = QueryOptions(filters={'invalid_field': 'value'})

        with pytest.raises(ValueError, match="Invalid filter field"):
            diary_provider.query_diaries(options)

    def test_invalid_order_field(self, diary_provider):
        """测试无效的排序字段"""
        options = QueryOptions(order_by='invalid_field')

        with pytest.raises(ValueError, match="Invalid order_by field"):
            diary_provider.query_diaries(options)

    def test_invalid_update_field(self, diary_provider):
        """测试无效的更新字段"""
        date = "2026-10-01"
        diary_provider.insert_diary(date)

        with pytest.raises(ValueError, match="Invalid update fields"):
            diary_provider.update_diary(date, {'invalid_field': 'value'})
