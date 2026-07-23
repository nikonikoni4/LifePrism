"""
CommitmentProvider 迁移后测试

验证迁移到 repository/providers/commitment_provider.py 后的新行为：
- 子类元数据定义完整
- create_commitment 走 _generic_insert（自动生成 cmt- 前缀 ID + ISO 时间戳）
- update_commitment 走 _generic_update（自动更新 updated_at + 白名单验证）
- delete_commitment 走 _generic_delete（写墓碑到 deletion_log）
- 新增 delete_by_value_id（走 _generic_batch_delete，含写墓碑）
- 新增 null_value_id（置空某价值下所有承诺的 value_id）
- 新增 count_by_value（统计某价值下的承诺数）

依据 issue: 03-commitment-provider-migration
"""

import re

import pytest

# 迁移后从 repository.providers 导入
from lifeprism.repository.providers.commitment_provider import CommitmentProvider

pytestmark = pytest.mark.core


# ==================== Fixtures（与基线测试一致，独立定义避免耦合）====================


@pytest.fixture
def commitment_provider(test_data_path):
    """创建 CommitmentProvider 实例并初始化 commitments 表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = CommitmentProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
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
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

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


# ==================== 元数据定义测试 ====================


class TestCommitmentProviderMetadata:
    """验证 CommitmentProvider 定义了完整的子类元数据

    依据 issue: 03-commitment-provider-migration
    元数据是 _generic_* 方法的契约，缺失会导致 CRUD 通道行为异常。
    """

    def test_defines_complete_metadata(self):
        """CommitmentProvider 应定义完整的子类元数据"""
        assert CommitmentProvider._TABLE_NAME == "commitments", (
            f"_TABLE_NAME 应为 'commitments'，实际: {CommitmentProvider._TABLE_NAME}"
        )
        assert CommitmentProvider._PRIMARY_KEY == "id", (
            f"_PRIMARY_KEY 应为 'id'，实际: {CommitmentProvider._PRIMARY_KEY}"
        )
        assert CommitmentProvider._ON_CONFLICT == "abort", (
            f"_ON_CONFLICT 应为 'abort'，实际: {CommitmentProvider._ON_CONFLICT}"
        )

        # _UPDATE_FIELDS 应包含允许更新的字段（不含 id/created_at/updated_at）
        expected_update_fields = {"content", "value_id", "status"}
        assert CommitmentProvider._UPDATE_FIELDS == expected_update_fields, (
            f"_UPDATE_FIELDS 应为 {expected_update_fields}，"
            f"实际: {CommitmentProvider._UPDATE_FIELDS}"
        )
        # id 不应在 _UPDATE_FIELDS 中（主键不应被更新）
        assert "id" not in CommitmentProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'id'（主键不应被更新）"
        )
        assert "created_at" not in CommitmentProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'created_at'（系统字段不应被更新）"
        )
        assert "updated_at" not in CommitmentProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'updated_at'（系统字段不应被更新）"
        )


# ==================== create_commitment 走 _generic_insert 测试 ====================


class TestCreateCommitmentUsesGenericInsert:
    """验证 create_commitment 走 _generic_insert

    _generic_insert 会自动：
    - 生成 cmt- 前缀 ID（8 位 hex）
    - 写入 created_at（ISO 8601 + UTC，因为 commitments 配置 timestamps=True）
    - 写入 updated_at（ISO 8601 + UTC，因为 commitments 配置 update_at=True）
    - 走 _ON_CONFLICT = "abort" 策略
    """

    def test_create_commitment_writes_complete_record_with_iso_timestamps(
        self, commitment_provider, sample_commitment_data
    ):
        """create_commitment 写入完整记录，时间戳为 ISO 8601 + UTC（_generic_insert 自动写入）"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        assert commitment_id is not None
        assert commitment_id.startswith("cmt-"), (
            f"ID 应以 'cmt-' 开头，实际: {commitment_id}"
        )
        assert len(commitment_id) == 12, f"ID 长度应为 12，实际: {len(commitment_id)}"

        # 查询验证完整记录
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, value_id, status, created_at, updated_at "
                "FROM commitments WHERE id = ?",
                (commitment_id,),
            )
            row = cursor.fetchone()

        assert row is not None, "记录应已写入 commitments 表"
        assert row[0] == commitment_id
        assert row[1] == "每天阅读 30 分钟"  # content
        assert row[2] == "val-test-001"  # value_id
        assert row[3] == "active"  # status（DB DEFAULT 兜底）

        created_at = row[4]
        updated_at = row[5]

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


