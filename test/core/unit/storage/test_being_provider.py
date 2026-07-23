"""
BeingProvider 基线测试

目的：在迁移到 repository/providers/ 之前，先补齐基线测试覆盖现有公共接口行为。
迁移后此测试的导入路径切换到 repository.providers，再次运行以验证行为等价。

注意：基线测试只覆盖"正常路径"行为（CRUD 成功路径），不覆盖异常路径
（异常路径在迁移前后行为不同：旧实现返回 None/False，新实现抛出 DataAccessError，
这部分由 test_being_provider_migration.py 中的迁移后测试覆盖）。

依据 issue: 04-being-provider-migration
"""

import pytest

# 迁移后从 repository.providers 导入（验证行为等价）
from lifeprism.repository.providers.being_provider import BeingProvider

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def being_provider(test_data_path):
    """创建 BeingProvider 实例并初始化 time_paradoxes 表

    fixture 同时创建 deletion_log 表，为迁移后 delete_by_user_mode_version
    写墓碑预留，基线测试也建好以避免迁移后改 fixture。

    表结构参考 TIME_PARADOXES_CONFIG（PRD 1 后含 hash_id 字段）：
    - id INTEGER PRIMARY KEY AUTOINCREMENT
    - hash_id TEXT NOT NULL UNIQUE（同步专用标识）
    - user_id INTEGER NOT NULL
    - version INTEGER NOT NULL
    - mode TEXT NOT NULL
    - content TEXT NOT NULL
    - ai_abstract TEXT DEFAULT NULL
    - UNIQUE(user_id, mode, version)
    - timestamps=True, update_at=True
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = BeingProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        # time_paradoxes 表（参考 TIME_PARADOXES_CONFIG schema，PRD 1 后含 hash_id）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS time_paradoxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                mode TEXT NOT NULL,
                content TEXT NOT NULL,
                ai_abstract TEXT DEFAULT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(user_id, mode, version)
            )
            """
        )
        # deletion_log 表（迁移后 delete_by_user_mode_version 会写墓碑）
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
        cursor.execute("DELETE FROM time_paradoxes")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

    # 清理表数据
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM time_paradoxes")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


@pytest.fixture
def sample_content():
    """测试用的 content 数据（dict）"""
    return {
        "past_self": {"mood": "happy", "goal": "成为更好的自己"},
        "present_self": {"mood": "calm", "activity": "学习"},
        "future_self": {"mood": "hopeful", "vision": "5年后成为专家"},
    }


# ==================== 基线测试：公共接口行为 ====================


