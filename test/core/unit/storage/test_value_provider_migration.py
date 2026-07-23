"""
ValueProvider 迁移后测试

验证迁移到 repository/providers/value_provider.py 后的新行为：
- 子类元数据定义完整（_ON_CONFLICT = "abort" 防止默认 replace 覆盖）
- create_value 走 _generic_insert（自动生成 val- 前缀 ID + ISO 时间戳）
- update_value 走 _generic_update（自动更新 updated_at + 白名单验证，修复时间戳不一致）
- delete_value 走 _generic_delete（含写墓碑到 deletion_log，单表删除不含级联）
- value_service.delete_value 协调级联（cascade=True 调用 CommitmentProvider.delete_by_value_id
  + ValueProvider.delete_value；cascade=False 调用 CommitmentProvider.null_value_id
  + ValueProvider.delete_value）

依据 issue: 05-value-provider-migration
"""

import re

import pytest

# 迁移后从 repository.providers 导入
from lifeprism.repository.providers.value_provider import ValueProvider

pytestmark = pytest.mark.core


# ==================== Fixtures（与基线测试一致，独立定义避免耦合）====================


@pytest.fixture
def value_provider(test_data_path):
    """创建 ValueProvider 实例并初始化 user_values 表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = ValueProvider()

    with provider.db.get_connection() as conn:
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
        cursor.execute("DELETE FROM user_values")
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_values")
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


@pytest.fixture
def sample_value_data():
    """测试用的价值数据"""
    return {
        "keywords": "成长;自律",
        "content_positive": "我想成为持续成长的人",
        "content_negative": "我不想成为停滞不前的人",
        "sort_order": 10,
    }


# ==================== 元数据定义测试 ====================


class TestValueProviderMetadata:
    """验证 ValueProvider 定义了完整的子类元数据

    依据 issue: 05-value-provider-migration
    元数据是 _generic_* 方法的契约，缺失会导致 CRUD 通道行为异常。
    _ON_CONFLICT = "abort" 防止默认 replace 覆盖已有记录（replace 会删除旧记录再插入新记录，
    导致墓碑问题）。
    """

    def test_defines_complete_metadata(self):
        """ValueProvider 应定义完整的子类元数据"""
        assert ValueProvider._TABLE_NAME == "user_values", (
            f"_TABLE_NAME 应为 'user_values'，实际: {ValueProvider._TABLE_NAME}"
        )
        assert ValueProvider._PRIMARY_KEY == "id", (
            f"_PRIMARY_KEY 应为 'id'，实际: {ValueProvider._PRIMARY_KEY}"
        )
        # _ON_CONFLICT = "abort" 防止默认 replace 覆盖已有记录
        assert ValueProvider._ON_CONFLICT == "abort", (
            f"_ON_CONFLICT 应为 'abort'（防止默认 replace 覆盖），"
            f"实际: {ValueProvider._ON_CONFLICT}"
        )

        # _UPDATE_FIELDS 应包含允许更新的字段（不含 id/created_at/updated_at）
        expected_update_fields = {"keywords", "content_positive", "content_negative", "sort_order"}
        assert ValueProvider._UPDATE_FIELDS == expected_update_fields, (
            f"_UPDATE_FIELDS 应为 {expected_update_fields}，"
            f"实际: {ValueProvider._UPDATE_FIELDS}"
        )
        # id 不应在 _UPDATE_FIELDS 中（主键不应被更新）
        assert "id" not in ValueProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'id'（主键不应被更新）"
        )
        assert "created_at" not in ValueProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'created_at'（系统字段不应被更新）"
        )
        assert "updated_at" not in ValueProvider._UPDATE_FIELDS, (
            "_UPDATE_FIELDS 不应包含 'updated_at'（系统字段不应被更新）"
        )


# ==================== create_value 走 _generic_insert 测试 ====================


class TestCreateValueUsesGenericInsert:
    """验证 create_value 走 _generic_insert

    _generic_insert 会自动：
    - 生成 val- 前缀 ID（8 位 hex）
    - 写入 created_at（ISO 8601 + UTC，因为 user_values 配置 timestamps=True）
    - 写入 updated_at（ISO 8601 + UTC，因为 user_values 配置 update_at=True）
    - 走 _ON_CONFLICT = "abort" 策略（重复 ID 抛异常）
    """

    def test_create_value_writes_complete_record_with_iso_timestamps(
        self, value_provider, sample_value_data
    ):
        """create_value 写入完整记录，时间戳为 ISO 8601 + UTC（_generic_insert 自动写入）

        旧实现显式调用 get_utc_now_iso() 写时间戳，新实现由 _generic_insert 自动写入，
        行为等价但代码更简洁。
        """
        value_id = value_provider.create_value(sample_value_data)

        assert value_id is not None
        assert value_id.startswith("val-"), (
            f"ID 应以 'val-' 开头，实际: {value_id}"
        )
        assert len(value_id) == 12, f"ID 长度应为 12，实际: {len(value_id)}"

        # 查询验证完整记录
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, keywords, content_positive, content_negative, sort_order, "
                "created_at, updated_at FROM user_values WHERE id = ?",
                (value_id,),
            )
            row = cursor.fetchone()

        assert row is not None, "记录应已写入 user_values 表"
        assert row[0] == value_id
        assert row[1] == "成长;自律"  # keywords
        assert row[2] == "我想成为持续成长的人"  # content_positive
        assert row[3] == "我不想成为停滞不前的人"  # content_negative
        assert row[4] == 10  # sort_order

        created_at = row[5]
        updated_at = row[6]

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


# ==================== update_value 走 _generic_update 测试 ====================


class TestUpdateValueUsesGenericUpdate:
    """验证 update_value 走 _generic_update

    _generic_update 会自动：
    - 更新 updated_at（ISO 8601 + UTC，因为 user_values 配置 update_at=True）
    - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）

    修复点：旧实现使用 datetime.now(timezone.utc).isoformat()，与新插入时使用的
    get_utc_now_iso() 不一致（datetime.now 输出 +00:00，get_utc_now_iso 输出 +00:00
    但格式可能不同）。新实现统一用 _generic_update，时间戳由 get_utc_now_iso() 生成。
    """

    def test_update_value_auto_updates_updated_at_to_iso_utc(
        self, value_provider, sample_value_data
    ):
        """update_value 自动更新 updated_at 为 ISO 8601 + UTC（_generic_update 的行为）"""
        import time

        value_id = value_provider.create_value(sample_value_data)

        # 获取原始 updated_at
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM user_values WHERE id = ?", (value_id,)
            )
            original_updated_at = cursor.fetchone()[0]

        # 等待以确保时间戳不同
        time.sleep(0.01)

        # 更新
        result = value_provider.update_value(value_id, {"keywords": "成长;自律;专注"})

        assert result is True

        # 验证 updated_at 已更新
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT keywords, updated_at FROM user_values WHERE id = ?", (value_id,)
            )
            row = cursor.fetchone()

        assert row[0] == "成长;自律;专注"
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

    def test_update_value_rejects_invalid_field(self, value_provider, sample_value_data):
        """update_value 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）

        旧实现静默忽略无效字段；新实现走 _generic_update，无效字段抛 ValueError。
        """
        value_id = value_provider.create_value(sample_value_data)

        # 尝试更新不在白名单中的字段（id 是主键，不应被更新）
        with pytest.raises(ValueError, match="Invalid update fields"):
            value_provider.update_value(value_id, {"id": "val-hacked"})

    def test_update_value_rejects_system_field(self, value_provider, sample_value_data):
        """update_value 拒绝更新系统字段 created_at（不在 _UPDATE_FIELDS 白名单中）"""
        value_id = value_provider.create_value(sample_value_data)

        with pytest.raises(ValueError, match="Invalid update fields"):
            value_provider.update_value(
                value_id, {"created_at": "2020-01-01T00:00:00+00:00"}
            )


# ==================== delete_value 走 _generic_delete 写墓碑测试 ====================


class TestDeleteValueUsesGenericDelete:
    """验证 delete_value 走 _generic_delete

    _generic_delete 会自动：
    - 删除 user_values 表中的记录
    - 写墓碑到 deletion_log（因为 user_values 在 SYNC_TABLES 中）
    - 墓碑 record_id = 主键值（TEXT 主键表，不在 HASH_ID_PREFIXES 中）
    - 墓碑 source = "local"
    - 墓碑与 DELETE 在同一事务（DELETE 失败时墓碑回滚）

    重构点：原 delete_value_with_cascade 在 Provider 层直接调用 CommitmentProvider，
    违反 Repository 只做 CRUD 的原则。新实现 delete_value 只做单表删除，
    级联协调上移到 value_service。
    """

    def test_delete_value_writes_tombstone_to_deletion_log(
        self, value_provider, sample_value_data
    ):
        """delete_value 写墓碑到 deletion_log（_generic_delete 的行为）"""
        value_id = value_provider.create_value(sample_value_data)

        # 删除前确认记录存在
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM user_values WHERE id = ?", (value_id,)
            )
            assert cursor.fetchone()[0] == 1, "删除前记录应存在"

        # 删除
        result = value_provider.delete_value(value_id)

        assert result is True

        # 验证记录已从 user_values 表消失
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM user_values WHERE id = ?", (value_id,)
            )
            assert cursor.fetchone()[0] == 0, "删除后记录应消失"

        # 验证墓碑已写入 deletion_log
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT target_table, record_id, source FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("user_values", value_id),
            )
            tombstone = cursor.fetchone()

        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[0] == "user_values", (
            f"墓碑 target_table 应为 'user_values'，实际: {tombstone[0]}"
        )
        # TEXT 主键表：墓碑 record_id = 主键值（不是 hash_id，因为 user_values 不在 HASH_ID_PREFIXES 中）
        assert tombstone[1] == value_id, (
            f"墓碑 record_id 应为主键值 '{value_id}'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == "local", (
            f"墓碑 source 应为 'local'，实际: {tombstone[2]}"
        )

    def test_delete_value_is_single_table_only_no_cascade(
        self, value_provider, sample_value_data
    ):
        """delete_value 只删除 user_values 表，不级联删除 commitments

        重构点：原 delete_value_with_cascade 在 Provider 层直接 DELETE FROM commitments，
        新实现 delete_value 只做单表删除，级联协调上移到 value_service。
        此测试验证：调用 ValueProvider.delete_value 后，关联的 commitments 不受影响
        （记录仍存在，value_id 不变）。

        注意：项目 database_manager 未开启外键约束（PRAGMA foreign_keys = ON），
        所以 ON DELETE SET NULL 不会自动触发。value_id 的置空由 service 层的
        cascade=False 路径通过 CommitmentProvider.null_value_id() 显式完成
        （见 TestValueServiceCascadeCoordination 测试）。
        """
        value_id = value_provider.create_value(sample_value_data)

        # 手动插入一条关联的 commitment（绕过 CommitmentProvider 以隔离测试）
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO commitments (id, content, value_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', ?, ?)",
                (
                    "cmt-test-001",
                    "每天阅读 30 分钟",
                    value_id,
                    "2026-07-23T00:00:00+00:00",
                    "2026-07-23T00:00:00+00:00",
                ),
            )
            conn.commit()

        # 删除 value（不应级联删除 commitment）
        result = value_provider.delete_value(value_id)

        assert result is True

        # 验证 commitment 仍然存在且 value_id 不变（未受 Provider 层删除影响）
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, value_id FROM commitments WHERE id = ?",
                ("cmt-test-001",),
            )
            row = cursor.fetchone()

        assert row is not None, (
            "commitment 记录应仍然存在（ValueProvider.delete_value 不级联删除）"
        )
        assert row[0] == "cmt-test-001"
        assert row[1] == "每天阅读 30 分钟"
        # value_id 保持原值：因 database_manager 未开启外键约束，ON DELETE SET NULL
        # 不会自动触发；ValueProvider.delete_value 只删 user_values 表，不触碰 commitments。
        # value_id 的置空是 service 层 cascade=False 路径的职责（通过 null_value_id）。
        assert row[2] == value_id, (
            f"commitment 的 value_id 应保持原值 '{value_id}'（未开启外键约束，"
            f"Provider 层不级联），实际: {row[2]}"
        )


# ==================== value_service 级联协调测试 ====================


class TestValueServiceCascadeCoordination:
    """验证 value_service.delete_value 协调级联删除

    依据 issue: 05-value-provider-migration
    级联逻辑从 Provider 层上移到 Service 层：
    - cascade=True：先调用 CommitmentProvider.delete_by_value_id(value_id) 删除关联承诺，
      再调用 ValueProvider.delete_value(value_id) 删除价值本身
    - cascade=False：先调用 CommitmentProvider.null_value_id(value_id) 置空关联承诺的
      value_id，再调用 ValueProvider.delete_value(value_id) 删除价值本身

    此测试通过 value_service.delete_value 公共接口验证级联协调行为。
    """

    @pytest.fixture
    def setup_value_with_commitments(self, value_provider):
        """创建一个价值 + 2 条关联承诺，返回 (value_id, [commitment_id, ...])

        使用 CommitmentProvider 创建承诺，确保走 _generic_insert 通道（含正确时间戳）。
        """
        from lifeprism.repository.providers.commitment_provider import CommitmentProvider

        commitment_provider = CommitmentProvider()

        # 清理 commitments 表（避免不同测试间状态污染）
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM commitments")
            conn.commit()

        # 创建价值
        value_id = value_provider.create_value(
            {
                "keywords": "成长",
                "content_positive": "持续成长",
                "content_negative": None,
                "sort_order": 10,
            }
        )

        # 创建 2 条关联承诺
        commitment_ids = [
            commitment_provider.create_commitment(
                {"content": "每天阅读 30 分钟", "value_id": value_id}
            ),
            commitment_provider.create_commitment(
                {"content": "每周运动 3 次", "value_id": value_id}
            ),
        ]

        yield value_id, commitment_ids

        # 清理
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM commitments")
            cursor.execute("DELETE FROM user_values WHERE id = ?", (value_id,))
            conn.commit()

    def test_delete_value_cascade_true_deletes_commitments_and_value(
        self, value_provider, setup_value_with_commitments
    ):
        """value_service.delete_value(cascade=True) 删除关联承诺 + 价值本身

        cascade=True 行为：
        1. CommitmentProvider.delete_by_value_id(value_id) 删除所有关联承诺（含写墓碑）
        2. ValueProvider.delete_value(value_id) 删除价值本身（含写墓碑）
        """
        from lifeprism.server.services import value_service

        value_id, commitment_ids = setup_value_with_commitments

        # 调用 service 层删除（cascade=True）
        result = value_service.delete_value(value_id, cascade=True)

        assert result is True, "service.delete_value 应返回 True"

        # 验证 value 已被删除
        value = value_provider.get_value_by_id(value_id)
        assert value is None, "价值应已被删除"

        # 验证所有关联承诺已被删除
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM commitments WHERE id IN (?, ?)",
                commitment_ids,
            )
            remaining = cursor.fetchone()[0]
        assert remaining == 0, (
            f"cascade=True 应删除所有关联承诺，实际剩余: {remaining}"
        )

        # 验证写入了墓碑：user_values 墓碑 + 2 条 commitments 墓碑
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ? AND record_id = ?",
                ("user_values", value_id),
            )
            value_tombstone_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ? AND record_id IN (?, ?)",
                ("commitments", *commitment_ids),
            )
            commitment_tombstone_count = cursor.fetchone()[0]

        assert value_tombstone_count == 1, "应写入 1 条 user_values 墓碑"
        assert commitment_tombstone_count == 2, (
            f"应写入 2 条 commitments 墓碑，实际: {commitment_tombstone_count}"
        )

    def test_delete_value_cascade_false_nulls_commitments_and_deletes_value(
        self, value_provider, setup_value_with_commitments
    ):
        """value_service.delete_value(cascade=False) 置空承诺的 value_id + 删除价值本身

        cascade=False 行为：
        1. CommitmentProvider.null_value_id(value_id) 置空所有关联承诺的 value_id
           （不删除承诺记录，不写墓碑）
        2. ValueProvider.delete_value(value_id) 删除价值本身（含写墓碑）
        """
        from lifeprism.server.services import value_service

        value_id, commitment_ids = setup_value_with_commitments

        # 调用 service 层删除（cascade=False）
        result = value_service.delete_value(value_id, cascade=False)

        assert result is True, "service.delete_value 应返回 True"

        # 验证 value 已被删除
        value = value_provider.get_value_by_id(value_id)
        assert value is None, "价值应已被删除"

        # 验证承诺记录仍然存在，但 value_id 已被置空
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, value_id FROM commitments WHERE id IN (?, ?) ORDER BY id",
                commitment_ids,
            )
            rows = cursor.fetchall()

        assert len(rows) == 2, (
            f"cascade=False 不应删除承诺记录，实际剩余: {len(rows)}"
        )
        for row in rows:
            assert row[1] is None, (
                f"承诺 {row[0]} 的 value_id 应被置空，实际: {row[1]}"
            )

        # 验证只写入 user_values 墓碑，不写入 commitments 墓碑
        with value_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ? AND record_id = ?",
                ("user_values", value_id),
            )
            value_tombstone_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM deletion_log WHERE target_table = ?",
                ("commitments",),
            )
            commitment_tombstone_count = cursor.fetchone()[0]

        assert value_tombstone_count == 1, "应写入 1 条 user_values 墓碑"
        assert commitment_tombstone_count == 0, (
            "cascade=False 不应写 commitments 墓碑（仅置空 value_id，不删除承诺）"
        )

    def test_delete_value_nonexistent_returns_false(self, value_provider):
        """value_service.delete_value 删除不存在的价值返回 False"""
        from lifeprism.server.services import value_service

        result = value_service.delete_value("val-nonexist", cascade=True)

        assert result is False
