"""
CommitmentProvider 基线测试

目的：在迁移到 repository/providers/ 之前，先补齐基线测试覆盖现有公共接口行为。
迁移后此测试的导入路径切换到 repository.providers，再次运行以验证行为等价。

注意：基线测试只覆盖"正常路径"行为（CRUD 成功路径），不覆盖异常路径
（异常路径在迁移前后行为不同：旧实现返回 None/False，新实现抛出 DataAccessError，
这部分由 test_commitment_provider_migration.py 中的迁移后测试覆盖）。
"""

import pytest

# 迁移后从 repository.providers 导入（验证行为等价）
from lifeprism.repository.providers.commitment_provider import CommitmentProvider

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def commitment_provider(test_data_path):
    """创建 CommitmentProvider 实例并初始化 commitments 表

    fixture 同时创建 user_values 表（外键父表）、commitments 表、deletion_log 表。
    deletion_log 表为迁移后 delete_commitment 写墓碑预留，基线测试也建好以避免迁移后改 fixture。
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = CommitmentProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        # 简化的 user_values 表（仅必要字段，作为外键父表）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_values (
                id TEXT PRIMARY KEY,
                keywords TEXT NOT NULL,
                content_positive TEXT,
                content_negative TEXT,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            "INSERT OR IGNORE INTO user_values (id, keywords) VALUES (?, ?)",
            ("val-test-001", "成长"),
        )
        # commitments 表（参考 COMMITMENTS_CONFIG schema）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS commitments (
                id TEXT PRIMARY KEY NOT NULL,
                content TEXT NOT NULL,
                value_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT,
                CHECK(status IN ('active', 'completed', 'archived')),
                FOREIGN KEY (value_id) REFERENCES user_values(id) ON DELETE SET NULL
            )
            """
        )
        # deletion_log 表（迁移后 delete_commitment 会写墓碑）
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
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

    # 清理表（其他测试可能仍依赖 user_values 表，仅清理 commitments 数据）
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


@pytest.fixture
def sample_commitment_data():
    """测试用的承诺数据"""
    return {
        "content": "每天阅读 30 分钟",
        "value_id": "val-test-001",
    }


# ==================== 基线测试：公共接口行为 ====================


