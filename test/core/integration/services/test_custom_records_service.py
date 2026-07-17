"""
CustomRecordService 集成测试

测试 seam: Service 层（直接调用 repository 单例，连接真实数据库）
参考: test/core/integration/repository/test_custom_records_repository.py
"""

import pytest

from lifeprism.repository.exceptions import EntityNotFoundError
from lifeprism.server.schemas.custom_records_schemas import (
    CreateCustomRecordEntryRequest,
    CreateCustomRecordTypeRequest,
    CustomRecordTypeItem,
    FieldDefinition,
)
from lifeprism.server.services import custom_records_service

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def setup_db(test_data_path):
    """初始化数据库 meta 表，测试后清理所有 custom_* 表

    Service 层直接调用 repository 单例（连接 lw_db_manager），
    因此需在单例所用的数据库上创建 meta 表。
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager

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

    yield

    # 清理：删除所有 custom_ 开头的表（含 meta 表与动态数据表）
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%'")
        tables = [row[0] for row in cursor.fetchall()]
        for table_name in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()


@pytest.fixture
def make_type(setup_db):
    """创建临时类型的工厂，返回 CustomRecordTypeItem"""

    def _make(
        name="体育活动",
        slug="sport",
        fields=None,
    ):
        if fields is None:
            fields = [
                FieldDefinition(
                    field_name="锻炼内容", field_key="exercise_content", field_type="text"
                )
            ]
        request = CreateCustomRecordTypeRequest(name=name, slug=slug, fields=fields)
        return custom_records_service.create_type(request)

    return _make


# ==================== get_type 测试 ====================


class TestGetType:
    """测试 custom_records_service.get_type()"""

    def test_get_type_raises_entity_not_found_for_nonexistent_type(self, make_type):
        """类型不存在：抛出 EntityNotFoundError（而非 TypeError）

        若 Service 层未对 repository.get_type_by_id 返回 None 做处理，
        直接访问 None 的字段会抛 TypeError。此测试验证 Service 层
        正确转换为 EntityNotFoundError。
        """
        with pytest.raises(EntityNotFoundError):
            custom_records_service.get_type("crt-nonexist")


# ==================== get_entries 测试 ====================


class TestGetEntries:
    """测试 custom_records_service.get_entries()"""

    def test_get_entries_returns_total_as_total_count_not_page_size(self, make_type):
        """get_entries 返回的 total 是满足筛选条件的总记录数，而非当前页条数"""
        # Arrange: 创建类型并录入 5 条记录
        type_item = make_type(
            name="体育活动",
            slug="sport",
            fields=[FieldDefinition(field_name="内容", field_key="content", field_type="text")],
        )
        for i in range(5):
            custom_records_service.create_entry(
                type_id=type_item.id,
                request=CreateCustomRecordEntryRequest(data={"content": f"记录{i}"}),
            )

        # Act: 第 1 页，每页 2 条
        response = custom_records_service.get_entries(type_id=type_item.id, page=1, page_size=2)

        # Assert: 当前页 2 条，total = 5（总记录数，不是当前页条数）
        assert len(response.items) == 2
        assert response.total == 5


# ==================== create_type 测试 ====================


class TestCreateType:
    """测试 custom_records_service.create_type()"""

    def test_create_type_returns_custom_record_type_item(self, make_type):
        """create_type 正常流程返回 CustomRecordTypeItem"""
        # Act
        item = make_type(
            name="阅读",
            slug="reading",
            fields=[
                FieldDefinition(field_name="书名", field_key="title", field_type="text"),
                FieldDefinition(field_name="笔记", field_key="notes", field_type="text"),
            ],
        )

        # Assert: 返回类型正确
        assert isinstance(item, CustomRecordTypeItem)
        assert item.id.startswith("crt-")
        assert item.name == "阅读"
        assert item.slug == "reading"
        assert len(item.fields) == 2
        field_keys = {f.field_key for f in item.fields}
        assert field_keys == {"title", "notes"}
        # 字段定义内容正确
        for f in item.fields:
            assert f.field_type == "text"
            assert f.display_role == "auto"
