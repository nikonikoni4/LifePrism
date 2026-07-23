"""
ComputerUsageProvider 5 个新增方法 + Aggregator 委托测试

对应 issue: 02-computer-usage-provider-gap-methods
对应 PRD: deletion-sync-02a-statistical（Slice 02 预重构）

测试接缝：
- S1: Provider 层 5 个新增方法（batch_update / batch_delete / update_by_filter / get_total_duration / get_top_groups_by_duration）
- S2: Aggregator 层 5 个委托方法（验证 computer_usage_repository.xxx(...) 可调用）
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 共用工具函数 ====================


def _create_user_app_behavior_log(db):
    """创建 user_app_behavior_log 表（含 hash_id 字段，按 USER_APP_BEHAVIOR_LOG_CONFIG schema）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_app_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER,
                app TEXT NOT NULL,
                title TEXT,
                is_multipurpose_app INTEGER DEFAULT 0,
                category_id TEXT,
                sub_category_id TEXT,
                link_to_goal_id TEXT DEFAULT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(app, start_time),
                CHECK(end_time > start_time)
            )
            """
        )
        conn.commit()


def _create_deletion_log(db):
    """创建 deletion_log 表（按 ADR 2026-07-22 schema）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS deletion_log (
                id TEXT PRIMARY KEY,
                target_table TEXT NOT NULL,
                record_id TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(target_table, record_id)
            )
            """
        )
        conn.commit()


def _clear_tables(db, table_names):
    """清理指定表的数据"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for name in table_names:
            cursor.execute(f"DELETE FROM {name}")
        conn.commit()


def _count_tombstones(db, target_table):
    """查询 deletion_log 中的墓碑数量"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM deletion_log WHERE target_table = ?",
            (target_table,),
        )
        return cursor.fetchone()[0]


def _get_tombstone_record_ids(db, target_table):
    """查询 deletion_log 中指定表的所有墓碑 record_id"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT record_id FROM deletion_log WHERE target_table = ?",
            (target_table,),
        )
        return [row[0] for row in cursor.fetchall()]


def _insert_record(provider, **kwargs):
    """插入测试记录，返回 record_id（字符串）

    通过 _generic_insert 直接插入，自动生成 hash_id / created_at / updated_at。
    """
    defaults = {
        "start_time": "2026-07-23T10:00:00.000000+00:00",
        "end_time": "2026-07-23T11:00:00.000000+00:00",
        "duration": 3600,
        "app": "test_app.exe",
        "title": "Test Title",
        "is_multipurpose_app": 0,
    }
    defaults.update(kwargs)
    return provider._generic_insert(defaults)


# ==================== Fixtures ====================


@pytest.fixture
def provider_fixture(test_data_path):
    """创建 ComputerUsageProvider 实例并初始化 user_app_behavior_log + deletion_log 表

    user_app_behavior_log 是 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中，前缀 awbl-），
    也是 SYNC_TABLES 成员。墓碑 record_id = hash_id。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.computer_usage_provider import ComputerUsageProvider

    settings._initialize()

    provider = ComputerUsageProvider()

    _create_user_app_behavior_log(provider.db)
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["user_app_behavior_log", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["user_app_behavior_log", "deletion_log"])


@pytest.fixture
def aggregator_fixture(test_data_path):
    """创建 ComputerUsageAggregator 实例并初始化底层表

    Aggregator 内部创建自己的 ComputerUsageProvider，共享同一 db_manager 单例，
    因此数据互通。用于验证委托方法可调用。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.aggregators.computer_usage_aggregator import ComputerUsageAggregator

    settings._initialize()

    aggregator = ComputerUsageAggregator()

    _create_user_app_behavior_log(aggregator.computer_usage_provider.db)
    _create_deletion_log(aggregator.computer_usage_provider.db)
    _clear_tables(
        aggregator.computer_usage_provider.db,
        ["user_app_behavior_log", "deletion_log"],
    )

    yield aggregator

    _clear_tables(
        aggregator.computer_usage_provider.db,
        ["user_app_behavior_log", "deletion_log"],
    )


# ==================== 1. batch_update_computer_usage 测试 ====================


