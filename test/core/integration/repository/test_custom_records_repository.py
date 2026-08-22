"""
CustomRecordRepository 集成测试

测试 seam: Repository 层
参考: test/core/unit/storage/test_base_provider_generic_methods.py
"""

import pytest

from lifeprism.repository.exceptions import DuplicateEntityError, EntityNotFoundError
from lifeprism.utils.exceptions import ValidationError

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


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
                updated_at TEXT,
                UNIQUE (type_id, field_key)
            )
        """
        )
        # 与生产 schema 对齐（m012 迁移后含 updated_at 列）：
        # 旧测试库的表由本 fixture 早期版本建出、缺 updated_at 列，
        # CREATE TABLE IF NOT EXISTS 不会补列，需显式 ALTER（模拟 m012）
        cursor.execute("PRAGMA table_info(custom_record_fields)")
        columns = {row[1] for row in cursor.fetchall()}
        if "updated_at" not in columns:
            cursor.execute("ALTER TABLE custom_record_fields ADD COLUMN updated_at TEXT")
        conn.commit()

    yield repo

    # 清理：删除所有动态表 + meta 表
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        # 查询所有 custom_ 开头的表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%'")
        tables = [row[0] for row in cursor.fetchall()]
        for table_name in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()


def _table_exists(db_manager, table_name: str) -> bool:
    """检查表是否存在"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return cursor.fetchone() is not None


# ==================== 创建类型测试 ====================


class TestCreateType:
    """测试 create_type() 方法"""

    def test_create_type_returns_type_id_and_creates_meta_and_data_table(self, repository):
        """创建类型：返回 type_id，meta 表有记录，数据表存在"""
        # Act
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

        # Assert: type_id 格式
        assert type_id.startswith("crt-")
        assert len(type_id) == 12  # crt- + 8 位 hex

        # Assert: custom_record_types 表有记录
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, slug FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == type_id
            assert row[1] == "体育活动"
            assert row[2] == "sport"

            # Assert: custom_record_fields 表有字段记录
            cursor.execute(
                "SELECT type_id, field_name, field_key, field_type, sort_order "
                "FROM custom_record_fields WHERE type_id = ?",
                (type_id,),
            )
            field_rows = cursor.fetchall()
            assert len(field_rows) == 1
            assert field_rows[0][0] == type_id
            assert field_rows[0][1] == "锻炼内容"
            assert field_rows[0][2] == "exercise_content"
            assert field_rows[0][3] == "text"
            assert field_rows[0][4] == 0  # 默认 sort_order

        # Assert: 数据表 custom_sport 存在
        assert _table_exists(repository.db, "custom_sport")

        # Assert: 数据表结构包含 id, exercise_content, created_at, updated_at
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_sport)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "id" in columns
            assert "exercise_content" in columns
            assert "created_at" in columns
            assert "updated_at" in columns


# ==================== 列出类型测试 ====================


class TestListTypes:
    """测试 list_types() 方法"""

    def test_list_types_returns_all_types_with_fields(self, repository):
        """列出类型：返回所有类型（含 fields）"""
        # Arrange: 创建 2 个类型
        type_id_1 = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )
        type_id_2 = repository.create_type(
            name="每日饮食",
            slug="diet",
            fields=[
                {"field_name": "食物", "field_key": "food", "field_type": "text"},
                {"field_name": "分量", "field_key": "portion", "field_type": "text"},
            ],
        )

        # Act
        types = repository.list_types()

        # Assert
        assert len(types) == 2
        type_map = {t["id"]: t for t in types}

        # 类型 1
        t1 = type_map[type_id_1]
        assert t1["name"] == "体育活动"
        assert t1["slug"] == "sport"
        assert len(t1["fields"]) == 1
        assert t1["fields"][0]["field_key"] == "exercise_content"
        assert t1["fields"][0]["field_name"] == "锻炼内容"

        # 类型 2
        t2 = type_map[type_id_2]
        assert t2["name"] == "每日饮食"
        assert t2["slug"] == "diet"
        assert len(t2["fields"]) == 2
        field_keys = {f["field_key"] for f in t2["fields"]}
        assert field_keys == {"food", "portion"}


# ==================== 获取类型详情测试 ====================


class TestGetTypeById:
    """测试 get_type_by_id() 和 get_type_fields() 方法"""

    def test_get_type_by_id_returns_type_with_fields(self, repository):
        """获取类型详情：返回类型含 fields"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "日期", "field_key": "exercise_date", "field_type": "text"},
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"},
            ],
        )

        t = repository.get_type_by_id(type_id)
        assert t is not None
        assert t["id"] == type_id
        assert t["name"] == "体育活动"
        assert t["slug"] == "sport"
        assert len(t["fields"]) == 2
        assert t["fields"][0]["field_key"] == "exercise_date"
        assert t["fields"][1]["field_key"] == "exercise_content"

    def test_get_type_by_id_returns_none_for_nonexistent(self, repository):
        """获取不存在的类型：返回 None"""
        assert repository.get_type_by_id("crt-nonexist") is None

    def test_get_type_fields_returns_fields_list(self, repository):
        """获取字段定义：返回字段列表"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )

        fields = repository.get_type_fields(type_id)
        assert len(fields) == 1
        assert fields[0]["field_key"] == "exercise_content"
        assert fields[0]["field_name"] == "锻炼内容"


# ==================== 校验测试 ====================


class TestValidation:
    """测试 slug/field_key/fields 校验"""

    def test_create_type_with_duplicate_slug_raises_duplicate_entity_error(self, repository):
        """slug 冲突：抛 DuplicateEntityError"""
        repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        with pytest.raises(DuplicateEntityError):
            repository.create_type(
                name="运动",
                slug="sport",
                fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
            )

    def test_create_type_with_invalid_slug_format_raises_validation_error(self, repository):
        """slug 格式错误：抛 ValidationError"""
        with pytest.raises(ValidationError, match="slug"):
            repository.create_type(
                name="体育活动",
                slug="Sport-Activity",
                fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
            )

    def test_create_type_with_invalid_field_key_format_raises_validation_error(self, repository):
        """field_key 格式错误：抛 ValidationError"""
        with pytest.raises(ValidationError, match="field_key"):
            repository.create_type(
                name="体育活动",
                slug="sport",
                fields=[{"field_name": "内容", "field_key": "Wrong-Key", "field_type": "text"}],
            )

    def test_create_type_with_duplicate_field_keys_raises_validation_error(self, repository):
        """field_key 同类型重复：抛 ValidationError"""
        with pytest.raises(ValidationError, match="重复"):
            repository.create_type(
                name="体育活动",
                slug="sport",
                fields=[
                    {"field_name": "内容1", "field_key": "content", "field_type": "text"},
                    {"field_name": "内容2", "field_key": "content", "field_type": "text"},
                ],
            )

    def test_create_type_with_empty_fields_raises_validation_error(self, repository):
        """fields 为空：抛 ValidationError"""
        with pytest.raises(ValidationError, match="fields"):
            repository.create_type(name="空类型", slug="empty", fields=[])


# ==================== 删除类型测试 ====================


