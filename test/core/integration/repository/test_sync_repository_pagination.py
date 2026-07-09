"""
SyncRepository 分页查询集成测试

测试 seam:
- query_incremental() 分页参数（offset / limit）

测试用例:
1. limit 参数返回部分记录
2. offset 参数跳过记录
3. 跨页查询合并等于全部
4. limit=None 返回全部记录
5. 不存在的表抛出 DataAccessError（sqlite3.Error 转换）

参考: test/core/integration/repository/test_sync_repository.py
"""
import pytest

from lifeprism.utils.exceptions import DataAccessError

pytestmark = pytest.mark.core


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
def repository(initialized_db):
    """创建 SyncRepository 实例，测试后清理数据并重建表结构"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo

    # 清理：重新初始化表结构（防止某些测试 DROP 了表）并删除数据
    from lifeprism.repository.lw_table_manager import LWTableManager

    manager = LWTableManager(db_manager=initialized_db)
    manager.init_database()

    sync_tables = [
        "mood_entries",
        "todo_list",
        "goal",
        "diary",
        "timeline_custom_block",
        "user_app_behavior_log",
        "category_map_cache",
    ]
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in sync_tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


# ==================== 辅助函数 ====================


def _insert_mood_rows(initialized_db, count: int, base_time: str = "2026-07-01"):
    """批量插入 mood_entries 记录，updated_at 递增

    Args:
        initialized_db: 数据库管理器
        count: 插入记录数
        base_time: 日期前缀（不含时间部分）
    """
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for i in range(count):
            hour = 10 + i  # 从 10:00:00 开始递增
            timestamp = f"{base_time} {hour:02d}:00:00"
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"mood-page-{i:03d}", "happy", 5 + i, timestamp, timestamp),
            )
        conn.commit()


# ==================== 分页查询测试 ====================


class TestQueryIncrementalPagination:
    """测试 query_incremental() 分页参数"""

    def test_query_incremental_with_limit_returns_subset(self, repository, initialized_db):
        """limit 参数：使用 limit 返回部分记录"""
        # Arrange: 插入 10 条记录
        _insert_mood_rows(initialized_db, 10)

        # Act: limit=3，只返回前 3 条
        rows = repository.query_incremental(
            "mood_entries", "", offset=0, limit=3
        )

        # Assert: 返回 3 条记录，且是最早的 3 条（按 updated_at ASC）
        assert len(rows) == 3
        assert rows[0]["id"] == "mood-page-000"
        assert rows[1]["id"] == "mood-page-001"
        assert rows[2]["id"] == "mood-page-002"

    def test_query_incremental_with_offset_skips_records(self, repository, initialized_db):
        """offset 参数：使用 offset 跳过前 N 条记录"""
        # Arrange: 插入 10 条记录
        _insert_mood_rows(initialized_db, 10)

        # Act: offset=5，跳过前 5 条
        rows = repository.query_incremental(
            "mood_entries", "", offset=5, limit=3
        )

        # Assert: 返回第 6-8 条记录
        assert len(rows) == 3
        assert rows[0]["id"] == "mood-page-005"
        assert rows[1]["id"] == "mood-page-006"
        assert rows[2]["id"] == "mood-page-007"

    def test_query_incremental_pagination_across_pages(self, repository, initialized_db):
        """跨页查询：offset=0,limit=5 + offset=5,limit=5 合并等于全部"""
        # Arrange: 插入 10 条记录
        _insert_mood_rows(initialized_db, 10)

        # Act: 分两页查询
        page1 = repository.query_incremental(
            "mood_entries", "", offset=0, limit=5
        )
        page2 = repository.query_incremental(
            "mood_entries", "", offset=5, limit=5
        )

        # Assert: 两页合计 10 条，ID 不重复，覆盖全部记录
        all_ids = {row["id"] for row in page1} | {row["id"] for row in page2}
        assert len(page1) == 5
        assert len(page2) == 5
        assert len(all_ids) == 10
        # 验证 ID 连续
        expected_ids = {f"mood-page-{i:03d}" for i in range(10)}
        assert all_ids == expected_ids

    def test_query_incremental_no_limit_returns_all(self, repository, initialized_db):
        """limit=None：返回全部记录（不分页）"""
        # Arrange: 插入 10 条记录
        _insert_mood_rows(initialized_db, 10)

        # Act: limit=None（默认值）
        rows = repository.query_incremental(
            "mood_entries", "", offset=0, limit=None
        )

        # Assert: 返回全部 10 条记录
        assert len(rows) == 10

    def test_query_incremental_no_limit_default_returns_all(self, repository, initialized_db):
        """不传 offset/limit：使用默认值返回全部记录（向后兼容）"""
        # Arrange: 插入 5 条记录
        _insert_mood_rows(initialized_db, 5)

        # Act: 不传分页参数（使用默认值 offset=0, limit=None）
        rows = repository.query_incremental("mood_entries", "")

        # Assert: 返回全部 5 条记录
        assert len(rows) == 5

    def test_query_incremental_invalid_table_raises_error(self, repository, initialized_db):
        """不存在的表：sqlite3.Error 转换为 DataAccessError"""
        # Arrange: 临时删除表模拟表不存在
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS mood_entries")
            conn.commit()

        # Act + Assert: 应抛出 DataAccessError
        with pytest.raises(DataAccessError):
            repository.query_incremental(
                "mood_entries", "2026-07-01 00:00:00", offset=0, limit=10
            )