class TestBatchUpdateComputerUsageProvider:
    """测试 ComputerUsageProvider.batch_update_computer_usage"""

    def test_batch_update_returns_affected_count(self, provider_fixture):
        """批量更新返回受影响行数"""
        provider = provider_fixture
        ids = []
        for i in range(3):
            rid = _insert_record(
                provider,
                start_time=f"2026-07-23T1{i}:00:00.000000+00:00",
                end_time=f"2026-07-23T1{i}:30:00.000000+00:00",
                app=f"app-{i}.exe",
            )
            ids.append(str(rid))

        affected = provider.batch_update_computer_usage(
            ids, {"category_id": "cat-new", "sub_category_id": "sub-new"}
        )
        assert affected == 3, f"应更新 3 条记录，实际: {affected}"

        # 验证字段已更新
        for rid in ids:
            record = provider.get_computer_usage_by_id(rid)
            assert record is not None
            assert record["category_id"] == "cat-new"
            assert record["sub_category_id"] == "sub-new"

    def test_batch_update_empty_ids_returns_zero(self, provider_fixture):
        """空 ID 列表返回 0"""
        provider = provider_fixture
        affected = provider.batch_update_computer_usage([], {"category_id": "cat-x"})
        assert affected == 0

    def test_batch_update_skips_none_values(self, provider_fixture):
        """data 中 None 值被跳过（不修改该字段，不设为 NULL）

        先插入有 sub_category_id 的记录，再更新时传 sub_category_id=None，
        验证 sub_category_id 保持原值不变（None=跳过，不是清除为 NULL）。
        """
        provider = provider_fixture
        rid = _insert_record(
            provider, category_id="cat-original", sub_category_id="sub-original"
        )
        affected = provider.batch_update_computer_usage(
            [str(rid)], {"category_id": "cat-new", "sub_category_id": None}
        )
        assert affected == 1

        record = provider.get_computer_usage_by_id(str(rid))
        assert record["category_id"] == "cat-new"
        # sub_category_id 应保持原值 "sub-original"（None 被跳过，不设为 NULL）
        assert record["sub_category_id"] == "sub-original"

    def test_batch_update_rejects_invalid_field(self, provider_fixture):
        """不在白名单内的字段拒绝执行"""
        provider = provider_fixture
        rid = _insert_record(provider)
        with pytest.raises((ValueError, Exception)):
            provider.batch_update_computer_usage(
                [str(rid)], {"invalid_field": "value"}
            )

    def test_batch_update_partial_match(self, provider_fixture):
        """部分 ID 不存在时只更新存在的记录"""
        provider = provider_fixture
        rid = _insert_record(provider)
        affected = provider.batch_update_computer_usage(
            [str(rid), "999999"], {"category_id": "cat-x"}
        )
        assert affected == 1, f"只应更新 1 条存在的记录，实际: {affected}"


class TestBatchUpdateComputerUsageAggregator:
    """测试 ComputerUsageAggregator.batch_update_computer_usage 委托"""

    def test_aggregator_delegates_batch_update(self, aggregator_fixture):
        """Aggregator 委托 batch_update_computer_usage 给 Provider"""
        aggregator = aggregator_fixture
        ids = []
        for i in range(2):
            rid = _insert_record(
                aggregator.computer_usage_provider,
                start_time=f"2026-07-23T0{i}:00:00.000000+00:00",
                end_time=f"2026-07-23T0{i}:30:00.000000+00:00",
                app=f"agg-app-{i}.exe",
            )
            ids.append(str(rid))

        affected = aggregator.batch_update_computer_usage(
            ids, {"category_id": "cat-agg"}
        )
        assert affected == 2

        # 验证字段已通过委托更新
        for rid in ids:
            record = aggregator.get_computer_usage_by_id(rid)
            assert record["category_id"] == "cat-agg"


# ==================== 2. batch_delete_computer_usage 测试 ====================


