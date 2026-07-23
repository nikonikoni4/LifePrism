"""
L1 剩余删除统一测试（Slice 07）

验证已迁移 Provider 中的 5 处单表删除走 _generic_delete / _generic_batch_delete
（含写墓碑到 deletion_log）。

覆盖：
- plan_doc_provider.delete_plan_doc（TEXT 主键表，单条删除）
- custom_block_provider.delete_custom_block（AUTOINCREMENT 表，墓碑 record_id = hash_id）
- habit_checkin_provider.delete_checkin（复合条件 habit_id+date，先查 id 再删）
- behavior_analysis_provider.delete_behaviors_by_date_range（按日期范围批量删除）
- raw_behavior_analysis_provider.delete_raw_behaviors_by_date_range（按日期范围批量删除）

依据 issue: 07-l1-remaining-single-delete-unification
依据 ADR: docs/adr/2026-07-22-deletion-log-table.md
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 共用工具函数 ====================


def _create_deletion_log(db):
    """创建 deletion_log 表（按 DELETION_LOG_CONFIG schema）"""
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


# ==================== Slice A: plan_doc_provider 测试 ====================


@pytest.fixture
def plan_doc_provider(test_data_path):
    """创建 PlanDocProvider 实例并初始化 plan_doc + deletion_log 表

    注意：测试建表去掉外键约束（FOREIGN KEY (goal_id) REFERENCES goal(id)），
    因为 database_manager 未开启外键约束，且测试关注删除墓碑行为而非 FK 联动。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.plan_doc_provider import PlanDocProvider

    settings._initialize()

    provider = PlanDocProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_doc (
                id TEXT PRIMARY KEY,
                goal_id TEXT,
                content TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                order_index INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["plan_doc", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["plan_doc", "deletion_log"])


class TestPlanDocDeleteWritesTombstone:
    """验证 PlanDocProvider.delete_plan_doc 走 _generic_delete（含写墓碑）

    依据 issue: 07-l1-remaining-single-delete-unification
    plan_doc 是 SYNC_TABLES 中的 TEXT 主键表，墓碑 record_id 应为主键值（doc_id）。
    """

    def test_delete_plan_doc_writes_tombstone_with_pk_as_record_id(self, plan_doc_provider):
        """delete_plan_doc 写墓碑到 deletion_log，record_id = doc_id（TEXT 主键表）"""
        doc_id = "plandoc-test01"
        plan_doc_provider.create_plan_doc(
            {"id": doc_id, "goal_id": "goal-1", "status": "active", "order_index": 1}
        )

        # 删除前确认记录存在
        assert plan_doc_provider.get_plan_doc_by_id(doc_id) is not None, "删除前记录应存在"

        # 删除
        result = plan_doc_provider.delete_plan_doc(doc_id)
        assert result is True, "删除应返回 True"

        # 验证记录已从 plan_doc 表消失
        assert plan_doc_provider.get_plan_doc_by_id(doc_id) is None, "删除后记录应消失"

        # 验证墓碑已写入 deletion_log
        tombstone = _get_tombstone(plan_doc_provider.db, "plan_doc", doc_id)
        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[1] == "plan_doc", (
            f"墓碑 target_table 应为 'plan_doc'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == doc_id, (
            f"墓碑 record_id 应为 doc_id '{doc_id}'，实际: {tombstone[2]}"
        )
        assert tombstone[3] == "local", f"墓碑 source 应为 'local'，实际: {tombstone[3]}"

    def test_delete_plan_doc_nonexistent_returns_false(self, plan_doc_provider):
        """删除不存在的 plan_doc 返回 False

        注意：_generic_delete 对 TEXT 主键 SYNC 表的 nonexistent 记录会乐观写墓碑
        （Slice 01 既有行为，墓碑与 DELETE 同事务，DELETE 0 行后墓碑仍提交）。
        Slice 07 不改变该行为，此处只验证返回值。
        """
        result = plan_doc_provider.delete_plan_doc("plandoc-nonexist")
        assert result is False, "删除不存在的记录应返回 False"


# ==================== Slice B: custom_block_provider 测试 ====================


@pytest.fixture
def custom_block_provider(test_data_path):
    """创建 CustomBlockProvider 实例并初始化 timeline_custom_block + deletion_log 表

    timeline_custom_block 是 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中，前缀 tcb-），
    墓碑 record_id 应为 hash_id 而非自增 id。
    测试建表去掉 CHECK 约束以简化数据构造（测试关注删除墓碑行为）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.custom_block_provider import CustomBlockProvider

    settings._initialize()

    provider = CustomBlockProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS timeline_custom_block (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                content TEXT NOT NULL,
                todo_id TEXT,
                color TEXT NOT NULL,
                category_id TEXT,
                sub_category_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(start_time)
            )
            """
        )
        conn.commit()
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["timeline_custom_block", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["timeline_custom_block", "deletion_log"])


