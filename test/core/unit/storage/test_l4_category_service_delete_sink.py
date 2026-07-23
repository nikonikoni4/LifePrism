"""
L4 Service/Aggregator 下沉测试（Slice 09 Sub-PR 3）

验证 CategoryService 中 4 处直接 DELETE FROM multi/single_purpose_map_cache
下沉到 map_cache_repository.batch_delete_* 走 _generic_batch_delete（含写墓碑）：

- _enable_category_map_records_by_category:
  - multi_purpose_map_cache DELETE（第 1 处）
  - single_purpose_map_cache DELETE（第 2 处）
- _enable_category_map_records_by_sub_category:
  - multi_purpose_map_cache DELETE（第 3 处）
  - single_purpose_map_cache DELETE（第 4 处）

依据 issue: 09-l3-cascade-l4-service-sink
依据 ADR: docs/adr/2026-07-22-deletion-log-table.md
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 共用工具函数 ====================


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


def _count_tombstones(db, target_table, record_id=None):
    """查询 deletion_log 中的墓碑数量"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if record_id is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ? AND record_id = ?",
                (target_table, record_id),
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ?",
                (target_table,),
            )
        return cursor.fetchone()[0]


def _get_tombstone(db, target_table, record_id):
    """查询单条墓碑记录，返回 (id, target_table, record_id, source, created_at, updated_at)"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, target_table, record_id, source, created_at, updated_at "
            "FROM deletion_log WHERE target_table = ? AND record_id = ?",
            (target_table, record_id),
        )
        return cursor.fetchone()


def _get_record_state(db, table_name, record_id):
    """查询记录的 state 字段"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT state FROM {table_name} WHERE id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def _record_exists(db, table_name, record_id):
    """检查记录是否存在"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE id = ?",
            (record_id,),
        )
        return cursor.fetchone()[0] > 0


# ==================== Fixture ====================


@pytest.fixture
def category_service_fixture(test_data_path):
    """创建 CategoryService 实例并初始化测试表

    创建 category、sub_category、multi_purpose_map_cache、
    single_purpose_map_cache、deletion_log 表，
    然后实例化 CategoryService（load_categories/load_sub_categories 返回空 DataFrame）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository import lw_db_manager
    from lifeprism.server.services.category_service import CategoryService

    settings._initialize()

    # 创建测试所需的表
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS category (
                id TEXT PRIMARY KEY,
                name TEXT,
                state INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sub_category (
                id TEXT PRIMARY KEY,
                category_id TEXT,
                name TEXT,
                state INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS multi_purpose_map_cache (
                id TEXT PRIMARY KEY,
                app TEXT,
                title TEXT,
                app_description TEXT,
                title_analysis TEXT,
                category_id TEXT,
                sub_category_id TEXT,
                state INTEGER DEFAULT 0,
                link_to_goal_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS single_purpose_map_cache (
                id TEXT PRIMARY KEY,
                app TEXT,
                title TEXT,
                app_description TEXT,
                category_id TEXT,
                sub_category_id TEXT,
                state INTEGER DEFAULT 0,
                link_to_goal_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(lw_db_manager)
    _clear_tables(
        lw_db_manager,
        [
            "category",
            "sub_category",
            "multi_purpose_map_cache",
            "single_purpose_map_cache",
            "deletion_log",
        ],
    )

    # 实例化 CategoryService（不通过单例，避免跨测试状态泄漏）
    service = CategoryService()

    yield service

    _clear_tables(
        lw_db_manager,
        [
            "category",
            "sub_category",
            "multi_purpose_map_cache",
            "single_purpose_map_cache",
            "deletion_log",
        ],
    )


def _insert_multi_record(
    db, record_id, app, title, category_id, sub_category_id, state, created_at
):
    """插入 multi_purpose_map_cache 记录"""
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO multi_purpose_map_cache (id, app, title, category_id, sub_category_id, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (record_id, app, title, category_id, sub_category_id, state, created_at, created_at),
        )
        conn.commit()


def _insert_single_record(db, record_id, app, category_id, sub_category_id, state, created_at):
    """插入 single_purpose_map_cache 记录"""
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO single_purpose_map_cache (id, app, title, category_id, sub_category_id, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (record_id, app, "", category_id, sub_category_id, state, created_at, created_at),
        )
        conn.commit()


# ==================== 测试类 ====================


class TestEnableByCategoryWritesTombstones:
    """验证 _enable_category_map_records_by_category 中 2 处 DELETE 下沉走 _generic_batch_delete

    依据 issue: 09-l3-cascade-l4-service-sink
    multi_purpose_map_cache 和 single_purpose_map_cache 均在 SYNC_TABLES 中，
    墓碑 record_id = 主键 id（TEXT 主键表）。
    """

    def test_enable_by_category_writes_tombstones_for_multi_and_single(
        self, category_service_fixture
    ):
        """启用主分类时，multi 和 single 中 created_at 更晚的记录被删除并写墓碑"""
        from lifeprism.repository import lw_db_manager

        service = category_service_fixture

        # 插入子分类（state=1，启用）
        with lw_db_manager.get_connection() as conn:
            conn.execute(
                "INSERT INTO sub_category (id, category_id, name, state) VALUES (?, ?, ?, ?)",
                ("sub-1", "cat-1", "子分类1", 1),
            )
            conn.commit()

        # multi_purpose_map_cache:
        # m-1: state=0（待恢复），created_at=T1
        # m-2: state=1，created_at=T2 > T1（同 app+title，应被删除并写墓碑）
        _insert_multi_record(
            lw_db_manager,
            "m-1",
            "app1",
            "title1",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )
        _insert_multi_record(
            lw_db_manager,
            "m-2",
            "app1",
            "title1",
            "cat-1",
            "sub-1",
            1,
            "2026-07-02T00:00:00+00:00",
        )

        # single_purpose_map_cache:
        # s-1: state=0（待恢复），created_at=T1
        # s-2: state=1，created_at=T2 > T1（同 app，应被删除并写墓碑）
        _insert_single_record(
            lw_db_manager,
            "s-1",
            "app2",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )
        _insert_single_record(
            lw_db_manager,
            "s-2",
            "app2",
            "cat-1",
            "sub-1",
            1,
            "2026-07-02T00:00:00+00:00",
        )

        # 调用 _enable_category_map_records_by_category
        service._enable_category_map_records_by_category("cat-1")

        # 验证 m-1 恢复为 state=1
        assert _get_record_state(lw_db_manager, "multi_purpose_map_cache", "m-1") == 1

        # 验证 m-2 已删除
        assert not _record_exists(lw_db_manager, "multi_purpose_map_cache", "m-2")

        # 验证 m-2 墓碑
        assert _count_tombstones(lw_db_manager, "multi_purpose_map_cache") == 1
        m2_tombstone = _get_tombstone(lw_db_manager, "multi_purpose_map_cache", "m-2")
        assert m2_tombstone is not None
        assert m2_tombstone[1] == "multi_purpose_map_cache"
        assert m2_tombstone[2] == "m-2"
        assert m2_tombstone[3] == "local"

        # 验证 s-1 恢复为 state=1
        assert _get_record_state(lw_db_manager, "single_purpose_map_cache", "s-1") == 1

        # 验证 s-2 已删除
        assert not _record_exists(lw_db_manager, "single_purpose_map_cache", "s-2")

        # 验证 s-2 墓碑
        assert _count_tombstones(lw_db_manager, "single_purpose_map_cache") == 1
        s2_tombstone = _get_tombstone(lw_db_manager, "single_purpose_map_cache", "s-2")
        assert s2_tombstone is not None
        assert s2_tombstone[1] == "single_purpose_map_cache"
        assert s2_tombstone[2] == "s-2"
        assert s2_tombstone[3] == "local"

    def test_enable_by_category_no_later_records_no_tombstones(self, category_service_fixture):
        """启用主分类时，无 created_at 更晚的记录则不写墓碑"""
        from lifeprism.repository import lw_db_manager

        service = category_service_fixture

        # 插入子分类（state=1）
        with lw_db_manager.get_connection() as conn:
            conn.execute(
                "INSERT INTO sub_category (id, category_id, name, state) VALUES (?, ?, ?, ?)",
                ("sub-1", "cat-1", "子分类1", 1),
            )
            conn.commit()

        # 只有一条 state=0 记录，无更晚的记录
        _insert_multi_record(
            lw_db_manager,
            "m-1",
            "app1",
            "title1",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )
        _insert_single_record(
            lw_db_manager,
            "s-1",
            "app2",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )

        service._enable_category_map_records_by_category("cat-1")

        # 恢复 state=1
        assert _get_record_state(lw_db_manager, "multi_purpose_map_cache", "m-1") == 1
        assert _get_record_state(lw_db_manager, "single_purpose_map_cache", "s-1") == 1

        # 无墓碑
        assert _count_tombstones(lw_db_manager, "multi_purpose_map_cache") == 0
        assert _count_tombstones(lw_db_manager, "single_purpose_map_cache") == 0


class TestEnableBySubCategoryWritesTombstones:
    """验证 _enable_category_map_records_by_sub_category 中 2 处 DELETE 下沉走 _generic_batch_delete

    依据 issue: 09-l3-cascade-l4-service-sink
    该方法先检查主分类是否启用（state=1），再恢复子分类下 state=0 的记录。
    """

    def test_enable_by_sub_category_writes_tombstones_for_multi_and_single(
        self, category_service_fixture
    ):
        """启用子分类时，multi 和 single 中 created_at 更晚的记录被删除并写墓碑"""
        from lifeprism.repository import lw_db_manager

        service = category_service_fixture

        # 插入主分类（state=1，必须启用；color 为 NOT NULL 列）
        with lw_db_manager.get_connection() as conn:
            conn.execute(
                "INSERT INTO category (id, name, color, state) VALUES (?, ?, ?, ?)",
                ("cat-1", "主分类1", "#5B8FF9", 1),
            )
            conn.commit()

        # multi_purpose_map_cache:
        # m-3: state=0（待恢复），sub_category_id=sub-1，created_at=T1
        # m-4: state=1，created_at=T2 > T1（同 app+title，应被删除并写墓碑）
        _insert_multi_record(
            lw_db_manager,
            "m-3",
            "app3",
            "title3",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )
        _insert_multi_record(
            lw_db_manager,
            "m-4",
            "app3",
            "title3",
            "cat-1",
            "sub-1",
            1,
            "2026-07-02T00:00:00+00:00",
        )

        # single_purpose_map_cache:
        # s-3: state=0（待恢复），sub_category_id=sub-1，created_at=T1
        # s-4: state=1，created_at=T2 > T1（同 app，应被删除并写墓碑）
        _insert_single_record(
            lw_db_manager,
            "s-3",
            "app4",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )
        _insert_single_record(
            lw_db_manager,
            "s-4",
            "app4",
            "cat-1",
            "sub-1",
            1,
            "2026-07-02T00:00:00+00:00",
        )

        # 调用 _enable_category_map_records_by_sub_category
        service._enable_category_map_records_by_sub_category("sub-1", "cat-1")

        # 验证 m-3 恢复为 state=1
        assert _get_record_state(lw_db_manager, "multi_purpose_map_cache", "m-3") == 1

        # 验证 m-4 已删除
        assert not _record_exists(lw_db_manager, "multi_purpose_map_cache", "m-4")

        # 验证 m-4 墓碑
        assert _count_tombstones(lw_db_manager, "multi_purpose_map_cache") == 1
        m4_tombstone = _get_tombstone(lw_db_manager, "multi_purpose_map_cache", "m-4")
        assert m4_tombstone is not None
        assert m4_tombstone[1] == "multi_purpose_map_cache"
        assert m4_tombstone[2] == "m-4"
        assert m4_tombstone[3] == "local"

        # 验证 s-3 恢复为 state=1
        assert _get_record_state(lw_db_manager, "single_purpose_map_cache", "s-3") == 1

        # 验证 s-4 已删除
        assert not _record_exists(lw_db_manager, "single_purpose_map_cache", "s-4")

        # 验证 s-4 墓碑
        assert _count_tombstones(lw_db_manager, "single_purpose_map_cache") == 1
        s4_tombstone = _get_tombstone(lw_db_manager, "single_purpose_map_cache", "s-4")
        assert s4_tombstone is not None
        assert s4_tombstone[1] == "single_purpose_map_cache"
        assert s4_tombstone[2] == "s-4"
        assert s4_tombstone[3] == "local"

    def test_enable_by_sub_category_parent_disabled_skips(self, category_service_fixture):
        """主分类禁用时，_enable_category_map_records_by_sub_category 跳过恢复"""
        from lifeprism.repository import lw_db_manager

        service = category_service_fixture

        # 插入主分类（state=0，禁用；color 为 NOT NULL 列）
        with lw_db_manager.get_connection() as conn:
            conn.execute(
                "INSERT INTO category (id, name, color, state) VALUES (?, ?, ?, ?)",
                ("cat-1", "主分类1", "#5B8FF9", 0),
            )
            conn.commit()

        _insert_multi_record(
            lw_db_manager,
            "m-3",
            "app3",
            "title3",
            "cat-1",
            "sub-1",
            0,
            "2026-07-01T00:00:00+00:00",
        )

        # 主分类禁用，应跳过
        service._enable_category_map_records_by_sub_category("sub-1", "cat-1")

        # 记录未被恢复（state 仍为 0）
        assert _get_record_state(lw_db_manager, "multi_purpose_map_cache", "m-3") == 0

        # 无墓碑
        assert _count_tombstones(lw_db_manager, "multi_purpose_map_cache") == 0
