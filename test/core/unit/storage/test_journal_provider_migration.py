"""
JournalProvider 迁移后测试

验证迁移到 repository/providers/journal_provider.py 后的新行为：
- 子类元数据定义完整
- create_journal 走 _generic_insert（自动生成 journal- 前缀 ID）
- update_journal 走 _generic_update（自动更新 updated_at 为 ISO 8601 + UTC）
- delete_journal 走 _generic_delete（写墓碑到 deletion_log）
- 异常处理抛出 DataAccessError（而非静默返回 None/False）

依据 issue: 02-journal-provider-migration
"""

import re

import pytest

# 迁移后从 repository.providers 导入
from lifeprism.repository.providers.journal_provider import JournalProvider

pytestmark = pytest.mark.core


# ==================== Fixtures（与基线测试一致，独立定义避免耦合）====================


@pytest.fixture
def journal_provider(test_data_path):
    """创建 JournalProvider 实例并初始化 goal_journal 表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = JournalProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goal (
                id TEXT PRIMARY KEY
            )
            """
        )
        cursor.execute(
            "INSERT OR IGNORE INTO goal (id) VALUES (?)", ("goal-test-001",)
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_journal (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT,
                content TEXT NOT NULL,
                mood TEXT DEFAULT "neutral",
                duration INTEGER DEFAULT 0,
                tags TEXT DEFAULT "[]",
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (goal_id) REFERENCES goal(id) ON DELETE CASCADE
            )
            """
        )
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

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goal_journal")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goal_journal")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


@pytest.fixture
def sample_journal_data():
    """测试用的日志数据"""
    return {
        "goal_id": "goal-test-001",
        "date": "2026-07-23",
        "time": "10:30",
        "content": "今天完成了重要任务",
        "mood": "joy",
        "duration": 30,
        "tags": '["工作", "重要"]',
    }


# ==================== 元数据定义测试（Slice B）====================


class TestJournalProviderMetadata:
    """验证 JournalProvider 定义了完整的子类元数据

    依据 issue: 02-journal-provider-migration
    元数据是 _generic_* 方法的契约，缺失会导致 CRUD 通道行为异常。
    """

    def test_defines_complete_metadata(self):
        """JournalProvider 应定义完整的子类元数据"""
        assert JournalProvider._TABLE_NAME == "goal_journal", (
            f"_TABLE_NAME 应为 'goal_journal'，实际: {JournalProvider._TABLE_NAME}"
        )
        assert JournalProvider._PRIMARY_KEY == "id", (
            f"_PRIMARY_KEY 应为 'id'，实际: {JournalProvider._PRIMARY_KEY}"
        )
        assert JournalProvider._ON_CONFLICT == "abort", (
            f"_ON_CONFLICT 应为 'abort'，实际: {JournalProvider._ON_CONFLICT}"
        )

        # _FILTER_FIELDS 应包含可筛选字段
        assert "goal_id" in JournalProvider._FILTER_FIELDS, (
            f"_FILTER_FIELDS 应包含 'goal_id'，实际: {JournalProvider._FILTER_FIELDS}"
        )
        assert "date" in JournalProvider._FILTER_FIELDS, (
            f"_FILTER_FIELDS 应包含 'date'，实际: {JournalProvider._FILTER_FIELDS}"
        )
        assert "mood" in JournalProvider._FILTER_FIELDS, (
            f"_FILTER_FIELDS 应包含 'mood'，实际: {JournalProvider._FILTER_FIELDS}"
        )

        # _UPDATE_FIELDS 应包含允许更新的字段（不含 id/goal_id/created_at/updated_at）
        expected_update_fields = {"date", "time", "content", "mood", "duration", "tags"}
        assert expected_update_fields.issubset(JournalProvider._UPDATE_FIELDS), (
            f"_UPDATE_FIELDS 应包含 {expected_update_fields}，"
            f"实际: {JournalProvider._UPDATE_FIELDS}"
        )
        # id/goal_id 不应在 _UPDATE_FIELDS 中（主键和外键不应被更新）
        assert "id" not in JournalProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'id'（主键不应被更新）"
        )
        assert "goal_id" not in JournalProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'goal_id'（外键不应被更新）"
        )


# ==================== create_journal 走 _generic_insert 测试（Slice C）====================


class TestCreateJournalUsesGenericInsert:
    """验证 create_journal 走 _generic_insert

    _generic_insert 会自动：
    - 生成 journal- 前缀 ID（8 位 hex）
    - 写入 created_at（ISO 8601 + UTC，因为 goal_journal 配置 timestamps=True）
    - 写入 updated_at（ISO 8601 + UTC，因为 goal_journal 配置 update_at=True）
    - 走 _ON_CONFLICT = "abort" 策略
    """

    def test_create_journal_writes_complete_record_with_iso_timestamps(
        self, journal_provider, sample_journal_data
    ):
        """create_journal 写入完整记录，时间戳为 ISO 8601 + UTC（_generic_insert 自动写入）"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        assert journal_id is not None
        assert journal_id.startswith("journal-"), (
            f"ID 应以 'journal-' 开头，实际: {journal_id}"
        )
        assert len(journal_id) == 16, f"ID 长度应为 16，实际: {len(journal_id)}"

        # 查询验证完整记录
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, goal_id, date, time, content, mood, duration, tags, "
                "created_at, updated_at FROM goal_journal WHERE id = ?",
                (journal_id,),
            )
            row = cursor.fetchone()

        assert row is not None, "记录应已写入 goal_journal 表"
        assert row[0] == journal_id
        assert row[1] == "goal-test-001"  # goal_id
        assert row[2] == "2026-07-23"  # date
        assert row[3] == "10:30"  # time
        assert row[4] == "今天完成了重要任务"  # content
        assert row[5] == "joy"  # mood
        assert row[6] == 30  # duration
        assert row[7] == '["工作", "重要"]'  # tags

        created_at = row[8]
        updated_at = row[9]

        # 验证时间戳被 _generic_insert 自动写入（调用方未传入）
        assert created_at is not None, "created_at 应被 _generic_insert 自动写入"
        assert updated_at is not None, "updated_at 应被 _generic_insert 自动写入"

        # 验证 ISO 8601 + UTC 格式（含 T 分隔符和 +00:00 后缀）
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")
        assert iso_pattern.match(created_at), (
            f"created_at 应为 ISO 8601 + UTC 格式，实际: {created_at}"
        )
        assert iso_pattern.match(updated_at), (
            f"updated_at 应为 ISO 8601 + UTC 格式，实际: {updated_at}"
        )