# ==================== update_commitment 走 _generic_update 测试 ====================


class TestUpdateCommitmentUsesGenericUpdate:
    """验证 update_commitment 走 _generic_update

    _generic_update 会自动：
    - 更新 updated_at（ISO 8601 + UTC，因为 commitments 配置 update_at=True）
    - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）
    """

    def test_update_commitment_auto_updates_updated_at_to_iso_utc(
        self, commitment_provider, sample_commitment_data
    ):
        """update_commitment 自动更新 updated_at 为 ISO 8601 + UTC（_generic_update 的行为）"""
        import time

        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        # 获取原始 updated_at
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM commitments WHERE id = ?", (commitment_id,)
            )
            original_updated_at = cursor.fetchone()[0]

        # 等待以确保时间戳不同
        time.sleep(0.01)

        # 更新
        result = commitment_provider.update_commitment(commitment_id, {"content": "更新后的内容"})

        assert result is True

        # 验证 updated_at 已更新
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, updated_at FROM commitments WHERE id = ?", (commitment_id,)
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

    def test_update_commitment_rejects_invalid_field(
        self, commitment_provider, sample_commitment_data
    ):
        """update_commitment 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）

        旧实现静默忽略无效字段；新实现走 _generic_update，无效字段抛 ValueError。
        """
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        # 尝试更新不在白名单中的字段（id 是主键，不应被更新）
        with pytest.raises(ValueError, match="Invalid update fields"):
            commitment_provider.update_commitment(commitment_id, {"id": "cmt-hacked"})

    def test_update_commitment_rejects_system_field(
        self, commitment_provider, sample_commitment_data
    ):
        """update_commitment 拒绝更新系统字段 created_at（不在 _UPDATE_FIELDS 白名单中）"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        with pytest.raises(ValueError, match="Invalid update fields"):
            commitment_provider.update_commitment(
                commitment_id, {"created_at": "2020-01-01T00:00:00+00:00"}
            )


# ==================== delete_commitment 走 _generic_delete 写墓碑测试 ====================


class TestDeleteCommitmentUsesGenericDelete:
    """验证 delete_commitment 走 _generic_delete

    _generic_delete 会自动：
    - 删除 commitments 表中的记录
    - 写墓碑到 deletion_log（因为 commitments 在 SYNC_TABLES 中）
    - 墓碑 record_id = 主键值（TEXT 主键表，不在 HASH_ID_PREFIXES 中）
    - 墓碑 source = "local"
    """

    def test_delete_commitment_writes_tombstone_to_deletion_log(
        self, commitment_provider, sample_commitment_data
    ):
        """delete_commitment 写墓碑到 deletion_log（_generic_delete 的行为）"""
        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        # 删除前确认记录存在
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM commitments WHERE id = ?", (commitment_id,)
            )
            assert cursor.fetchone()[0] == 1, "删除前记录应存在"

        # 删除
        result = commitment_provider.delete_commitment(commitment_id)

        assert result is True

        # 验证记录已从 commitments 表消失
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM commitments WHERE id = ?", (commitment_id,)
            )
            assert cursor.fetchone()[0] == 0, "删除后记录应消失"

        # 验证墓碑已写入 deletion_log
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT target_table, record_id, source FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("commitments", commitment_id),
            )
            tombstone = cursor.fetchone()

        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[0] == "commitments", (
            f"墓碑 target_table 应为 'commitments'，实际: {tombstone[0]}"
        )
        # TEXT 主键表：墓碑 record_id = 主键值（不是 hash_id，因为 commitments 不在 HASH_ID_PREFIXES 中）
        assert tombstone[1] == commitment_id, (
            f"墓碑 record_id 应为主键值 '{commitment_id}'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == "local", (
            f"墓碑 source 应为 'local'，实际: {tombstone[2]}"
        )


# ==================== delete_by_value_id 级联删除测试 ====================


class TestDeleteByValueId:
    """验证 delete_by_value_id 级联删除某价值下所有承诺

    依据 issue: 03-commitment-provider-migration
    走 _generic_batch_delete 通道，含写墓碑到 deletion_log。
    """

    def test_delete_by_value_id_removes_all_commitments_for_value(
        self, commitment_provider
    ):
        """delete_by_value_id 删除某价值下所有承诺，返回删除数"""
        # 创建 3 条承诺关联 val-test-001
        for i in range(3):
            commitment_provider.create_commitment(
                {"content": f"承诺 {i}", "value_id": "val-test-001"}
            )
        # 创建 1 条承诺关联其他价值（不应被删除）
        commitment_provider.create_commitment(
            {"content": "其他承诺", "value_id": "val-other"}
        )

        deleted_count = commitment_provider.delete_by_value_id("val-test-001")

        assert deleted_count == 3, f"应删除 3 条承诺，实际: {deleted_count}"

        # 验证 val-test-001 下的承诺已全部删除
        remaining = commitment_provider.get_commitments_by_value("val-test-001")
        assert remaining == [], "val-test-001 下的承诺应已全部删除"

        # 验证其他价值的承诺不受影响
        other = commitment_provider.get_commitments_by_value("val-other")
        assert len(other) == 1, "其他价值的承诺不应被删除"

    def test_delete_by_value_id_writes_tombstones_for_all_deleted(
        self, commitment_provider
    ):
        """delete_by_value_id 为每条删除的承诺写墓碑到 deletion_log"""
        # 创建 2 条承诺
        cid1 = commitment_provider.create_commitment(
            {"content": "承诺 1", "value_id": "val-test-001"}
        )
        cid2 = commitment_provider.create_commitment(
            {"content": "承诺 2", "value_id": "val-test-001"}
        )

        commitment_provider.delete_by_value_id("val-test-001")

        # 验证两条墓碑都已写入 deletion_log
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT record_id FROM deletion_log WHERE target_table = ? "
                "AND record_id IN (?, ?) ORDER BY record_id",
                ("commitments", cid1, cid2),
            )
            tombstones = [row[0] for row in cursor.fetchall()]

        assert len(tombstones) == 2, (
            f"应写入 2 条墓碑，实际: {len(tombstones)}"
        )
        assert set(tombstones) == {cid1, cid2}, (
            f"墓碑 record_id 应为 {cid1} 和 {cid2}，实际: {tombstones}"
        )

    def test_delete_by_value_id_returns_zero_for_no_match(self, commitment_provider):
        """delete_by_value_id 无匹配时返回 0"""
        deleted_count = commitment_provider.delete_by_value_id("val-no-match")

        assert deleted_count == 0


# ==================== null_value_id 级联置空测试 ====================


class TestNullValueId:
    """验证 null_value_id 置空某价值下所有承诺的 value_id

    依据 issue: 03-commitment-provider-migration
    供 ValueProvider 删除价值时选择"置空关联"而非"级联删除"。
    """

    def test_null_value_id_sets_value_id_to_null_for_all_matches(
        self, commitment_provider
    ):
        """null_value_id 将某价值下所有承诺的 value_id 置空，返回更新数"""
        # 创建 3 条承诺关联 val-test-001
        for i in range(3):
            commitment_provider.create_commitment(
                {"content": f"承诺 {i}", "value_id": "val-test-001"}
            )
        # 创建 1 条承诺关联其他价值（不应被置空）
        commitment_provider.create_commitment(
            {"content": "其他承诺", "value_id": "val-other"}
        )

        updated_count = commitment_provider.null_value_id("val-test-001")

        assert updated_count == 3, f"应更新 3 条承诺，实际: {updated_count}"

        # 验证 val-test-001 下的承诺 value_id 已全部置空
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value_id FROM commitments WHERE value_id IS NULL"
            )
            null_rows = cursor.fetchall()
        assert len(null_rows) == 3, (
            f"应有 3 条承诺 value_id 为 NULL，实际: {len(null_rows)}"
        )

        # 验证其他价值的承诺不受影响
        other = commitment_provider.get_commitments_by_value("val-other")
        assert len(other) == 1, "其他价值的承诺不应被置空"

    def test_null_value_id_updates_updated_at_to_iso_utc(
        self, commitment_provider, sample_commitment_data
    ):
        """null_value_id 同时更新 updated_at 为 ISO 8601 + UTC"""
        import time

        commitment_id = commitment_provider.create_commitment(sample_commitment_data)

        # 获取原始 updated_at
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM commitments WHERE id = ?", (commitment_id,)
            )
            original_updated_at = cursor.fetchone()[0]

        time.sleep(0.01)

        commitment_provider.null_value_id("val-test-001")

        # 验证 updated_at 已更新
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM commitments WHERE id = ?", (commitment_id,)
            )
            new_updated_at = cursor.fetchone()[0]

        assert new_updated_at != original_updated_at, (
            f"updated_at 应被 null_value_id 更新，原值: {original_updated_at}，"
            f"新值: {new_updated_at}"
        )
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")
        assert iso_pattern.match(new_updated_at), (
            f"updated_at 应为 ISO 8601 + UTC 格式，实际: {new_updated_at}"
        )

    def test_null_value_id_returns_zero_for_no_match(self, commitment_provider):
        """null_value_id 无匹配时返回 0"""
        updated_count = commitment_provider.null_value_id("val-no-match")

        assert updated_count == 0


# ==================== count_by_value 统计测试 ====================


class TestCountByValue:
    """验证 count_by_value 统计某价值下的承诺数

    依据 issue: 03-commitment-provider-migration
    从 ValueProvider.count_commitments_by_value 迁移而来，
    供 ValueProvider 删除价值前询问用户"是否级联删除"时统计关联数。
    """

    def test_count_by_value_returns_correct_count(self, commitment_provider):
        """count_by_value 返回某价值下承诺数"""
        for i in range(3):
            commitment_provider.create_commitment(
                {"content": f"承诺 {i}", "value_id": "val-test-001"}
            )

        count = commitment_provider.count_by_value("val-test-001")

        assert count == 3, f"应返回 3 条承诺，实际: {count}"

    def test_count_by_value_returns_zero_for_no_match(self, commitment_provider):
        """count_by_value 无匹配时返回 0"""
        count = commitment_provider.count_by_value("val-no-match")

        assert count == 0

    def test_count_by_value_excludes_null_value_id(self, commitment_provider):
        """count_by_value 不统计 value_id 为 NULL 的承诺"""
        # 创建 2 条关联 val-test-001 的承诺
        commitment_provider.create_commitment(
            {"content": "承诺 1", "value_id": "val-test-001"}
        )
        commitment_provider.create_commitment(
            {"content": "承诺 2", "value_id": "val-test-001"}
        )
        # 创建 1 条 value_id 为 NULL 的承诺（直接 SQL 插入，绕过 create_commitment 的必填校验）
        with commitment_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO commitments (id, content, value_id, status, created_at, updated_at) "
                "VALUES (?, ?, NULL, 'active', ?, ?)",
                ("cmt-manual-1", "无关联承诺", "2026-07-23T00:00:00+00:00", "2026-07-23T00:00:00+00:00"),
            )
            conn.commit()

        count = commitment_provider.count_by_value("val-test-001")

        assert count == 2, (
            f"应只统计 val-test-001 的承诺（2 条），不含 NULL value_id，实际: {count}"
        )

    def test_count_by_value_only_counts_specified_value(self, commitment_provider):
        """count_by_value 只统计指定 value_id 的承诺，不统计其他价值"""
        commitment_provider.create_commitment(
            {"content": "承诺 A", "value_id": "val-test-001"}
        )
        commitment_provider.create_commitment(
            {"content": "承诺 B", "value_id": "val-other"}
        )

        count = commitment_provider.count_by_value("val-test-001")

        assert count == 1, f"应只统计 val-test-001 的承诺（1 条），实际: {count}"