class TestBatchDeleteComputerUsageProvider:
    """测试 ComputerUsageProvider.batch_delete_computer_usage（含写墓碑）"""

    def test_batch_delete_writes_tombstone_for_each_record(self, provider_fixture):
        """批量删除为每条记录写墓碑（record_id = hash_id，因为 AUTOINCREMENT 表）"""
        provider = provider_fixture
        ids = []
        hash_ids = []
        for i in range(3):
            rid = _insert_record(
                provider,
                start_time=f"2026-07-23T0{i}:00:00.000000+00:00",
                end_time=f"2026-07-23T0{i}:30:00.000000+00:00",
                app=f"del-app-{i}.exe",
            )
            ids.append(str(rid))
            # 获取 hash_id（墓碑 record_id 应为 hash_id）
            record = provider.get_computer_usage_by_id(str(rid))
            hash_ids.append(record["hash_id"])

        deleted = provider.batch_delete_computer_usage(ids)
        assert deleted == 3, f"应删除 3 条记录，实际: {deleted}"

        # 验证记录已消失
        for rid in ids:
            assert provider.get_computer_usage_by_id(rid) is None

        # 验证 3 条墓碑已写入 deletion_log
        count = _count_tombstones(provider.db, "user_app_behavior_log")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证墓碑 record_id = hash_id（不是主键 id）
        tombstone_record_ids = set(_get_tombstone_record_ids(provider.db, "user_app_behavior_log"))
        for hid in hash_ids:
            assert hid in tombstone_record_ids, f"hash_id '{hid}' 应有对应墓碑"

    def test_batch_delete_empty_list_returns_zero(self, provider_fixture):
        """空列表返回 0，不写墓碑"""
        provider = provider_fixture
        deleted = provider.batch_delete_computer_usage([])
        assert deleted == 0

        count = _count_tombstones(provider.db, "user_app_behavior_log")
        assert count == 0, "空列表不应写墓碑"


class TestBatchDeleteComputerUsageAggregator:
    """测试 ComputerUsageAggregator.batch_delete_computer_usage 委托"""

    def test_aggregator_delegates_batch_delete(self, aggregator_fixture):
        """Aggregator 委托 batch_delete_computer_usage 给 Provider"""
        aggregator = aggregator_fixture
        ids = []
        for i in range(2):
            rid = _insert_record(
                aggregator.computer_usage_provider,
                start_time=f"2026-07-23T0{i}:00:00.000000+00:00",
                end_time=f"2026-07-23T0{i}:30:00.000000+00:00",
                app=f"agg-del-{i}.exe",
            )
            ids.append(str(rid))

        deleted = aggregator.batch_delete_computer_usage(ids)
        assert deleted == 2

        # 验证记录已消失
        for rid in ids:
            assert aggregator.get_computer_usage_by_id(rid) is None

        # 验证墓碑已写入
        count = _count_tombstones(
            aggregator.computer_usage_provider.db, "user_app_behavior_log"
        )
        assert count == 2


# ==================== 3. update_by_filter 测试 ====================


