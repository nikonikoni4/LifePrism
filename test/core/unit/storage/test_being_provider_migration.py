"""
BeingProvider 迁移后测试

验证迁移到 repository/providers/being_provider.py 后的新行为：
- 子类元数据定义完整（_TABLE_NAME="time_paradoxes"、_PRIMARY_KEY="hash_id"、
  _FILTER_FIELDS={"user_id","mode","version"}、_ON_CONFLICT="abort"）
- create 走 _generic_insert（AUTOINCREMENT 表，自动生成 tp- 前缀 hash_id）
- update 走 _generic_update(hash_id, data)（自动更新 updated_at 为 ISO 8601 + UTC）
- delete 走 _generic_delete(hash_id)（写墓碑，AUTOINCREMENT 表墓碑 record_id = hash_id）
- delete_by_user_mode_version 先查 hash_id 再走 _generic_delete
- update_by_user_mode_version 先查 hash_id 再走 _generic_update
- upsert 改用"先查 hash_id 再 update/create"（self.db.upsert 在新 schema 下
  INSERT 路径缺 hash_id 且 UPDATE 路径会改变 hash_id，破坏同步语义）
- get_latest_version 保留原生 SQL（基类无 _generic_max）
- 单例改用 LazySingleton
- 异常处理抛出 DataAccessError（而非静默返回 None/False）

依据 issue: 04-being-provider-migration
"""

import re

import pytest

# 迁移后从 repository.providers 导入
from lifeprism.repository.providers.being_provider import BeingProvider

pytestmark = pytest.mark.core


# ==================== Fixtures（与基线测试一致，独立定义避免耦合）====================