# ==================== update_journal 走 _generic_update 测试（Slice D）====================


class TestUpdateJournalUsesGenericUpdate:
    """验证 update_journal 走 _generic_update

    _generic_update 会自动：
    - 更新 updated_at（ISO 8601 + UTC，因为 goal_journal 配置 update_at=True）
    - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）
    """

    def test_update_journal_auto_updates_updated_at_to_iso_utc(
        self, journal_provider, sample_journal_data
    ):
        """update_journal 自动更新 updated_at 为 ISO 8601 + UTC（_generic_update 的行为）"""
        import time

        journal_id = journal_provider.create_journal(sample_journal_data)

        # 获取原始 updated_at
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM goal_journal WHERE id = ?", (journal_id,)
            )
            original_updated_at = cursor.fetchone()[0]

        # 等待以确保时间戳不同
        time.sleep(0.01)

        # 更新
        result = journal_provider.update_journal(journal_id, {"content": "更新后的内容"})

        assert result is True

        # 验证 updated_at 已更新
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, updated_at FROM goal_journal WHERE id = ?", (journal_id,)
            )
            row = cursor.fetchone()

        assert row[0] == "更新后的内容"
        new_updated_at = row[1]

        # updated_at 应与原值不同（_generic_update 自动更新）
        assert new_updated_at != original_updated_at, (
            f"updated_at 应被 _generic_update 自动更新，原值: {original_updated_at}，"
            f"新值: {new_updated_at}"
        )

        # 验证 ISO 8601 + UTC 格式
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")
        assert iso_pattern.match(new_updated_at), (
            f"updated_at 应为 ISO 8601 + UTC 格式，实际: {new_updated_at}"
        )

    def test_update_journal_rejects_invalid_field(self, journal_provider, sample_journal_data):
        """update_journal 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        # 尝试更新不在白名单中的字段（goal_id 是外键，不应被更新）
        with pytest.raises(ValueError, match="Invalid update fields"):
            journal_provider.update_journal(journal_id, {"goal_id": "new-goal"})


# ==================== delete_journal 走 _generic_delete 写墓碑测试（Slice E）====================


class TestDeleteJournalUsesGenericDelete:
    """验证 delete_journal 走 _generic_delete

    _generic_delete 会自动：
    - 删除 goal_journal 表中的记录
    - 写墓碑到 deletion_log（因为 goal_journal 在 SYNC_TABLES 中）
    - 墓碑 record_id = 主键值（TEXT 主键表，不在 HASH_ID_PREFIXES 中）
    - 墓碑 source = "local"
    """

    def test_delete_journal_writes_tombstone_to_deletion_log(
        self, journal_provider, sample_journal_data
    ):
        """delete_journal 写墓碑到 deletion_log（_generic_delete 的行为）"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        # 删除前确认记录存在
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM goal_journal WHERE id = ?", (journal_id,)
            )
            assert cursor.fetchone()[0] == 1, "删除前记录应存在"

        # 删除
        result = journal_provider.delete_journal(journal_id)

        assert result is True

        # 验证记录已从 goal_journal 表消失
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM goal_journal WHERE id = ?", (journal_id,)
            )
            assert cursor.fetchone()[0] == 0, "删除后记录应消失"

        # 验证墓碑已写入 deletion_log
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT target_table, record_id, source FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("goal_journal", journal_id),
            )
            tombstone = cursor.fetchone()

        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[0] == "goal_journal", (
            f"墓碑 target_table 应为 'goal_journal'，实际: {tombstone[0]}"
        )
        # TEXT 主键表：墓碑 record_id = 主键值（不是 hash_id，因为 goal_journal 不在 HASH_ID_PREFIXES 中）
        assert tombstone[1] == journal_id, (
            f"墓碑 record_id 应为主键值 '{journal_id}'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == "local", (
            f"墓碑 source 应为 'local'，实际: {tombstone[2]}"
        )