class TestCustomBlockDeleteWritesTombstone:
    """验证 CustomBlockProvider.delete_custom_block 走 _generic_delete（含写墓碑）

    依据 issue: 07-l1-remaining-single-delete-unification
    timeline_custom_block 是 SYNC_TABLES 中的 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中），
    墓碑 record_id 应为 hash_id（由 _generic_delete 自动通过 _resolve_tombstone_record_id 解析）。
    """

    def test_delete_custom_block_writes_tombstone_with_hash_id_as_record_id(
        self, custom_block_provider
    ):
        """delete_custom_block 写墓碑，record_id = hash_id（AUTOINCREMENT 表）"""
        # 创建记录（_generic_insert 自动生成 hash_id）
        block = custom_block_provider.create_custom_block(
            {
                "start_time": "2026-07-23T10:00:00+00:00",
                "end_time": "2026-07-23T11:00:00+00:00",
                "duration": 60,
                "content": "测试时间块",
                "color": "#ff0000",
            }
        )
        block_id = block["id"]

        # 查询 hash_id（墓碑 record_id 应为 hash_id 而非自增 id）
        with custom_block_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT hash_id FROM timeline_custom_block WHERE id = ?", (block_id,))
            row = cursor.fetchone()
        assert row is not None, "记录应已插入"
        hash_id = row[0]
        assert hash_id is not None, "hash_id 应被 _generic_insert 自动生成"
        assert hash_id.startswith("tcb-"), f"hash_id 应以 'tcb-' 开头，实际: {hash_id}"

        # 删除
        result = custom_block_provider.delete_custom_block(block_id)
        assert result is True, "删除应返回 True"

        # 验证记录已从 timeline_custom_block 表消失
        assert custom_block_provider.get_custom_block_by_id(block_id) is None, "删除后记录应消失"

        # 验证墓碑已写入 deletion_log，record_id = hash_id（不是自增 id）
        tombstone = _get_tombstone(custom_block_provider.db, "timeline_custom_block", hash_id)
        assert tombstone is not None, "应写入墓碑，record_id 为 hash_id"
        assert tombstone[1] == "timeline_custom_block", (
            f"墓碑 target_table 应为 'timeline_custom_block'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == hash_id, (
            f"墓碑 record_id 应为 hash_id '{hash_id}'，实际: {tombstone[2]}"
        )
        assert tombstone[3] == "local", f"墓碑 source 应为 'local'，实际: {tombstone[3]}"

        # 验证：不应有以自增 id 为 record_id 的墓碑
        tombstone_by_pk = _get_tombstone(
            custom_block_provider.db, "timeline_custom_block", str(block_id)
        )
        assert tombstone_by_pk is None, "AUTOINCREMENT 表墓碑 record_id 不应为自增 id"

    def test_delete_custom_block_nonexistent_returns_false(self, custom_block_provider):
        """删除不存在的 custom_block 返回 False

        注意：AUTOINCREMENT 表的 _generic_delete 会先查 hash_id，记录不存在时返回 None，
        _generic_delete 据此跳过墓碑和删除，直接返回 False（不写墓碑）。
        """
        result = custom_block_provider.delete_custom_block(99999)
        assert result is False, "删除不存在的记录应返回 False"

        # AUTOINCREMENT 表记录不存在时不写墓碑（_resolve_tombstone_record_id 返回 None）
        count = _count_tombstones(custom_block_provider.db, "timeline_custom_block")
        assert count == 0, "AUTOINCREMENT 表删除不存在的记录不应写墓碑"