@pytest.fixture
def being_provider(test_data_path):
    """创建 BeingProvider 实例并初始化 time_paradoxes 表

    fixture 同时创建 deletion_log 表，用于验证 delete_by_user_mode_version
    走 _generic_delete 时写墓碑到 deletion_log。
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = BeingProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        # time_paradoxes 表（参考 TIME_PARADOXES_CONFIG schema）
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
        cursor.execute("DELETE FROM time_paradoxes")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

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


@pytest.fixture
def created_record(being_provider, sample_content):
    """创建一条记录并返回完整 dict（包含 hash_id）"""
    return being_provider.create_new_version(
        user_id=1, mode="past", content=sample_content
    )


# ==================== 元数据定义测试 ====================


class TestBeingProviderMetadata:
    """验证 BeingProvider 定义了完整的子类元数据

    依据 issue: 04-being-provider-migration
    元数据是 _generic_* 方法的契约，缺失会导致 CRUD 通道行为异常。

    AUTOINCREMENT 表特殊性：
    - _PRIMARY_KEY = "hash_id"（跨端稳定标识，不是自增 id）
    - _ON_CONFLICT = "abort"（time_paradoxes 有 UNIQUE(user_id,mode,version) 约束，
      业务层应主动管理版本号，冲突时抛异常而非静默替换）
    """

    def test_defines_complete_metadata(self):
        """BeingProvider 应定义完整的子类元数据"""
        assert BeingProvider._TABLE_NAME == "time_paradoxes", (
            f"_TABLE_NAME 应为 'time_paradoxes'，实际: {BeingProvider._TABLE_NAME}"
        )
        # AUTOINCREMENT 表的主键设为 hash_id（跨端稳定标识，非自增 id）
        assert BeingProvider._PRIMARY_KEY == "hash_id", (
            f"_PRIMARY_KEY 应为 'hash_id'（AUTOINCREMENT 表跨端标识），"
            f"实际: {BeingProvider._PRIMARY_KEY}"
        )
        assert BeingProvider._ON_CONFLICT == "abort", (
            f"_ON_CONFLICT 应为 'abort'，实际: {BeingProvider._ON_CONFLICT}"
        )
        # _FILTER_FIELDS 应包含复合键字段（user_id, mode, version）
        expected_filter_fields = {"user_id", "mode", "version"}
        assert expected_filter_fields.issubset(BeingProvider._FILTER_FIELDS), (
            f"_FILTER_FIELDS 应包含 {expected_filter_fields}，"
            f"实际: {BeingProvider._FILTER_FIELDS}"
        )

    def test_no_legacy_table_name_constant(self):
        """不应保留旧的无下划线 TABLE_NAME 常量

        旧实现：TABLE_NAME = "time_paradoxes"（无下划线）
        新实现：_TABLE_NAME = "time_paradoxes"（带下划线，符合基类约定）
        """
        # 旧的无下划线常量不应存在（迁移后应改为 _TABLE_NAME）
        assert not hasattr(BeingProvider, "TABLE_NAME"), (
            "不应保留旧的无下划线 TABLE_NAME 常量，应改为 _TABLE_NAME"
        )


# ==================== create 走 _generic_insert 测试 ====================


class TestCreateUsesGenericInsert:
    """验证 create 走 _generic_insert

    _generic_insert 对 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中）会自动：
    - 生成 tp- 前缀的 hash_id（12 位 hex，共 15 字符）
    - 写入 created_at（ISO 8601 + UTC，因为 time_paradoxes 配置 timestamps=True）
    - 写入 updated_at（ISO 8601 + UTC，因为 time_paradoxes 配置 update_at=True）
    - 走 _ON_CONFLICT = "abort" 策略

    依据 issue: 04-being-provider-migration（create 必须走 _generic_insert 以保证 hash_id 生成）
    """

    def test_create_auto_generates_hash_id_with_tp_prefix(
        self, being_provider, sample_content
    ):
        """create 自动生成 tp- 前缀的 hash_id（_generic_insert 的行为）"""
        data = {
            "user_id": 1,
            "mode": "past",
            "version": 1,
            "content": sample_content,
        }
        record_id = being_provider.create(data)

        # _generic_insert 对 AUTOINCREMENT 表返回 str(lastrowid)
        # create 应返回 hash_id（跨端稳定标识），而非自增 id
        assert record_id is not None
        assert isinstance(record_id, str), (
            f"create 应返回 hash_id (str)，实际类型: {type(record_id).__name__}"
        )
        assert record_id.startswith("tp-"), (
            f"hash_id 应以 'tp-' 开头，实际: {record_id}"
        )
        # tp- (3 字符) + 12 位 hex = 15 字符
        assert len(record_id) == 15, (
            f"hash_id 长度应为 15（前缀 'tp-' + 12 位 hex），实际长度: {len(record_id)}"
        )
        # 验证 hex 部分都是合法的十六进制字符
        hex_part = record_id[3:]
        assert all(c in "0123456789abcdef" for c in hex_part), (
            f"hash_id 后 12 位应为合法 hex 字符，实际值: {hex_part}"
        )

    def test_create_writes_iso_timestamps_automatically(
        self, being_provider, sample_content
    ):
        """create 自动写入 ISO 8601 + UTC 时间戳（_generic_insert 的行为）"""
        data = {
            "user_id": 1,
            "mode": "past",
            "version": 1,
            "content": sample_content,
        }
        being_provider.create(data)

        # 查询验证时间戳被自动写入
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id, created_at, updated_at FROM time_paradoxes "
                "WHERE user_id = ? AND mode = ? AND version = ?",
                (1, "past", 1),
            )
            row = cursor.fetchone()

        assert row is not None, "记录应已写入 time_paradoxes 表"
        hash_id, created_at, updated_at = row

        # 验证时间戳被 _generic_insert 自动写入
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


# ==================== update 走 _generic_update 测试 ====================


class TestUpdateUsesGenericUpdate:
    """验证 update 走 _generic_update(hash_id, data)

    _generic_update 会自动：
    - 更新 updated_at（ISO 8601 + UTC，因为 time_paradoxes 配置 update_at=True）
    - 按 _PRIMARY_KEY = "hash_id" 定位记录
    - 走 _UPDATE_FIELDS 白名单验证（如定义）

    依据 issue: 04-being-provider-migration（update 改用 _generic_update(hash_id, data)）
    """

    def test_update_by_hash_id_auto_updates_updated_at(
        self, being_provider, created_record
    ):
        """update 按 hash_id 更新记录，自动更新 updated_at 为 ISO 8601 + UTC"""
        import time

        hash_id = created_record["hash_id"]

        # 获取原始 updated_at
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM time_paradoxes WHERE hash_id = ?", (hash_id,)
            )
            original_updated_at = cursor.fetchone()[0]

        # 等待以确保时间戳不同
        time.sleep(0.01)

        # 按 hash_id 更新
        new_content = {"updated": True}
        result = being_provider.update(hash_id, {"content": new_content})

        assert result is True

        # 验证 updated_at 已更新
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, updated_at FROM time_paradoxes WHERE hash_id = ?",
                (hash_id,),
            )
            row = cursor.fetchone()

        # content 应被序列化为 JSON 字符串
        import json

        assert json.loads(row[0]) == new_content
        new_updated_at = row[1]

        assert new_updated_at != original_updated_at, (
            f"updated_at 应被 _generic_update 自动更新，原值: {original_updated_at}，"
            f"新值: {new_updated_at}"
        )

        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")
        assert iso_pattern.match(new_updated_at), (
            f"updated_at 应为 ISO 8601 + UTC 格式，实际: {new_updated_at}"
        )

    def test_update_by_hash_id_returns_false_for_nonexistent(self, being_provider):
        """update 不存在的 hash_id 返回 False"""
        result = being_provider.update("tp-nonexist0000", {"content": {"x": 1}})

        assert result is False


# ==================== delete 走 _generic_delete 测试（含写墓碑）====================


class TestDeleteUsesGenericDelete:
    """验证 delete 走 _generic_delete(hash_id)

    _generic_delete 对 SYNC_TABLES 中的 AUTOINCREMENT 表会自动：
    - 删除 time_paradoxes 表中的记录
    - 写墓碑到 deletion_log（time_paradoxes 在 SYNC_TABLES 中）
    - 墓碑 record_id = hash_id（AUTOINCREMENT 表用 hash_id 而非自增 id）
    - 墓碑 source = "local"
    - 墓碑与 DELETE 在同一事务（DELETE 失败时墓碑回滚）

    依据 issue: 04-being-provider-migration（delete 走 _generic_delete，含写墓碑）
    """

    def test_delete_by_hash_id_removes_record_and_writes_tombstone(
        self, being_provider, created_record
    ):
        """delete 按 hash_id 删除记录，墓碑 record_id = hash_id"""
        hash_id = created_record["hash_id"]

        # 删除前确认记录存在
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM time_paradoxes WHERE hash_id = ?", (hash_id,)
            )
            assert cursor.fetchone()[0] == 1, "删除前记录应存在"

        # 删除
        result = being_provider.delete(hash_id)

        assert result is True

        # 验证记录已从 time_paradoxes 表消失
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM time_paradoxes WHERE hash_id = ?", (hash_id,)
            )
            assert cursor.fetchone()[0] == 0, "删除后记录应消失"

        # 验证墓碑已写入 deletion_log
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT target_table, record_id, source FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("time_paradoxes", hash_id),
            )
            tombstone = cursor.fetchone()

        assert tombstone is not None, "应写入墓碑到 deletion_log"
        assert tombstone[0] == "time_paradoxes", (
            f"墓碑 target_table 应为 'time_paradoxes'，实际: {tombstone[0]}"
        )
        # AUTOINCREMENT 表：墓碑 record_id = hash_id（不是自增 id）
        assert tombstone[1] == hash_id, (
            f"墓碑 record_id 应为 hash_id '{hash_id}'，实际: {tombstone[1]}"
        )
        assert tombstone[2] == "local", (
            f"墓碑 source 应为 'local'，实际: {tombstone[2]}"
        )

    def test_delete_by_hash_id_returns_false_for_nonexistent(self, being_provider):
        """delete 不存在的 hash_id 返回 False（无墓碑写入）"""
        result = being_provider.delete("tp-nonexist0000")

        assert result is False


# ==================== delete_by_user_mode_version 走 _generic_delete 测试 ====================


class TestDeleteByUserModeVersionUsesGenericDelete:
    """验证 delete_by_user_mode_version 先查 hash_id 再走 _generic_delete

    复合键方法（*_by_user_mode_version）采用"先查 hash_id 再调用 _generic_*"方案：
    1. 按 (user_id, mode, version) 查询获取 hash_id
    2. 用 hash_id 调用 _generic_delete（自动写墓碑，record_id = hash_id）

    依据 issue: 04-being-provider-migration（delete_by_user_mode_version 走 _generic_delete，
    先查 hash_id 再删除）
    """

    def test_delete_by_user_mode_version_writes_tombstone_with_hash_id(
        self, being_provider, created_record
    ):
        """delete_by_user_mode_version 写墓碑，record_id = hash_id"""
        hash_id = created_record["hash_id"]

        # 删除
        result = being_provider.delete_by_user_mode_version(
            user_id=1, mode="past", version=1
        )

        assert result is True

        # 验证墓碑已写入 deletion_log，record_id = hash_id
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT target_table, record_id FROM deletion_log "
                "WHERE target_table = ? AND record_id = ?",
                ("time_paradoxes", hash_id),
            )
            tombstone = cursor.fetchone()

        assert tombstone is not None, (
            f"应写入墓碑到 deletion_log，record_id = hash_id '{hash_id}'"
        )
        assert tombstone[1] == hash_id, (
            f"墓碑 record_id 应为 hash_id '{hash_id}'，实际: {tombstone[1]}"
        )

    def test_delete_by_user_mode_version_returns_false_for_nonexistent(
        self, being_provider
    ):
        """delete_by_user_mode_version 不存在的复合键返回 False"""
        result = being_provider.delete_by_user_mode_version(
            user_id=999, mode="past", version=1
        )

        assert result is False


# ==================== update_by_user_mode_version 走 _generic_update 测试 ====================


class TestUpdateByUserModeVersionUsesGenericUpdate:
    """验证 update_by_user_mode_version 先查 hash_id 再走 _generic_update

    复合键方法（*_by_user_mode_version）采用"先查 hash_id 再调用 _generic_*"方案：
    1. 按 (user_id, mode, version) 查询获取 hash_id
    2. 用 hash_id 调用 _generic_update（自动更新 updated_at）

    依据 issue: 04-being-provider-migration（复合键方法先查 hash_id 再调用 _generic_*）
    """

    def test_update_by_user_mode_version_auto_updates_updated_at(
        self, being_provider, created_record
    ):
        """update_by_user_mode_version 自动更新 updated_at（_generic_update 的行为）"""
        import time

        hash_id = created_record["hash_id"]

        # 获取原始 updated_at
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM time_paradoxes WHERE hash_id = ?", (hash_id,)
            )
            original_updated_at = cursor.fetchone()[0]

        time.sleep(0.01)

        # 按复合键更新
        new_content = {"updated": True}
        result = being_provider.update_by_user_mode_version(
            user_id=1, mode="past", version=1, data={"content": new_content}
        )

        assert result is True

        # 验证 updated_at 已更新
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM time_paradoxes WHERE hash_id = ?", (hash_id,)
            )
            new_updated_at = cursor.fetchone()[0]

        assert new_updated_at != original_updated_at, (
            f"updated_at 应被 _generic_update 自动更新，原值: {original_updated_at}，"
            f"新值: {new_updated_at}"
        )

    def test_update_by_user_mode_version_returns_false_for_nonexistent(
        self, being_provider
    ):
        """update_by_user_mode_version 不存在的复合键返回 False"""
        result = being_provider.update_by_user_mode_version(
            user_id=999, mode="past", version=1, data={"content": {"x": 1}}
        )

        assert result is False


# ==================== upsert 改用 _generic_* 通道测试 ====================


class TestUpsertUsesGenericMethods:
    """验证 upsert 改用"先查 hash_id 再 update/create"方案

    依据 issue: 04-being-provider-migration（upsert 原保留 self.db.upsert，
    但新 schema 下 self.db.upsert INSERT 路径缺 hash_id 且 UPDATE 路径会改变
    hash_id，故改用 _generic_* 通道保证 hash_id 不可变）

    upsert 行为：
    - 记录存在 → 调用 update(hash_id, data)（走 _generic_update，保留原 hash_id）
    - 记录不存在 → 调用 create(data)（走 _generic_insert，生成 tp- 前缀 hash_id）
    """

    def test_upsert_updates_existing_record(
        self, being_provider, created_record, sample_content
    ):
        """upsert 对已存在记录执行 UPDATE（保留原 hash_id）"""
        original_hash_id = created_record["hash_id"]
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
        # UPDATE 路径应保留原 hash_id（不可变）
        assert record["hash_id"] == original_hash_id, (
            f"UPDATE 路径应保留原 hash_id '{original_hash_id}'，"
            f"实际: {record['hash_id']}"
        )

    def test_upsert_inserts_new_record(self, being_provider, sample_content):
        """upsert 对不存在记录执行 INSERT（生成 tp- 前缀 hash_id）"""
        result = being_provider.upsert(
            user_id=1, mode="past", version=1, content=sample_content, ai_abstract="AI"
        )

        assert result is True
        record = being_provider.get_by_user_mode_version(
            user_id=1, mode="past", version=1
        )
        assert record is not None, "INSERT 路径应创建新记录"
        assert record["content"] == sample_content
        assert record["ai_abstract"] == "AI"
        # INSERT 路径应生成 tp- 前缀 hash_id
        assert record["hash_id"].startswith("tp-"), (
            f"INSERT 路径应生成 tp- 前缀 hash_id，实际: {record['hash_id']}"
        )
        assert len(record["hash_id"]) == 15, (
            f"hash_id 长度应为 15（tp- + 12 位 hex），实际: {len(record['hash_id'])}"
        )


# ==================== get_latest_version 保留原生 SQL 测试 ====================


class TestGetLatestVersionPreservesNativeSQL:
    """验证 get_latest_version 保留原生 SQL

    依据 issue: 04-being-provider-migration（get_latest_version 保留原生 SQL，基类无 _generic_max）
    """

    def test_get_latest_version_returns_max_version(
        self, being_provider, sample_content
    ):
        """get_latest_version 返回最新版本号"""
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)
        being_provider.create_new_version(user_id=1, mode="past", content=sample_content)

        latest = being_provider.get_latest_version(user_id=1, mode="past")

        assert latest == 2

    def test_get_latest_version_returns_zero_for_no_match(self, being_provider):
        """get_latest_version 没有记录时返回 0"""
        latest = being_provider.get_latest_version(user_id=999, mode="past")

        assert latest == 0


# ==================== 异常处理抛出 DataAccessError 测试 ====================


class TestBeingProviderRaisesDataAccessError:
    """验证异常处理从"静默返回 None/False"改为"抛出 DataAccessError"

    迁移前：server.providers.BeingProvider 部分方法在 except 中返回 None/False
    迁移后：repository.providers.BeingProvider 走 _generic_* 方法，异常抛出 DataAccessError

    依据 issue: 04-being-provider-migration（异常处理抛出 DataAccessError）
    """

    def test_create_raises_data_access_error_on_db_failure(
        self, being_provider, sample_content
    ):
        """create 在数据库失败时抛出 DataAccessError（而非返回 None）"""
        from lifeprism.utils.exceptions import DataAccessError

        # 创建触发器阻止 INSERT，模拟数据库失败
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TRIGGER prevent_insert_being BEFORE INSERT ON time_paradoxes "
                "BEGIN SELECT RAISE(ABORT, 'Insert prevented'); END"
            )
            conn.commit()

        try:
            data = {
                "user_id": 1,
                "mode": "past",
                "version": 1,
                "content": sample_content,
            }
            with pytest.raises(DataAccessError):
                being_provider.create(data)
        finally:
            with being_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TRIGGER IF EXISTS prevent_insert_being")
                conn.commit()

    def test_delete_raises_data_access_error_on_db_failure(
        self, being_provider, created_record
    ):
        """delete 在数据库失败时抛出 DataAccessError（而非返回 False）"""
        from lifeprism.utils.exceptions import DataAccessError

        hash_id = created_record["hash_id"]

        # 创建触发器阻止 DELETE，模拟数据库失败
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TRIGGER prevent_delete_being BEFORE DELETE ON time_paradoxes "
                "BEGIN SELECT RAISE(ABORT, 'Delete prevented'); END"
            )
            conn.commit()

        try:
            with pytest.raises(DataAccessError):
                being_provider.delete(hash_id)
        finally:
            with being_provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TRIGGER IF EXISTS prevent_delete_being")
                conn.commit()

    def test_get_by_user_mode_version_raises_data_access_error_on_db_failure(
        self, being_provider
    ):
        """get_by_user_mode_version 在数据库失败时抛出 DataAccessError（而非返回 None）"""
        from lifeprism.utils.exceptions import DataAccessError

        # 删除 time_paradoxes 表模拟数据库失败
        with being_provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS time_paradoxes")
            conn.commit()

        try:
            with pytest.raises(DataAccessError):
                being_provider.get_by_user_mode_version(
                    user_id=1, mode="past", version=1
                )
        finally:
            # 重建表以避免影响后续测试
            with being_provider.db.get_connection() as conn:
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
                        ai_abstract TEXT DEFAULT NULL,
                        created_at TEXT,
                        updated_at TEXT,
                        UNIQUE(user_id, mode, version)
                    )
                    """
                )
                conn.commit()