class TestDeleteType:
    """测试 delete_type() 方法"""

    def test_delete_type_drops_data_table_and_removes_meta(self, repository):
        """硬删类型：DROP 数据表 + 删除 meta 记录"""
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )

        # 确认表存在
        assert _table_exists(repository.db, "custom_sport")

        # 删除
        repository.delete_type(type_id)

        # 确认数据表已 DROP
        assert not _table_exists(repository.db, "custom_sport")

        # 确认 meta 表记录已删除
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM custom_record_types WHERE id = ?", (type_id,))
            assert cursor.fetchone() is None
            cursor.execute("SELECT id FROM custom_record_fields WHERE type_id = ?", (type_id,))
            assert cursor.fetchone() is None


# ==================== 录入记录测试 ====================


class TestCreateEntry:
    """测试 create_entry() 方法"""

    def test_create_entry_returns_entry_id_and_persists_data(self, repository):
        """录入记录：返回 entry_id，数据表有记录且字段值正确"""
        # Arrange: 创建类型
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "日期", "field_key": "exercise_date", "field_type": "text"},
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"},
            ],
        )

        # Act
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"exercise_date": "2026-07-07", "exercise_content": "跑步5公里"},
        )

        # Assert: entry_id 格式
        assert entry_id.startswith("cre-")

        # Assert: 数据表有记录
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, exercise_date, exercise_content FROM custom_sport WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == entry_id
            assert row[1] == "2026-07-07"
            assert row[2] == "跑步5公里"

    def test_create_entry_with_wrong_field_key_raises_validation_error_with_valid_fields(
        self, repository
    ):
        """录入时 field_key 错误：抛 ValidationError 且 details 含 valid_fields"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "日期", "field_key": "exercise_date", "field_type": "text"},
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"},
            ],
        )

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            repository.create_entry(
                type_id=type_id,
                data={"wrong_field": "值"},
            )

        # Assert: details 含 valid_fields
        details = exc_info.value.details
        assert "valid_fields" in details
        valid_fields = details["valid_fields"]
        assert len(valid_fields) == 2
        field_keys = {f["field_key"] for f in valid_fields}
        assert field_keys == {"exercise_date", "exercise_content"}
        # valid_fields 每项含 field_key + field_name
        for f in valid_fields:
            assert "field_key" in f
            assert "field_name" in f

    def test_create_entry_with_partial_data_persists_missing_as_null(self, repository):
        """录入时字段缺失：落库成功，缺失字段为 NULL"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "日期", "field_key": "exercise_date", "field_type": "text"},
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"},
            ],
        )

        # Act: 只传一个字段
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"exercise_content": "跑步5公里"},
        )

        # Assert: 落库成功，缺失字段为 NULL
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT exercise_date, exercise_content FROM custom_sport WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] is None  # exercise_date 缺失 → NULL
            assert row[1] == "跑步5公里"

    def test_create_entry_with_empty_data_succeeds(self, repository):
        """录入时 data 为空字典：落库成功"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )

        # Act
        entry_id = repository.create_entry(type_id=type_id, data={})

        # Assert: 落库成功
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM custom_sport WHERE id = ?", (entry_id,))
            assert cursor.fetchone() is not None


# ==================== 查询记录测试 ====================


def _set_event_time(db_manager, table: str, entry_id: str, event_time: str):
    """用直接 SQL 设置 event_time（避免真实 UTC ISO 计算），同时同步 created_at"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {table} SET event_time = ?, created_at = ? WHERE id = ?",
            (event_time, event_time, entry_id),
        )
        conn.commit()


class TestQueryEntries:
    """测试 query_entries() 方法"""

    def test_query_entries_with_date_range_returns_correct_subset(self, repository):
        """查询记录（时间范围筛选）：返回正确子集（date_range 过滤 event_time）"""
        # Arrange: 创建类型并录入 3 条记录
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eid1 = repository.create_entry(type_id=type_id, data={"content": "7月1日"})
        eid2 = repository.create_entry(type_id=type_id, data={"content": "7月5日"})
        eid3 = repository.create_entry(type_id=type_id, data={"content": "7月10日"})
        # 用直接 SQL 设置不同的 event_time（UTC ISO 格式）
        _set_event_time(repository.db, "custom_sport", eid1, "2026-07-01T10:00:00+00:00")
        _set_event_time(repository.db, "custom_sport", eid2, "2026-07-05T10:00:00+00:00")
        _set_event_time(repository.db, "custom_sport", eid3, "2026-07-10T10:00:00+00:00")

        # Act: 查询 7月3日~7月8日 的记录（UTC 时间范围）
        entries, total_count = repository.query_entries(
            type_id=type_id,
            date_range=("2026-07-03T00:00:00+00:00", "2026-07-08T23:59:59+00:00"),
        )

        # Assert: 只返回 7月5日 的记录
        assert len(entries) == 1
        assert entries[0]["content"] == "7月5日"
        assert total_count == 1

    def test_query_entries_with_only_start_date(self, repository):
        """date_range 单侧缺失（只有 start）：查询正常，start 侧加约束"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eid1 = repository.create_entry(type_id=type_id, data={"content": "7月1日"})
        eid2 = repository.create_entry(type_id=type_id, data={"content": "7月10日"})
        eid3 = repository.create_entry(type_id=type_id, data={"content": "7月20日"})
        _set_event_time(repository.db, "custom_sport", eid1, "2026-07-01T10:00:00+00:00")
        _set_event_time(repository.db, "custom_sport", eid2, "2026-07-10T10:00:00+00:00")
        _set_event_time(repository.db, "custom_sport", eid3, "2026-07-20T10:00:00+00:00")

        # Act: 只传 start
        entries, total_count = repository.query_entries(
            type_id=type_id,
            date_range=("2026-07-05T00:00:00+00:00", None),
        )

        # Assert: 返回 7月10日 + 7月20日
        assert len(entries) == 2
        dates = {e["content"] for e in entries}
        assert dates == {"7月10日", "7月20日"}
        assert total_count == 2

    def test_query_entries_with_only_end_date(self, repository):
        """date_range 单侧缺失（只有 end）：查询正常，end 侧加约束"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eid1 = repository.create_entry(type_id=type_id, data={"content": "7月1日"})
        eid2 = repository.create_entry(type_id=type_id, data={"content": "7月10日"})
        eid3 = repository.create_entry(type_id=type_id, data={"content": "7月20日"})
        _set_event_time(repository.db, "custom_sport", eid1, "2026-07-01T10:00:00+00:00")
        _set_event_time(repository.db, "custom_sport", eid2, "2026-07-10T10:00:00+00:00")
        _set_event_time(repository.db, "custom_sport", eid3, "2026-07-20T10:00:00+00:00")

        # Act: 只传 end
        entries, total_count = repository.query_entries(
            type_id=type_id,
            date_range=(None, "2026-07-15T23:59:59+00:00"),
        )

        # Assert: 返回 7月1日 + 7月10日
        assert len(entries) == 2
        dates = {e["content"] for e in entries}
        assert dates == {"7月1日", "7月10日"}
        assert total_count == 2

    def test_query_entries_pagination(self, repository):
        """查询分页：page/page_size 生效"""
        # Arrange: 录入 5 条记录，设置不同 event_time 以保证排序稳定
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eids = []
        for day in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]:
            eid = repository.create_entry(type_id=type_id, data={"content": day})
            eids.append(eid)
            _set_event_time(repository.db, "custom_sport", eid, f"{day}T10:00:00+00:00")

        # Act: 第 1 页，每页 2 条
        page1, total1 = repository.query_entries(
            type_id=type_id, date_range=None, page=1, page_size=2
        )
        page2, total2 = repository.query_entries(
            type_id=type_id, date_range=None, page=2, page_size=2
        )

        # Assert: 每页 2 条，且按 event_time DESC 排序（7月5日、7月4日在 page1）
        assert len(page1) == 2
        assert len(page2) == 2
        assert total1 == 5  # 总记录数始终为 5
        assert total2 == 5
        dates_page1 = {e["content"] for e in page1}
        assert dates_page1 == {"2026-07-05", "2026-07-04"}
        dates_page2 = {e["content"] for e in page2}
        assert dates_page2 == {"2026-07-03", "2026-07-02"}

    def test_query_entries_returns_empty_for_no_match(self, repository):
        """查询无结果：返回空列表"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eid = repository.create_entry(type_id=type_id, data={"content": "7月1日"})
        _set_event_time(repository.db, "custom_sport", eid, "2026-07-01T10:00:00+00:00")

        # Act: 查询一个没有记录的日期范围（UTC）
        entries, total_count = repository.query_entries(
            type_id=type_id,
            date_range=("2026-08-01T00:00:00+00:00", "2026-08-31T23:59:59+00:00"),
        )

        # Assert
        assert entries == []
        assert total_count == 0


# ==================== 获取单条记录测试 ====================


class TestGetEntry:
    """测试 get_entry() 方法"""

    def test_get_entry_returns_record(self, repository):
        """获取单条记录：返回正确数据"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )
        entry_id = repository.create_entry(type_id=type_id, data={"exercise_content": "跑步5公里"})

        # Act
        entry = repository.get_entry(type_id=type_id, entry_id=entry_id)

        # Assert
        assert entry is not None
        assert entry["id"] == entry_id
        assert entry["exercise_content"] == "跑步5公里"

    def test_get_entry_returns_none_for_nonexistent(self, repository):
        """获取不存在的记录：返回 None"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )

        # Act
        entry = repository.get_entry(type_id=type_id, entry_id="cre-nonexist")

        # Assert
        assert entry is None


# ==================== 删除记录测试 ====================


class TestDeleteEntry:
    """测试 delete_entry() 方法"""

    def test_delete_entry_removes_record_from_data_table(self, repository):
        """删除记录：从数据表删除"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )
        entry_id = repository.create_entry(type_id=type_id, data={"exercise_content": "跑步5公里"})

        # Act
        repository.delete_entry(type_id=type_id, entry_id=entry_id)

        # Assert: 数据表无此记录
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM custom_sport WHERE id = ?", (entry_id,))
            assert cursor.fetchone() is None

    def test_delete_entry_raises_entity_not_found_for_nonexistent_entry(self, repository):
        """删除不存在的记录：抛 EntityNotFoundError（而非静默返回 200）"""
        # Arrange: 创建类型但不录入记录
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}
            ],
        )

        # Act + Assert: 删除不存在的 entry 应抛 EntityNotFoundError
        with pytest.raises(EntityNotFoundError):
            repository.delete_entry(type_id=type_id, entry_id="cre-nonexist")