class TestCommitmentProviderBaseline:
    """基线测试：验证 CommitmentProvider 公共接口行为

    这些测试在迁移前后都应通过，证明 CRUD 行为等价。
    """

    def test_create_commitment_returns_cmt_prefix_id(
        self, commitment_provider, sample_commitment_data
    ):
        """创建承诺返回 cmt- 前缀的 ID"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        assert commitment_id is not None
        assert commitment_id.startswith("cmt-"), (
            f"ID 应以 'cmt-' 开头，实际: {commitment_id}"
        )
        # cmt- (4 字符) + 8 位 hex = 12 字符
        assert len(commitment_id) == 12, f"ID 长度应为 12，实际: {len(commitment_id)}"

    def test_get_commitment_by_id_returns_created_commitment(
        self, commitment_provider, sample_commitment_data
    ):
        """按 ID 查询返回新创建的承诺（含 LEFT JOIN value_keywords）"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        commitment = commitment_provider.get_commitment_by_id(commitment_id)

        assert commitment is not None
        assert commitment["id"] == commitment_id
        assert commitment["content"] == "每天阅读 30 分钟"
        assert commitment["value_id"] == "val-test-001"
        assert commitment["status"] == "active"
        # LEFT JOIN 应带出 value_keywords 字段
        assert commitment.get("value_keywords") == "成长"

    def test_get_commitment_by_id_returns_none_for_nonexistent(self, commitment_provider):
        """查询不存在的 ID 返回 None"""
        commitment = commitment_provider.get_commitment_by_id("cmt-nonexist")

        assert commitment is None

    def test_get_commitments_returns_list_with_join(
        self, commitment_provider, sample_commitment_data
    ):
        """获取承诺列表返回列表（含 LEFT JOIN value_keywords），按状态+创建时间排序"""
        commitment_provider.create_commitment(sample_commitment_data)

        commitments = commitment_provider.get_commitments()

        assert isinstance(commitments, list)
        assert len(commitments) == 1
        assert commitments[0]["content"] == "每天阅读 30 分钟"
        # LEFT JOIN 应带出 value_keywords 字段
        assert commitments[0].get("value_keywords") == "成长"

    def test_get_commitments_filter_by_status(self, commitment_provider, sample_commitment_data):
        """按 status 筛选承诺列表（支持逗号分隔多值）"""
        # 创建一条 active
        commitment_provider.create_commitment(sample_commitment_data)
        # 创建第二条并归档
        cid2 = commitment_provider.create_commitment(
            {"content": "每周运动 3 次", "value_id": "val-test-001"}
        )
        commitment_provider.update_commitment(cid2, {"status": "archived"})

        # 仅查 active
        active = commitment_provider.get_commitments(status="active")
        assert len(active) == 1
        assert active[0]["content"] == "每天阅读 30 分钟"

        # 查 active,archived 多值
        both = commitment_provider.get_commitments(status="active,archived")
        assert len(both) == 2

    def test_get_commitments_filter_by_value_id(self, commitment_provider, sample_commitment_data):
        """按 value_id 筛选承诺列表"""
        commitment_provider.create_commitment(sample_commitment_data)

        # 匹配的 value_id
        matched = commitment_provider.get_commitments(value_id="val-test-001")
        assert len(matched) == 1

        # 不匹配的 value_id
        empty = commitment_provider.get_commitments(value_id="val-no-match")
        assert empty == []

    def test_get_commitments_by_value_returns_list(self, commitment_provider, sample_commitment_data):
        """获取某价值下所有承诺（不 JOIN，用于 ValueDetailItem）"""
        commitment_provider.create_commitment(sample_commitment_data)
        commitment_provider.create_commitment(
            {"content": "每天冥想 10 分钟", "value_id": "val-test-001"}
        )

        commitments = commitment_provider.get_commitments_by_value("val-test-001")

        assert isinstance(commitments, list)
        assert len(commitments) == 2
        # 不 JOIN，只有 id/content/status/created_at 字段
        assert "id" in commitments[0]
        assert "content" in commitments[0]
        assert "status" in commitments[0]
        assert "value_keywords" not in commitments[0]

    def test_get_commitments_by_value_returns_empty_for_no_match(
        self, commitment_provider
    ):
        """没有匹配的 value_id 返回空列表"""
        commitments = commitment_provider.get_commitments_by_value("val-no-match")

        assert commitments == []

    def test_update_commitment_updates_fields(
        self, commitment_provider, sample_commitment_data
    ):
        """更新承诺字段成功"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        result = commitment_provider.update_commitment(
            commitment_id, {"content": "每天阅读 60 分钟", "status": "completed"}
        )

        assert result is True

        commitment = commitment_provider.get_commitment_by_id(commitment_id)
        assert commitment["content"] == "每天阅读 60 分钟"
        assert commitment["status"] == "completed"
        # 未更新的字段应保持原值
        assert commitment["value_id"] == "val-test-001"

    def test_update_commitment_with_empty_data_returns_true(
        self, commitment_provider, sample_commitment_data
    ):
        """空数据更新返回 True（无操作）"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        result = commitment_provider.update_commitment(commitment_id, {})

        assert result is True

    def test_update_commitment_nonexistent_returns_false(self, commitment_provider):
        """更新不存在的承诺返回 False"""
        result = commitment_provider.update_commitment("cmt-nonexist", {"content": "x"})

        assert result is False

    def test_delete_commitment_removes_record(
        self, commitment_provider, sample_commitment_data
    ):
        """删除承诺后记录消失"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        result = commitment_provider.delete_commitment(commitment_id)

        assert result is True
        # 验证记录已被删除
        commitment = commitment_provider.get_commitment_by_id(commitment_id)
        assert commitment is None

    def test_delete_commitment_nonexistent_returns_false(self, commitment_provider):
        """删除不存在的承诺返回 False"""
        result = commitment_provider.delete_commitment("cmt-nonexist")

        assert result is False