# ==================== 单例改用 LazySingleton 测试 ====================


class TestBeingProviderUsesLazySingleton:
    """验证单例改用 LazySingleton

    依据 issue: 04-being-provider-migration（单例改用 LazySingleton）

    迁移前：being_provider = BeingProvider()（模块导入时立即实例化）
    迁移后：being_provider = LazySingleton(BeingProvider)（首次访问时才实例化）
    """

    def test_module_exports_lazy_singleton_instance(self):
        """模块应导出 LazySingleton 包裹的 being_provider 单例"""
        from lifeprism.repository.providers.being_provider import being_provider
        from lifeprism.utils import LazySingleton

        assert isinstance(being_provider, LazySingleton), (
            f"being_provider 应为 LazySingleton 实例，实际类型: "
            f"{type(being_provider).__name__}"
        )

    def test_lazy_singleton_proxies_method_calls(self, being_provider, sample_content):
        """LazySingleton 代理方法调用（首次访问时实例化 BeingProvider）"""
        # being_provider fixture 已经是 BeingProvider 实例（直接构造）
        # 这里验证 LazySingleton 单例也能正常工作
        from lifeprism.repository.providers.being_provider import being_provider as lazy_provider

        # 通过 LazySingleton 调用方法（首次访问触发实例化）
        latest = lazy_provider.get_latest_version(user_id=999, mode="past")
        assert latest == 0  # 空表返回 0
