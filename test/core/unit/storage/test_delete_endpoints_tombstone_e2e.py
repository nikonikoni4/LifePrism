"""
端到端删除墓碑测试 - 覆盖 L1-L4 未测试的删除端点

验证所有未在 L1-L4 测试中覆盖的删除端点能正确写入墓碑到 deletion_log 表。
共覆盖 19 个删除方法，分为以下几类：

TEXT 主键表（墓碑 record_id = 主键值）：
- MoodEntryProvider.delete_mood_entry（mood_entries）
- MoodTypeProvider.delete_mood_type（mood_types）
- DiaryProvider.delete_diary（diary, PK=date）
- TodoProvider.delete_todo（todo_list）
- GoalProvider.delete_goal（goal, 含清除 todo_list.link_to_goal_id 副作用）
- JournalProvider.delete_journal（goal_journal）
- CategoryProvider.delete_category（category）
- SubCategoryProvider.delete_sub_category（sub_category）
- ValueProvider.delete_value（user_values）
- CommitmentProvider.delete_commitment（commitments）
- CommitmentProvider.delete_by_value_id（commitments, 批量）
- MultiPurposeMapCacheProvider.delete_multi_purpose_map_cache（multi_purpose_map_cache）
- SinglePurposeMapCacheProvider.delete_single_purpose_map_cache（single_purpose_map_cache）
- TokensUsageProvider.delete_tokens_usage（tokens_usage_log, PK=session_id）

AUTOINCREMENT 表（墓碑 record_id = hash_id）：
- MoodImpactProvider.delete_mood_impact（mood_impacts, 前缀 mi-）
- BeingProvider.delete（time_paradoxes, 前缀 tp-, PK=hash_id）
- BeingProvider.delete_by_user_mode_version（time_paradoxes, 复合键→hash_id）
- ComputerUsageProvider.delete_computer_usage（user_app_behavior_log, 前缀 awbl-）

特殊：不写墓碑：
- CommitmentProvider.null_value_id（commitments, UPDATE 操作, 不删除不写墓碑）

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


def _record_exists(db, table_name, record_id, pk_field="id"):
    """检查记录是否存在"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE {pk_field} = ?",
            (record_id,),
        )
        return cursor.fetchone()[0] > 0