class TestUpdateByFilterProvider:
    """测试 ComputerUsageProvider.update_by_filter"""

    def test_update_by_filter_basic(self, provider_fixture):
        """基本条件更新：按 app 更新 category_id"""
        provider = provider_fixture
        _insert_record(provider, app="chrome.exe", title="Tab1", category_id="cat-old",
                       start_time="2026-07-23T10:00:00.000000+00:00",
                       end_time="2026-07-23T10:30:00.000000+00:00")
        _insert_record(provider, app="chrome.exe", title="Tab2", category_id="cat-old",
                       start_time="2026-07-23T11:00:00.000000+00:00",
                       end_time="2026-07-23T11:30:00.000000+00:00")
        _insert_record(provider, app="firefox.exe", title="Tab1", category_id="cat-old",
                       start_time="2026-07-23T12:00:00.000000+00:00",
                       end_time="2026-07-23T12:30:00.000000+00:00")

        affected = provider.update_by_filter(
            set_fields={"category_id": "cat-new"},
            where_conditions={"app": "chrome.exe"},
        )
        assert affected == 2, f"应更新 2 条 chrome.exe 记录，实际: {affected}"

        # 验证 chrome 的记录已更新
        from lifeprism.repository.providers.common_query_options import QueryOptions

        records, _ = provider.query_computer_usage(
            QueryOptions(filters={"app": "chrome.exe"})
        )
        for r in records:
            assert r["category_id"] == "cat-new"

        # firefox 不受影响
        records_ff, _ = provider.query_computer_usage(
            QueryOptions(filters={"app": "firefox.exe"})
        )
        for r in records_ff:
            assert r["category_id"] == "cat-old"

    def test_update_by_filter_none_clears_to_null(self, provider_fixture):
        """set_fields 中 None 值清除字段为 NULL"""
        provider = provider_fixture
        _insert_record(provider, app="code.exe", title="Main", link_to_goal_id="goal-123")

        affected = provider.update_by_filter(
            set_fields={"link_to_goal_id": None},
            where_conditions={"app": "code.exe"},
        )
        assert affected == 1

        from lifeprism.repository.providers.common_query_options import QueryOptions

        records, _ = provider.query_computer_usage(
            QueryOptions(filters={"app": "code.exe"})
        )
        assert len(records) == 1
        assert records[0]["link_to_goal_id"] is None, "link_to_goal_id 应被清除为 NULL"

    def test_update_by_filter_operator_suffix_ge(self, provider_fixture):
        """支持操作符后缀 'start_time >=' """
        provider = provider_fixture
        _insert_record(
            provider,
            app="slack.exe",
            title="Morning",
            start_time="2026-07-23T08:00:00.000000+00:00",
            end_time="2026-07-23T09:00:00.000000+00:00",
            category_id="cat-old",
        )
        _insert_record(
            provider,
            app="slack.exe",
            title="Afternoon",
            start_time="2026-07-23T14:00:00.000000+00:00",
            end_time="2026-07-23T15:00:00.000000+00:00",
            category_id="cat-old",
        )

        affected = provider.update_by_filter(
            set_fields={"category_id": "cat-afternoon"},
            where_conditions={"app": "slack.exe", "start_time >=": "2026-07-23T12:00:00.000000+00:00"},
        )
        assert affected == 1, f"应只更新 1 条下午记录，实际: {affected}"

        from lifeprism.repository.providers.common_query_options import QueryOptions

        records, _ = provider.query_computer_usage(
            QueryOptions(filters={"app": "slack.exe"})
        )
        for r in records:
            if r["title"] == "Afternoon":
                assert r["category_id"] == "cat-afternoon"
            else:
                assert r["category_id"] == "cat-old"

    def test_update_by_filter_operator_suffix_le(self, provider_fixture):
        """支持操作符后缀 'start_time <='"""
        provider = provider_fixture
        _insert_record(
            provider,
            app="zoom.exe",
            title="Morning",
            start_time="2026-07-23T08:00:00.000000+00:00",
            end_time="2026-07-23T09:00:00.000000+00:00",
            category_id="cat-old",
        )
        _insert_record(
            provider,
            app="zoom.exe",
            title="Evening",
            start_time="2026-07-23T20:00:00.000000+00:00",
            end_time="2026-07-23T21:00:00.000000+00:00",
            category_id="cat-old",
        )

        affected = provider.update_by_filter(
            set_fields={"category_id": "cat-morning"},
            where_conditions={"app": "zoom.exe", "start_time <=": "2026-07-23T12:00:00.000000+00:00"},
        )
        assert affected == 1, f"应只更新 1 条上午记录，实际: {affected}"

    def test_update_by_filter_rejects_invalid_where_field(self, provider_fixture):
        """不在 _FILTER_FIELDS 白名单内的 where 字段拒绝执行"""
        provider = provider_fixture
        _insert_record(provider, app="test.exe")
        with pytest.raises((ValueError, Exception)):
            provider.update_by_filter(
                set_fields={"category_id": "cat-x"},
                where_conditions={"invalid_field": "value"},
            )

    def test_update_by_filter_rejects_invalid_where_field_with_suffix(self, provider_fixture):
        """带操作符后缀的字段剥除后缀后校验白名单，不在白名单内拒绝执行"""
        provider = provider_fixture
        _insert_record(provider, app="test.exe")
        with pytest.raises((ValueError, Exception)):
            provider.update_by_filter(
                set_fields={"category_id": "cat-x"},
                where_conditions={"invalid_field >=": "value"},
            )

    def test_update_by_filter_multiple_conditions(self, provider_fixture):
        """多条件组合更新"""
        provider = provider_fixture
        _insert_record(
            provider, app="code.exe", title="Project A", category_id="cat-old",
            start_time="2026-07-23T10:00:00.000000+00:00",
            end_time="2026-07-23T10:30:00.000000+00:00",
        )
        _insert_record(
            provider, app="code.exe", title="Project B", category_id="cat-old",
            start_time="2026-07-23T11:00:00.000000+00:00",
            end_time="2026-07-23T11:30:00.000000+00:00",
        )
        _insert_record(
            provider, app="code.exe", title="Project A", category_id="cat-other",
            start_time="2026-07-23T12:00:00.000000+00:00",
            end_time="2026-07-23T12:30:00.000000+00:00",
        )

        affected = provider.update_by_filter(
            set_fields={"category_id": "cat-new"},
            where_conditions={"app": "code.exe", "title": "Project A"},
        )
        assert affected == 2, f"应更新 2 条 code.exe + Project A 记录，实际: {affected}"

    def test_update_by_filter_in_clause(self, provider_fixture):
        """IN 子句：按 ID 列表批量更新"""
        provider = provider_fixture
        rid1 = _insert_record(provider, app="app1.exe", category_id="cat-old")
        rid2 = _insert_record(provider, app="app2.exe", category_id="cat-old")
        _insert_record(provider, app="app3.exe", category_id="cat-old")  # 不在 IN 列表中

        affected = provider.update_by_filter(
            set_fields={"category_id": "cat-new"},
            where_conditions={"id IN": [str(rid1), str(rid2)]},
        )
        assert affected == 2, f"应更新 2 条记录，实际: {affected}"

        # 验证更新结果
        rec1 = provider.get_computer_usage_by_id(str(rid1))
        rec2 = provider.get_computer_usage_by_id(str(rid2))
        assert rec1["category_id"] == "cat-new"
        assert rec2["category_id"] == "cat-new"

    def test_update_by_filter_in_clause_empty_list(self, provider_fixture):
        """IN 子句空列表：不匹配任何行（1=0），返回 0"""
        provider = provider_fixture
        _insert_record(provider, app="app1.exe", category_id="cat-old")

        affected = provider.update_by_filter(
            set_fields={"category_id": "cat-new"},
            where_conditions={"id IN": []},
        )
        assert affected == 0

    def test_update_by_filter_in_clause_rejects_non_list(self, provider_fixture):
        """IN 子句 value 必须是 list/tuple，否则抛 ValidationError"""
        from lifeprism.utils.exceptions import ValidationError

        provider = provider_fixture
        with pytest.raises(ValidationError, match="IN 操作符要求"):
            provider.update_by_filter(
                set_fields={"category_id": "cat-new"},
                where_conditions={"id IN": "not-a-list"},
            )

    def test_update_by_filter_in_clause_with_none_set_field(self, provider_fixture):
        """IN 子句 + None set_field：清除为 NULL"""
        provider = provider_fixture
        rid1 = _insert_record(
            provider, app="app1.exe", category_id="cat-old", sub_category_id="sub-old"
        )
        rid2 = _insert_record(
            provider, app="app2.exe", category_id="cat-old", sub_category_id="sub-old"
        )

        affected = provider.update_by_filter(
            set_fields={"sub_category_id": None},  # None → 清除为 NULL
            where_conditions={"id IN": [str(rid1), str(rid2)]},
        )
        assert affected == 2

        rec1 = provider.get_computer_usage_by_id(str(rid1))
        rec2 = provider.get_computer_usage_by_id(str(rid2))
        assert rec1["sub_category_id"] is None
        assert rec2["sub_category_id"] is None


