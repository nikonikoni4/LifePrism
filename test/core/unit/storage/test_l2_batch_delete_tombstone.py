"""
L2 批量删除统一测试（Slice 08）

验证 6 处批量删除走 _generic_batch_delete（含写墓碑到 deletion_log）：

- map_cache_providers.batch_delete_multi_purpose_map_cache（按 ID 列表批量删除）
- map_cache_providers.batch_delete_single_purpose_map_cache（按 ID 列表批量删除）
- todo_provider.batch_delete_todos（按 ID 列表批量删除）
- todo_provider.delete_todo_cascade（递归收集子任务 ID 后批量删除）
- habit_challenge_provider.delete_by_habit_id（先查 ID 列表再批量删除）
- habit_checkin_provider.delete_by_habit_id（先查 ID 列表再批量删除）

上述 6 张表均在 SYNC_TABLES 中，但均不在 HASH_ID_PREFIXES 中（TEXT 主键表），
墓碑 record_id = 主键值。

依据 issue: 08-l2-batch-delete-unification
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
    """清理指定表的数据（含 deletion_log）"""
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


# ==================== Slice A+B: map_cache_providers 测试 ====================


@pytest.fixture
def map_cache_providers_fixture(test_data_path):
    """创建 MultiPurposeMapCacheProvider 和 SinglePurposeMapCacheProvider 实例

    两张表均为 TEXT 主键表（id 格式 m-xxx / s-xxx），在 SYNC_TABLES 中但不在
    HASH_ID_PREFIXES 中。墓碑 record_id = 主键值。
    测试建表去掉 UNIQUE 约束以简化数据构造（测试关注批量删除墓碑行为）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.map_cache_providers import (
        MultiPurposeMapCacheProvider,
        SinglePurposeMapCacheProvider,
    )

    settings._initialize()

    multi_provider = MultiPurposeMapCacheProvider()
    single_provider = SinglePurposeMapCacheProvider()

    with multi_provider.db.get_connection() as conn:
        cursor = conn.cursor()
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
                link_to_goal_id TEXT,
                state INTEGER,
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
                link_to_goal_id TEXT,
                state INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    _create_deletion_log(multi_provider.db)
    _clear_tables(
        multi_provider.db,
        ["multi_purpose_map_cache", "single_purpose_map_cache", "deletion_log"],
    )

    yield multi_provider, single_provider

    _clear_tables(
        multi_provider.db,
        ["multi_purpose_map_cache", "single_purpose_map_cache", "deletion_log"],
    )


class TestMultiPurposeMapCacheBatchDeleteWritesTombstone:
    """验证 MultiPurposeMapCacheProvider.batch_delete_multi_purpose_map_cache
    走 _generic_batch_delete（含写墓碑）

    依据 issue: 08-l2-batch-delete-unification
    multi_purpose_map_cache 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id = id。
    """

    def test_batch_delete_writes_tombstone_for_each_record(self, map_cache_providers_fixture):
        """批量删除为每条记录写墓碑（record_id = 主键 id）"""
        multi_provider, _ = map_cache_providers_fixture
        ids = ["m-test01", "m-test02", "m-test03"]
        for cid in ids:
            multi_provider.create_multi_purpose_map_cache(
                {"id": cid, "app": f"app-{cid}", "title": f"title-{cid}", "state": 1}
            )

        # 删除前确认 3 条记录存在
        for cid in ids:
            assert multi_provider.get_multi_purpose_map_cache_by_id(cid) is not None

        # 批量删除
        deleted = multi_provider.batch_delete_multi_purpose_map_cache(ids)
        assert deleted == 3, f"应删除 3 条记录，实际: {deleted}"

        # 验证记录已消失
        for cid in ids:
            assert multi_provider.get_multi_purpose_map_cache_by_id(cid) is None

        # 验证 3 条墓碑已写入 deletion_log
        count = _count_tombstones(multi_provider.db, "multi_purpose_map_cache")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = id
        for cid in ids:
            tombstone = _get_tombstone(multi_provider.db, "multi_purpose_map_cache", cid)
            assert tombstone is not None, f"id '{cid}' 应有对应墓碑"
            assert tombstone[1] == "multi_purpose_map_cache"
            assert tombstone[2] == cid
            assert tombstone[3] == "local"

    def test_batch_delete_empty_list_returns_zero(self, map_cache_providers_fixture):
        """空列表返回 0，不写墓碑"""
        multi_provider, _ = map_cache_providers_fixture
        deleted = multi_provider.batch_delete_multi_purpose_map_cache([])
        assert deleted == 0

        count = _count_tombstones(multi_provider.db, "multi_purpose_map_cache")
        assert count == 0, "空列表不应写墓碑"