# ==================== 更新类型配置测试 (Slice 6) ====================


class TestUpdateTypeConfig:
    """测试 update_type_config() 方法（Slice 6 新增）"""

    def test_update_type_config_persists_card_template_icon_accent(self, repository):
        """更新类型配置：card_template/icon/accent_color 持久化到数据库"""
        type_id = repository.create_type(
            name="阅读",
            slug="reading_cfg_test",
            fields=[{"field_name": "书名", "field_key": "title", "field_type": "text"}],
        )

        repository.update_type_config(
            type_id=type_id,
            card_template="paper",
            icon="book",
            accent_color="amber",
        )

        # Assert: 数据库中有新值
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT card_template, icon, accent_color FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "paper"
            assert row[1] == "book"
            assert row[2] == "amber"

    def test_update_type_config_with_partial_fields_only_updates_provided(self, repository):
        """部分更新：只传 card_template，icon 和 accent_color 不变"""
        type_id = repository.create_type(
            name="阅读",
            slug="reading_s6",
            fields=[{"field_name": "书名", "field_key": "title", "field_type": "text"}],
        )

        # 先设全部
        repository.update_type_config(
            type_id=type_id, card_template="bold", icon="zap", accent_color="rose"
        )
        # 再只更新 card_template
        repository.update_type_config(
            type_id=type_id, card_template="minimal", icon=None, accent_color=None
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT card_template, icon, accent_color FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "minimal"  # 更新了
            assert row[1] == "zap"  # 未变
            assert row[2] == "rose"  # 未变

    def test_update_type_config_raises_entity_not_found_for_nonexistent(self, repository):
        """更新不存在的类型：抛 EntityNotFoundError"""
        with pytest.raises(EntityNotFoundError):
            repository.update_type_config(
                type_id="crt-nonexist", card_template="paper", icon=None, accent_color=None
            )

    def test_list_types_returns_config_fields_with_defaults(self, repository):
        """list_types 返回的配置字段有 DEFAULT 值"""
        repository.create_type(
            name="阅读",
            slug="reading_s6",
            fields=[{"field_name": "书名", "field_key": "title", "field_type": "text"}],
        )

        types = repository.list_types()
        t = types[0]
        assert t["card_template"] == "clean"  # DEFAULT
        assert t["icon"] == "fileText"  # DEFAULT
        assert t["accent_color"] == "blue"  # DEFAULT


class TestUpdateFieldRole:
    """测试 update_field_role() 方法（Slice 6 新增）"""

    def test_update_field_role_persists_display_role(self, repository):
        """更新字段角色：display_role 持久化"""
        type_id = repository.create_type(
            name="阅读",
            slug="reading_s6",
            fields=[
                {"field_name": "书名", "field_key": "title", "field_type": "text"},
                {"field_name": "笔记", "field_key": "notes", "field_type": "text"},
            ],
        )

        # 获取 field_id
        fields = repository.get_type_fields(type_id)
        field_id = None
        for f in fields:
            if f["field_key"] == "notes":
                field_id = f["id"]
                break
        assert field_id is not None

        repository.update_field_role(type_id=type_id, field_id=field_id, display_role="main")

        # Assert
        fields_after = repository.get_type_fields(type_id)
        notes_field = next(f for f in fields_after if f["field_key"] == "notes")
        assert notes_field["display_role"] == "main"

    def test_update_field_role_defaults_to_auto(self, repository):
        """新建字段默认 display_role = 'auto'"""
        type_id = repository.create_type(
            name="阅读",
            slug="reading_s6",
            fields=[{"field_name": "书名", "field_key": "title", "field_type": "text"}],
        )

        fields = repository.get_type_fields(type_id)
        assert fields[0]["display_role"] == "auto"

    def test_update_field_role_raises_entity_not_found_for_nonexistent_field(self, repository):
        """更新不存在的字段：抛 EntityNotFoundError"""
        type_id = repository.create_type(
            name="阅读",
            slug="reading_s6",
            fields=[{"field_name": "书名", "field_key": "title", "field_type": "text"}],
        )

        with pytest.raises(EntityNotFoundError):
            repository.update_field_role(
                type_id=type_id, field_id="crf-nonexist", display_role="hidden"
            )


# ==================== P2: 数值字段类型测试 ====================


class TestCreateTypeWithNumericFields:
    """P2: 测试 create_type() 对 integer/float 字段类型的 DDL 列类型映射"""

    def test_create_type_with_integer_field_creates_integer_column(self, repository):
        """创建含 integer 字段的类型：DDL 列类型应为 INTEGER"""
        type_id = repository.create_type(
            name="步数记录",
            slug="step_count",
            fields=[
                {"field_name": "步数", "field_key": "steps", "field_type": "integer"},
            ],
        )

        # Assert: 数据表存在
        assert _table_exists(repository.db, "custom_step_count")

        # Assert: steps 列类型为 INTEGER
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_step_count)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            assert "steps" in columns
            assert columns["steps"].upper() == "INTEGER"

    def test_create_type_with_float_field_creates_real_column(self, repository):
        """创建含 float 字段的类型：DDL 列类型应为 REAL"""
        type_id = repository.create_type(
            name="体重记录",
            slug="body_weight",
            fields=[
                {"field_name": "体重(kg)", "field_key": "weight", "field_type": "float"},
            ],
        )

        # Assert: 数据表存在
        assert _table_exists(repository.db, "custom_body_weight")

        # Assert: weight 列类型为 REAL
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_body_weight)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            assert "weight" in columns
            assert columns["weight"].upper() == "REAL"

    def test_create_type_with_mixed_field_types_creates_correct_columns(self, repository):
        """创建含混合字段类型的类型：各列类型正确映射"""
        repository.create_type(
            name="运动记录",
            slug="mixed_sport",
            fields=[
                {"field_name": "内容", "field_key": "content", "field_type": "text"},
                {"field_name": "次数", "field_key": "count", "field_type": "integer"},
                {"field_name": "里程(km)", "field_key": "distance", "field_type": "float"},
            ],
        )

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_mixed_sport)")
            columns = {row[1]: row[2].upper() for row in cursor.fetchall()}
            assert columns["content"] == "TEXT"
            assert columns["count"] == "INTEGER"
            assert columns["distance"] == "REAL"

    def test_create_type_with_unknown_field_type_raises_validation_error(self, repository):
        """未知 field_type：抛 ValidationError(code=INVALID_FIELD_TYPE)"""
        with pytest.raises(ValidationError) as exc_info:
            repository.create_type(
                name="错误类型",
                slug="bad_type",
                fields=[
                    {"field_name": "字段", "field_key": "field", "field_type": "boolean"},
                ],
            )
        assert exc_info.value.code == "INVALID_FIELD_TYPE"


