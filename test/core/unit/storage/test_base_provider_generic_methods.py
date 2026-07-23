"""
LWBaseDataProvider 通用方法单元测试

测试基类的通用 CRUD 方法，确保边界情况和错误处理正确。
"""

import re
from typing import Set

import pytest

from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions

pytestmark = pytest.mark.core


# ==================== 测试用 Mock Provider ====================


class MockProvider(LWBaseDataProvider):
    """测试用的 Mock Provider"""

    _TABLE_NAME = "test_table"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "date"
    _TIME_FIELD = "time"

    _FILTER_FIELDS: Set[str] = {"id", "name", "status", "date", "time"}
    _ORDER_FIELDS: Set[str] = {"id", "name", "created_at"}
    _SELECT_FIELDS: Set[str] = {"id", "name", "status", "date", "time", "created_at"}
    _UPDATE_FIELDS: Set[str] = {"name", "status"}


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
    _FILTER_FIELDS: Set[str] = {"id", "name"}
    _ORDER_FIELDS: Set[str] = {"id", "name"}


# ==================== Fixtures ====================


@pytest.fixture
def mock_provider(test_data_path):
    """创建 MockProvider 实例并初始化测试表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = MockProvider()

    # 创建测试表（使用 UTC DEFAULT，与迁移后的表定义一致）
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
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
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
        options = QueryOptions(filters={"invalid_field": "value"})
        with pytest.raises(ValueError, match="Invalid filter field"):
            mock_provider._generic_query(options)

    def test_query_with_invalid_order_field(self, mock_provider):
        """测试使用无效的排序字段"""
        options = QueryOptions(order_by="invalid_field")
        with pytest.raises(ValueError, match="Invalid order_by field"):
            mock_provider._generic_query(options)

    def test_query_with_invalid_select_field(self, mock_provider):
        """测试使用无效的查询字段"""
        options = QueryOptions(fields=["invalid_field"])
        with pytest.raises(ValueError, match="Invalid select fields"):
            mock_provider._generic_query(options)

    def test_query_without_whitelist_definition(self, test_data_path):
        """测试未定义白名单时使用 filters"""
        from lifeprism.config.settings_manager import settings

        settings._initialize()

        provider = MockProviderNoWhitelist()
        options = QueryOptions(filters={"name": "test"})
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
            cursor.execute(
                "INSERT INTO test_table (id, name, status) VALUES ('1', 'test1', 'active')"
            )
            cursor.execute(
                "INSERT INTO test_table (id, name, status) VALUES ('2', 'test2', 'active')"
            )
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
        options = QueryOptions(order_by="id", order_desc=False)
        order_clause = mock_provider._build_order_clause(options)
        assert order_clause == "ORDER BY id ASC"

        # 测试降序
        options = QueryOptions(order_by="name", order_desc=True)
        order_clause = mock_provider._build_order_clause(options)
        assert order_clause == "ORDER BY name DESC"


# ==================== 插入方法测试 ====================


class TestGenericInsert:
    """测试 _generic_insert() 方法"""

    def test_insert_with_id_prefix(self, mock_provider):
        """测试自动生成 ID"""
        data = {"name": "test", "status": "active"}
        record_id = mock_provider._generic_insert(data, id_prefix="t-")

        # 验证 ID 格式
        assert record_id.startswith("t-")
        assert len(record_id) == 10  # t- + 8 位 hex

    def test_insert_with_auto_order_index(self, mock_provider):
        """测试自动计算 order_index"""
        # 第一次插入
        data1 = {"name": "test1", "status": "active"}
        mock_provider._generic_insert(data1, id_prefix="t-", auto_order_index=True)

        # 第二次插入应该有更大的 order_index
        data2 = {"name": "test2", "status": "active"}
        mock_provider._generic_insert(data2, id_prefix="t-", auto_order_index=True)

        # 验证 order_index 被设置（通过查询验证）
        # 注意：这里只是测试方法不抛出异常，实际值需要查询数据库验证


# ==================== 更新方法测试 ====================


class TestGenericUpdate:
    """测试 _generic_update() 方法"""

    def test_update_with_invalid_field(self, mock_provider):
        """测试使用无效的更新字段"""
        data = {"invalid_field": "value"}
        with pytest.raises(ValueError, match="Invalid update fields"):
            mock_provider._generic_update("test-id", data)

    def test_update_with_empty_data(self, mock_provider):
        """测试空数据更新"""
        result = mock_provider._generic_update("test-id", {})
        assert result is True  # 空数据应该返回 True

    def test_update_generates_utc_timestamp(self, mock_provider):
        """测试 _generic_update 自动生成的 updated_at 带有 UTC 时区信息"""
        # 先插入一条记录
        mock_provider._generic_insert({"id": "test-utc-1", "name": "test", "status": "active"})

        # 将 test_table 加入 _TABLES_WITH_UPDATE_AT 缓存，模拟配置了 update_at=True 的表
        LWBaseDataProvider._init_update_at_cache()
        original_cache = LWBaseDataProvider._TABLES_WITH_UPDATE_AT
        LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache | {"test_table"}

        try:
            # 执行更新（不显式传入 updated_at）
            mock_provider._generic_update("test-utc-1", {"name": "updated"})

            # 查询验证 updated_at
            with mock_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT updated_at FROM test_table WHERE id = 'test-utc-1'")
                row = cursor.fetchone()

            assert row is not None
            updated_at = row[0]

            # 验证是 ISO 8601 格式且带时区后缀（+00:00）
            # 格式：2026-07-12T12:34:56.789012+00:00
            iso_8601_with_tz = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")
            assert iso_8601_with_tz.match(updated_at) is not None, (
                f"updated_at 应为带 UTC 时区的 ISO 8601 格式，实际值: {updated_at}"
            )
        finally:
            # 恢复原始缓存
            LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache

    def test_update_does_not_override_explicit_updated_at(self, mock_provider):
        """测试 _generic_update 不在白名单中的 updated_at 字段会被白名单拦截（设计如此）"""
        mock_provider._generic_insert({"id": "test-utc-2", "name": "test", "status": "active"})

        LWBaseDataProvider._init_update_at_cache()
        original_cache = LWBaseDataProvider._TABLES_WITH_UPDATE_AT
        LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache | {"test_table"}

        try:
            # updated_at 不在 _UPDATE_FIELDS 白名单中，显式传入应被拦截
            # 这是设计行为：updated_at 由系统自动管理，不应由调用方显式设置
            with pytest.raises(ValueError, match="Invalid update fields"):
                mock_provider._generic_update(
                    "test-utc-2",
                    {
                        "name": "updated",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    },
                )
        finally:
            LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache

    def test_update_actually_changes_updated_at_value(self, mock_provider):
        """S14: _generic_update 调用后 updated_at 与原值不同（确实变化）"""
        import time

        # 插入时显式设置 updated_at（test_table 此时不在 _TABLES_WITH_UPDATE_AT 中）
        original_updated_at = "2026-01-01T00:00:00+00:00"
        mock_provider._generic_insert(
            {
                "id": "test-utc-change",
                "name": "test",
                "status": "active",
                "updated_at": original_updated_at,
            }
        )

        # 将 test_table 加入 _TABLES_WITH_UPDATE_AT，使 _generic_update 自动更新 updated_at
        LWBaseDataProvider._init_update_at_cache()
        original_cache = LWBaseDataProvider._TABLES_WITH_UPDATE_AT
        LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache | {"test_table"}

        try:
            # 等待以确保时间戳不同
            time.sleep(0.01)

            # 执行更新
            mock_provider._generic_update("test-utc-change", {"name": "updated"})

            # 查询更新后的 updated_at
            with mock_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT updated_at FROM test_table WHERE id = 'test-utc-change'"
                )
                new_updated_at = cursor.fetchone()[0]

            # 验证：updated_at 已变化（与原值不同）
            assert new_updated_at != original_updated_at, (
                f"updated_at 应在更新后变化，原值: {original_updated_at}, 新值: {new_updated_at}"
            )
        finally:
            LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache


# ==================== 删除方法测试 ====================


class TestGenericDelete:
    """测试 _generic_delete() 方法"""

    def test_delete_nonexistent_record(self, mock_provider):
        """测试删除不存在的记录"""
        # 删除不存在的记录应该返回 False
        result = mock_provider._generic_delete("nonexistent-id")
        assert result is False

    def test_delete_removes_record_from_table(self, mock_provider):
        """S4: 删除已存在记录后，该记录从数据表消失（DELETE 生效）"""
        # 插入一条记录
        mock_provider._generic_insert({"id": "to-delete", "name": "test", "status": "active"})

        # 确认记录存在
        with mock_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM test_table WHERE id = 'to-delete'")
            assert cursor.fetchone() is not None, "记录应已插入"

        # 执行删除
        result = mock_provider._generic_delete("to-delete")

        # 验证：返回 True 表示删除成功
        assert result is True

        # 验证：记录已从表中消失
        with mock_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM test_table WHERE id = 'to-delete'")
            assert cursor.fetchone() is None, "删除后记录不应再存在于表中"


# ==================== QueryOptions 测试 ====================


class TestQueryOptions:
    """测试 QueryOptions 类"""

    def test_immutability(self):
        """测试 QueryOptions 的不可变性"""
        options = QueryOptions(filters={"status": "active"})

        # 尝试修改应该失败
        with pytest.raises(Exception):  # frozen dataclass 会抛出异常
            options.filters = {"status": "inactive"}

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
        options = QueryOptions(filters={"status": "active"})
        new_options = options.with_filters(name="test")

        assert new_options.filters == {"status": "active", "name": "test"}
        assert options.filters == {"status": "active"}  # 原对象不变

    def test_with_order(self):
        """测试 with_order() 方法"""
        options = QueryOptions()
        new_options = options.with_order("name", desc=False)

        assert new_options.order_by == "name"
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
        new_options = options.with_fields("id", "name", "status")

        assert new_options.fields == ["id", "name", "status"]

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


# ==================== UTC 时区迁移测试 ====================


class TestUTCTimestampGeneration:
    """测试 UTC 时间戳生成"""

    def test_generated_timestamp_has_timezone_info(self, mock_provider):
        """测试自动生成的 updated_at 包含时区信息（aware datetime）"""
        from datetime import datetime

        mock_provider._generic_insert({"id": "test-tz-1", "name": "test", "status": "active"})

        LWBaseDataProvider._init_update_at_cache()
        original_cache = LWBaseDataProvider._TABLES_WITH_UPDATE_AT
        LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache | {"test_table"}

        try:
            mock_provider._generic_update("test-tz-1", {"name": "updated"})

            with mock_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT updated_at FROM test_table WHERE id = 'test-tz-1'")
                row = cursor.fetchone()

            assert row is not None
            updated_at_str = row[0]

            # 解析为 datetime 对象，验证 tzinfo 不为 None
            parsed = datetime.fromisoformat(updated_at_str)
            assert parsed.tzinfo is not None, (
                f"自动生成的 updated_at 应为 aware datetime（tzinfo 不为 None），"
                f"实际值: {updated_at_str}"
            )

            # 验证时区为 UTC（utcoffset 为 0）
            assert parsed.utcoffset().total_seconds() == 0, (
                f"自动生成的 updated_at 时区应为 UTC（offset=0），实际 offset: {parsed.utcoffset()}"
            )
        finally:
            LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache

    def test_generated_timestamp_is_iso_8601_format(self, mock_provider):
        """测试自动生成的 updated_at 符合 ISO 8601 格式"""
        mock_provider._generic_insert({"id": "test-iso-1", "name": "test", "status": "active"})

        LWBaseDataProvider._init_update_at_cache()
        original_cache = LWBaseDataProvider._TABLES_WITH_UPDATE_AT
        LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache | {"test_table"}

        try:
            mock_provider._generic_update("test-iso-1", {"name": "updated"})

            with mock_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT updated_at FROM test_table WHERE id = 'test-iso-1'")
                row = cursor.fetchone()

            assert row is not None
            updated_at_str = row[0]

            # 验证 ISO 8601 格式：YYYY-MM-DDTHH:MM:SS.ffffff+00:00
            # T 分隔符 + 微秒 + UTC 时区后缀
            iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\+00:00$")
            assert iso_pattern.match(updated_at_str) is not None, (
                f"updated_at 应为 ISO 8601 格式（含 T 分隔符和 +00:00 后缀），"
                f"实际值: {updated_at_str}"
            )

            # 验证不包含空格分隔符（旧格式特征）
            assert " " not in updated_at_str, (
                f"updated_at 不应包含空格分隔符（旧格式），实际值: {updated_at_str}"
            )
        finally:
            LWBaseDataProvider._TABLES_WITH_UPDATE_AT = original_cache


class TestM008MigrationScript:
    """测试 m008 UTC 迁移脚本"""

    def test_check_if_applied_returns_true_when_no_localtime(self, test_data_path):
        """测试 check_if_applied 在没有 localtime 时返回 True"""
        import sqlite3

        from lifeprism.repository.migrations.scripts import m008_migrate_to_utc

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 创建一个使用 UTC DEFAULT 的表
        cursor.execute(
            "CREATE TABLE test_utc (id TEXT, created_at TIMESTAMP DEFAULT (datetime('now')))"
        )
        conn.commit()

        assert m008_migrate_to_utc.check_if_applied(cursor) is True
        conn.close()

    def test_check_if_applied_returns_false_when_localtime_exists(self, test_data_path):
        """测试 check_if_applied 在存在 localtime 时返回 False"""
        import sqlite3

        from lifeprism.repository.migrations.scripts import m008_migrate_to_utc

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # 创建一个使用 localtime DEFAULT 的表
        cursor.execute(
            "CREATE TABLE test_local (id TEXT, created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')))"
        )
        conn.commit()

        assert m008_migrate_to_utc.check_if_applied(cursor) is False
        conn.close()

    def test_upgrade_rebuilds_table_with_utc_default(self, test_data_path):
        """测试 upgrade 将表的 DEFAULT 从 localtime 改为 UTC"""
        import sqlite3

        from lifeprism.repository.migrations.scripts import m008_migrate_to_utc

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # 创建一个使用 localtime DEFAULT 的表
        cursor.execute("""
            CREATE TABLE test_rebuild (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)
        cursor.execute("CREATE INDEX idx_test_rebuild_name ON test_rebuild(name)")
        cursor.execute("INSERT INTO test_rebuild (id, name) VALUES ('1', 'test1')")
        cursor.execute("INSERT INTO test_rebuild (id, name) VALUES ('2', 'test2')")
        conn.commit()

        # 执行迁移
        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 验证数据保留
        cursor.execute("SELECT COUNT(*) FROM test_rebuild")
        assert cursor.fetchone()[0] == 2

        # 验证 DEFAULT 已改为 UTC
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='test_rebuild'")
        create_sql = cursor.fetchone()[0]
        assert "datetime('now')" in create_sql
        assert "localtime" not in create_sql

        # 验证索引保留
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_rebuild' AND sql IS NOT NULL"
        )
        indexes = cursor.fetchall()
        assert len(indexes) == 1
        assert indexes[0][0] == "idx_test_rebuild_name"

        conn.close()

    def test_upgrade_idempotent_on_already_utc_tables(self, test_data_path):
        """测试 upgrade 对已经是 UTC 的表是幂等的（不报错）"""
        import sqlite3

        from lifeprism.repository.migrations.scripts import m008_migrate_to_utc

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # 创建一个已经使用 UTC DEFAULT 的表
        cursor.execute("""
            CREATE TABLE test_already_utc (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("INSERT INTO test_already_utc (id) VALUES ('1')")
        conn.commit()

        # 执行迁移（不应该报错也不应该修改表）
        m008_migrate_to_utc.upgrade(cursor)
        conn.commit()

        # 验证数据保留
        cursor.execute("SELECT COUNT(*) FROM test_already_utc")
        assert cursor.fetchone()[0] == 1

        # 验证 check_if_applied 返回 True
        assert m008_migrate_to_utc.check_if_applied(cursor) is True

        conn.close()


# ==================== hash_id 兜底生成测试 ====================


class MockProviderWithHashId(LWBaseDataProvider):
    """模拟有 hash_id 字段的表（HASH_ID_PREFIXES 中的表，前缀 mi-）"""

    _TABLE_NAME = "test_hash_id_table"
    _PRIMARY_KEY = "id"


class MockProviderTextPrimaryKey(LWBaseDataProvider):
    """模拟 TEXT 主键表（不在 HASH_ID_PREFIXES 中，如 diary 风格）"""

    _TABLE_NAME = "test_text_pk_table"
    _PRIMARY_KEY = "id"


@pytest.fixture
def hash_id_provider(test_data_path, monkeypatch):
    """创建带 hash_id 字段的 AUTOINCREMENT 表的 Provider 实例

    通过 monkeypatch 向 HASH_ID_PREFIXES 临时添加测试表，避免污染真实表名。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.sync.constants import HASH_ID_PREFIXES

    settings._initialize()

    # 临时向 HASH_ID_PREFIXES 添加测试专用表（前缀 mi- 与 mood_impacts 一致）
    # monkeypatch.setitem 会在测试结束后自动还原
    monkeypatch.setitem(HASH_ID_PREFIXES, "test_hash_id_table", "mi-")

    provider = MockProviderWithHashId()

    # 创建测试表：模拟有 hash_id 字段的 AUTOINCREMENT 表
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_hash_id_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                hash_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()

    yield provider

    # 清理测试表
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS test_hash_id_table")
        conn.commit()


@pytest.fixture
def text_pk_provider(test_data_path):
    """创建 TEXT 主键表（不在 HASH_ID_PREFIXES 中）的 Provider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = MockProviderTextPrimaryKey()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_text_pk_table (
                id TEXT PRIMARY KEY,
                name TEXT
            )
        """)
        conn.commit()

    yield provider

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS test_text_pk_table")
        conn.commit()


class TestGenericInsertHashIdFallback:
    """测试 _generic_insert 兜底生成 hash_id

    对应 issue: 03-generic-insert-hash-id-fallback
    依据 ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md
    """

    def test_auto_generate_hash_id_when_not_provided(self, hash_id_provider):
        """循环 1: 未传入 hash_id 时自动生成（前缀 + 12 位 hex）"""
        data = {"name": "test_impact"}
        record_id = hash_id_provider._generic_insert(data)

        # 验证：插入成功，返回自增 id
        assert record_id is not None

        # 验证：hash_id 应该被自动生成
        with hash_id_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id FROM test_hash_id_table WHERE id = ?", (record_id,)
            )
            row = cursor.fetchone()

        assert row is not None, "应该查询到刚插入的记录"
        hash_id = row[0]
        assert hash_id is not None, "hash_id 应该被自动生成（未传入时兜底生成）"

        # 测试表中前缀为 "mi-"（通过 monkeypatch 注入 HASH_ID_PREFIXES）
        assert hash_id.startswith("mi-"), (
            f"hash_id 应该以 'mi-' 前缀开头，实际值: {hash_id}"
        )

        # 验证长度：前缀(3) + 12 位 hex = 15
        assert len(hash_id) == 15, (
            f"hash_id 长度应为 15（前缀 'mi-' + 12 位 hex），实际长度: {len(hash_id)}, 值: {hash_id}"
        )

        # 验证 hex 部分都是合法的十六进制字符
        hex_part = hash_id[3:]
        assert all(c in "0123456789abcdef" for c in hex_part), (
            f"hash_id 后 12 位应为合法 hex 字符，实际值: {hex_part}"
        )

    def test_preserve_hash_id_when_provided(self, hash_id_provider):
        """循环 2: 已传入 hash_id 时保留不覆盖"""
        custom_hash_id = "mi-custom123456"
        data = {"name": "test_impact", "hash_id": custom_hash_id}
        record_id = hash_id_provider._generic_insert(data)

        # 验证：插入成功
        assert record_id is not None

        # 验证：hash_id 应该是传入的值，未被覆盖
        with hash_id_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id FROM test_hash_id_table WHERE id = ?", (record_id,)
            )
            row = cursor.fetchone()

        assert row is not None, "应该查询到刚插入的记录"
        hash_id = row[0]
        assert hash_id == custom_hash_id, (
            f"hash_id 应保留调用方传入的值 '{custom_hash_id}'，实际值: {hash_id}"
        )

    def test_text_pk_table_not_affected(self, text_pk_provider):
        """循环 3: TEXT 主键表（不在 HASH_ID_PREFIXES 中）不受影响"""
        data = {"id": "test-001", "name": "test"}
        text_pk_provider._generic_insert(data)

        # 验证：data 字典中没有被添加 hash_id（兜底逻辑不触发）
        assert "hash_id" not in data, (
            "TEXT 主键表（不在 HASH_ID_PREFIXES 中）调用 _generic_insert 后，"
            "data 字典不应该被添加 hash_id 字段"
        )

        # 验证：表结构中没有 hash_id 字段（插入成功即证明未尝试写入 hash_id 列）
        with text_pk_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(test_text_pk_table)")
            columns = [col[1] for col in cursor.fetchall()]
            cursor.execute(
                "SELECT id, name FROM test_text_pk_table WHERE id = ?", ("test-001",)
            )
            row = cursor.fetchone()

        assert "hash_id" not in columns, "TEXT 主键表不应该有 hash_id 字段"
        assert row is not None, "记录应该插入成功"
        assert row[0] == "test-001"
        assert row[1] == "test"


# ==================== habit_chain_nodes CASCADE 移除测试（S15） ====================


class TestHabitChainNodesCascade:
    """测试 habit_chain_nodes 表的 DB CASCADE 已移除

    对应 issue: 01-base-infra-generic-delete-tombstone（S15）
    移除 ON DELETE CASCADE，改为纯应用层级联，确保墓碑必写。
    """

    def test_no_on_delete_cascade_in_constraints(self):
        """habit_chain_nodes 的表约束不再含 ON DELETE CASCADE，但保留外键约束"""
        from lifeprism.config.database import HABIT_CHAIN_NODES_CONFIG

        constraints = HABIT_CHAIN_NODES_CONFIG["table_constraints"]
        joined = " ".join(constraints)

        assert "ON DELETE CASCADE" not in joined, (
            f"habit_chain_nodes 不应含 ON DELETE CASCADE，实际约束: {constraints}"
        )
        assert "FOREIGN KEY (chain_id) REFERENCES habit_chains(id)" in joined, (
            f"habit_chain_nodes 应保留外键约束，实际约束: {constraints}"
        )


# ==================== 墓碑逻辑测试基础设施 ====================


def _create_deletion_log(db):
    """创建 deletion_log 表（按 DELETION_LOG_CONFIG schema）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deletion_log (
                id TEXT PRIMARY KEY,
                target_table TEXT NOT NULL,
                record_id TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(target_table, record_id)
            )
        """)
        conn.commit()


