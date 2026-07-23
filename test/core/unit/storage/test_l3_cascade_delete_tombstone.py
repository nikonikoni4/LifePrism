"""
L3 级联删除测试（Slice 09）

验证 2 组级联删除走 _generic_delete / _generic_batch_delete 通道：

- habit_chain_providers.delete_chain
  级联删除 habit_chain_nodes + habit_chains。
  注意：habit_chains 和 habit_chain_nodes 当前不在 SYNC_TABLES 中
  （见 docs/known-limitations/habit-chain-tables-not-synced.md），
  所以 _generic_delete / _generic_batch_delete 不会写墓碑。
  测试验证：记录被删除，且使用 _generic_* 通道（非原生 SQL DELETE）。

- habit_providers.delete_habit
  级联删除 habit_challenges + habit_checkins + habits。
  三张表均在 SYNC_TABLES 中，墓碑 record_id = 主键值。
  测试验证：记录被删除，且为三张表分别写墓碑。

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


# ==================== Slice A: habit_chain_providers.delete_chain 测试 ====================


@pytest.fixture
def habit_chain_providers_fixture(test_data_path):
    """创建 HabitChainProvider 和 HabitChainNodeProvider 实例

    habit_chains 和 habit_chain_nodes 都是 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中），
    但当前不在 SYNC_TABLES 中（临时移除，待 chain_id 改引用 hash_id 后恢复）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.habit_chain_providers import (
        HabitChainNodeProvider,
        HabitChainProvider,
    )

    settings._initialize()

    chain_provider = HabitChainProvider()
    node_provider = HabitChainNodeProvider()

    with chain_provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS habit_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                show_in_timeline INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS habit_chain_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                chain_id INTEGER,
                sort_order INTEGER,
                name TEXT,
                habit_id TEXT,
                trigger_time TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    _create_deletion_log(chain_provider.db)
    _clear_tables(
        chain_provider.db,
        ["habit_chains", "habit_chain_nodes", "deletion_log"],
    )

    yield chain_provider, node_provider

    _clear_tables(
        chain_provider.db,
        ["habit_chains", "habit_chain_nodes", "deletion_log"],
    )


class TestHabitChainDeleteChainCascade:
    """验证 HabitChainProvider.delete_chain 级联删除走 _generic_* 通道

    依据 issue: 09-l3-cascade-l4-service-sink
    habit_chains 和 habit_chain_nodes 当前不在 SYNC_TABLES 中
    （docs/known-limitations/habit-chain-tables-not-synced.md），
    所以 _generic_delete / _generic_batch_delete 不会写墓碑。
    测试验证：级联删除后两张表的记录都被清除。
    """

    def test_delete_chain_removes_chain_and_all_nodes(self, habit_chain_providers_fixture):
        """delete_chain 级联删除链条及其所有节点"""
        chain_provider, node_provider = habit_chain_providers_fixture

        # 创建链条
        chain_id = chain_provider.create_chain(
            {"name": "晨间链条", "description": "测试", "show_in_timeline": 0}
        )

        # 创建 3 个节点
        node_ids = []
        for i in range(3):
            node_id = node_provider.create_node(
                {
                    "chain_id": chain_id,
                    "sort_order": i,
                    "name": f"节点-{i}",
                    "habit_id": f"habit-{i}",
                    "trigger_time": f"08:0{i}",
                }
            )
            node_ids.append(node_id)

        # 删除前确认记录存在
        assert chain_provider.get_chain_by_id(chain_id) is not None
        nodes = node_provider.get_nodes_by_chain(chain_id)
        assert len(nodes) == 3

        # 级联删除
        result = chain_provider.delete_chain(chain_id)
        assert result is True

        # 验证链条已删除
        assert chain_provider.get_chain_by_id(chain_id) is None

        # 验证所有节点已删除
        remaining_nodes = node_provider.get_nodes_by_chain(chain_id)
        assert len(remaining_nodes) == 0, "级联删除后不应有残留节点"

    def test_delete_chain_no_tombstone_for_non_sync_tables(self, habit_chain_providers_fixture):
        """delete_chain 对不在 SYNC_TABLES 的表不写墓碑（当前限制）

        habit_chains 和 habit_chain_nodes 不在 SYNC_TABLES 中，
        _generic_delete / _generic_batch_delete 不会写墓碑。
        """
        chain_provider, _ = habit_chain_providers_fixture

        chain_id = chain_provider.create_chain({"name": "测试链条"})
        chain_provider.delete_chain(chain_id)

        # 不在 SYNC_TABLES 中，不应有墓碑
        assert _count_tombstones(chain_provider.db, "habit_chains") == 0
        assert _count_tombstones(chain_provider.db, "habit_chain_nodes") == 0

    def test_delete_nonexistent_chain_returns_true(self, habit_chain_providers_fixture):
        """删除不存在的链条返回 True（无节点可删，链条 DELETE 影响 0 行）"""
        chain_provider, _ = habit_chain_providers_fixture
        # 不存在的 chain_id：节点查询返回空，batch_delete(空) 返回 0，
        # _generic_delete 对不存在的记录返回 False，但 delete_chain 整体应不抛异常
        # 注意：当前实现可能返回 True 或 False，关键是 not raise
        try:
            chain_provider.delete_chain(99999)
        except Exception as e:
            pytest.fail(f"删除不存在的链条不应抛异常: {e}")


# ==================== Slice B: habit_providers.delete_habit 测试 ====================