class TestSinglePurposeMapCacheBatchDeleteWritesTombstone:
    """验证 SinglePurposeMapCacheProvider.batch_delete_single_purpose_map_cache
    走 _generic_batch_delete（含写墓碑）

    依据 issue: 08-l2-batch-delete-unification
    single_purpose_map_cache 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id = id。
    """

    def test_batch_delete_writes_tombstone_for_each_record(self, map_cache_providers_fixture):
        """批量删除为每条记录写墓碑（record_id = 主键 id）"""
        _, single_provider = map_cache_providers_fixture
        ids = ["s-test01", "s-test02", "s-test03"]
        for cid in ids:
            single_provider.create_single_purpose_map_cache(
                {"id": cid, "app": f"app-{cid}", "title": f"title-{cid}", "state": 1}
            )

        # 删除前确认 3 条记录存在
        for cid in ids:
            assert single_provider.get_single_purpose_map_cache_by_id(cid) is not None

        # 批量删除
        deleted = single_provider.batch_delete_single_purpose_map_cache(ids)
        assert deleted == 3, f"应删除 3 条记录，实际: {deleted}"

        # 验证记录已消失
        for cid in ids:
            assert single_provider.get_single_purpose_map_cache_by_id(cid) is None

        # 验证 3 条墓碑已写入 deletion_log
        count = _count_tombstones(single_provider.db, "single_purpose_map_cache")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = id
        for cid in ids:
            tombstone = _get_tombstone(single_provider.db, "single_purpose_map_cache", cid)
            assert tombstone is not None, f"id '{cid}' 应有对应墓碑"
            assert tombstone[1] == "single_purpose_map_cache"
            assert tombstone[2] == cid
            assert tombstone[3] == "local"

    def test_batch_delete_empty_list_returns_zero(self, map_cache_providers_fixture):
        """空列表返回 0，不写墓碑"""
        _, single_provider = map_cache_providers_fixture
        deleted = single_provider.batch_delete_single_purpose_map_cache([])
        assert deleted == 0

        count = _count_tombstones(single_provider.db, "single_purpose_map_cache")
        assert count == 0, "空列表不应写墓碑"


# ==================== Slice C+D: todo_provider 测试 ====================


