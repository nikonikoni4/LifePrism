"""
L3 级联删除测试 - Custom Record（Slice 09 Sub-PR 2）

验证 CustomRecordRepository.delete_type 级联删除走 _generic_* 通道（含写墓碑）：

- custom_record_fields（在 SYNC_TABLES 中）：每条 field 记录都写墓碑
- custom_record_types（在 SYNC_TABLES 中）：type 记录写墓碑
- 动态表 custom_<slug>（不在 SYNC_TABLES 中）：DROP TABLE，不写墓碑

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


def _table_exists(db, table_name: str) -> bool:
    """检查表是否存在"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return cursor.fetchone() is not None


# ==================== Fixture ====================


@pytest.fixture
def custom_record_repository_fixture(test_data_path):
    """创建 CustomRecordRepository 实例并初始化 meta 表 + deletion_log 表"""
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
    _clear_tables(lw_db_manager, ["custom_record_types", "custom_record_fields", "deletion_log"])

    yield repo

    # 清理：删除动态数据表（custom_<slug>，排除 meta 表 custom_record_types/custom_record_fields）
    # + 清空 meta 表和 deletion_log 数据
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


# ==================== 测试类 ====================


class TestCustomRecordDeleteTypeCascade:
    """验证 CustomRecordRepository.delete_type 级联删除走 _generic_* 通道（含写墓碑）

    依据 issue: 09-l3-cascade-l4-service-sink
    custom_record_types 和 custom_record_fields 均在 SYNC_TABLES 中，
    墓碑 record_id = 主键值（TEXT 主键表）。
    动态表 custom_<slug> 不在 SYNC_TABLES 中，DROP TABLE 不写墓碑。
    """

    def test_delete_type_writes_tombstone_for_fields_and_type(
        self, custom_record_repository_fixture
    ):
        """delete_type 为 custom_record_fields（每条）和 custom_record_types 分别写墓碑"""
        repo = custom_record_repository_fixture

        # 创建类型（含 3 个字段）
        type_id = repo.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"},
                {"field_name": "时长", "field_key": "duration", "field_type": "integer"},
                {"field_name": "强度", "field_key": "intensity", "field_type": "float"},
            ],
        )

        # 查询 field_id 列表（用于后续墓碑验证）
        with repo.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM custom_record_fields WHERE type_id = ? ORDER BY sort_order",
                (type_id,),
            )
            field_ids = [row[0] for row in cursor.fetchall()]
        assert len(field_ids) == 3

        # 向动态表插入 2 条记录
        repo.create_entry(type_id, {"exercise_content": "跑步", "duration": 30, "intensity": 1.5})
        repo.create_entry(type_id, {"exercise_content": "游泳", "duration": 45, "intensity": 2.0})

        # 确认动态表存在
        assert _table_exists(repo.db, "custom_sport")

        # 删除类型
        result = repo.delete_type(type_id)
        assert result is True

        # 验证动态表已删除
        assert not _table_exists(repo.db, "custom_sport")

        # 验证 custom_record_types 记录已删除
        with repo.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM custom_record_types WHERE id = ?", (type_id,))
            assert cursor.fetchone()[0] == 0

        # 验证 custom_record_fields 记录已删除
        with repo.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM custom_record_fields WHERE type_id = ?", (type_id,)
            )
            assert cursor.fetchone()[0] == 0

        # 验证 custom_record_types 墓碑（1 条）
        assert _count_tombstones(repo.db, "custom_record_types") == 1
        type_tombstone = _get_tombstone(repo.db, "custom_record_types", type_id)
        assert type_tombstone is not None
        assert type_tombstone[1] == "custom_record_types"
        assert type_tombstone[2] == type_id
        assert type_tombstone[3] == "local"

        # 验证 custom_record_fields 墓碑（3 条，每个 field 一条）
        assert _count_tombstones(repo.db, "custom_record_fields") == 3
        for fid in field_ids:
            tombstone = _get_tombstone(repo.db, "custom_record_fields", fid)
            assert tombstone is not None, f"field_id '{fid}' 应有墓碑"
            assert tombstone[1] == "custom_record_fields"
            assert tombstone[2] == fid
            assert tombstone[3] == "local"

        # 验证动态表不写墓碑（不在 SYNC_TABLES 中）
        # 动态表的墓碑 target_table 应为 "custom_sport"，不应存在
        assert _count_tombstones(repo.db, "custom_sport") == 0

    def test_delete_type_nonexistent_raises_not_found(self, custom_record_repository_fixture):
        """删除不存在的类型抛出 EntityNotFoundError"""
        from lifeprism.repository.exceptions import EntityNotFoundError

        repo = custom_record_repository_fixture
        with pytest.raises(EntityNotFoundError):
            repo.delete_type("crt-nonexistent")

    def test_delete_type_no_fields_writes_only_type_tombstone(
        self, custom_record_repository_fixture
    ):
        """删除没有字段的类型只写 custom_record_types 墓碑

        虽然 create_type 要求至少 1 个字段，但直接构造数据测试边界：
        只插入 type 记录不插入 field 记录，验证 delete_type 仍正确写 type 墓碑。
        """
        from datetime import datetime, timezone

        repo = custom_record_repository_fixture

        # 直接插入一个无字段的类型（绕过 create_type 校验）
        type_id = "crt-no fields"
        now = datetime.now(timezone.utc).isoformat()
        with repo.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (type_id, "无字段类型", "no_fields", "", now, now),
            )
            # 不创建动态表也不插入字段
            conn.commit()

        # 删除类型
        result = repo.delete_type(type_id)
        assert result is True

        # 只有 custom_record_types 墓碑，无 custom_record_fields 墓碑
        assert _count_tombstones(repo.db, "custom_record_types") == 1
        assert _count_tombstones(repo.db, "custom_record_fields") == 0