# ==================== P2: 数值字段录入校验测试 ====================


class TestCreateEntryWithNumericFields:
    """P2: 测试 create_entry() 对 integer/float 字段值的类型校验"""

    def test_create_entry_with_integer_int_value_persists(self, repository):
        """录入 integer 字段正确 int 值：落库成功"""
        type_id = repository.create_type(
            name="步数记录",
            slug="step_int",
            fields=[{"field_name": "步数", "field_key": "steps", "field_type": "integer"}],
        )

        entry_id = repository.create_entry(type_id=type_id, data={"steps": 5})

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT steps FROM custom_step_int WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 5

    def test_create_entry_with_integer_numeric_string_persists(self, repository):
        """录入 integer 字段字符串数字 "5"：落库成功，存储为 int 5"""
        type_id = repository.create_type(
            name="步数记录",
            slug="step_str",
            fields=[{"field_name": "步数", "field_key": "steps", "field_type": "integer"}],
        )

        entry_id = repository.create_entry(type_id=type_id, data={"steps": "5"})

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT steps FROM custom_step_str WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 5

    def test_create_entry_with_integer_non_numeric_string_raises(self, repository):
        """录入 integer 字段非数值字符串 "abc"：抛 ValidationError(code=INVALID_FIELD_VALUE)"""
        type_id = repository.create_type(
            name="步数记录",
            slug="step_bad",
            fields=[{"field_name": "步数", "field_key": "steps", "field_type": "integer"}],
        )

        with pytest.raises(ValidationError) as exc_info:
            repository.create_entry(type_id=type_id, data={"steps": "abc"})

        assert exc_info.value.code == "INVALID_FIELD_VALUE"
        details = exc_info.value.details
        assert "invalid_fields" in details
        assert len(details["invalid_fields"]) == 1
        assert details["invalid_fields"][0]["field_key"] == "steps"
        assert details["invalid_fields"][0]["expected_type"] == "integer"
        assert "valid_fields" in details

    def test_create_entry_with_integer_float_string_raises(self, repository):
        """录入 integer 字段浮点字符串 "5.5"：抛 ValidationError(code=INVALID_FIELD_VALUE)"""
        type_id = repository.create_type(
            name="步数记录",
            slug="step_float_str",
            fields=[{"field_name": "步数", "field_key": "steps", "field_type": "integer"}],
        )

        with pytest.raises(ValidationError) as exc_info:
            repository.create_entry(type_id=type_id, data={"steps": "5.5"})

        assert exc_info.value.code == "INVALID_FIELD_VALUE"

    def test_create_entry_with_float_float_value_persists(self, repository):
        """录入 float 字段正确 float 值：落库成功"""
        type_id = repository.create_type(
            name="体重记录",
            slug="weight_float",
            fields=[{"field_name": "体重(kg)", "field_key": "weight", "field_type": "float"}],
        )

        entry_id = repository.create_entry(type_id=type_id, data={"weight": 65.5})

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT weight FROM custom_weight_float WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 65.5

    def test_create_entry_with_float_int_value_persists_as_float(self, repository):
        """录入 float 字段 int 值：落库成功，存储为 float"""
        type_id = repository.create_type(
            name="体重记录",
            slug="weight_int",
            fields=[{"field_name": "体重(kg)", "field_key": "weight", "field_type": "float"}],
        )

        entry_id = repository.create_entry(type_id=type_id, data={"weight": 70})

        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT weight FROM custom_weight_int WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 70.0  # int 70 被转为 float 70.0

    def test_create_entry_with_float_non_numeric_string_raises(self, repository):
        """录入 float 字段非数值字符串 "abc"：抛 ValidationError(code=INVALID_FIELD_VALUE)"""
        type_id = repository.create_type(
            name="体重记录",
            slug="weight_bad",
            fields=[{"field_name": "体重(kg)", "field_key": "weight", "field_type": "float"}],
        )

        with pytest.raises(ValidationError) as exc_info:
            repository.create_entry(type_id=type_id, data={"weight": "abc"})

        assert exc_info.value.code == "INVALID_FIELD_VALUE"


# ==================== P2: 查询返回值类型保留测试 ====================