@pytest.fixture
def todo_provider_fixture(test_data_path):
    """创建 TodoProvider 实例并初始化 todo_list + deletion_log 表

    todo_list 是 TEXT 主键表（id 格式 t-xxx），在 SYNC_TABLES 中但不在
    HASH_ID_PREFIXES 中。墓碑 record_id = id。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.todo_provider import TodoProvider

    settings._initialize()

    provider = TodoProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS todo_list (
                id TEXT PRIMARY KEY,
                order_index INTEGER DEFAULT 0,
                pool_order_index INTEGER DEFAULT 0,
                content TEXT,
                color TEXT DEFAULT '#FFFFFF',
                state TEXT DEFAULT 'pool',
                link_to_goal_id TEXT,
                date TEXT,
                expected_finished_at TEXT,
                actual_finished_at TEXT,
                cross_day INTEGER DEFAULT 0,
                folder_id INTEGER,
                parent_id TEXT,
                plan_doc_id TEXT,
                delay_days INTEGER,
                delay_reason TEXT,
                waid_order INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["todo_list", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["todo_list", "deletion_log"])


class TestTodoBatchDeleteWritesTombstone:
    """验证 TodoProvider.batch_delete_todos 走 _generic_batch_delete（含写墓碑）

    依据 issue: 08-l2-batch-delete-unification
    todo_list 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id = id。
    """

    def test_batch_delete_writes_tombstone_for_each_record(self, todo_provider_fixture):
        """batch_delete_todos 为每条删除的记录写墓碑（record_id = todo_id）"""
        provider = todo_provider_fixture
        todo_ids = []
        for i in range(3):
            todo_id = provider.create_todo(
                {
                    "content": f"task-{i}",
                    "state": "pool",
                    "order_index": i,
                    "pool_order_index": i,
                }
            )
            todo_ids.append(todo_id)

        # 删除前确认 3 条记录存在
        for tid in todo_ids:
            assert provider.get_todo_by_id(tid) is not None

        # 批量删除
        deleted = provider.batch_delete_todos(todo_ids)
        assert deleted == 3, f"应删除 3 条记录，实际: {deleted}"

        # 验证记录已消失
        for tid in todo_ids:
            assert provider.get_todo_by_id(tid) is None

        # 验证 3 条墓碑已写入 deletion_log
        count = _count_tombstones(provider.db, "todo_list")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = todo_id
        for tid in todo_ids:
            tombstone = _get_tombstone(provider.db, "todo_list", tid)
            assert tombstone is not None, f"todo_id '{tid}' 应有对应墓碑"
            assert tombstone[1] == "todo_list"
            assert tombstone[2] == tid
            assert tombstone[3] == "local"

    def test_batch_delete_empty_list_returns_zero(self, todo_provider_fixture):
        """空列表返回 0，不写墓碑"""
        provider = todo_provider_fixture
        deleted = provider.batch_delete_todos([])
        assert deleted == 0

        count = _count_tombstones(provider.db, "todo_list")
        assert count == 0, "空列表不应写墓碑"


class TestTodoCascadeDeleteWritesTombstone:
    """验证 TodoProvider.delete_todo_cascade 走 _generic_batch_delete（含写墓碑）

    依据 issue: 08-l2-batch-delete-unification
    递归收集所有子任务 ID（含自身），一次性批量删除+写墓碑。
    todo_list 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id = id。
    """

    def test_cascade_delete_writes_tombstone_for_all_descendants(self, todo_provider_fixture):
        """delete_todo_cascade 递归收集所有子任务 ID，批量写墓碑"""
        provider = todo_provider_fixture
        # 构造 3 层树：
        #   root (t-root01)
        #   ├── child1 (t-child01)
        #   │   └── grandchild1 (t-grand01)
        #   └── child2 (t-child02)
        root_id = provider.create_todo({"content": "root", "state": "pool", "order_index": 0})
        child1_id = provider.create_todo(
            {
                "content": "child1",
                "state": "pool",
                "order_index": 1,
                "parent_id": root_id,
            }
        )
        child2_id = provider.create_todo(
            {
                "content": "child2",
                "state": "pool",
                "order_index": 2,
                "parent_id": root_id,
            }
        )
        grandchild1_id = provider.create_todo(
            {
                "content": "grandchild1",
                "state": "pool",
                "order_index": 3,
                "parent_id": child1_id,
            }
        )
        all_ids = [root_id, child1_id, child2_id, grandchild1_id]

        # 删除前确认 4 条记录存在
        for tid in all_ids:
            assert provider.get_todo_by_id(tid) is not None

        # 级联删除
        deleted = provider.delete_todo_cascade(root_id)
        assert deleted == 4, f"应删除 4 条记录（含子任务），实际: {deleted}"

        # 验证记录已消失
        for tid in all_ids:
            assert provider.get_todo_by_id(tid) is None

        # 验证 4 条墓碑已写入 deletion_log
        count = _count_tombstones(provider.db, "todo_list")
        assert count == 4, f"应写入 4 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = todo_id
        for tid in all_ids:
            tombstone = _get_tombstone(provider.db, "todo_list", tid)
            assert tombstone is not None, f"todo_id '{tid}' 应有对应墓碑"
            assert tombstone[1] == "todo_list"
            assert tombstone[2] == tid
            assert tombstone[3] == "local"

    def test_cascade_delete_leaf_node_writes_single_tombstone(self, todo_provider_fixture):
        """删除叶子节点（无子任务）只写 1 条墓碑"""
        provider = todo_provider_fixture
        leaf_id = provider.create_todo({"content": "leaf", "state": "pool", "order_index": 0})

        deleted = provider.delete_todo_cascade(leaf_id)
        assert deleted == 1

        count = _count_tombstones(provider.db, "todo_list")
        assert count == 1

        tombstone = _get_tombstone(provider.db, "todo_list", leaf_id)
        assert tombstone is not None
        assert tombstone[2] == leaf_id


# ==================== Slice E+F: habit_providers 测试 ====================


@pytest.fixture
def habit_providers_fixture(test_data_path):
    """创建 HabitChallengeProvider 和 HabitCheckinProvider 实例

    habit_challenges 和 habit_checkins 均为 TEXT 主键表，在 SYNC_TABLES 中但不在
    HASH_ID_PREFIXES 中。墓碑 record_id = 主键 id。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.habit_providers import (
        HabitChallengeProvider,
        HabitCheckinProvider,
    )

    settings._initialize()

    challenge_provider = HabitChallengeProvider()
    checkin_provider = HabitCheckinProvider()

    with challenge_provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS habit_challenges (
                id TEXT PRIMARY KEY,
                habit_id TEXT NOT NULL,
                challenge_weeks INTEGER,
                required_completions INTEGER,
                from_level INTEGER,
                to_level INTEGER,
                start_date TEXT,
                end_date TEXT,
                completed_count INTEGER DEFAULT 0,
                streak_base INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                finished_at TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS habit_checkins (
                id TEXT PRIMARY KEY,
                habit_id TEXT NOT NULL,
                challenge_id TEXT NOT NULL,
                date TEXT NOT NULL,
                completed_at TEXT,
                created_at TEXT,
                UNIQUE(habit_id, date)
            )
            """
        )
        conn.commit()
    _create_deletion_log(challenge_provider.db)
    _clear_tables(
        challenge_provider.db,
        ["habit_challenges", "habit_checkins", "deletion_log"],
    )

    yield challenge_provider, checkin_provider

    _clear_tables(
        challenge_provider.db,
        ["habit_challenges", "habit_checkins", "deletion_log"],
    )


class TestHabitChallengeDeleteByHabitIdWritesTombstone:
    """验证 HabitChallengeProvider.delete_by_habit_id 走 _generic_batch_delete
    （先查 ID 列表，含写墓碑）

    依据 issue: 08-l2-batch-delete-unification
    habit_challenges 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id = id。
    """

    def test_delete_by_habit_id_writes_tombstone_for_each_record(self, habit_providers_fixture):
        """delete_by_habit_id 先查 ID 列表再批量删除，每条记录写墓碑"""
        challenge_provider, _ = habit_providers_fixture
        habit_id = "habit-test01"
        # 创建 3 条该 habit 的 challenge
        challenge_ids = []
        for i in range(3):
            cid = challenge_provider.create_challenge(
                {
                    "habit_id": habit_id,
                    "challenge_weeks": 4,
                    "required_completions": 20,
                    "from_level": i,
                    "to_level": i + 1,
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-29",
                    "status": "succeeded" if i > 0 else "in_progress",
                }
            )
            challenge_ids.append(cid)

        # 创建 1 条其他 habit 的 challenge（不应被删除）
        other_id = challenge_provider.create_challenge(
            {
                "habit_id": "habit-other",
                "challenge_weeks": 4,
                "required_completions": 20,
                "from_level": 0,
                "to_level": 1,
                "start_date": "2026-07-01",
                "end_date": "2026-07-29",
            }
        )

        # 删除
        result = challenge_provider.delete_by_habit_id(habit_id)
        assert result is True

        # 验证该 habit 的 challenge 已消失
        remaining = challenge_provider.get_challenges_by_habit(habit_id)
        assert len(remaining) == 0, "该 habit 的 challenge 应已全部删除"

        # 验证其他 habit 的 challenge 仍在
        other_remaining = challenge_provider.get_challenges_by_habit("habit-other")
        assert len(other_remaining) == 1, "其他 habit 的 challenge 不应被删除"
        assert other_remaining[0]["id"] == other_id

        # 验证 3 条墓碑已写入 deletion_log（其他 habit 的不应有墓碑）
        count = _count_tombstones(challenge_provider.db, "habit_challenges")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = challenge_id
        for cid in challenge_ids:
            tombstone = _get_tombstone(challenge_provider.db, "habit_challenges", cid)
            assert tombstone is not None, f"challenge_id '{cid}' 应有对应墓碑"
            assert tombstone[1] == "habit_challenges"
            assert tombstone[2] == cid
            assert tombstone[3] == "local"

    def test_delete_by_habit_id_no_records(self, habit_providers_fixture):
        """habit 没有 challenge 记录时返回 True，不写墓碑"""
        challenge_provider, _ = habit_providers_fixture
        result = challenge_provider.delete_by_habit_id("habit-empty")
        assert result is True

        count = _count_tombstones(challenge_provider.db, "habit_challenges")
        assert count == 0, "无记录时不应写墓碑"


class TestHabitCheckinDeleteByHabitIdWritesTombstone:
    """验证 HabitCheckinProvider.delete_by_habit_id 走 _generic_batch_delete
    （先查 ID 列表，含写墓碑）

    依据 issue: 08-l2-batch-delete-unification
    habit_checkins 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id = id。
    """

    def test_delete_by_habit_id_writes_tombstone_for_each_record(self, habit_providers_fixture):
        """delete_by_habit_id 先查 ID 列表再批量删除，每条记录写墓碑"""
        _, checkin_provider = habit_providers_fixture
        habit_id = "habit-test01"
        # 创建 3 条该 habit 的 checkin（不同日期，避免 UNIQUE 冲突）
        checkin_ids = []
        for i in range(3):
            cid = checkin_provider.create_checkin(
                {
                    "habit_id": habit_id,
                    "challenge_id": "challenge-test01",
                    "date": f"2026-07-{i + 1:02d}",
                }
            )
            assert cid is not None
            checkin_ids.append(cid)

        # 创建 1 条其他 habit 的 checkin（不应被删除）
        other_id = checkin_provider.create_checkin(
            {
                "habit_id": "habit-other",
                "challenge_id": "challenge-other",
                "date": "2026-07-01",
            }
        )
        assert other_id is not None

        # 删除
        result = checkin_provider.delete_by_habit_id(habit_id)
        assert result is True

        # 验证该 habit 的 checkin 已消失（按日期查应返回 None）
        for i in range(3):
            assert checkin_provider.get_checkin_by_date(habit_id, f"2026-07-{i + 1:02d}") is None

        # 验证其他 habit 的 checkin 仍在
        assert checkin_provider.get_checkin_by_date("habit-other", "2026-07-01") is not None

        # 验证 3 条墓碑已写入 deletion_log
        count = _count_tombstones(checkin_provider.db, "habit_checkins")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = checkin_id
        for cid in checkin_ids:
            tombstone = _get_tombstone(checkin_provider.db, "habit_checkins", cid)
            assert tombstone is not None, f"checkin_id '{cid}' 应有对应墓碑"
            assert tombstone[1] == "habit_checkins"
            assert tombstone[2] == cid
            assert tombstone[3] == "local"

    def test_delete_by_habit_id_no_records(self, habit_providers_fixture):
        """habit 没有 checkin 记录时返回 True，不写墓碑"""
        _, checkin_provider = habit_providers_fixture
        result = checkin_provider.delete_by_habit_id("habit-empty")
        assert result is True

        count = _count_tombstones(checkin_provider.db, "habit_checkins")
        assert count == 0, "无记录时不应写墓碑"