class TestUpdateByFilterAggregator:
    """测试 ComputerUsageAggregator.update_by_filter 委托"""

    def test_aggregator_delegates_update_by_filter(self, aggregator_fixture):
        """Aggregator 委托 update_by_filter 给 Provider"""
        aggregator = aggregator_fixture
        _insert_record(
            aggregator.computer_usage_provider,
            app="agg-filter.exe",
            title="Test",
            category_id="cat-old",
            start_time="2026-07-23T10:00:00.000000+00:00",
            end_time="2026-07-23T10:30:00.000000+00:00",
        )
        _insert_record(
            aggregator.computer_usage_provider,
            app="agg-filter.exe",
            title="Test2",
            category_id="cat-old",
            start_time="2026-07-23T11:00:00.000000+00:00",
            end_time="2026-07-23T11:30:00.000000+00:00",
        )

        affected = aggregator.update_by_filter(
            set_fields={"category_id": "cat-agg-new"},
            where_conditions={"app": "agg-filter.exe"},
        )
        assert affected == 2

        from lifeprism.repository.providers.common_query_options import QueryOptions

        records, _ = aggregator.query_computer_usage(
            QueryOptions(filters={"app": "agg-filter.exe"})
        )
        for r in records:
            assert r["category_id"] == "cat-agg-new"