# ==================== 异常处理抛出 DataAccessError 测试（Slice F）====================


class TestJournalProviderRaisesDataAccessError:
    """验证异常处理从"静默返回 None/False"改为"抛出 DataAccessError"

    迁移前：server.providers.JournalProvider 在 except 中返回 None/False
    迁移后：repository.providers.JournalProvider 走 _generic_* 方法，异常抛出 DataAccessError

    依据 issue: 02-journal-provider-migration（异常处理改为抛出 DataAccessError）
    """

    def test_create_journal_raises_data_access_error_on_db_failure(
        self, journal_provider, sample_journal_data
    ):
        """create_journal 在数据库失败时抛出 DataAccessError（而非返回 None）"""
        from lifeprism.utils.exceptions import DataAccessError

        # 创建触发器阻止 INSERT，模拟数据库失败
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TRIGGER prevent_insert_journal BEFORE INSERT ON goal_journal "
                "BEGIN SELECT RAISE(ABORT, 'Insert prevented'); END"
            )
            conn.commit()

        try:
            # 调用 create_journal 应抛出 DataAccessError（而非返回 None）
            with pytest.raises(DataAccessError):
                journal_provider.create_journal(sample_journal_data)
        finally:
            # 清理触发器
            with journal_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TRIGGER IF EXISTS prevent_insert_journal")
                conn.commit()

    def test_delete_journal_raises_data_access_error_on_db_failure(
        self, journal_provider, sample_journal_data
    ):
        """delete_journal 在数据库失败时抛出 DataAccessError（而非返回 False）"""
        from lifeprism.utils.exceptions import DataAccessError

        # 先创建一条记录
        journal_id = journal_provider.create_journal(sample_journal_data)

        # 创建触发器阻止 DELETE，模拟数据库失败
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TRIGGER prevent_delete_journal BEFORE DELETE ON goal_journal "
                "BEGIN SELECT RAISE(ABORT, 'Delete prevented'); END"
            )
            conn.commit()

        try:
            # 调用 delete_journal 应抛出 DataAccessError（而非返回 False）
            with pytest.raises(DataAccessError):
                journal_provider.delete_journal(journal_id)
        finally:
            # 清理触发器
            with journal_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TRIGGER IF EXISTS prevent_delete_journal")
                conn.commit()

    def test_get_journals_by_goal_raises_data_access_error_on_db_failure(
        self, journal_provider
    ):
        """get_journals_by_goal 在数据库失败时抛出 DataAccessError（而非返回空列表）"""
        from lifeprism.utils.exceptions import DataAccessError

        # 删除 goal_journal 表模拟数据库失败
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS goal_journal")
            conn.commit()

        try:
            # 调用 get_journals_by_goal 应抛出 DataAccessError（而非返回 []）
            with pytest.raises(DataAccessError):
                journal_provider.get_journals_by_goal("goal-test-001")
        finally:
            # 重建表以避免影响后续测试
            with journal_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS goal_journal (
                        id TEXT PRIMARY KEY,
                        goal_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        time TEXT,
                        content TEXT NOT NULL,
                        mood TEXT DEFAULT "neutral",
                        duration INTEGER DEFAULT 0,
                        tags TEXT DEFAULT "[]",
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (goal_id) REFERENCES goal(id) ON DELETE CASCADE
                    )
                    """
                )
                conn.commit()

    def test_get_journal_by_id_raises_data_access_error_on_db_failure(
        self, journal_provider
    ):
        """get_journal_by_id 在数据库失败时抛出 DataAccessError（而非返回 None）"""
        from lifeprism.utils.exceptions import DataAccessError

        # 删除 goal_journal 表模拟数据库失败
        with journal_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS goal_journal")
            conn.commit()

        try:
            # 调用 get_journal_by_id 应抛出 DataAccessError（而非返回 None）
            with pytest.raises(DataAccessError):
                journal_provider.get_journal_by_id("journal-anything")
        finally:
            # 重建表以避免影响后续测试
            with journal_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS goal_journal (
                        id TEXT PRIMARY KEY,
                        goal_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        time TEXT,
                        content TEXT NOT NULL,
                        mood TEXT DEFAULT "neutral",
                        duration INTEGER DEFAULT 0,
                        tags TEXT DEFAULT "[]",
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (goal_id) REFERENCES goal(id) ON DELETE CASCADE
                    )
                    """
                )
                conn.commit()