# ==================== Slice C: habit_checkin_provider 测试 ====================


@pytest.fixture
def habit_checkin_provider(test_data_path):
    """创建 HabitCheckinProvider 实例并初始化 habit_checkins + deletion_log 表

    habit_checkins 是 TEXT 主键表（id 格式 checkin-xxx），UNIQUE(habit_id, date)。
    delete_checkin 按 habit_id+date 复合条件删除，需先查 id 再走 _generic_delete。
    测试建表去掉外键约束以简化数据构造。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.habit_providers import HabitCheckinProvider

    settings._initialize()

    provider = HabitCheckinProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
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
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["habit_checkins", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["habit_checkins", "deletion_log"])


class TestHabitCheckinDeleteWritesTombstone:
    """验证 HabitCheckinProvider.delete_checkin 走 _generic_delete（含写墓碑）

    依据 issue: 07-l1-remaining-single-delete-unification
    habit_checkins 是 SYNC_TABLES 中的 TEXT 主键表，按 habit_id+date 复合条件删除。
    改造方式：先用 get_checkin_by_date 查 id，再走 _generic_delete（墓碑 record_id = checkin_id）。
    """

    def test_delete_checkin_writes_tombstone_with_pk_as_record_id(self, habit_checkin_provider):
        """delete_checkin 写墓碑，record_id = checkin_id（TEXT 主键表）"""
        habit_id = "habit-test01"
        checkin_date = "2026-07-23"
        checkin_id = habit_checkin_provider.create_checkin(
            {
                "habit_id": habit_id,
                "challenge_id": "challenge-test01",
                "date": checkin_date,
            }
        )
        assert checkin_id is not None, "创建打卡记录应成功"

        # 删除前确认记录存在
        assert habit_checkin_provider.get_checkin_by_date(habit_id, checkin_date) is not None

        # 删除
        result = habit_checkin_provider.delete_checkin(habit_id, checkin_date)
        assert result is True, "删除应返回 True"

        # 验证记录已从 habit_checkins 表消失
        assert habit_checkin_provider.get_checkin_by_date(habit_id, checkin_date) is None

        # 验证墓碑已写入 deletion_log，record_id = checkin_id
        tombstone = _get_tombstone(habit_checkin_provider.db, "habit_checkins", checkin_id)
        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[1] == "habit_checkins", (
            f"墓碑 target_table 应为 'habit_checkins'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == checkin_id, (
            f"墓碑 record_id 应为 checkin_id '{checkin_id}'，实际: {tombstone[2]}"
        )
        assert tombstone[3] == "local", f"墓碑 source 应为 'local'，实际: {tombstone[3]}"

    def test_delete_checkin_nonexistent_returns_false(self, habit_checkin_provider):
        """删除不存在的打卡记录返回 False（先查 id，不存在则不调用 _generic_delete）"""
        result = habit_checkin_provider.delete_checkin("habit-nonexist", "2026-07-23")
        assert result is False, "删除不存在的记录应返回 False"

        # 先查 id 模式下，记录不存在不会调用 _generic_delete，因此不写墓碑
        count = _count_tombstones(habit_checkin_provider.db, "habit_checkins")
        assert count == 0, "先查 id 模式下，删除不存在的记录不应写墓碑"


# ==================== Slice D: behavior_analysis_provider 测试 ====================


@pytest.fixture
def behavior_analysis_provider(test_data_path):
    """创建 BehaviorAnalysisProvider 实例并初始化 behavior_analysis + deletion_log 表

    behavior_analysis 是 TEXT 主键表（主键 start_time），在 SYNC_TABLES 中但不在
    HASH_ID_PREFIXES 中。delete_behaviors_by_date_range 按日期范围批量删除，
    改造方式：先查 start_time 列表，再走 _generic_batch_delete。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.behavior_analysis_provider import (
        BehaviorAnalysisProvider,
    )

    settings._initialize()

    provider = BehaviorAnalysisProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS behavior_analysis (
                start_time TEXT PRIMARY KEY NOT NULL,
                end_time TEXT NOT NULL,
                behavior TEXT NOT NULL,
                behavior_summary TEXT,
                title TEXT,
                screen_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["behavior_analysis", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["behavior_analysis", "deletion_log"])


class TestBehaviorAnalysisDeleteWritesTombstone:
    """验证 BehaviorAnalysisProvider.delete_behaviors_by_date_range 走 _generic_batch_delete

    依据 issue: 07-l1-remaining-single-delete-unification
    behavior_analysis 是 SYNC_TABLES 中的 TEXT 主键表（主键 start_time，不在 HASH_ID_PREFIXES）。
    按日期范围批量删除时，先查 start_time 列表，再走 _generic_batch_delete（墓碑 record_id = start_time）。
    """

    def test_delete_by_date_range_writes_tombstone_for_each_record(
        self, behavior_analysis_provider
    ):
        """delete_behaviors_by_date_range 为每条删除的记录写墓碑（record_id = start_time）"""
        # 插入 2 条记录（start_time 在 2026-07-23 的 UTC 范围内）
        # Etc/GMT-8 = UTC+8，2026-07-23 本地 → UTC 范围约 [07-22T16:00, 07-23T15:59]
        records = [
            ("2026-07-23T01:00:00+00:00", "2026-07-23T02:00:00+00:00"),
            ("2026-07-23T10:00:00+00:00", "2026-07-23T11:00:00+00:00"),
        ]
        start_times = []
        for st, et in records:
            start_times.append(st)
            behavior_analysis_provider.create_behavior(
                {
                    "start_time": st,
                    "end_time": et,
                    "behavior": "working",
                    "screen_count": 1,
                }
            )

        # 删除（按本地日期范围，覆盖 UTC 范围内的记录）
        deleted = behavior_analysis_provider.delete_behaviors_by_date_range(
            "2026-07-23", "2026-07-23"
        )
        assert deleted == 2, f"应删除 2 条记录，实际: {deleted}"

        # 验证记录已从 behavior_analysis 表消失
        with behavior_analysis_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM behavior_analysis WHERE start_time IN (?, ?)",
                start_times,
            )
            remaining = cursor.fetchone()[0]
        assert remaining == 0, "所有记录应已删除"

        # 验证 2 条墓碑已写入 deletion_log
        count = _count_tombstones(behavior_analysis_provider.db, "behavior_analysis")
        assert count == 2, f"应写入 2 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = start_time
        for st in start_times:
            tombstone = _get_tombstone(behavior_analysis_provider.db, "behavior_analysis", st)
            assert tombstone is not None, f"start_time '{st}' 应有对应墓碑"
            assert tombstone[1] == "behavior_analysis"
            assert tombstone[2] == st
            assert tombstone[3] == "local"

    def test_delete_by_date_range_no_records_returns_zero(self, behavior_analysis_provider):
        """日期范围内无记录时返回 0，不写墓碑"""
        deleted = behavior_analysis_provider.delete_behaviors_by_date_range(
            "2026-07-23", "2026-07-23"
        )
        assert deleted == 0, "无记录时应返回 0"

        count = _count_tombstones(behavior_analysis_provider.db, "behavior_analysis")
        assert count == 0, "无记录时不应写墓碑"