def _get_hash_id(db, table_name, record_id, pk_field="id"):
    """查询 AUTOINCREMENT 表的 hash_id"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT hash_id FROM {table_name} WHERE {pk_field} = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None


# ==================== Group 1: Mood Providers ====================


@pytest.fixture
def mood_providers_fixture(test_data_path):
    """创建 MoodEntryProvider/MoodTypeProvider/MoodImpactProvider 实例并初始化表

    mood_entries / mood_types 为 TEXT 主键表（在 SYNC_TABLES 中，不在 HASH_ID_PREFIXES）。
    mood_impacts 为 AUTOINCREMENT 表（在 SYNC_TABLES 中，在 HASH_ID_PREFIXES 前缀 mi-）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.mood_providers import (
        MoodEntryProvider,
        MoodImpactProvider,
        MoodTypeProvider,
    )

    settings._initialize()

    entry_provider = MoodEntryProvider()
    type_provider = MoodTypeProvider()
    impact_provider = MoodImpactProvider()

    with entry_provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_entries (
                id TEXT PRIMARY KEY NOT NULL,
                mood_type_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                content TEXT,
                factors TEXT,
                event_time TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_types (
                id TEXT PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                icon TEXT NOT NULL,
                color TEXT NOT NULL,
                score INTEGER NOT NULL,
                is_dark INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_impacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(name)
            )
            """
        )
        conn.commit()

    _create_deletion_log(entry_provider.db)
    _clear_tables(
        entry_provider.db,
        ["mood_entries", "mood_types", "mood_impacts", "deletion_log"],
    )

    yield (entry_provider, type_provider, impact_provider)

    _clear_tables(
        entry_provider.db,
        ["mood_entries", "mood_types", "mood_impacts", "deletion_log"],
    )


class TestMoodEntryDeleteWritesTombstone:
    """验证 MoodEntryProvider.delete_mood_entry 写墓碑（TEXT 主键表）"""

    def test_delete_mood_entry_writes_tombstone(self, mood_providers_fixture):
        entry_provider, _, _ = mood_providers_fixture
        entry_id = entry_provider.create_mood_entry(
            {"mood_type_id": "mt-test01", "score": 80}
        )

        assert entry_provider.get_mood_entry_by_id(entry_id) is not None

        result = entry_provider.delete_mood_entry(entry_id)
        assert result is True

        assert entry_provider.get_mood_entry_by_id(entry_id) is None

        tombstone = _get_tombstone(entry_provider.db, "mood_entries", entry_id)
        assert tombstone is not None
        assert tombstone[1] == "mood_entries"
        assert tombstone[2] == entry_id
        assert tombstone[3] == "local"


class TestMoodTypeDeleteWritesTombstone:
    """验证 MoodTypeProvider.delete_mood_type 写墓碑（TEXT 主键表）"""

    def test_delete_mood_type_writes_tombstone(self, mood_providers_fixture):
        _, type_provider, _ = mood_providers_fixture
        type_id = type_provider.create_mood_type(
            {
                "name": "喜悦",
                "icon": "Sun",
                "color": "#fed7aa",
                "score": 90,
                "is_dark": 0,
                "sort_order": 1,
            }
        )

        assert type_provider.get_mood_type_by_id(type_id) is not None

        result = type_provider.delete_mood_type(type_id)
        assert result is True

        assert type_provider.get_mood_type_by_id(type_id) is None

        tombstone = _get_tombstone(type_provider.db, "mood_types", type_id)
        assert tombstone is not None
        assert tombstone[1] == "mood_types"
        assert tombstone[2] == type_id
        assert tombstone[3] == "local"


class TestMoodImpactDeleteWritesTombstone:
    """验证 MoodImpactProvider.delete_mood_impact 写墓碑（AUTOINCREMENT 表, record_id=hash_id）"""

    def test_delete_mood_impact_writes_tombstone_with_hash_id(self, mood_providers_fixture):
        _, _, impact_provider = mood_providers_fixture
        impact_id = impact_provider.create_mood_impact({"name": "健康", "sort_order": 1})

        hash_id = _get_hash_id(impact_provider.db, "mood_impacts", impact_id)
        assert hash_id is not None
        assert hash_id.startswith("mi-")

        result = impact_provider.delete_mood_impact(impact_id)
        assert result is True

        assert not _record_exists(impact_provider.db, "mood_impacts", impact_id)

        tombstone = _get_tombstone(impact_provider.db, "mood_impacts", hash_id)
        assert tombstone is not None
        assert tombstone[1] == "mood_impacts"
        assert tombstone[2] == hash_id
        assert tombstone[3] == "local"

        # 不应有以自增 id 为 record_id 的墓碑
        tombstone_by_pk = _get_tombstone(impact_provider.db, "mood_impacts", str(impact_id))
        assert tombstone_by_pk is None


# ==================== Group 2: Todo/Goal/Journal/Diary ====================


@pytest.fixture
def todo_provider_fixture(test_data_path):
    """创建 TodoProvider 实例并初始化 todo_list + deletion_log 表"""
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
                order_index INTEGER NOT NULL DEFAULT 0,
                content TEXT NOT NULL,
                color TEXT DEFAULT '#FFFFFF',
                state TEXT DEFAULT 'pool',
                link_to_goal_id TEXT,
                date TEXT,
                parent_id TEXT DEFAULT NULL,
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


class TestTodoDeleteWritesTombstone:
    """验证 TodoProvider.delete_todo 写墓碑（TEXT 主键表）"""

    def test_delete_todo_writes_tombstone(self, todo_provider_fixture):
        provider = todo_provider_fixture
        todo_id = provider.create_todo(
            {"content": "测试任务", "order_index": 0}
        )

        assert provider.get_todo_by_id(todo_id) is not None

        result = provider.delete_todo(todo_id)
        assert result is True

        assert provider.get_todo_by_id(todo_id) is None

        tombstone = _get_tombstone(provider.db, "todo_list", todo_id)
        assert tombstone is not None
        assert tombstone[1] == "todo_list"
        assert tombstone[2] == todo_id
        assert tombstone[3] == "local"


@pytest.fixture
def goal_provider_fixture(test_data_path):
    """创建 GoalProvider 实例并初始化 goal + todo_list + deletion_log 表

    todo_list 表用于验证 delete_goal 的副作用（清除 link_to_goal_id）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.goal_providers import GoalProvider

    settings._initialize()
    provider = GoalProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goal (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                content TEXT DEFAULT '',
                color TEXT DEFAULT '#5B8FF9',
                status TEXT DEFAULT 'active',
                order_index INTEGER DEFAULT 0,
                time_unit TEXT DEFAULT 'HRS',
                time_invested INTEGER DEFAULT 0,
                track_time_automatically INTEGER DEFAULT 1,
                milestones TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS todo_list (
                id TEXT PRIMARY KEY,
                order_index INTEGER NOT NULL DEFAULT 0,
                content TEXT NOT NULL,
                link_to_goal_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["goal", "todo_list", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["goal", "todo_list", "deletion_log"])


class TestGoalDeleteWritesTombstone:
    """验证 GoalProvider.delete_goal 写墓碑（TEXT 主键表, 含清除 todo_list 关联副作用）"""

    def test_delete_goal_writes_tombstone_and_clears_todo_links(self, goal_provider_fixture):
        provider = goal_provider_fixture
        goal_id = provider.create_goal({"name": "测试目标"})

        # 插入关联的 todo_list 记录
        with provider.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO todo_list (id, order_index, content, link_to_goal_id) "
                "VALUES (?, ?, ?, ?)",
                ("t-test01", 0, "关联任务", goal_id),
            )
            conn.commit()

        # 验证关联存在
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT link_to_goal_id FROM todo_list WHERE id = ?", ("t-test01",)
            )
            assert cursor.fetchone()[0] == goal_id

        result = provider.delete_goal(goal_id)
        assert result is True

        assert provider.get_goal_by_id(goal_id) is None

        # 验证墓碑
        tombstone = _get_tombstone(provider.db, "goal", goal_id)
        assert tombstone is not None
        assert tombstone[1] == "goal"
        assert tombstone[2] == goal_id
        assert tombstone[3] == "local"

        # 验证副作用：link_to_goal_id 已被清除为 NULL
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT link_to_goal_id FROM todo_list WHERE id = ?", ("t-test01",)
            )
            assert cursor.fetchone()[0] is None