class TestQueryEntriesNumericTypePreservation:
    """P2: 测试 query_entries() / get_entry() 返回的数值字段保留原始类型"""

    def test_query_entries_returns_integer_field_as_int(self, repository):
        """查询 integer 字段：返回值为 Python int 类型"""
        type_id = repository.create_type(
            name="步数记录",
            slug="step_query",
            fields=[{"field_name": "步数", "field_key": "steps", "field_type": "integer"}],
        )
        repository.create_entry(type_id=type_id, data={"steps": 5})

        entries, _ = repository.query_entries(type_id=type_id, date_range=None)

        assert len(entries) == 1
        assert entries[0]["steps"] == 5
        assert isinstance(entries[0]["steps"], int)

    def test_query_entries_returns_float_field_as_float(self, repository):
        """查询 float 字段：返回值为 Python float 类型"""
        type_id = repository.create_type(
            name="体重记录",
            slug="weight_query",
            fields=[{"field_name": "体重(kg)", "field_key": "weight", "field_type": "float"}],
        )
        repository.create_entry(type_id=type_id, data={"weight": 65.5})

        entries, _ = repository.query_entries(type_id=type_id, date_range=None)

        assert len(entries) == 1
        assert entries[0]["weight"] == 65.5
        assert isinstance(entries[0]["weight"], float)

    def test_get_entry_returns_integer_and_float_with_correct_types(self, repository):
        """get_entry 返回的 integer/float 字段类型正确"""
        type_id = repository.create_type(
            name="运动记录",
            slug="mixed_query",
            fields=[
                {"field_name": "内容", "field_key": "content", "field_type": "text"},
                {"field_name": "次数", "field_key": "count", "field_type": "integer"},
                {"field_name": "里程(km)", "field_key": "distance", "field_type": "float"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"content": "跑步", "count": 3, "distance": 5.2},
        )

        entry = repository.get_entry(type_id=type_id, entry_id=entry_id)
        assert entry is not None
        assert entry["content"] == "跑步"
        assert isinstance(entry["content"], str)
        assert entry["count"] == 3
        assert isinstance(entry["count"], int)
        assert entry["distance"] == 5.2
        assert isinstance(entry["distance"], float)


# ==================== P2: text 字段回归测试 ====================


class TestTextFieldRegression:
    """P2: 确保 text 字段行为与 P1 一致（_coerce_field_value 的 text 分支不破坏现有行为）"""

    def test_text_field_accepts_string_value(self, repository):
        """text 字段接受字符串值：落库成功，查询返回 str"""
        type_id = repository.create_type(
            name="阅读",
            slug="reading_regression",
            fields=[{"field_name": "书名", "field_key": "title", "field_type": "text"}],
        )
        repository.create_entry(type_id=type_id, data={"title": "三体"})

        entries, _ = repository.query_entries(type_id=type_id, date_range=None)
        assert len(entries) == 1
        assert entries[0]["title"] == "三体"
        assert isinstance(entries[0]["title"], str)

    def test_text_field_coerces_int_to_string(self, repository):
        """text 字段接受 int 值：转为字符串存储（保持 P1 行为）"""
        type_id = repository.create_type(
            name="笔记",
            slug="note_regression",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        repository.create_entry(type_id=type_id, data={"content": 123})

        entries, _ = repository.query_entries(type_id=type_id, date_range=None)
        assert len(entries) == 1
        assert entries[0]["content"] == "123"
        assert isinstance(entries[0]["content"], str)

    def test_text_field_with_explicit_field_type_text_works(self, repository):
        """显式声明 field_type='text'：行为与 P1 默认一致"""
        type_id = repository.create_type(
            name="日记",
            slug="diary_regression",
            fields=[
                {"field_name": "标题", "field_key": "title", "field_type": "text"},
                {"field_name": "正文", "field_key": "body", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id, data={"title": "今日", "body": "天气晴"}
        )

        entry = repository.get_entry(type_id=type_id, entry_id=entry_id)
        assert entry is not None
        assert entry["title"] == "今日"
        assert entry["body"] == "天气晴"

    def test_text_field_default_field_type_works(self, repository):
        """field_type 缺省时默认为 text：DDL 列为 TEXT，行为与 P1 一致"""
        type_id = repository.create_type(
            name="默认字段类型",
            slug="default_ftype",
            fields=[
                {"field_name": "字段", "field_key": "field"}  # 不传 field_type
            ],
        )

        # DDL 列应为 TEXT
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(custom_default_ftype)")
            columns = {row[1]: row[2].upper() for row in cursor.fetchall()}
            assert columns["field"] == "TEXT"

        # 录入正常
        repository.create_entry(type_id=type_id, data={"field": "值"})


# ==================== 字段级过滤测试（2026-08-18 新增） ====================


class TestQueryEntriesFieldFilters:
    """测试 query_entries() 的 filters 字段级过滤"""

    def _setup_sport_type(self, repository):
        """创建含 text/integer/float 三种字段类型的运动记录类型，录入 4 条记录"""
        type_id = repository.create_type(
            name="运动记录",
            slug="filter_sport",
            fields=[
                {"field_name": "内容", "field_key": "content", "field_type": "text"},
                {"field_name": "心率(bpm)", "field_key": "heart_rate", "field_type": "integer"},
                {"field_name": "里程(km)", "field_key": "distance", "field_type": "float"},
            ],
        )
        repository.create_entry(
            type_id=type_id, data={"content": "晨跑", "heart_rate": 120, "distance": 5.0}
        )
        repository.create_entry(
            type_id=type_id, data={"content": "夜跑", "heart_rate": 150, "distance": 8.5}
        )
        repository.create_entry(
            type_id=type_id, data={"content": "游泳", "heart_rate": 110, "distance": 1.0}
        )
        repository.create_entry(
            type_id=type_id, data={"content": "完成100%计划", "heart_rate": 100, "distance": 2.0}
        )
        return type_id

    def test_filter_eq_integer(self, repository):
        """eq 过滤 integer 字段：只返回精确匹配的记录"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "heart_rate", "op": "eq", "value": 120}]
        )
        assert total == 1
        assert entries[0]["content"] == "晨跑"

    def test_filter_gt_integer(self, repository):
        """gt 过滤 integer 字段：返回大于阈值的记录"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "heart_rate", "op": "gt", "value": 120}]
        )
        assert total == 1
        assert entries[0]["content"] == "夜跑"

    def test_filter_gte_float_with_numeric_string(self, repository):
        """gte 过滤 float 字段：数值字符串自动转换后比较"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "distance", "op": "gte", "value": "8.5"}]
        )
        assert total == 1
        assert entries[0]["content"] == "夜跑"

    def test_filter_lt_float(self, repository):
        """lt 过滤 float 字段"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "distance", "op": "lt", "value": 2.0}]
        )
        assert total == 1
        assert entries[0]["content"] == "游泳"

    def test_filter_contains_text(self, repository):
        """contains 过滤 text 字段：模糊包含匹配"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "content", "op": "contains", "value": "跑"}]
        )
        assert total == 2
        assert {e["content"] for e in entries} == {"晨跑", "夜跑"}

    def test_filter_contains_escapes_like_wildcards(self, repository):
        """contains 值含 % 通配符：按字面匹配而非通配（ESCAPE 转义生效）"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "content", "op": "contains", "value": "%"}]
        )
        # 未转义时 % 会匹配所有 4 条；转义后只匹配字面含 % 的 1 条
        assert total == 1
        assert entries[0]["content"] == "完成100%计划"

    def test_filter_in_text(self, repository):
        """in 过滤 text 字段：命中列表中的任意值"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id,
            filters=[{"field_key": "content", "op": "in", "value": ["晨跑", "游泳"]}],
        )
        assert total == 2
        assert {e["content"] for e in entries} == {"晨跑", "游泳"}

    def test_filter_ne_integer(self, repository):
        """ne 过滤 integer 字段"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id, filters=[{"field_key": "heart_rate", "op": "ne", "value": 120}]
        )
        assert total == 3
        assert "晨跑" not in {e["content"] for e in entries}

    def test_filter_multiple_conditions_are_and(self, repository):
        """多条件组合：AND 语义"""
        type_id = self._setup_sport_type(repository)
        entries, total = repository.query_entries(
            type_id=type_id,
            filters=[
                {"field_key": "heart_rate", "op": "gte", "value": 110},
                {"field_key": "content", "op": "contains", "value": "跑"},
            ],
        )
        assert total == 2
        assert {e["content"] for e in entries} == {"晨跑", "夜跑"}

    def test_filter_combined_with_date_range(self, repository):
        """filters 与 date_range 组合：AND 语义"""
        type_id = self._setup_sport_type(repository)
        # 时间范围限定后 2 条记录（相对其余靠后创建），再叠加数值过滤
        all_entries, _ = repository.query_entries(type_id=type_id)
        event_times = sorted(e["event_time"] for e in all_entries)
        mid_time = event_times[2]  # 只保留时间最靠后的 2 条
        entries, total = repository.query_entries(
            type_id=type_id,
            date_range=(mid_time, None),
            filters=[{"field_key": "heart_rate", "op": "lt", "value": 105}],
        )
        # 靠后的 2 条为「游泳(110)」「完成100%计划(100)」，lt 105 只命中后者
        assert total == 1
        assert entries[0]["content"] == "完成100%计划"

    def test_filter_no_filters_returns_all(self, repository):
        """不传 filters：行为不变（向后兼容）"""
        type_id = self._setup_sport_type(repository)
        _, total = repository.query_entries(type_id=type_id)
        assert total == 4

    def test_filter_invalid_field_key_raises_with_valid_fields(self, repository):
        """field_key 不存在：抛 ValidationError(INVALID_FIELD_KEY)，details 含 valid_fields"""
        type_id = self._setup_sport_type(repository)
        with pytest.raises(ValidationError) as exc_info:
            repository.query_entries(
                type_id=type_id,
                filters=[{"field_key": "wrong_field", "op": "eq", "value": 1}],
            )
        assert exc_info.value.code == "INVALID_FIELD_KEY"
        valid_fields = exc_info.value.details["valid_fields"]
        assert {f["field_key"] for f in valid_fields} == {"content", "heart_rate", "distance"}

    def test_filter_invalid_op_for_text_field_raises(self, repository):
        """text 字段使用数值比较 op：抛 ValidationError(INVALID_FILTER_OP)，details 含 allowed_ops"""
        type_id = self._setup_sport_type(repository)
        with pytest.raises(ValidationError) as exc_info:
            repository.query_entries(
                type_id=type_id,
                filters=[{"field_key": "content", "op": "gt", "value": "a"}],
            )
        assert exc_info.value.code == "INVALID_FILTER_OP"
        assert set(exc_info.value.details["allowed_ops"]) == {"eq", "ne", "in", "contains"}

    def test_filter_invalid_op_for_integer_field_raises(self, repository):
        """integer 字段使用 contains：抛 ValidationError(INVALID_FILTER_OP)"""
        type_id = self._setup_sport_type(repository)
        with pytest.raises(ValidationError) as exc_info:
            repository.query_entries(
                type_id=type_id,
                filters=[{"field_key": "heart_rate", "op": "contains", "value": "12"}],
            )
        assert exc_info.value.code == "INVALID_FILTER_OP"
        assert set(exc_info.value.details["allowed_ops"]) == {
            "eq",
            "ne",
            "in",
            "gt",
            "gte",
            "lt",
            "lte",
        }

    def test_filter_value_type_mismatch_raises(self, repository):
        """integer 字段过滤值非数值：抛 ValidationError(INVALID_FIELD_VALUE)"""
        type_id = self._setup_sport_type(repository)
        with pytest.raises(ValidationError) as exc_info:
            repository.query_entries(
                type_id=type_id,
                filters=[{"field_key": "heart_rate", "op": "eq", "value": "abc"}],
            )
        assert exc_info.value.code == "INVALID_FIELD_VALUE"
        assert exc_info.value.details["invalid_fields"][0]["field_key"] == "heart_rate"

    def test_filter_in_with_empty_list_raises(self, repository):
        """op=in 且 value 为空数组：抛 ValidationError(INVALID_FIELD_VALUE)"""
        type_id = self._setup_sport_type(repository)
        with pytest.raises(ValidationError) as exc_info:
            repository.query_entries(
                type_id=type_id,
                filters=[{"field_key": "heart_rate", "op": "in", "value": []}],
            )
        assert exc_info.value.code == "INVALID_FIELD_VALUE"

    def test_filter_in_with_mixed_invalid_values_raises(self, repository):
        """op=in 且列表中混入类型不匹配值：抛 ValidationError(INVALID_FIELD_VALUE)"""
        type_id = self._setup_sport_type(repository)
        with pytest.raises(ValidationError):
            repository.query_entries(
                type_id=type_id,
                filters=[{"field_key": "heart_rate", "op": "in", "value": [120, "abc"]}],
            )


