"""
同步表范围扩展测试（Issue #13）

测试 seam:
- Seam 1: SYNC_TABLES 常量 - 验证 31 张静态表完整性
- Seam 2: get_all_sync_tables() - 验证动态表（custom_{slug}）的运行时获取

参考: test/core/integration/sync/test_sync_client.py
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 31 张静态表期望清单 ====================

EXPECTED_STATIC_TABLES = [
    # 用户输入数据（15张）
    "mood_entries",
    "diary",
    "todo_list",
    "goal",
    "goal_journal",
    "plan_doc",
    "daily_focus",
    "weekly_focus",
    "habits",
    "habit_challenges",
    "habit_checkins",
    "habit_chains",
    "habit_chain_nodes",
    "timeline_custom_block",
    "time_paradoxes",
    # 元数据（8张）
    "category",
    "sub_category",
    "mood_types",
    "mood_impacts",
    "user_values",
    "commitments",
    "custom_record_types",
    "custom_record_fields",
    # Monitor 数据（3张）
    "user_app_behavior_log",
    "behavior_analysis",
    "raw_behavior_analysis",
    # 缓存表（3张）
    "multi_purpose_map_cache",
    "single_purpose_map_cache",
    "category_map_cache",
    # 统计数据（1张）
    "tokens_usage_log",
    # 微信账户状态（1张）- 替代 channel/wechat/account.json 文件存储（Issue 35）
    "wechat_account_state",
]


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def sync_repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo


@pytest.fixture
def sync_client(initialized_db, sync_repository):
    """创建 SyncClient 实例"""
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient(db_manager=initialized_db, sync_repository=sync_repository)
    yield client


@pytest.fixture
def clean_custom_record_types(initialized_db):
    """清理 custom_record_types 表（测试后执行）"""
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_record_types")
        conn.commit()


# ==================== Seam 1: SYNC_TABLES 常量 ====================


class TestSyncTablesStatic:
    """Seam 1: SYNC_TABLES 常量 - 验证 31 张静态表完整性"""

    def test_sync_tables_contains_all_31_static_tables(self):
        """验证 SYNC_TABLES 包含所有 31 张静态表"""
        # Arrange: 从模块导入 SYNC_TABLES
        from lifeprism.sync.sync_client import SYNC_TABLES

        # Act: 检查每张期望表是否在 SYNC_TABLES 中

        # Assert: 所有 31 张期望表都在 SYNC_TABLES 中
        for table in EXPECTED_STATIC_TABLES:
            assert table in SYNC_TABLES, (
                f"静态表 {table} 不在 SYNC_TABLES 中"
            )

        # Assert: SYNC_TABLES 恰好包含 31 张表
        assert len(SYNC_TABLES) == 31, (
            f"SYNC_TABLES 应包含 31 张表，实际 {len(SYNC_TABLES)} 张"
        )


# ==================== Seam 2: get_all_sync_tables() ====================


class TestGetAllSyncTables:
    """Seam 2: get_all_sync_tables() - 验证动态表（custom_{slug}）的运行时获取"""

    def test_get_all_sync_tables_includes_dynamic_tables(
        self, sync_client, initialized_db, clean_custom_record_types
    ):
        """验证动态表（custom_{slug}）被包含在返回列表中"""
        # Arrange: 向 custom_record_types 插入一条记录，slug = "sport"
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("crt-test-sport", "体育活动", "sport", "", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # Act: 调用 get_all_sync_tables()
        tables = sync_client.get_all_sync_tables()

        # Assert: 返回列表中包含 custom_sport
        assert "custom_sport" in tables, (
            "get_all_sync_tables() 应包含动态表 custom_sport"
        )

    def test_get_all_sync_tables_includes_static_tables(
        self, sync_client, initialized_db, clean_custom_record_types
    ):
        """验证静态表也被包含在返回列表中"""
        # Arrange: custom_record_types 为空（依赖 clean_custom_record_types 清理）

        # Act: 调用 get_all_sync_tables()
        tables = sync_client.get_all_sync_tables()

        # Assert: 所有 30 张静态表都在返回列表中
        for table in EXPECTED_STATIC_TABLES:
            assert table in tables, (
                f"get_all_sync_tables() 应包含静态表 {table}"
            )

    def test_get_all_sync_tables_no_duplicates(
        self, sync_client, initialized_db, clean_custom_record_types
    ):
        """验证返回列表中没有重复表名"""
        # Arrange: 插入两条自定义记录类型
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("crt-test-a", "类型A", "type_a", "", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("crt-test-b", "类型B", "type_b", "", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # Act: 调用 get_all_sync_tables()
        tables = sync_client.get_all_sync_tables()

        # Assert: 没有重复表名
        assert len(tables) == len(set(tables)), (
            f"get_all_sync_tables() 返回列表存在重复表名: {tables}"
        )

    def test_get_all_sync_tables_empty_custom_records(
        self, sync_client, initialized_db, clean_custom_record_types
    ):
        """没有自定义记录类型时只返回静态表"""
        # Arrange: 确保没有清理后 custom_record_types 为空
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_record_types")
            conn.commit()

        # Act: 调用 get_all_sync_tables()
        tables = sync_client.get_all_sync_tables()

        # Assert: 返回列表恰好等于 31 张静态表（无动态表）
        assert len(tables) == 31, (
            f"无自定义记录类型时应返回 31 张静态表，实际 {len(tables)} 张"
        )
        assert set(tables) == set(EXPECTED_STATIC_TABLES), (
            "无自定义记录类型时返回列表应与 SYNC_TABLES 完全一致"
        )