# ==================== 4. get_total_duration 测试 ====================


class TestGetTotalDurationProvider:
    """测试 ComputerUsageProvider.get_total_duration"""

    def test_get_total_duration_sums_records(self, provider_fixture):
        """返回时间范围内所有记录的 duration 之和"""
        provider = provider_fixture
        _insert_record(
            provider,
            app="a1.exe",
            start_time="2026-07-23T10:00:00.000000+00:00",
            end_time="2026-07-23T10:30:00.000000+00:00",
            duration=1800,
        )
        _insert_record(
            provider,
            app="a2.exe",
            start_time="2026-07-23T11:00:00.000000+00:00",
            end_time="2026-07-23T11:45:00.000000+00:00",
            duration=2700,
        )
        _insert_record(
            provider,
            app="a3.exe",
            start_time="2026-07-23T23:00:00.000000+00:00",  # 范围外
            end_time="2026-07-23T23:30:00.000000+00:00",
            duration=1800,
        )

        total = provider.get_total_duration(
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T20:00:00.000000+00:00",
        )
        assert total == 4500, f"应为 1800+2700=4500，实际: {total}"

    def test_get_total_duration_no_data_returns_zero(self, provider_fixture):
        """无数据返回 0"""
        provider = provider_fixture
        total = provider.get_total_duration(
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
        )
        assert total == 0, "无数据时应返回 0"

    def test_get_total_duration_outside_range_returns_zero(self, provider_fixture):
        """所有记录都在范围外时返回 0"""
        provider = provider_fixture
        _insert_record(
            provider,
            app="a.exe",
            start_time="2026-07-23T10:00:00.000000+00:00",
            end_time="2026-07-23T11:00:00.000000+00:00",
            duration=3600,
        )
        total = provider.get_total_duration(
            "2026-07-24T00:00:00.000000+00:00",
            "2026-07-24T23:59:59.000000+00:00",
        )
        assert total == 0, "范围外应返回 0"


class TestGetTotalDurationAggregator:
    """测试 ComputerUsageAggregator.get_total_duration 委托"""

    def test_aggregator_delegates_get_total_duration(self, aggregator_fixture):
        """Aggregator 委托 get_total_duration 给 Provider"""
        aggregator = aggregator_fixture
        _insert_record(
            aggregator.computer_usage_provider,
            app="agg-dur.exe",
            start_time="2026-07-23T10:00:00.000000+00:00",
            end_time="2026-07-23T10:30:00.000000+00:00",
            duration=1800,
        )

        total = aggregator.get_total_duration(
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
        )
        assert total == 1800


# ==================== 5. get_top_groups_by_duration 测试 ====================