def _clear_deletion_log(db):
    """清理 deletion_log 表数据"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


def _count_tombstones(db, target_table=None, record_id=None):
    """查询 deletion_log 中的墓碑数量"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if target_table is not None and record_id is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ? AND record_id = ?",
                (target_table, record_id),
            )
        elif target_table is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ?",
                (target_table,),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM deletion_log")
        return cursor.fetchone()[0]


def _get_tombstone(db, target_table, record_id):
    """查询单条墓碑记录"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, target_table, record_id, source, created_at, updated_at "
            "FROM deletion_log WHERE target_table = ? AND record_id = ?",
            (target_table, record_id),
        )
        return cursor.fetchone()


@pytest.fixture
def tombstone_mock_provider(mock_provider):
    """mock_provider + deletion_log 表（test_table 不在 SYNC_TABLES，用于非 SYNC 墓碑测试）"""
    _create_deletion_log(mock_provider.db)
    _clear_deletion_log(mock_provider.db)
    yield mock_provider
    _clear_deletion_log(mock_provider.db)


@pytest.fixture
def sync_hash_id_provider(hash_id_provider, monkeypatch):
    """hash_id_provider + deletion_log + test_hash_id_table 在 SYNC_TABLES

    test_hash_id_table 模拟 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中），
    通过 monkeypatch 同时注入 SYNC_TABLES 和 HASH_ID_PREFIXES。
    """
    from lifeprism.sync.constants import SYNC_TABLES

    # 临时将测试表加入 SYNC_TABLES（用新列表替换，避免污染原列表）
    monkeypatch.setattr(
        "lifeprism.sync.constants.SYNC_TABLES", SYNC_TABLES + ["test_hash_id_table"]
    )
    _create_deletion_log(hash_id_provider.db)
    _clear_deletion_log(hash_id_provider.db)
    yield hash_id_provider
    _clear_deletion_log(hash_id_provider.db)


@pytest.fixture
def sync_text_pk_provider(text_pk_provider, monkeypatch):
    """text_pk_provider + deletion_log + test_text_pk_table 在 SYNC_TABLES

    test_text_pk_table 模拟 TEXT 主键表（不在 HASH_ID_PREFIXES 中）。
    """
    from lifeprism.sync.constants import SYNC_TABLES

    monkeypatch.setattr(
        "lifeprism.sync.constants.SYNC_TABLES", SYNC_TABLES + ["test_text_pk_table"]
    )
    _create_deletion_log(text_pk_provider.db)
    _clear_deletion_log(text_pk_provider.db)
    yield text_pk_provider
    _clear_deletion_log(text_pk_provider.db)


# ==================== _generic_delete 墓碑逻辑测试（S3/S1/S2/S5/S6） ====================


class TestGenericDeleteTombstone:
    """测试 _generic_delete() 的墓碑逻辑

    对应 issue: 01-base-infra-generic-delete-tombstone
    依据 ADR: docs/adr/2026-07-22-deletion-log-table.md
    """

    def test_non_sync_table_no_tombstone(self, tombstone_mock_provider):
        """S3: 删非 SYNC_TABLES 的表 → 不写墓碑"""
        provider = tombstone_mock_provider
        provider._generic_insert({"id": "s3-record", "name": "test", "status": "active"})
        provider._generic_delete("s3-record")

        count = _count_tombstones(provider.db, target_table="test_table")
        assert count == 0, "非 SYNC_TABLES 的表删除不应写墓碑"

    def test_sync_autoincrement_table_tombstone_uses_hash_id(self, sync_hash_id_provider):
        """S1: 删 SYNC_TABLES 的 AUTOINCREMENT 表 → 墓碑 record_id = hash_id"""
        provider = sync_hash_id_provider
        # 插入记录（自动生成 hash_id）
        record_id = provider._generic_insert({"name": "s1-test"})

        # 查询获取 hash_id（墓碑 record_id 应为 hash_id 而非主键 id）
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT hash_id FROM test_hash_id_table WHERE id = ?", (record_id,))
            row = cursor.fetchone()
        assert row is not None, "记录应已插入"
        hash_id = row[0]
        assert hash_id is not None, "hash_id 应被自动生成"

        # 删除记录（按主键 id 删除）
        provider._generic_delete(record_id)

        # 验证：墓碑已写入，record_id = hash_id（不是主键 id）
        tombstone = _get_tombstone(provider.db, "test_hash_id_table", hash_id)
        assert tombstone is not None, "应写入墓碑，record_id 为 hash_id"
        assert tombstone[2] == hash_id, f"墓碑 record_id 应为 hash_id '{hash_id}'"
        assert tombstone[3] == "local", "墓碑 source 应为 'local'"

        # 验证：不应有以主键 id 为 record_id 的墓碑
        tombstone_by_pk = _get_tombstone(provider.db, "test_hash_id_table", str(record_id))
        assert tombstone_by_pk is None, "AUTOINCREMENT 表墓碑 record_id 不应为主键 id"

    def test_sync_text_pk_table_tombstone_uses_primary_key(self, sync_text_pk_provider):
        """S2: 删 SYNC_TABLES 的 TEXT 主键表 → 墓碑 record_id = 主键值"""
        provider = sync_text_pk_provider
        pk_value = "s2-text-pk"
        provider._generic_insert({"id": pk_value, "name": "s2-test"})

        # 删除记录
        result = provider._generic_delete(pk_value)
        assert result is True, "删除应成功"

        # 验证：墓碑已写入，record_id = 主键值（TEXT 主键表不用 hash_id）
        tombstone = _get_tombstone(provider.db, "test_text_pk_table", pk_value)
        assert tombstone is not None, "应写入墓碑，record_id 为主键值"
        assert tombstone[2] == pk_value, f"墓碑 record_id 应为主键值 '{pk_value}'"
        assert tombstone[3] == "local", "墓碑 source 应为 'local'"

    def test_delete_failure_rolls_back_tombstone(self, sync_text_pk_provider):
        """S5: DELETE 失败时墓碑回滚（事务原子性）"""
        from lifeprism.utils.exceptions import DataAccessError

        provider = sync_text_pk_provider
        pk_value = "s5-record"
        provider._generic_insert({"id": pk_value, "name": "s5-test"})

        # 创建触发器阻止 DELETE，模拟 DELETE 失败
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TRIGGER prevent_delete_s5 BEFORE DELETE ON test_text_pk_table "
                "BEGIN SELECT RAISE(ABORT, 'Delete prevented'); END"
            )
            conn.commit()

        try:
            # 调用 _generic_delete 应抛出异常（DELETE 被触发器阻止）
            with pytest.raises(DataAccessError):
                provider._generic_delete(pk_value)
        finally:
            # 清理触发器
            with provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TRIGGER IF EXISTS prevent_delete_s5")
                conn.commit()

        # 验证：墓碑已回滚（不存在）
        count = _count_tombstones(provider.db, target_table="test_text_pk_table")
        assert count == 0, "DELETE 失败时墓碑应回滚"

    def test_repeat_delete_preserves_old_tombstone(self, sync_text_pk_provider):
        """S6: 重复删除同一记录 → IGNORE 策略（保留旧墓碑，不刷新 updated_at）"""
        import time

        provider = sync_text_pk_provider
        pk_value = "s6-record"

        # 第一次插入并删除
        provider._generic_insert({"id": pk_value, "name": "s6-test"})
        provider._generic_delete(pk_value)

        # 记录第一次墓碑的 id 和 updated_at
        tombstone1 = _get_tombstone(provider.db, "test_text_pk_table", pk_value)
        assert tombstone1 is not None, "第一次删除应写入墓碑"
        tombstone1_id = tombstone1[0]
        tombstone1_updated_at = tombstone1[5]

        # 等待以确保时间戳不同（如果 updated_at 被刷新，值会变）
        time.sleep(0.01)

        # 再次插入并删除同一记录
        provider._generic_insert({"id": pk_value, "name": "s6-test-2"})
        provider._generic_delete(pk_value)

        # 验证：墓碑仍只有一条（IGNORE 策略，不新增）
        count = _count_tombstones(provider.db, target_table="test_text_pk_table")
        assert count == 1, "重复删除不应新增墓碑（INSERT OR IGNORE）"

        # 验证：墓碑 id 未变（旧墓碑被保留，未被替换）
        tombstone2 = _get_tombstone(provider.db, "test_text_pk_table", pk_value)
        assert tombstone2[0] == tombstone1_id, "墓碑 id 应不变（保留旧墓碑）"

        # 验证：updated_at 未被刷新（IGNORE 策略保留旧值）
        assert tombstone2[5] == tombstone1_updated_at, "updated_at 不应被刷新（IGNORE 策略）"


# ==================== _generic_batch_delete 测试（S11/S8/S7/S9/S10） ====================


class TestGenericBatchDelete:
    """测试 _generic_batch_delete() 方法

    对应 issue: 01-base-infra-generic-delete-tombstone
    批量写墓碑 + 批量 DELETE 在同一事务，采用批量 SQL 而非循环单条。
    """

    def test_empty_list_returns_zero(self, mock_provider):
        """S11: 空列表返回 0"""
        result = mock_provider._generic_batch_delete([])
        assert result == 0

    def test_returns_deleted_row_count(self, tombstone_mock_provider):
        """S8: 返回值为成功删除的行数（int）"""
        provider = tombstone_mock_provider
        ids = ["s8-1", "s8-2", "s8-3"]
        for rid in ids:
            provider._generic_insert({"id": rid, "name": "test", "status": "active"})

        result = provider._generic_batch_delete(ids)

        assert isinstance(result, int), "返回值应为 int"
        assert result == 3, f"应删除 3 条记录，实际返回 {result}"

    def test_batch_delete_sync_table_writes_tombstones(self, sync_text_pk_provider):
        """S7: 批量删 SYNC_TABLES → 所有记录消失 + 对应数量墓碑"""
        provider = sync_text_pk_provider
        ids = ["s7-1", "s7-2", "s7-3"]
        for rid in ids:
            provider._generic_insert({"id": rid, "name": "s7-test"})

        result = provider._generic_batch_delete(ids)

        # 验证：返回删除行数
        assert result == 3, f"应删除 3 条记录，实际返回 {result}"

        # 验证：所有记录已从表中消失
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM test_text_pk_table WHERE id IN (?, ?, ?)", ids
            )
            remaining = cursor.fetchone()[0]
        assert remaining == 0, "所有记录应已删除"

        # 验证：写入了 3 条墓碑
        count = _count_tombstones(provider.db, target_table="test_text_pk_table")
        assert count == 3, f"应写入 3 条墓碑，实际 {count}"

        # 验证：每条墓碑的 record_id 对应主键值
        for rid in ids:
            tombstone = _get_tombstone(provider.db, "test_text_pk_table", rid)
            assert tombstone is not None, f"主键 {rid} 应有对应墓碑"

    def test_batch_delete_non_sync_table_no_tombstone(self, tombstone_mock_provider):
        """S9: 批量删非 SYNC_TABLES → 无墓碑"""
        provider = tombstone_mock_provider
        ids = ["s9-1", "s9-2"]
        for rid in ids:
            provider._generic_insert({"id": rid, "name": "test", "status": "active"})

        provider._generic_batch_delete(ids)

        count = _count_tombstones(provider.db, target_table="test_table")
        assert count == 0, "非 SYNC_TABLES 批量删除不应写墓碑"

    def test_batch_delete_failure_rolls_back_all(self, sync_text_pk_provider):
        """S10: 批量 DELETE 失败 → 墓碑和 DELETE 全部回滚（事务原子性）"""
        from lifeprism.utils.exceptions import DataAccessError

        provider = sync_text_pk_provider
        ids = ["s10-1", "s10-2", "s10-3"]
        for rid in ids:
            provider._generic_insert({"id": rid, "name": "s10-test"})

        # 创建触发器阻止 DELETE，模拟批量 DELETE 失败
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TRIGGER prevent_delete_s10 BEFORE DELETE ON test_text_pk_table "
                "BEGIN SELECT RAISE(ABORT, 'Batch delete prevented'); END"
            )
            conn.commit()

        try:
            with pytest.raises(DataAccessError):
                provider._generic_batch_delete(ids)
        finally:
            with provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TRIGGER IF EXISTS prevent_delete_s10")
                conn.commit()

        # 验证：墓碑已回滚（不存在）
        count = _count_tombstones(provider.db, target_table="test_text_pk_table")
        assert count == 0, "DELETE 失败时墓碑应全部回滚"

        # 验证：记录仍存在（DELETE 也回滚）
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM test_text_pk_table WHERE id IN (?, ?, ?)", ids
            )
            remaining = cursor.fetchone()[0]
        assert remaining == 3, "DELETE 失败时记录不应被删除（全部回滚）"