@pytest.fixture
def journal_provider_fixture(test_data_path):
    """创建 JournalProvider 实例并初始化 goal_journal + deletion_log 表"""
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.journal_provider import JournalProvider

    settings._initialize()
    provider = JournalProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_journal (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["goal_journal", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["goal_journal", "deletion_log"])


class TestJournalDeleteWritesTombstone:
    """验证 JournalProvider.delete_journal 写墓碑（TEXT 主键表）"""

    def test_delete_journal_writes_tombstone(self, journal_provider_fixture):
        provider = journal_provider_fixture
        journal_id = provider.create_journal(
            {"goal_id": "goal-test01", "date": "2026-07-23", "content": "测试日志"}
        )

        assert provider.get_journal_by_id(journal_id) is not None

        result = provider.delete_journal(journal_id)
        assert result is True

        assert provider.get_journal_by_id(journal_id) is None

        tombstone = _get_tombstone(provider.db, "goal_journal", journal_id)
        assert tombstone is not None
        assert tombstone[1] == "goal_journal"
        assert tombstone[2] == journal_id
        assert tombstone[3] == "local"


@pytest.fixture
def diary_provider_fixture(test_data_path):
    """创建 DiaryProvider 实例并初始化 diary + deletion_log 表

    diary 表使用 date 作为主键。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.diary_provider import DiaryProvider

    settings._initialize()
    provider = DiaryProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS diary (
                date TEXT PRIMARY KEY NOT NULL,
                mood TEXT,
                importance TEXT,
                custom_tags TEXT DEFAULT '[]',
                word_count INTEGER DEFAULT 0,
                ai_summary TEXT,
                diary_source_hash TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["diary", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["diary", "deletion_log"])


class TestDiaryDeleteWritesTombstone:
    """验证 DiaryProvider.delete_diary 写墓碑（TEXT 主键表, PK=date）"""

    def test_delete_diary_writes_tombstone(self, diary_provider_fixture):
        provider = diary_provider_fixture
        date = "2026-07-23"
        provider.create_diary(date, {"mood": "happy", "word_count": 100})

        assert provider.get_diary_by_id(date) is not None

        result = provider.delete_diary(date)
        assert result is True

        assert provider.get_diary_by_id(date) is None

        tombstone = _get_tombstone(provider.db, "diary", date)
        assert tombstone is not None
        assert tombstone[1] == "diary"
        assert tombstone[2] == date
        assert tombstone[3] == "local"


# ==================== Group 3: Category Providers ====================


@pytest.fixture
def category_providers_fixture(test_data_path):
    """创建 CategoryProvider/SubCategoryProvider 实例并初始化表

    category / sub_category 均为 TEXT 主键表（在 SYNC_TABLES 中）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.category_provider import (
        CategoryProvider,
        SubCategoryProvider,
    )

    settings._initialize()
    cat_provider = CategoryProvider()
    sub_provider = SubCategoryProvider()

    with cat_provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS category (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
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
                category_id TEXT NOT NULL,
                name TEXT NOT NULL,
                state INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(cat_provider.db)
    _clear_tables(
        cat_provider.db,
        ["category", "sub_category", "deletion_log"],
    )

    yield (cat_provider, sub_provider)

    _clear_tables(
        cat_provider.db,
        ["category", "sub_category", "deletion_log"],
    )


class TestCategoryDeleteWritesTombstone:
    """验证 CategoryProvider.delete_category 写墓碑（TEXT 主键表）"""

    def test_delete_category_writes_tombstone(self, category_providers_fixture):
        cat_provider, _ = category_providers_fixture
        cat_provider.create_category(
            {"id": "cat-test01", "name": "工作", "color": "#5B8FF9"}
        )

        assert cat_provider.get_category_by_id("cat-test01") is not None

        result = cat_provider.delete_category("cat-test01")
        assert result is True

        assert cat_provider.get_category_by_id("cat-test01") is None

        tombstone = _get_tombstone(cat_provider.db, "category", "cat-test01")
        assert tombstone is not None
        assert tombstone[1] == "category"
        assert tombstone[2] == "cat-test01"
        assert tombstone[3] == "local"


class TestSubCategoryDeleteWritesTombstone:
    """验证 SubCategoryProvider.delete_sub_category 写墓碑（TEXT 主键表）"""

    def test_delete_sub_category_writes_tombstone(self, category_providers_fixture):
        _, sub_provider = category_providers_fixture
        sub_provider.create_sub_category(
            {"id": "sub-test01", "category_id": "cat-test01", "name": "编程"}
        )

        assert sub_provider.get_sub_category_by_id("sub-test01") is not None

        result = sub_provider.delete_sub_category("sub-test01")
        assert result is True

        assert sub_provider.get_sub_category_by_id("sub-test01") is None

        tombstone = _get_tombstone(sub_provider.db, "sub_category", "sub-test01")
        assert tombstone is not None
        assert tombstone[1] == "sub_category"
        assert tombstone[2] == "sub-test01"
        assert tombstone[3] == "local"


# ==================== Group 4: Value/Commitment Providers ====================


@pytest.fixture
def value_commitment_providers_fixture(test_data_path):
    """创建 ValueProvider/CommitmentProvider 实例并初始化表

    user_values / commitments 均为 TEXT 主键表（在 SYNC_TABLES 中）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.commitment_provider import CommitmentProvider
    from lifeprism.repository.providers.value_provider import ValueProvider

    settings._initialize()
    value_provider = ValueProvider()
    commitment_provider = CommitmentProvider()

    with value_provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_values (
                id TEXT PRIMARY KEY NOT NULL,
                keywords TEXT NOT NULL UNIQUE,
                content_positive TEXT,
                content_negative TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS commitments (
                id TEXT PRIMARY KEY NOT NULL,
                content TEXT NOT NULL,
                value_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(value_provider.db)
    _clear_tables(
        value_provider.db,
        ["user_values", "commitments", "deletion_log"],
    )

    yield (value_provider, commitment_provider)

    _clear_tables(
        value_provider.db,
        ["user_values", "commitments", "deletion_log"],
    )


class TestValueDeleteWritesTombstone:
    """验证 ValueProvider.delete_value 写墓碑（TEXT 主键表）"""

    def test_delete_value_writes_tombstone(self, value_commitment_providers_fixture):
        value_provider, _ = value_commitment_providers_fixture
        value_id = value_provider.create_value({"keywords": "健康;活力"})

        assert value_provider.get_value_by_id(value_id) is not None

        result = value_provider.delete_value(value_id)
        assert result is True

        assert value_provider.get_value_by_id(value_id) is None

        tombstone = _get_tombstone(value_provider.db, "user_values", value_id)
        assert tombstone is not None
        assert tombstone[1] == "user_values"
        assert tombstone[2] == value_id
        assert tombstone[3] == "local"


class TestCommitmentDeleteWritesTombstone:
    """验证 CommitmentProvider.delete_commitment 写墓碑（TEXT 主键表）"""

    def test_delete_commitment_writes_tombstone(self, value_commitment_providers_fixture):
        _, commitment_provider = value_commitment_providers_fixture
        commitment_id = commitment_provider.create_commitment(
            {"content": "每天运动30分钟", "value_id": "val-test01"}
        )

        assert commitment_provider.get_commitment_by_id(commitment_id) is not None

        result = commitment_provider.delete_commitment(commitment_id)
        assert result is True

        assert commitment_provider.get_commitment_by_id(commitment_id) is None

        tombstone = _get_tombstone(commitment_provider.db, "commitments", commitment_id)
        assert tombstone is not None
        assert tombstone[1] == "commitments"
        assert tombstone[2] == commitment_id
        assert tombstone[3] == "local"


class TestCommitmentDeleteByValueIdWritesTombstones:
    """验证 CommitmentProvider.delete_by_value_id 批量写墓碑（TEXT 主键表, 批量删除）"""

    def test_delete_by_value_id_writes_tombstones_for_each(self, value_commitment_providers_fixture):
        _, commitment_provider = value_commitment_providers_fixture
        value_id = "val-cascade01"

        cmt1 = commitment_provider.create_commitment(
            {"content": "承诺1", "value_id": value_id}
        )
        cmt2 = commitment_provider.create_commitment(
            {"content": "承诺2", "value_id": value_id}
        )
        cmt3 = commitment_provider.create_commitment(
            {"content": "承诺3", "value_id": value_id}
        )

        deleted = commitment_provider.delete_by_value_id(value_id)
        assert deleted == 3

        assert not _record_exists(commitment_provider.db, "commitments", cmt1)
        assert not _record_exists(commitment_provider.db, "commitments", cmt2)
        assert not _record_exists(commitment_provider.db, "commitments", cmt3)

        count = _count_tombstones(commitment_provider.db, "commitments")
        assert count == 3

        for cmt_id in [cmt1, cmt2, cmt3]:
            tombstone = _get_tombstone(commitment_provider.db, "commitments", cmt_id)
            assert tombstone is not None
            assert tombstone[1] == "commitments"
            assert tombstone[2] == cmt_id
            assert tombstone[3] == "local"

    def test_delete_by_value_id_no_records_returns_zero(self, value_commitment_providers_fixture):
        _, commitment_provider = value_commitment_providers_fixture
        deleted = commitment_provider.delete_by_value_id("val-nonexist")
        assert deleted == 0

        count = _count_tombstones(commitment_provider.db, "commitments")
        assert count == 0


class TestCommitmentNullValueIdNoTombstone:
    """验证 CommitmentProvider.null_value_id 不写墓碑（UPDATE 操作, 不删除记录）

    null_value_id 只是将 commitments.value_id 置为 NULL，不删除记录，不写墓碑。
    """

    def test_null_value_id_does_not_write_tombstone(self, value_commitment_providers_fixture):
        _, commitment_provider = value_commitment_providers_fixture
        value_id = "val-nulltest01"

        cmt_id = commitment_provider.create_commitment(
            {"content": "承诺", "value_id": value_id}
        )

        updated = commitment_provider.null_value_id(value_id)
        assert updated == 1

        # 记录仍然存在（未被删除）
        assert commitment_provider.get_commitment_by_id(cmt_id) is not None

        # value_id 已被置空
        record = commitment_provider.get_commitment_by_id(cmt_id)
        assert record["value_id"] is None

        # 不应有墓碑
        count = _count_tombstones(commitment_provider.db, "commitments")
        assert count == 0


# ==================== Group 5: Map Cache Providers ====================


@pytest.fixture
def map_cache_providers_fixture(test_data_path):
    """创建 MultiPurposeMapCacheProvider/SinglePurposeMapCacheProvider 实例并初始化表

    multi_purpose_map_cache / single_purpose_map_cache 均为 TEXT 主键表（在 SYNC_TABLES 中）。
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
                app TEXT NOT NULL,
                title TEXT NOT NULL,
                category_id TEXT,
                sub_category_id TEXT,
                state INTEGER DEFAULT 1,
                link_to_goal_id TEXT DEFAULT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS single_purpose_map_cache (
                id TEXT PRIMARY KEY,
                app TEXT NOT NULL,
                title TEXT NOT NULL,
                category_id TEXT,
                sub_category_id TEXT,
                state INTEGER DEFAULT 1,
                link_to_goal_id TEXT DEFAULT NULL,
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

    yield (multi_provider, single_provider)

    _clear_tables(
        multi_provider.db,
        ["multi_purpose_map_cache", "single_purpose_map_cache", "deletion_log"],
    )


class TestMultiPurposeMapCacheDeleteWritesTombstone:
    """验证 MultiPurposeMapCacheProvider.delete_multi_purpose_map_cache 写墓碑（TEXT 主键表）"""

    def test_delete_multi_map_cache_writes_tombstone(self, map_cache_providers_fixture):
        multi_provider, _ = map_cache_providers_fixture
        multi_provider.create_multi_purpose_map_cache(
            {"id": "m-test01", "app": "chrome.exe", "title": "Google Chrome"}
        )

        assert multi_provider.get_multi_purpose_map_cache_by_id("m-test01") is not None

        result = multi_provider.delete_multi_purpose_map_cache("m-test01")
        assert result is True

        assert multi_provider.get_multi_purpose_map_cache_by_id("m-test01") is None

        tombstone = _get_tombstone(multi_provider.db, "multi_purpose_map_cache", "m-test01")
        assert tombstone is not None
        assert tombstone[1] == "multi_purpose_map_cache"
        assert tombstone[2] == "m-test01"
        assert tombstone[3] == "local"


class TestSinglePurposeMapCacheDeleteWritesTombstone:
    """验证 SinglePurposeMapCacheProvider.delete_single_purpose_map_cache 写墓碑（TEXT 主键表）"""

    def test_delete_single_map_cache_writes_tombstone(self, map_cache_providers_fixture):
        _, single_provider = map_cache_providers_fixture
        single_provider.create_single_purpose_map_cache(
            {"id": "s-test01", "app": "notepad.exe", "title": "Notepad"}
        )

        assert single_provider.get_single_purpose_map_cache_by_id("s-test01") is not None

        result = single_provider.delete_single_purpose_map_cache("s-test01")
        assert result is True

        assert single_provider.get_single_purpose_map_cache_by_id("s-test01") is None

        tombstone = _get_tombstone(single_provider.db, "single_purpose_map_cache", "s-test01")
        assert tombstone is not None
        assert tombstone[1] == "single_purpose_map_cache"
        assert tombstone[2] == "s-test01"
        assert tombstone[3] == "local"


# ==================== Group 6: Tokens Usage Provider ====================


@pytest.fixture
def tokens_usage_provider_fixture(test_data_path):
    """创建 TokensUsageProvider 实例并初始化 tokens_usage_log + deletion_log 表

    tokens_usage_log 使用 session_id 作为主键（TEXT 主键表, 在 SYNC_TABLES 中）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.tokens_usage_provider import TokensUsageProvider

    settings._initialize()
    provider = TokensUsageProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens_usage_log (
                session_id TEXT PRIMARY KEY NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                search_count INTEGER NOT NULL DEFAULT 0,
                result_items_count INTEGER NOT NULL DEFAULT 0,
                mode TEXT NOT NULL DEFAULT 'classification',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["tokens_usage_log", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["tokens_usage_log", "deletion_log"])


class TestTokensUsageDeleteWritesTombstone:
    """验证 TokensUsageProvider.delete_tokens_usage 写墓碑（TEXT 主键表, PK=session_id）"""

    def test_delete_tokens_usage_writes_tombstone(self, tokens_usage_provider_fixture):
        provider = tokens_usage_provider_fixture
        session_id = "test-session-01"
        provider.create_tokens_usage(
            {
                "session_id": session_id,
                "input_tokens": 100,
                "output_tokens": 200,
                "total_tokens": 300,
                "mode": "chatbot",
            }
        )

        assert provider.get_tokens_usage_by_session_id(session_id) is not None

        result = provider.delete_tokens_usage(session_id)
        assert result is True

        assert provider.get_tokens_usage_by_session_id(session_id) is None

        tombstone = _get_tombstone(provider.db, "tokens_usage_log", session_id)
        assert tombstone is not None
        assert tombstone[1] == "tokens_usage_log"
        assert tombstone[2] == session_id
        assert tombstone[3] == "local"


# ==================== Group 7: Being Provider ====================


@pytest.fixture
def being_provider_fixture(test_data_path):
    """创建 BeingProvider 实例并初始化 time_paradoxes + deletion_log 表

    time_paradoxes 是 AUTOINCREMENT 表（在 SYNC_TABLES 中, 在 HASH_ID_PREFIXES 前缀 tp-）。
    BeingProvider._PRIMARY_KEY = "hash_id"（跨端稳定标识, 非自增 id）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.being_provider import BeingProvider

    settings._initialize()
    provider = BeingProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS time_paradoxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                mode TEXT NOT NULL,
                content TEXT NOT NULL,
                ai_abstract TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(user_id, mode, version)
            )
            """
        )
        conn.commit()

    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["time_paradoxes", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["time_paradoxes", "deletion_log"])


class TestBeingDeleteWritesTombstone:
    """验证 BeingProvider.delete 写墓碑（AUTOINCREMENT 表, record_id=hash_id, PK=hash_id）"""

    def test_delete_writes_tombstone_with_hash_id(self, being_provider_fixture):
        provider = being_provider_fixture
        hash_id = provider.create(
            {
                "user_id": 1,
                "mode": "past",
                "version": 1,
                "content": {"text": "测试内容"},
            }
        )

        assert provider.get_by_id(hash_id) is not None

        result = provider.delete(hash_id)
        assert result is True

        assert provider.get_by_id(hash_id) is None

        tombstone = _get_tombstone(provider.db, "time_paradoxes", hash_id)
        assert tombstone is not None
        assert tombstone[1] == "time_paradoxes"
        assert tombstone[2] == hash_id
        assert tombstone[3] == "local"


class TestBeingDeleteByUserModeVersionWritesTombstone:
    """验证 BeingProvider.delete_by_user_mode_version 写墓碑（复合键→hash_id）"""

    def test_delete_by_user_mode_version_writes_tombstone(self, being_provider_fixture):
        provider = being_provider_fixture
        hash_id = provider.create(
            {
                "user_id": 2,
                "mode": "present",
                "version": 1,
                "content": {"text": "现在测试"},
            }
        )

        assert provider.get_by_user_mode_version(2, "present", 1) is not None

        result = provider.delete_by_user_mode_version(2, "present", 1)
        assert result is True

        assert provider.get_by_user_mode_version(2, "present", 1) is None

        # 墓碑 record_id 应为 hash_id（由复合键查询解析得到）
        tombstone = _get_tombstone(provider.db, "time_paradoxes", hash_id)
        assert tombstone is not None
        assert tombstone[1] == "time_paradoxes"
        assert tombstone[2] == hash_id
        assert tombstone[3] == "local"


# ==================== Group 8: Computer Usage Provider ====================


@pytest.fixture
def computer_usage_provider_fixture(test_data_path):
    """创建 ComputerUsageProvider 实例并初始化 user_app_behavior_log + deletion_log 表

    user_app_behavior_log 是 AUTOINCREMENT 表（在 SYNC_TABLES 中, 在 HASH_ID_PREFIXES 前缀 awbl-）。
    ComputerUsageProvider._PRIMARY_KEY = "id"（自增 id），墓碑 record_id = hash_id。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository.providers.computer_usage_provider import (
        ComputerUsageProvider,
    )

    settings._initialize()
    provider = ComputerUsageProvider()

    with provider.db.get_connection() as conn:
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
                updated_at TEXT
            )
            """
        )
        conn.commit()

    _create_deletion_log(provider.db)
    _clear_tables(provider.db, ["user_app_behavior_log", "deletion_log"])

    yield provider

    _clear_tables(provider.db, ["user_app_behavior_log", "deletion_log"])


class TestComputerUsageDeleteWritesTombstone:
    """验证 ComputerUsageProvider.delete_computer_usage 写墓碑（AUTOINCREMENT 表, record_id=hash_id）"""

    def test_delete_computer_usage_writes_tombstone_with_hash_id(
        self, computer_usage_provider_fixture
    ):
        provider = computer_usage_provider_fixture
        record = provider.create_computer_usage(
            {
                "start_time": "2026-07-23T10:00:00+00:00",
                "end_time": "2026-07-23T11:00:00+00:00",
                "duration": 3600,
                "app": "chrome.exe",
                "title": "Google Chrome",
            }
        )
        record_id = str(record["id"])

        hash_id = _get_hash_id(provider.db, "user_app_behavior_log", record_id)
        assert hash_id is not None
        assert hash_id.startswith("awbl-")

        result = provider.delete_computer_usage(record_id)
        assert result is True

        assert not _record_exists(provider.db, "user_app_behavior_log", record_id)

        tombstone = _get_tombstone(provider.db, "user_app_behavior_log", hash_id)
        assert tombstone is not None
        assert tombstone[1] == "user_app_behavior_log"
        assert tombstone[2] == hash_id
        assert tombstone[3] == "local"

        # 不应有以自增 id 为 record_id 的墓碑
        tombstone_by_pk = _get_tombstone(
            provider.db, "user_app_behavior_log", record_id
        )
        assert tombstone_by_pk is None


class TestComputerUsageBatchDeleteWritesTombstone:
    """验证 ComputerUsageProvider.batch_delete_computer_usage 写墓碑（AUTOINCREMENT 表, 批量）

    批量删除 N 条记录，应为每条记录分别写墓碑（record_id=hash_id）。
    """

    def test_batch_delete_computer_usage_writes_tombstone_for_each(
        self, computer_usage_provider_fixture
    ):
        provider = computer_usage_provider_fixture

        # 创建 3 条记录
        record_ids = []
        hash_ids = []
        for i in range(3):
            record = provider.create_computer_usage(
                {
                    "start_time": f"2026-07-23T{i+10}:00:00+00:00",
                    "end_time": f"2026-07-23T{i+11}:00:00+00:00",
                    "duration": 3600,
                    "app": f"app{i}.exe",
                    "title": f"App {i}",
                }
            )
            rid = str(record["id"])
            record_ids.append(rid)
            hid = _get_hash_id(provider.db, "user_app_behavior_log", rid)
            assert hid is not None and hid.startswith("awbl-")
            hash_ids.append(hid)

        # 批量删除
        deleted_count = provider.batch_delete_computer_usage(record_ids)
        assert deleted_count == 3

        # 验证 3 条记录均已删除
        for rid in record_ids:
            assert not _record_exists(provider.db, "user_app_behavior_log", rid)

        # 验证为每条记录写入了墓碑（record_id=hash_id）
        for hid in hash_ids:
            tombstone = _get_tombstone(provider.db, "user_app_behavior_log", hid)
            assert tombstone is not None, f"应有 hash_id={hid} 的墓碑"
            assert tombstone[1] == "user_app_behavior_log"
            assert tombstone[2] == hid
            assert tombstone[3] == "local"

        # 不应有以自增 id 为 record_id 的墓碑
        for rid in record_ids:
            assert _get_tombstone(provider.db, "user_app_behavior_log", rid) is None

        # 墓碑总数应为 3
        assert _count_tombstones(provider.db, "user_app_behavior_log") == 3

    def test_batch_delete_empty_list_returns_zero(self, computer_usage_provider_fixture):
        """空列表批量删除返回 0，不写墓碑"""
        provider = computer_usage_provider_fixture
        result = provider.batch_delete_computer_usage([])
        assert result == 0
        assert _count_tombstones(provider.db, "user_app_behavior_log") == 0


# ==================== Group 9: Custom Record Aggregator (动态表显式写墓碑) ====================


@pytest.fixture
def custom_record_repository_fixture(test_data_path):
    """创建 CustomRecordRepository 实例并初始化 meta 表 + deletion_log 表

    CustomRecordRepository.delete_entry 对动态表 custom_<slug> 执行删除，
    通过 write_tombstone_with_cursor 显式写墓碑（动态表不在 SYNC_TABLES 中,
    无法走 _generic_delete 自动通道）。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.aggregators.custom_record_aggregator import (
        CustomRecordRepository,
    )

    settings._initialize()

    repo = CustomRecordRepository(db_manager=lw_db_manager)

    # 创建 meta 表
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_record_types (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT,
                card_template TEXT NOT NULL DEFAULT 'clean',
                icon TEXT NOT NULL DEFAULT 'fileText',
                accent_color TEXT NOT NULL DEFAULT 'blue',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_record_fields (
                id TEXT PRIMARY KEY,
                type_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_key TEXT NOT NULL,
                field_type TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                display_role TEXT NOT NULL DEFAULT 'auto',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (type_id, field_key)
            )
            """
        )
        conn.commit()

    _create_deletion_log(lw_db_manager)
    _clear_tables(
        lw_db_manager,
        ["custom_record_types", "custom_record_fields", "deletion_log"],
    )

    yield repo

    # 清理：删除动态数据表 + 清空 meta 表和 deletion_log
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%' "
            "AND name NOT IN ('custom_record_types', 'custom_record_fields')"
        )
        tables = [row[0] for row in cursor.fetchall()]
        for table_name in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute("DELETE FROM custom_record_types")
        cursor.execute("DELETE FROM custom_record_fields")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


class TestCustomRecordDeleteEntryWritesTombstone:
    """验证 CustomRecordRepository.delete_entry 写墓碑（动态表显式写墓碑）

    动态表 custom_<slug> 不在 SYNC_TABLES 中，无法走 _generic_delete 自动通道,
    Aggregator 通过 write_tombstone_with_cursor 显式写墓碑（与 DELETE 同事务）。
    墓碑 target_table = 动态表名 custom_<slug>, record_id = entry_id。
    """

    def test_delete_entry_writes_tombstone_for_dynamic_table(
        self, custom_record_repository_fixture
    ):
        repo = custom_record_repository_fixture

        # 1. 创建自定义记录类型（会创建动态表 custom_sport）
        type_id = repo.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "运动类型", "field_key": "sport_type", "field_type": "text"},
                {"field_name": "时长", "field_key": "duration_min", "field_type": "integer"},
            ],
        )

        # 2. 创建一条记录
        entry_id = repo.create_entry(
            type_id=type_id,
            data={"sport_type": "running", "duration_min": 30},
            event_time="2026-07-23T10:00:00+00:00",
        )

        # 验证记录存在
        assert entry_id is not None
        assert _record_exists(repo.db, "custom_sport", entry_id)

        # 3. 删除记录
        result = repo.delete_entry(type_id, entry_id)
        assert result is True

        # 4. 验证记录已从动态表删除
        assert not _record_exists(repo.db, "custom_sport", entry_id)

        # 5. 验证墓碑已写入 deletion_log
        tombstone = _get_tombstone(repo.db, "custom_sport", entry_id)
        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[1] == "custom_sport", (
            f"墓碑 target_table 应为 'custom_sport'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == entry_id, (
            f"墓碑 record_id 应为 entry_id '{entry_id}'，实际: {tombstone[2]}"
        )
        assert tombstone[3] == "local", f"墓碑 source 应为 'local'，实际: {tombstone[3]}"

    def test_delete_entry_nonexistent_raises_not_found(
        self, custom_record_repository_fixture
    ):
        """删除不存在的记录抛 EntityNotFoundError，不写墓碑"""
        from lifeprism.repository.exceptions import EntityNotFoundError

        repo = custom_record_repository_fixture

        type_id = repo.create_type(
            name="阅读记录",
            slug="reading",
            fields=[{"field_name": "书名", "field_key": "book_name", "field_type": "text"}],
        )

        # 删除不存在的 entry_id
        with pytest.raises(EntityNotFoundError):
            repo.delete_entry(type_id, "cre-nonexist")

        # 不应写墓碑
        assert _count_tombstones(repo.db, "custom_reading") == 0