# ==================== Slice E: raw_behavior_analysis_provider 测试 ====================


@pytest.fixture
def raw_behavior_analysis_provider(test_data_path):
    """创建 RawBehaviorAnalysisProvider 实例并初始化 raw_behavior_analysis + deletion_log 表

    raw_behavior_analysis 是 TEXT 主键表（主键 start_time），在 SYNC_TABLES 中但不在
    HASH_ID_PREFIXES 中。delete_raw_behaviors_by_date_range 按日期范围批量删除，
    改造方式：先查 start_time 列表，再走 _generic_batch_delete。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.raw_behavior_analysis_provider import (
        RawBehaviorAnalysisProvider,
    )

    settings._initialize()

    provider = RawBehaviorAnalysisProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_behavior_analysis (
                start_time TEXT PRIMARY KEY NOT NULL,
                end_time TEXT NOT NULL,
                behavior TEXT NOT NULL,
                screen_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
            )
            """
        )
        conn.commit()
    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["raw_behavior_analysis", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["raw_behavior_analysis", "deletion_log"])


class TestRawBehaviorAnalysisDeleteWritesTombstone:
    """验证 RawBehaviorAnalysisProvider.delete_raw_behaviors_by_date_range 走 _generic_batch_delete

    依据 issue: 07-l1-remaining-single-delete-unification
    raw_behavior_analysis 是 SYNC_TABLES 中的 TEXT 主键表（主键 start_time，不在 HASH_ID_PREFIXES）。
    按日期范围批量删除时，先查 start_time 列表，再走 _generic_batch_delete（墓碑 record_id = start_time）。
    """

    def test_delete_by_date_range_writes_tombstone_for_each_record(
        self, raw_behavior_analysis_provider
    ):
        """delete_raw_behaviors_by_date_range 为每条删除的记录写墓碑（record_id = start_time）"""
        # 插入 2 条记录（start_time 在 2026-07-23 的 UTC 范围内）
        # Etc/GMT-8 = UTC+8，2026-07-23 本地 → UTC 范围约 [07-22T16:00, 07-23T15:59]
        records = [
            ("2026-07-23T01:00:00+00:00", "2026-07-23T02:00:00+00:00"),
            ("2026-07-23T10:00:00+00:00", "2026-07-23T11:00:00+00:00"),
        ]
        start_times = []
        for st, et in records:
            start_times.append(st)
            raw_behavior_analysis_provider.create_raw_behavior(
                {
                    "start_time": st,
                    "end_time": et,
                    "behavior": "working",
                    "screen_count": 1,
                }
            )

        # 删除（按本地日期范围，覆盖 UTC 范围内的记录）
        deleted = raw_behavior_analysis_provider.delete_raw_behaviors_by_date_range(
            "2026-07-23", "2026-07-23"
        )
        assert deleted == 2, f"应删除 2 条记录，实际: {deleted}"

        # 验证记录已从 raw_behavior_analysis 表消失
        with raw_behavior_analysis_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM raw_behavior_analysis WHERE start_time IN (?, ?)",
                start_times,
            )
            remaining = cursor.fetchone()[0]
        assert remaining == 0, "所有记录应已删除"

        # 验证 2 条墓碑已写入 deletion_log
        count = _count_tombstones(raw_behavior_analysis_provider.db, "raw_behavior_analysis")
        assert count == 2, f"应写入 2 条墓碑，实际: {count}"

        # 验证每条墓碑的 record_id = start_time
        for st in start_times:
            tombstone = _get_tombstone(
                raw_behavior_analysis_provider.db, "raw_behavior_analysis", st
            )
            assert tombstone is not None, f"start_time '{st}' 应有对应墓碑"
            assert tombstone[1] == "raw_behavior_analysis"
            assert tombstone[2] == st
            assert tombstone[3] == "local"

    def test_delete_by_date_range_no_records_returns_zero(self, raw_behavior_analysis_provider):
        """日期范围内无记录时返回 0，不写墓碑"""
        deleted = raw_behavior_analysis_provider.delete_raw_behaviors_by_date_range(
            "2026-07-23", "2026-07-23"
        )
        assert deleted == 0, "无记录时应返回 0"

        count = _count_tombstones(raw_behavior_analysis_provider.db, "raw_behavior_analysis")
        assert count == 0, "无记录时不应写墓碑"
