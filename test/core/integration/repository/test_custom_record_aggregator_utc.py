"""
CustomRecordRepository UTC 时区迁移测试

验证 Issue #3: Repository 层各 Provider 迁移
测试 seam: CustomRecordRepository.create_type / create_entry / update_type_config

确保时间戳字段（created_at / updated_at）以 UTC ISO 8601 格式写入：
- custom_record_types 表的 created_at / updated_at
- custom_record_fields 表的 created_at
- 动态数据表（custom_<slug>）的 created_at / updated_at

注意：CustomRecordRepository 独立实现，不继承 LWBaseDataProvider（项目规则）。
"""
import re

import pytest

pytestmark = pytest.mark.core


# UTC ISO 8601 格式：2026-07-11T16:29:54.123456+00:00
UTC_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


@pytest.fixture
def repository(test_data_path):
    """创建 CustomRecordRepository 实例并初始化 meta 表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.aggregators.custom_record_aggregator import (
        CustomRecordRepository,
    )

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

    yield repo

    # 清理：删除所有 custom_ 开头的表
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        for table_name in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()


# ==================== create_type 测试 ====================


class TestCreateTypeUtcTimestamps:
    """测试 create_type 写入的 UTC 时间戳格式"""

    def test_type_created_at_is_utc_iso8601(self, repository):
        """custom_record_types.created_at 应为 UTC ISO 8601 格式"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {
                    "field_name": "锻炼内容",
                    "field_key": "exercise_content",
                    "field_type": "text",
                }
            ],
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            created_at = row[0]
            assert created_at is not None, "created_at 不应为 None"
            assert UTC_ISO_PATTERN.match(created_at), (
                f"created_at 应为 UTC ISO 8601 格式，实际: {created_at}"
            )

    def test_type_updated_at_is_utc_iso8601(self, repository):
        """custom_record_types.updated_at 应为 UTC ISO 8601 格式"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {
                    "field_name": "锻炼内容",
                    "field_key": "exercise_content",
                    "field_type": "text",
                }
            ],
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            updated_at = row[0]
            assert updated_at is not None, "updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )

    def test_field_created_at_is_utc_iso8601(self, repository):
        """custom_record_fields.created_at 应为 UTC ISO 8601 格式"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {
                    "field_name": "锻炼内容",
                    "field_key": "exercise_content",
                    "field_type": "text",
                }
            ],
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at FROM custom_record_fields WHERE type_id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            created_at = row[0]
            assert created_at is not None, "field created_at 不应为 None"
            assert UTC_ISO_PATTERN.match(created_at), (
                f"field created_at 应为 UTC ISO 8601 格式，实际: {created_at}"
            )


# ==================== create_entry 测试 ====================


class TestCreateEntryUtcTimestamps:
    """测试 create_entry 写入的 UTC 时间戳格式"""

    def test_entry_created_at_is_utc_iso8601(self, repository):
        """动态数据表的 created_at 应为 UTC ISO 8601 格式"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {
                    "field_name": "日期",
                    "field_key": "exercise_date",
                    "field_type": "text",
                },
                {
                    "field_name": "锻炼内容",
                    "field_key": "exercise_content",
                    "field_type": "text",
                },
            ],
        )

        entry_id = repository.create_entry(
            type_id=type_id,
            data={"exercise_date": "2026-07-07", "exercise_content": "跑步5公里"},
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at FROM custom_sport WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            created_at = row[0]
            assert created_at is not None, "entry created_at 不应为 None"
            assert UTC_ISO_PATTERN.match(created_at), (
                f"entry created_at 应为 UTC ISO 8601 格式，实际: {created_at}"
            )

    def test_entry_updated_at_is_utc_iso8601(self, repository):
        """动态数据表的 updated_at 应为 UTC ISO 8601 格式"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {
                    "field_name": "日期",
                    "field_key": "exercise_date",
                    "field_type": "text",
                },
                {
                    "field_name": "锻炼内容",
                    "field_key": "exercise_content",
                    "field_type": "text",
                },
            ],
        )

        entry_id = repository.create_entry(
            type_id=type_id,
            data={"exercise_date": "2026-07-07", "exercise_content": "跑步5公里"},
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM custom_sport WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            updated_at = row[0]
            assert updated_at is not None, "entry updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"entry updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )


# ==================== update_type_config 测试 ====================


class TestUpdateTypeConfigUtcTimestamps:
    """测试 update_type_config 写入的 UTC 时间戳格式"""

    def test_type_updated_at_is_utc_iso8601_after_config_update(self, repository):
        """update_type_config 后 custom_record_types.updated_at 应为 UTC ISO 8601 格式"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {
                    "field_name": "锻炼内容",
                    "field_key": "exercise_content",
                    "field_type": "text",
                }
            ],
        )

        # 执行配置更新
        repository.update_type_config(
            type_id=type_id,
            card_template="paper",
            icon="activity",
            accent_color="green",
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            updated_at = row[0]
            assert updated_at is not None, "updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )
