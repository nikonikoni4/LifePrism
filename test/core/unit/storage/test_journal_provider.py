"""
JournalProvider 基线测试

目的：在迁移到 repository/providers/ 之前，先补齐基线测试覆盖现有公共接口行为。
迁移后此测试的导入路径切换到 repository.providers，再次运行以验证行为等价。

注意：基线测试只覆盖"正常路径"行为（CRUD 成功路径），不覆盖异常路径
（异常路径在迁移前后行为不同：旧实现返回 None/False，新实现抛出 DataAccessError，
这部分由 test_journal_provider_migration.py 中的迁移后测试覆盖）。
"""

import pytest

# 迁移前从 server.providers 导入；迁移后切换到 repository.providers
from lifeprism.repository.providers.journal_provider import JournalProvider

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def journal_provider(test_data_path):
    """创建 JournalProvider 实例并初始化 goal_journal 表

    fixture 同时创建 goal 表（外键父表）、goal_journal 表、deletion_log 表。
    deletion_log 表为迁移后 delete_journal 写墓碑预留，基线测试也建好以避免迁移后改 fixture。
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = JournalProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        # 简化的 goal 表（仅 id 字段，作为外键父表）
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
        # goal_journal 表（参考 GOAL_JOURNAL_CONFIG schema）
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
        # deletion_log 表（迁移后 delete_journal 会写墓碑）
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

    # 清理旧的测试数据（避免不同测试间状态污染）
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goal_journal")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

    # 清理表（其他测试可能仍依赖 goal 表，仅清理 goal_journal 数据）
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


# ==================== 基线测试：公共接口行为 ====================


class TestJournalProviderBaseline:
    """基线测试：验证 JournalProvider 公共接口行为

    这些测试在迁移前后都应通过，证明 CRUD 行为等价。
    """

    def test_create_journal_returns_journal_prefix_id(self, journal_provider, sample_journal_data):
        """创建日志返回 journal- 前缀的 ID"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        assert journal_id is not None
        assert journal_id.startswith("journal-"), (
            f"ID 应以 'journal-' 开头，实际: {journal_id}"
        )
        # journal- (8 字符) + 8 位 hex = 16 字符
        assert len(journal_id) == 16, f"ID 长度应为 16，实际: {len(journal_id)}"

    def test_get_journal_by_id_returns_created_journal(
        self, journal_provider, sample_journal_data
    ):
        """按 ID 查询返回新创建的日志"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        journal = journal_provider.get_journal_by_id(journal_id)

        assert journal is not None
        assert journal["id"] == journal_id
        assert journal["goal_id"] == "goal-test-001"
        assert journal["content"] == "今天完成了重要任务"
        assert journal["mood"] == "joy"
        assert journal["duration"] == 30
        assert journal["date"] == "2026-07-23"
        assert journal["time"] == "10:30"

    def test_get_journal_by_id_returns_none_for_nonexistent(self, journal_provider):
        """查询不存在的 ID 返回 None"""
        journal = journal_provider.get_journal_by_id("journal-nonexist")

        assert journal is None

    def test_get_journals_by_goal_returns_list(self, journal_provider):
        """按 goal_id 查询返回日志列表（按 date DESC 排序）"""
        for i in range(3):
            data = {
                "goal_id": "goal-test-001",
                "date": f"2026-07-{20 + i:02d}",
                "time": "10:00",
                "content": f"日志 {i}",
                "mood": "neutral",
                "duration": 0,
                "tags": "[]",
            }
            journal_provider.create_journal(data)

        journals = journal_provider.get_journals_by_goal("goal-test-001")

        assert isinstance(journals, list)
        assert len(journals) == 3
        # 验证按 date DESC 排序
        dates = [j["date"] for j in journals]
        assert dates == sorted(dates, reverse=True), "应按 date DESC 排序"

    def test_get_journals_by_goal_returns_empty_for_no_match(self, journal_provider):
        """没有匹配的 goal_id 返回空列表"""
        journals = journal_provider.get_journals_by_goal("goal-no-match")

        assert journals == []

    def test_update_journal_updates_fields(self, journal_provider, sample_journal_data):
        """更新日志字段成功"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        result = journal_provider.update_journal(
            journal_id, {"content": "更新后的内容", "mood": "calm"}
        )

        assert result is True

        journal = journal_provider.get_journal_by_id(journal_id)
        assert journal["content"] == "更新后的内容"
        assert journal["mood"] == "calm"
        # 未更新的字段应保持原值
        assert journal["duration"] == 30

    def test_update_journal_with_empty_data_returns_true(
        self, journal_provider, sample_journal_data
    ):
        """空数据更新返回 True（无操作）"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        result = journal_provider.update_journal(journal_id, {})

        assert result is True

    def test_delete_journal_removes_record(self, journal_provider, sample_journal_data):
        """删除日志后记录消失"""
        journal_id = journal_provider.create_journal(sample_journal_data)

        result = journal_provider.delete_journal(journal_id)

        assert result is True
        # 验证记录已被删除
        journal = journal_provider.get_journal_by_id(journal_id)
        assert journal is None