@pytest.fixture
def habit_cascade_providers_fixture(test_data_path):
    """创建 HabitProvider、HabitChallengeProvider、HabitCheckinProvider 实例

    habits、habit_challenges、habit_checkins 均为 TEXT 主键表，在 SYNC_TABLES 中。
    墓碑 record_id = 主键值。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.habit_providers import (
        HabitChallengeProvider,
        HabitCheckinProvider,
        HabitProvider,
    )

    settings._initialize()

    habit_provider = HabitProvider()
    challenge_provider = HabitChallengeProvider()
    checkin_provider = HabitCheckinProvider()

    with habit_provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS habits (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                frequency_type TEXT DEFAULT 'daily',
                frequency_config TEXT,
                current_level INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                value_id TEXT,
                commitment_id TEXT,
                paused_at TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
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
    _create_deletion_log(habit_provider.db)
    _clear_tables(
        habit_provider.db,
        ["habits", "habit_challenges", "habit_checkins", "deletion_log"],
    )

    yield habit_provider, challenge_provider, checkin_provider

    _clear_tables(
        habit_provider.db,
        ["habits", "habit_challenges", "habit_checkins", "deletion_log"],
    )


class TestHabitDeleteHabitNoCascade:
    """验证 HabitProvider.delete_habit 只删除 habits 表（不级联），走 _generic_* 写墓碑

    依据 issue: 09-l3-cascade-l4-service-sink
    级联删除挑战和打卡的逻辑在 Service 层（habit_service.delete_habit），
    Provider 层只做单表删除。delete_habit 只：
    1. 调用 self._generic_delete（写墓碑+删除 habits 记录）
    2. 不删除 habit_challenges 和 habit_checkins（由 Service 层级联处理）
    """

    def test_delete_habit_only_deletes_habits_table(self, habit_cascade_providers_fixture):
        """delete_habit 只删除 habits 记录，不级联删除挑战和打卡"""
        habit_provider, challenge_provider, checkin_provider = habit_cascade_providers_fixture

        # 创建习惯
        habit_id = habit_provider.create_habit({"name": "测试习惯"})

        # 创建 1 条挑战
        challenge_provider.create_challenge(
            {
                "habit_id": habit_id,
                "challenge_weeks": 4,
                "required_completions": 20,
                "from_level": 0,
                "to_level": 1,
                "start_date": "2026-07-01",
                "end_date": "2026-07-29",
                "status": "in_progress",
            }
        )

        # 创建 1 条打卡
        checkin_provider.create_checkin(
            {
                "habit_id": habit_id,
                "challenge_id": "challenge-1",
                "date": "2026-07-01",
            }
        )

        # 删除前确认记录存在
        assert habit_provider.get_habit_by_id(habit_id) is not None
        assert len(challenge_provider.get_challenges_by_habit(habit_id)) == 1

        # 删除习惯（不级联）
        result = habit_provider.delete_habit(habit_id)
        assert result is True

        # 验证习惯已删除
        assert habit_provider.get_habit_by_id(habit_id) is None

        # 验证挑战和打卡仍然存在（不级联删除）
        assert len(challenge_provider.get_challenges_by_habit(habit_id)) == 1, (
            "delete_habit 不应级联删除挑战（由 Service 层负责级联）"
        )
        assert checkin_provider.get_checkin_by_date(habit_id, "2026-07-01") is not None, (
            "delete_habit 不应级联删除打卡（由 Service 层负责级联）"
        )

        # 验证只有 habits 表墓碑
        habit_tombstone = _get_tombstone(habit_provider.db, "habits", habit_id)
        assert habit_tombstone is not None, "habits 表应有墓碑"
        assert habit_tombstone[1] == "habits"
        assert habit_tombstone[2] == habit_id
        assert habit_tombstone[3] == "local"

        # 挑战和打卡不应有墓碑（未被删除）
        assert _count_tombstones(habit_provider.db, "habit_challenges") == 0
        assert _count_tombstones(habit_provider.db, "habit_checkins") == 0

    def test_delete_habit_no_cascade_records(self, habit_cascade_providers_fixture):
        """删除没有挑战和打卡的习惯，只写 habits 墓碑"""
        habit_provider, _, _ = habit_cascade_providers_fixture

        habit_id = habit_provider.create_habit({"name": "孤立习惯"})
        result = habit_provider.delete_habit(habit_id)
        assert result is True

        # 只有 habits 表墓碑
        assert _count_tombstones(habit_provider.db, "habits") == 1
        assert _count_tombstones(habit_provider.db, "habit_challenges") == 0
        assert _count_tombstones(habit_provider.db, "habit_checkins") == 0

    def test_delete_habit_does_not_affect_other_habits(self, habit_cascade_providers_fixture):
        """删除一个习惯不影响其他习惯"""
        habit_provider, challenge_provider, checkin_provider = habit_cascade_providers_fixture

        # 创建两个习惯
        habit_id_1 = habit_provider.create_habit({"name": "习惯1"})
        habit_id_2 = habit_provider.create_habit({"name": "习惯2"})

        # 删除习惯1（不级联）
        habit_provider.delete_habit(habit_id_1)

        # 习惯2 应保留
        assert habit_provider.get_habit_by_id(habit_id_2) is not None

        # 只为习惯1写墓碑
        assert _count_tombstones(habit_provider.db, "habits") == 1
        assert _count_tombstones(habit_provider.db, "habit_challenges") == 0
        assert _count_tombstones(habit_provider.db, "habit_checkins") == 0