class TestBeingProviderBaseline:
    """基线测试：验证 BeingProvider 公共接口行为

    这些测试在迁移前后都应通过，证明 CRUD 行为等价。
    仅覆盖 being_service 实际使用的方法（这些方法签名迁移后不变）。
    """

    def test_create_new_version_returns_record_dict(
        self, being_provider, sample_content
    ):
        """create_new_version 返回包含完整字段的记录 dict"""
        record = being_provider.create_new_version(
            user_id=1, mode="past", content=sample_content
        )

        assert record is not None
        assert isinstance(record, dict)
        # 验证核心字段
        assert record["user_id"] == 1
        assert record["mode"] == "past"
        assert record["version"] == 1  # 首个版本
        # content 应被反序列化为 dict（_deserialize_content 处理）
        assert isinstance(record["content"], dict)
        assert record["content"] == sample_content

    def test_create_new_version_increments_version(
        self, being_provider, sample_content
    ):
        """create_new_version 自动递增版本号"""
        # 创建第一个版本
        record1 = being_provider.create_new_version(
            user_id=1, mode="past", content=sample_content
        )
        assert record1["version"] == 1

        # 创建第二个版本
        record2 = being_provider.create_new_version(
            user_id=1, mode="past", content=sample_content
        )
        assert record2["version"] == 2

        # 不同 mode 的版本号独立
        record3 = being_provider.create_new_version(
            user_id=1, mode="future", content=sample_content
        )
        assert record3["version"] == 1

    def test_create_new_version_with_ai_abstract(self, being_provider, sample_content):
        """create_new_version 接受可选的 ai_abstract 参数"""
        record = being_provider.create_new_version(
            user_id=1, mode="past", content=sample_content, ai_abstract="AI 总结"
        )

        assert record is not None
        assert record["ai_abstract"] == "AI 总结"

    def test_get_by_user_mode_version_returns_record(
        self, being_provider, sample_content
    ):
        """按 (user_id, mode, version) 查询返回记录"""
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)

        record = being_provider.get_by_user_mode_version(
            user_id=1, mode="past", version=1
        )

        assert record is not None
        assert record["user_id"] == 1
        assert record["mode"] == "past"
        assert record["version"] == 1

    def test_get_by_user_mode_version_returns_none_for_nonexistent(
        self, being_provider
    ):
        """查询不存在的 (user_id, mode, version) 返回 None"""
        record = being_provider.get_by_user_mode_version(
            user_id=999, mode="past", version=1
        )

        assert record is None

    def test_get_all_by_user_mode_returns_list_sorted_by_version_desc(
        self, being_provider, sample_content
    ):
        """获取用户某模式所有版本，按 version DESC 排序"""
        # 创建 3 个版本
        for _ in range(3):
            being_provider.create_new_version(
                user_id=1, mode="past", content=sample_content
            )

        records = being_provider.get_all_by_user_mode(user_id=1, mode="past")

        assert isinstance(records, list)
        assert len(records) == 3
        # 验证按 version DESC 排序
        versions = [r["version"] for r in records]
        assert versions == [3, 2, 1], f"应按 version DESC 排序，实际: {versions}"

    def test_get_all_by_user_mode_returns_empty_for_no_match(
        self, being_provider
    ):
        """没有匹配的 (user_id, mode) 返回空列表"""
        records = being_provider.get_all_by_user_mode(user_id=999, mode="past")

        assert records == []

    def test_get_latest_version_returns_max_version(self, being_provider, sample_content):
        """获取最新版本号"""
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)

        latest = being_provider.get_latest_version(user_id=1, mode="past")

        assert latest == 2

    def test_get_latest_version_returns_zero_for_no_match(self, being_provider):
        """没有记录时返回 0"""
        latest = being_provider.get_latest_version(user_id=999, mode="past")

        assert latest == 0

    def test_get_latest_record_returns_highest_version(
        self, being_provider, sample_content
    ):
        """获取最新版本记录"""
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)

        record = being_provider.get_latest_record(user_id=1, mode="past")

        assert record is not None
        assert record["version"] == 2

    def test_get_latest_record_returns_none_for_no_match(self, being_provider):
        """没有记录时返回 None"""
        record = being_provider.get_latest_record(user_id=999, mode="past")

        assert record is None

    def test_update_by_user_mode_version_updates_content(
        self, being_provider, sample_content
    ):
        """按复合键更新 content 字段"""
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)
        new_content = {"updated": True}

        result = being_provider.update_by_user_mode_version(
            user_id=1, mode="past", version=1, data={"content": new_content}
        )

        assert result is True
        record = being_provider.get_by_user_mode_version(
            user_id=1, mode="past", version=1
        )
        assert record["content"] == new_content

    def test_update_by_user_mode_version_returns_false_for_nonexistent(
        self, being_provider
    ):
        """更新不存在的记录返回 False"""
        result = being_provider.update_by_user_mode_version(
            user_id=999, mode="past", version=1, data={"content": {"x": 1}}
        )

        assert result is False

    def test_delete_by_user_mode_version_removes_record(
        self, being_provider, sample_content
    ):
        """按复合键删除记录后查询返回 None"""
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)

        result = being_provider.delete_by_user_mode_version(
            user_id=1, mode="past", version=1
        )

        assert result is True
        record = being_provider.get_by_user_mode_version(
            user_id=1, mode="past", version=1
        )
        assert record is None

    def test_delete_by_user_mode_version_returns_false_for_nonexistent(
        self, being_provider
    ):
        """删除不存在的记录返回 False"""
        result = being_provider.delete_by_user_mode_version(
            user_id=999, mode="past", version=1
        )

        assert result is False

    def test_upsert_updates_existing_record(
        self, being_provider, sample_content
    ):
        """upsert 对已存在记录执行更新（UPDATE 路径）

        upsert 采用"先查 hash_id 再 update/create"方案：
        - 记录存在 → 调用 update(hash_id, data)（走 _generic_update，保留 hash_id）
        - 记录不存在 → 调用 create(data)（走 _generic_insert，生成 hash_id）
        """
        # 先创建一条记录
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)

        # upsert 同一 (user_id, mode, version) 应执行 UPDATE
        new_content = {"upserted": True}
        result = being_provider.upsert(
            user_id=1, mode="past", version=1, content=new_content, ai_abstract="AI"
        )

        assert result is True
        record = being_provider.get_by_user_mode_version(
            user_id=1, mode="past", version=1
        )
        assert record["content"] == new_content
        assert record["ai_abstract"] == "AI"
