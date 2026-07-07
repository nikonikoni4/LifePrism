"""
CustomRecordRepository 单元测试

测试 seam: Repository 层
参考: test/core/unit/storage/test_base_provider_generic_methods.py
"""
import pytest

from lifeprism.repository.exceptions import DuplicateEntityError, EntityNotFoundError
from lifeprism.utils.exceptions import ValidationError


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
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE (type_id, field_key)
            )
        """
        )
        conn.commit()

    yield repo

    # 清理：删除所有动态表 + meta 表
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        # 查询所有 custom_ 开头的表名
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%'"
        )
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
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
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
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
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
            name="体育活动", slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        with pytest.raises(DuplicateEntityError):
            repository.create_type(
                name="运动", slug="sport",
                fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
            )

    def test_create_type_with_invalid_slug_format_raises_validation_error(self, repository):
        """slug 格式错误：抛 ValidationError"""
        with pytest.raises(ValidationError, match="slug"):
            repository.create_type(
                name="体育活动", slug="Sport-Activity",
                fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
            )

    def test_create_type_with_invalid_field_key_format_raises_validation_error(self, repository):
        """field_key 格式错误：抛 ValidationError"""
        with pytest.raises(ValidationError, match="field_key"):
            repository.create_type(
                name="体育活动", slug="sport",
                fields=[{"field_name": "内容", "field_key": "Wrong-Key", "field_type": "text"}],
            )

    def test_create_type_with_duplicate_field_keys_raises_validation_error(self, repository):
        """field_key 同类型重复：抛 ValidationError"""
        with pytest.raises(ValidationError, match="重复"):
            repository.create_type(
                name="体育活动", slug="sport",
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
            name="体育活动", slug="sport",
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
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
        )

        # Act
        entry_id = repository.create_entry(type_id=type_id, data={})

        # Assert: 落库成功
        with repository.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM custom_sport WHERE id = ?", (entry_id,))
            assert cursor.fetchone() is not None


# ==================== 查询记录测试 ====================


def _set_created_at(db_manager, table: str, entry_id: str, created_at: str):
    """直接修改记录的 created_at（用于测试日期筛选）"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {table} SET created_at = ? WHERE id = ?",
            (created_at, entry_id),
        )
        conn.commit()


class TestQueryEntries:
    """测试 query_entries() 方法"""

    def test_query_entries_with_date_range_returns_correct_subset(self, repository):
        """查询记录（日期筛选）：返回正确子集（date_range 过滤 created_at）"""
        # Arrange: 创建类型并录入 3 条记录
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eid1 = repository.create_entry(type_id=type_id, data={"content": "7月1日"})
        eid2 = repository.create_entry(type_id=type_id, data={"content": "7月5日"})
        eid3 = repository.create_entry(type_id=type_id, data={"content": "7月10日"})
        # 用直接 SQL 设置不同的 created_at
        _set_created_at(repository.db, "custom_sport", eid1, "2026-07-01 10:00:00")
        _set_created_at(repository.db, "custom_sport", eid2, "2026-07-05 10:00:00")
        _set_created_at(repository.db, "custom_sport", eid3, "2026-07-10 10:00:00")

        # Act: 查询 7月3日~7月8日 的记录
        entries = repository.query_entries(
            type_id=type_id,
            date_range=("2026-07-03", "2026-07-08"),
        )

        # Assert: 只返回 7月5日 的记录
        assert len(entries) == 1
        assert entries[0]["content"] == "7月5日"

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
        _set_created_at(repository.db, "custom_sport", eid1, "2026-07-01 10:00:00")
        _set_created_at(repository.db, "custom_sport", eid2, "2026-07-10 10:00:00")
        _set_created_at(repository.db, "custom_sport", eid3, "2026-07-20 10:00:00")

        # Act: 只传 start
        entries = repository.query_entries(
            type_id=type_id,
            date_range=("2026-07-05", None),
        )

        # Assert: 返回 7月10日 + 7月20日
        assert len(entries) == 2
        dates = {e["content"] for e in entries}
        assert dates == {"7月10日", "7月20日"}

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
        _set_created_at(repository.db, "custom_sport", eid1, "2026-07-01 10:00:00")
        _set_created_at(repository.db, "custom_sport", eid2, "2026-07-10 10:00:00")
        _set_created_at(repository.db, "custom_sport", eid3, "2026-07-20 10:00:00")

        # Act: 只传 end
        entries = repository.query_entries(
            type_id=type_id,
            date_range=(None, "2026-07-15"),
        )

        # Assert: 返回 7月1日 + 7月10日
        assert len(entries) == 2
        dates = {e["content"] for e in entries}
        assert dates == {"7月1日", "7月10日"}

    def test_query_entries_pagination(self, repository):
        """查询分页：page/page_size 生效"""
        # Arrange: 录入 5 条记录，设置不同 created_at 以保证排序稳定
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "内容", "field_key": "content", "field_type": "text"}],
        )
        eids = []
        for day in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]:
            eid = repository.create_entry(type_id=type_id, data={"content": day})
            eids.append(eid)
            _set_created_at(repository.db, "custom_sport", eid, f"{day} 10:00:00")

        # Act: 第 1 页，每页 2 条
        page1 = repository.query_entries(
            type_id=type_id, date_range=None, page=1, page_size=2
        )
        page2 = repository.query_entries(
            type_id=type_id, date_range=None, page=2, page_size=2
        )

        # Assert: 每页 2 条，且按 created_at DESC 排序（7月5日、7月4日在 page1）
        assert len(page1) == 2
        assert len(page2) == 2
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
        _set_created_at(repository.db, "custom_sport", eid, "2026-07-01 10:00:00")

        # Act: 查询一个没有记录的日期范围
        entries = repository.query_entries(
            type_id=type_id,
            date_range=("2026-08-01", "2026-08-31"),
        )

        # Assert
        assert entries == []


# ==================== 获取单条记录测试 ====================


class TestGetEntry:
    """测试 get_entry() 方法"""

    def test_get_entry_returns_record(self, repository):
        """获取单条记录：返回正确数据"""
        # Arrange
        type_id = repository.create_type(
            name="体育活动",
            slug="sport",
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
        )
        entry_id = repository.create_entry(
            type_id=type_id, data={"exercise_content": "跑步5公里"}
        )

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
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
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
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
        )
        entry_id = repository.create_entry(
            type_id=type_id, data={"exercise_content": "跑步5公里"}
        )

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
            fields=[{"field_name": "锻炼内容", "field_key": "exercise_content", "field_type": "text"}],
        )

        # Act + Assert: 删除不存在的 entry 应抛 EntityNotFoundError
        with pytest.raises(EntityNotFoundError):
            repository.delete_entry(type_id=type_id, entry_id="cre-nonexist")