# ==================== P3: 更新记录测试 ====================


class TestUpdateEntry:
    """P3: 测试 update_entry() 方法（PATCH 三态语义：未传=不修改，传 null=清空，传值=更新）"""

    def test_update_entry_single_text_field_preserves_other_fields(self, repository):
        """P3 测试 1: 更新单字段（text）——仅更新该字段，其他字段保持原值"""
        # Arrange: 创建类型并录入初始记录
        type_id = repository.create_type(
            name="体育活动",
            slug="sport_p3",
            fields=[
                {"field_name": "日期", "field_key": "exercise_date", "field_type": "text"},
                {"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"exercise_date": "2026-07-07", "exercise_content": "跑步5公里"},
        )

        # Act: 只更新 exercise_content 字段
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"exercise_content": "跑步10公里"},
        )

        # Assert: 返回 True
        assert result is True

        # Assert: 仅 exercise_content 更新，exercise_date 保持原值
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT exercise_date, exercise_content FROM custom_sport_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "2026-07-07"  # 原值不变（未传字段不修改）
            assert row[1] == "跑步10公里"  # 已更新为新值

    def test_update_entry_all_fields_updates_all(self, repository):
        """P3 测试 2: 更新全部字段——所有字段值都更新为新值"""
        # Arrange
        type_id = repository.create_type(
            name="阅读记录",
            slug="reading_p3",
            fields=[
                {"field_name": "书名", "field_key": "book_title", "field_type": "text"},
                {"field_name": "页数", "field_key": "page_count", "field_type": "integer"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"book_title": "原书名", "page_count": 100},
        )

        # Act: 更新全部字段
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"book_title": "新书名", "page_count": 200},
        )

        # Assert
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT book_title, page_count FROM custom_reading_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "新书名"
            assert row[1] == 200

    def test_update_entry_empty_dict_only_refreshes_updated_at(self, repository):
        """P3 测试 3: 空字典更新——仅刷 updated_at，字段值全部不变"""
        # Arrange
        type_id = repository.create_type(
            name="空字典测试",
            slug="empty_p3",
            fields=[
                {"field_name": "笔记", "field_key": "note", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"note": "原始笔记"},
        )
        # 取原始 updated_at
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT note, updated_at FROM custom_empty_p3 WHERE id = ?",
                (entry_id,),
            )
            orig_row = cursor.fetchone()
            orig_note = orig_row[0]
            orig_updated_at = orig_row[1]

        # Act: 空字典更新
        import time as _time
        _time.sleep(1.1)  # 确保 updated_at 时间戳不同
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={},
        )

        # Assert
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT note, updated_at FROM custom_empty_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == orig_note  # 字段值不变
            assert row[1] != orig_updated_at  # updated_at 已变化

    def test_update_entry_none_value_clears_field(self, repository):
        """P3 测试 4: 清空字段（None 值，三态语义）——传 null 表达清空，写入 NULL"""
        # Arrange
        type_id = repository.create_type(
            name="清空字段测试",
            slug="clear_p3",
            fields=[
                {"field_name": "笔记", "field_key": "note", "field_type": "text"},
                {"field_name": "计数", "field_key": "count", "field_type": "integer"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"note": "原始笔记", "count": 42},
        )

        # Act: 把 note 清空（传 None）
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"note": None},
        )

        # Assert
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT note, count FROM custom_clear_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] is None  # note 已清空（NULL）
            assert row[1] == 42  # count 保持原值（未传字段不修改）

    def test_update_entry_unmentioned_field_preserved(self, repository):
        """P3 测试 5: 未传字段三态语义——未传的字段保持原值（不修改）"""
        # Arrange
        type_id = repository.create_type(
            name="未传字段测试",
            slug="unmentioned_p3",
            fields=[
                {"field_name": "字段A", "field_key": "field_a", "field_type": "text"},
                {"field_name": "字段B", "field_key": "field_b", "field_type": "text"},
                {"field_name": "字段C", "field_key": "field_c", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"field_a": "值A", "field_b": "值B", "field_c": "值C"},
        )

        # Act: 只传 field_b，不传 field_a 和 field_c
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"field_b": "新值B"},
        )

        # Assert: field_a 和 field_c 保持原值，field_b 更新
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT field_a, field_b, field_c FROM custom_unmentioned_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "值A"  # 未传，保持原值
            assert row[1] == "新值B"  # 已传，更新为新值
            assert row[2] == "值C"  # 未传，保持原值

    def test_update_entry_integer_correct_value_persists(self, repository):
        """P3 测试 6: 更新 integer 字段正确 int 值——落库成功"""
        # Arrange
        type_id = repository.create_type(
            name="整数测试",
            slug="int_p3",
            fields=[
                {"field_name": "计数", "field_key": "count", "field_type": "integer"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"count": 10},
        )

        # Act: 更新为新整数
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"count": 42},
        )

        # Assert
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count FROM custom_int_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == 42

    def test_update_entry_integer_invalid_value_raises_validation_error(self, repository):
        """P3 测试 7: 更新 integer 字段错误值——抛 ValidationError(INVALID_FIELD_VALUE) + valid_fields 详情"""
        # Arrange
        type_id = repository.create_type(
            name="整数错误值",
            slug="int_invalid_p3",
            fields=[
                {"field_name": "计数", "field_key": "count", "field_type": "integer"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"count": 10},
        )

        # Act + Assert: 传非数值字符串
        with pytest.raises(ValidationError) as exc_info:
            repository.update_entry(
                type_id=type_id,
                entry_id=entry_id,
                data={"count": "abc"},
            )

        # Assert: details 含 valid_fields
        assert exc_info.value.code == "INVALID_FIELD_VALUE"
        details = exc_info.value.details
        assert "invalid_fields" in details
        assert details["invalid_fields"][0]["field_key"] == "count"
        assert "valid_fields" in details

    def test_update_entry_float_correct_value_persists(self, repository):
        """P3 测试 8: 更新 float 字段正确值——落库成功"""
        # Arrange
        type_id = repository.create_type(
            name="浮点测试",
            slug="float_p3",
            fields=[
                {"field_name": "体重", "field_key": "weight", "field_type": "float"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"weight": 60.0},
        )

        # Act: 更新为新浮点数
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"weight": 65.5},
        )

        # Assert
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT weight FROM custom_float_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == 65.5

    def test_update_entry_float_invalid_value_raises_validation_error(self, repository):
        """P3 测试 9: 更新 float 字段错误值——抛 ValidationError(INVALID_FIELD_VALUE)"""
        # Arrange
        type_id = repository.create_type(
            name="浮点错误值",
            slug="float_invalid_p3",
            fields=[
                {"field_name": "体重", "field_key": "weight", "field_type": "float"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"weight": 60.0},
        )

        # Act + Assert: 传非数值字符串
        with pytest.raises(ValidationError) as exc_info:
            repository.update_entry(
                type_id=type_id,
                entry_id=entry_id,
                data={"weight": "xyz"},
            )

        assert exc_info.value.code == "INVALID_FIELD_VALUE"

    def test_update_entry_unknown_field_key_raises_validation_error(self, repository):
        """P3 测试 10: 更新不存在的 field_key——抛 ValidationError(INVALID_FIELD_KEY) 且 details 含 valid_fields"""
        # Arrange: 创建类型并录入初始记录
        type_id = repository.create_type(
            name="未知字段测试",
            slug="unknown_field_p3",
            fields=[
                {"field_name": "内容", "field_key": "content", "field_type": "text"},
                {"field_name": "心率", "field_key": "heart_rate", "field_type": "integer"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"content": "跑步", "heart_rate": 120},
        )

        # Act + Assert: 传 data 含未知 field_key
        with pytest.raises(ValidationError) as exc_info:
            repository.update_entry(
                type_id=type_id,
                entry_id=entry_id,
                data={"unknown_field": "x"},
            )

        # Assert: code 为 INVALID_FIELD_KEY
        assert exc_info.value.code == "INVALID_FIELD_KEY"

        # Assert: details 含 invalid_keys（按字母序）和 valid_fields
        details = exc_info.value.details
        assert details["invalid_keys"] == ["unknown_field"]
        valid_fields = details["valid_fields"]
        valid_keys = {f["field_key"] for f in valid_fields}
        assert valid_keys == {"content", "heart_rate"}
        # valid_fields 每项含 field_key + field_name（供前端展示可用字段清单）
        for f in valid_fields:
            assert "field_key" in f
            assert "field_name" in f

    def test_update_entry_nonexistent_type_id_raises_entity_not_found(self, repository):
        """P3 测试 11: 更新不存在的 type_id——抛 EntityNotFoundError(entity_type='CustomRecordType')"""
        # Arrange: 不存在的 type_id（格式合法但库里没有）
        nonexistent_type_id = "crt-not-exist-p3"
        # 先随便创建一条 entry_id 来调用（type_id 校验在前，不会到达 entry 存在性校验）
        fake_entry_id = "cre-fake-p3"

        # Act + Assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            repository.update_entry(
                type_id=nonexistent_type_id,
                entry_id=fake_entry_id,
                data={"any_field": "x"},
            )

        # Assert: code 固定为 ENTITY_NOT_FOUND，details 含 entity_type=CustomRecordType
        assert exc_info.value.code == "ENTITY_NOT_FOUND"
        assert exc_info.value.details["entity_type"] == "CustomRecordType"
        assert exc_info.value.details["entity_id"] == nonexistent_type_id

    def test_update_entry_nonexistent_entry_id_raises_entity_not_found(self, repository):
        """P3 测试 12: 类型存在但 entry_id 不存在——抛 EntityNotFoundError(entity_type='CustomRecordEntry')"""
        # Arrange: 创建类型，但不录入任何记录
        type_id = repository.create_type(
            name="空类型",
            slug="empty_type_p3",
            fields=[
                {"field_name": "内容", "field_key": "content", "field_type": "text"},
            ],
        )
        nonexistent_entry_id = "cre-not-exist-p3"

        # Act + Assert: type_id 存在但 entry_id 不存在
        with pytest.raises(EntityNotFoundError) as exc_info:
            repository.update_entry(
                type_id=type_id,
                entry_id=nonexistent_entry_id,
                data={"content": "x"},
            )

        # Assert: code 固定为 ENTITY_NOT_FOUND，details 含 entity_type=CustomRecordEntry
        assert exc_info.value.code == "ENTITY_NOT_FOUND"
        assert exc_info.value.details["entity_type"] == "CustomRecordEntry"
        assert exc_info.value.details["entity_id"] == nonexistent_entry_id

    def test_update_entry_event_time_updates_column_without_touching_data(self, repository):
        """P3 测试 13: 更新 event_time——event_time 列已更新，data 字段保持不变"""
        # Arrange: 录入记录时显式指定原始 event_time（便于对比）
        type_id = repository.create_type(
            name="事件时间更新测试",
            slug="event_time_update_p3",
            fields=[
                {"field_name": "笔记", "field_key": "note", "field_type": "text"},
            ],
        )
        orig_event_time = "2026-07-01T08:00:00+00:00"
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"note": "原始笔记"},
            event_time=orig_event_time,
        )
        # 捕获原始 note 值（确保 data 字段未被 update_entry 触及）
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT note, event_time FROM custom_event_time_update_p3 WHERE id = ?",
                (entry_id,),
            )
            orig_row = cursor.fetchone()
            orig_note = orig_row[0]
            assert orig_row[1] == orig_event_time  # 落库即原始 event_time

        # Act: 仅传 event_time，data 为空字典（不修改任何字段值）
        new_event_time = "2026-08-01T00:00:00+00:00"
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={},
            event_time=new_event_time,
        )

        # Assert: 返回 True，event_time 已更新，note 保持原值
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT note, event_time FROM custom_event_time_update_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == orig_note  # data 字段不变（空字典）
            assert row[1] == new_event_time  # event_time 已更新为新值

    def test_update_entry_event_time_none_keeps_original_event_time(self, repository):
        """P3 测试 14: event_time=None 不更新该列——event_time 列保持原值"""
        # Arrange: 录入记录时显式指定原始 event_time
        type_id = repository.create_type(
            name="事件时间不变测试",
            slug="event_time_none_p3",
            fields=[
                {"field_name": "笔记", "field_key": "note", "field_type": "text"},
            ],
        )
        orig_event_time = "2026-07-15T10:30:00+00:00"
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"note": "原始笔记"},
            event_time=orig_event_time,
        )

        # Act: 传 event_time=None（显式不更新该列），同时更新 note 字段
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"note": "更新后的笔记"},
            event_time=None,
        )

        # Assert: 返回 True，event_time 保持原值，note 已更新
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT note, event_time FROM custom_event_time_none_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "更新后的笔记"  # note 已更新
            assert row[1] == orig_event_time  # event_time 保持原值（None 不更新）

    def test_update_entry_refreshes_updated_at_automatically(self, repository):
        """P3 测试 15: updated_at 自动刷新——updated_at > created_at 且 updated_at > 原始 updated_at"""
        # Arrange: 录入记录
        type_id = repository.create_type(
            name="updated_at刷新测试",
            slug="updated_at_refresh_p3",
            fields=[
                {"field_name": "笔记", "field_key": "note", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"note": "原始笔记"},
        )
        # 捕获原始 created_at 和 updated_at
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at, updated_at FROM custom_updated_at_refresh_p3 WHERE id = ?",
                (entry_id,),
            )
            orig_row = cursor.fetchone()
            orig_created_at = orig_row[0]
            orig_updated_at = orig_row[1]

        # Act: 等待 1.1 秒后调 update_entry（确保时间戳不同）
        import time as _time
        _time.sleep(1.1)
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"note": "更新后的笔记"},
        )

        # Assert: 返回 True，created_at 不变，updated_at 已刷新
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT created_at, updated_at FROM custom_updated_at_refresh_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            new_created_at = row[0]
            new_updated_at = row[1]

        # created_at 不可变
        assert new_created_at == orig_created_at
        # updated_at 已刷新（与原始不同，且严格大于原始——字符串 ISO 时间戳字典序与时间序一致）
        assert new_updated_at != orig_updated_at
        assert new_updated_at > orig_updated_at
        # updated_at 应 ≥ created_at（更新发生在创建之后）
        assert new_updated_at >= new_created_at

    def test_update_entry_id_and_created_at_immutable(self, repository):
        """P3 测试 16: id 与 created_at 不可变——更新后 id 和 created_at 与原值一致"""
        # Arrange
        type_id = repository.create_type(
            name="不可变列测试",
            slug="immutable_p3",
            fields=[
                {"field_name": "笔记", "field_key": "note", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"note": "原始笔记"},
        )
        # 捕获原始 id 和 created_at
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, created_at FROM custom_immutable_p3 WHERE id = ?",
                (entry_id,),
            )
            orig_row = cursor.fetchone()
            orig_id = orig_row[0]
            orig_created_at = orig_row[1]

        # Act: 更新 note 字段
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"note": "更新后的笔记"},
        )

        # Assert: 返回 True，id 和 created_at 与原值一致
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, created_at, note FROM custom_immutable_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == orig_id  # id 不可变
            assert row[0] == entry_id  # id 仍为原 entry_id
            assert row[1] == orig_created_at  # created_at 不可变
            assert row[2] == "更新后的笔记"  # note 已更新

    def test_update_entry_none_value_skips_field_type_coercion(self, repository):
        """P3 测试 17: None 值跳过 _coerce_field_value 校验——传 None 给 integer 字段不抛 ValidationError，写入 NULL

        通过行为验证（非 mock）：若 Repository 对 None 调用 _coerce_field_value，
        会因 None 无法转 int 而返回 _INVALID_SENTINEL 并抛 ValidationError(INVALID_FIELD_VALUE)。
        本测试断言传 None 不抛错且写入 NULL，即证明 None 跳过了类型校验。
        """
        # Arrange: integer 字段
        type_id = repository.create_type(
            name="None跳过校验测试",
            slug="none_skip_coerce_p3",
            fields=[
                {"field_name": "心率", "field_key": "heart_rate", "field_type": "integer"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"heart_rate": 120},
        )

        # Act: 传 None 给 integer 字段（清空语义，应跳过类型校验）
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"heart_rate": None},
        )

        # Assert: 不抛 ValidationError，返回 True，heart_rate 写入 NULL
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT heart_rate FROM custom_none_skip_coerce_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] is None  # 已清空（NULL）

    def test_update_entry_text_field_regression_full_flow(self, repository):
        """P3 测试 18: text 字段保持原行为（回归）——创建+录入+更新 text 字段全流程成功（与 P1 行为一致）"""
        # Arrange: 多个 text 字段，含短文本和长文本
        type_id = repository.create_type(
            name="文本回归测试",
            slug="text_regression_p3",
            fields=[
                {"field_name": "标题", "field_key": "title", "field_type": "text"},
                {"field_name": "内容", "field_key": "content", "field_type": "text"},
            ],
        )
        entry_id = repository.create_entry(
            type_id=type_id,
            data={"title": "原始标题", "content": "原始内容"},
        )

        # Act: 更新 content 字段，title 保持原值
        result = repository.update_entry(
            type_id=type_id,
            entry_id=entry_id,
            data={"content": "更新后的内容"},
        )

        # Assert: 全流程成功，符合 PATCH 三态语义
        assert result is True
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, content FROM custom_text_regression_p3 WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "原始标题"  # 未传字段保持原值（P1 行为）
            assert row[1] == "更新后的内容"  # 已更新字段为新值