class TestGetTopGroupsByDurationProvider:
    """测试 ComputerUsageProvider.get_top_groups_by_duration"""

    def test_top_groups_by_app(self, provider_fixture):
        """按 app 分组聚合"""
        provider = provider_fixture
        # app1: 100 + 200 = 300
        _insert_record(provider, app="app1.exe", title="T1", duration=100,
                       start_time="2026-07-23T10:00:00.000000+00:00",
                       end_time="2026-07-23T10:01:40.000000+00:00")
        _insert_record(provider, app="app1.exe", title="T2", duration=200,
                       start_time="2026-07-23T11:00:00.000000+00:00",
                       end_time="2026-07-23T11:03:20.000000+00:00")
        # app2: 500
        _insert_record(provider, app="app2.exe", title="T3", duration=500,
                       start_time="2026-07-23T12:00:00.000000+00:00",
                       end_time="2026-07-23T12:08:20.000000+00:00")
        # app3: 50
        _insert_record(provider, app="app3.exe", title="T4", duration=50,
                       start_time="2026-07-23T13:00:00.000000+00:00",
                       end_time="2026-07-23T13:00:50.000000+00:00")

        result = provider.get_top_groups_by_duration(
            "app",
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
            10,
        )
        # 按 duration 降序：app2(500) > app1(300) > app3(50)
        assert len(result) == 3
        assert result[0] == ("app2.exe", 500)
        assert result[1] == ("app1.exe", 300)
        assert result[2] == ("app3.exe", 50)

    def test_top_groups_by_title(self, provider_fixture):
        """按 title 分组聚合"""
        provider = provider_fixture
        # TitleA: 100 + 300 = 400
        _insert_record(provider, app="a.exe", title="TitleA", duration=100,
                       start_time="2026-07-23T10:00:00.000000+00:00",
                       end_time="2026-07-23T10:01:40.000000+00:00")
        _insert_record(provider, app="b.exe", title="TitleA", duration=300,
                       start_time="2026-07-23T11:00:00.000000+00:00",
                       end_time="2026-07-23T11:05:00.000000+00:00")
        # TitleB: 200
        _insert_record(provider, app="c.exe", title="TitleB", duration=200,
                       start_time="2026-07-23T12:00:00.000000+00:00",
                       end_time="2026-07-23T12:03:20.000000+00:00")

        result = provider.get_top_groups_by_duration(
            "title",
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
            10,
        )
        assert len(result) == 2
        assert result[0] == ("TitleA", 400)
        assert result[1] == ("TitleB", 200)

    def test_top_groups_top_n_limit(self, provider_fixture):
        """top_n 限制返回条数"""
        provider = provider_fixture
        for i in range(5):
            _insert_record(
                provider,
                app=f"app{i}.exe",
                title=f"T{i}",
                duration=(i + 1) * 100,
                start_time=f"2026-07-23T{i:02d}:00:00.000000+00:00",
                end_time=f"2026-07-23T{i:02d}:01:40.000000+00:00",
            )

        result = provider.get_top_groups_by_duration(
            "app",
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
            3,
        )
        assert len(result) == 3, f"top_n=3 应返回 3 条，实际: {len(result)}"
        # 降序：app4(500) > app3(400) > app2(300)
        assert result[0] == ("app4.exe", 500)
        assert result[1] == ("app3.exe", 400)
        assert result[2] == ("app2.exe", 300)

    def test_top_groups_descending_order(self, provider_fixture):
        """结果按 duration 降序"""
        provider = provider_fixture
        durations = [100, 300, 200, 50, 400]
        for i, d in enumerate(durations):
            _insert_record(
                provider,
                app=f"ord{i}.exe",
                title=f"T{i}",
                duration=d,
                start_time=f"2026-07-23T{i:02d}:00:00.000000+00:00",
                end_time=f"2026-07-23T{i:02d}:01:00.000000+00:00",
            )

        result = provider.get_top_groups_by_duration(
            "app",
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
            10,
        )
        # 降序：400 > 300 > 200 > 100 > 50
        assert [r[1] for r in result] == [400, 300, 200, 100, 50]

    def test_top_groups_rejects_invalid_field(self, provider_fixture):
        """不在白名单内的 group_field 拒绝执行"""
        provider = provider_fixture
        _insert_record(provider, app="test.exe")
        with pytest.raises((ValueError, Exception)):
            provider.get_top_groups_by_duration(
                "invalid_field",
                "2026-07-23T00:00:00.000000+00:00",
                "2026-07-23T23:59:59.000000+00:00",
                10,
            )

    def test_top_groups_no_data_returns_empty(self, provider_fixture):
        """无数据返回空列表"""
        provider = provider_fixture
        result = provider.get_top_groups_by_duration(
            "app",
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
            10,
        )
        assert result == []


class TestGetTopGroupsByDurationAggregator:
    """测试 ComputerUsageAggregator.get_top_groups_by_duration 委托"""

    def test_aggregator_delegates_get_top_groups(self, aggregator_fixture):
        """Aggregator 委托 get_top_groups_by_duration 给 Provider"""
        aggregator = aggregator_fixture
        _insert_record(
            aggregator.computer_usage_provider,
            app="agg-top.exe",
            title="T1",
            duration=300,
            start_time="2026-07-23T10:00:00.000000+00:00",
            end_time="2026-07-23T10:05:00.000000+00:00",
        )
        _insert_record(
            aggregator.computer_usage_provider,
            app="agg-top2.exe",
            title="T2",
            duration=100,
            start_time="2026-07-23T11:00:00.000000+00:00",
            end_time="2026-07-23T11:01:40.000000+00:00",
        )

        result = aggregator.get_top_groups_by_duration(
            "app",
            "2026-07-23T00:00:00.000000+00:00",
            "2026-07-23T23:59:59.000000+00:00",
            10,
        )
        assert len(result) == 2
        assert result[0] == ("agg-top.exe", 300)
        assert result[1] == ("agg-top2.exe", 100)
