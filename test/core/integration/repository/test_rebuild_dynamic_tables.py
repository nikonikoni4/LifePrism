"""
动态表重建测试（自定义表同步修复验证）

测试范围：
- generate_create_table_ddl() DDL 生成正确性
- get_custom_record_types_snapshot() 快照对比
- get_custom_record_types_full_definitions() 完整定义查询
- rebuild_dynamic_tables() 重建逻辑（created/altered/skipped）

参考: test/core/integration/repository/test_sync_dynamic_tables.py
"""

import sqlite3

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有静态表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider = __import__(
        "lifeprism.repository.base_providers.lw_base_data_provider",
        fromlist=["LWBaseDataProvider"],
    ).LWBaseDataProvider
    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def sync_repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo


@pytest.fixture
def clean_custom_record_types(initialized_db):
    """清理 custom_record_types 和 custom_record_fields 表（测试前后执行）"""
    # 先清理
    with initialized_db.get_connection() as conn:
        conn.execute("DELETE FROM custom_record_fields")
        conn.execute("DELETE FROM custom_record_types")
        conn.commit()

    yield

    # 后清理：删除所有动态表 + meta 表数据
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%'")
        tables = [row[0] for row in cursor.fetchall()]
        for table_name in tables:
            if table_name not in ("custom_record_types", "custom_record_fields"):
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute("DELETE FROM custom_record_fields")
        conn.execute("DELETE FROM custom_record_types")
        conn.commit()


def _insert_custom_record_type(
    db, type_id: str, slug: str, name: str = "test", updated_at: str = "2026-07-01T10:00:00+00:00"
):
    """辅助：插入 custom_record_types 记录"""
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (type_id, name, slug, "", updated_at, updated_at),
        )
        conn.commit()


def _insert_custom_record_field(
    db, type_id: str, field_key: str, field_type: str = "text", sort_order: int = 0
):
    """辅助：插入 custom_record_fields 记录"""
    import uuid

    field_id = f"crf-{uuid.uuid4().hex[:8]}"
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO custom_record_fields "
            "(id, type_id, field_name, field_key, field_type, sort_order, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                field_id,
                type_id,
                field_key,
                field_key,
                field_type,
                sort_order,
                "2026-07-01T10:00:00+00:00",
            ),
        )
        conn.commit()


# ==================== generate_create_table_ddl() ====================


class TestGenerateCreateTableDdl:
    """DDL 生成静态方法测试"""

    def test_basic_ddl_generation(self):
        """基本 DDL 生成：包含 id + 用户字段 + event_time + created_at + updated_at"""
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        fields = [
            {"field_key": "activity", "field_type": "text"},
            {"field_key": "duration", "field_type": "integer"},
        ]

        ddl = CustomRecordRepository.generate_create_table_ddl("sport", fields)

        assert "CREATE TABLE custom_sport" in ddl
        assert "id TEXT PRIMARY KEY" in ddl
        assert "activity TEXT" in ddl
        assert "duration INTEGER" in ddl
        assert "event_time TEXT" in ddl
        assert "created_at TEXT" in ddl
        assert "updated_at TEXT" in ddl

    def test_float_field_type(self):
        """float 字段类型映射为 REAL"""
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        fields = [{"field_key": "score", "field_type": "float"}]
        ddl = CustomRecordRepository.generate_create_table_ddl("rating", fields)

        assert "score REAL" in ddl
        assert "CREATE TABLE custom_rating" in ddl

    def test_unknown_field_type_defaults_to_text(self):
        """未知 field_type 默认为 TEXT"""
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        fields = [{"field_key": "data", "field_type": "unknown_type"}]
        ddl = CustomRecordRepository.generate_create_table_ddl("test", fields)

        assert "data TEXT" in ddl

    def test_empty_fields(self):
        """无用户字段时仍包含基础列"""
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        ddl = CustomRecordRepository.generate_create_table_ddl("empty", [])

        assert "CREATE TABLE custom_empty" in ddl
        assert "id TEXT PRIMARY KEY" in ddl
        assert "event_time TEXT" in ddl


# ==================== get_custom_record_types_snapshot() ====================


class TestGetSnapshot:
    """快照查询测试"""

    def test_empty_snapshot(self, sync_repository, clean_custom_record_types):
        """无自定义记录类型时返回空集合"""
        snapshot = sync_repository.get_custom_record_types_snapshot()
        assert snapshot == set()

    def test_snapshot_returns_id_and_updated_at(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """快照返回 (id, updated_at) 元组集合"""
        _insert_custom_record_type(
            initialized_db, "crt-001", "sport", updated_at="2026-07-01T10:00:00+00:00"
        )

        snapshot = sync_repository.get_custom_record_types_snapshot()

        assert ("crt-001", "2026-07-01T10:00:00+00:00") in snapshot
        assert len(snapshot) == 1

    def test_snapshot_detects_change(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """快照能检测到 updated_at 变化"""
        _insert_custom_record_type(
            initialized_db, "crt-001", "sport", updated_at="2026-07-01T10:00:00+00:00"
        )

        before = sync_repository.get_custom_record_types_snapshot()

        # 模拟 updated_at 变化（pull 拉到新数据）
        with initialized_db.get_connection() as conn:
            conn.execute(
                "UPDATE custom_record_types SET updated_at = ? WHERE id = ?",
                ("2026-07-02T12:00:00+00:00", "crt-001"),
            )
            conn.commit()

        after = sync_repository.get_custom_record_types_snapshot()

        assert before != after
        assert ("crt-001", "2026-07-02T12:00:00+00:00") in after
        assert ("crt-001", "2026-07-01T10:00:00+00:00") not in after


# ==================== get_custom_record_types_full_definitions() ====================


class TestGetFullDefinitions:
    """完整定义查询测试"""

    def test_empty_definitions(self, sync_repository, clean_custom_record_types):
        """无自定义记录类型时返回空列表"""
        result = sync_repository.get_custom_record_types_full_definitions()
        assert result == []

    def test_returns_slug_and_fields(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """返回 slug 和 fields 列表"""
        _insert_custom_record_type(initialized_db, "crt-001", "sport")
        _insert_custom_record_field(initialized_db, "crt-001", "activity", "text", 0)
        _insert_custom_record_field(initialized_db, "crt-001", "duration", "integer", 1)

        result = sync_repository.get_custom_record_types_full_definitions()

        assert len(result) == 1
        assert result[0]["slug"] == "sport"
        assert len(result[0]["fields"]) == 2
        assert result[0]["fields"][0] == {"field_key": "activity", "field_type": "text"}
        assert result[0]["fields"][1] == {"field_key": "duration", "field_type": "integer"}

    def test_multiple_types(self, sync_repository, clean_custom_record_types, initialized_db):
        """多个 type 都能正确返回"""
        _insert_custom_record_type(initialized_db, "crt-001", "sport")
        _insert_custom_record_field(initialized_db, "crt-001", "activity", "text", 0)
        _insert_custom_record_type(initialized_db, "crt-002", "diet")
        _insert_custom_record_field(initialized_db, "crt-002", "calories", "integer", 0)

        result = sync_repository.get_custom_record_types_full_definitions()

        assert len(result) == 2
        slugs = {t["slug"] for t in result}
        assert slugs == {"sport", "diet"}


# ==================== rebuild_dynamic_tables() ====================


class TestRebuildDynamicTables:
    """动态表重建逻辑测试"""

    def test_create_new_table(self, sync_repository, clean_custom_record_types, initialized_db):
        """新建动态表（action=created）"""
        types = [
            {
                "slug": "sport",
                "fields": [
                    {"field_key": "activity", "field_type": "text"},
                    {"field_key": "duration", "field_type": "integer"},
                ],
            }
        ]

        results = sync_repository.rebuild_dynamic_tables(types)

        assert len(results) == 1
        assert results[0] == {"slug": "sport", "action": "created"}

        # 验证表已创建
        with initialized_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_sport'"
            )
            assert cursor.fetchone() is not None

            # 验证列
            cursor = conn.execute("PRAGMA table_info(custom_sport)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "id" in columns
            assert "activity" in columns
            assert "duration" in columns
            assert "event_time" in columns
            assert "created_at" in columns
            assert "updated_at" in columns

    def test_skip_existing_table_no_change(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """已有表无字段变化时跳过（action=skipped）"""
        # 先创建表
        types = [
            {
                "slug": "sport",
                "fields": [{"field_key": "activity", "field_type": "text"}],
            }
        ]
        sync_repository.rebuild_dynamic_tables(types)

        # 再次调用相同定义
        results = sync_repository.rebuild_dynamic_tables(types)

        assert len(results) == 1
        assert results[0] == {"slug": "sport", "action": "skipped"}

    def test_alter_existing_table_add_column(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """已有表新增字段时 ALTER ADD COLUMN（action=altered）"""
        # 先创建表（只有 activity 字段）
        types = [
            {
                "slug": "sport",
                "fields": [{"field_key": "activity", "field_type": "text"}],
            }
        ]
        sync_repository.rebuild_dynamic_tables(types)

        # 再用扩展定义调用（新增 duration 字段）
        types_extended = [
            {
                "slug": "sport",
                "fields": [
                    {"field_key": "activity", "field_type": "text"},
                    {"field_key": "duration", "field_type": "integer"},
                ],
            }
        ]
        results = sync_repository.rebuild_dynamic_tables(types_extended)

        assert len(results) == 1
        assert results[0] == {"slug": "sport", "action": "altered"}

        # 验证新列已添加
        with initialized_db.get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(custom_sport)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "duration" in columns

    def test_does_not_drop_orphan_table(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """不删除云端已有但本地定义中不存在的表（孤儿表保护）"""
        # 先创建一个表
        with initialized_db.get_connection() as conn:
            conn.execute(
                "CREATE TABLE custom_orphan (id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT)"
            )
            conn.commit()

        # 本地传入空定义（没有 orphan 类型）→ 不应删除 orphan 表
        results = sync_repository.rebuild_dynamic_tables([])

        # 不应有 dropped 动作
        dropped = [r for r in results if r.get("action") == "dropped"]
        assert len(dropped) == 0, "孤儿表不应被删除，删除同步需要独立的 tombstone 机制"

        # 验证表仍然存在
        with initialized_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_orphan'"
            )
            assert cursor.fetchone() is not None, "孤儿表不应被删除"

    def test_preserves_existing_meta_tables(
        self, sync_repository, clean_custom_record_types, initialized_db
    ):
        """不删除 custom_record_types 和 custom_record_fields meta 表"""
        results = sync_repository.rebuild_dynamic_tables([])

        # 验证 meta 表仍然存在
        with initialized_db.get_connection() as conn:
            for meta_table in ("custom_record_types", "custom_record_fields"):
                cursor = conn.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{meta_table}'"
                )
                assert cursor.fetchone() is not None, f"{meta_table} 不应被删除"

    def test_idempotent_operation(self, sync_repository, clean_custom_record_types, initialized_db):
        """幂等性：重复调用不产生副作用"""
        types = [
            {
                "slug": "sport",
                "fields": [{"field_key": "activity", "field_type": "text"}],
            }
        ]

        # 第一次调用：创建
        results1 = sync_repository.rebuild_dynamic_tables(types)
        assert results1[0]["action"] == "created"

        # 第二次调用：跳过
        results2 = sync_repository.rebuild_dynamic_tables(types)
        assert results2[0]["action"] == "skipped"

        # 第三次调用：仍然跳过
        results3 = sync_repository.rebuild_dynamic_tables(types)
        assert results3[0]["action"] == "skipped"

    def test_mixed_operations(self, sync_repository, clean_custom_record_types, initialized_db):
        """混合操作：新建 + 修改 + 删除同时发生"""
        # 先创建一个已有表
        with initialized_db.get_connection() as conn:
            conn.execute(
                "CREATE TABLE custom_old (id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT)"
            )
            conn.commit()

        # 本地定义：新增 sport + 保留 old
        types = [
            {
                "slug": "sport",
                "fields": [{"field_key": "activity", "field_type": "text"}],
            },
            {
                "slug": "old",
                "fields": [{"field_key": "name", "field_type": "text"}],
            },
        ]

        results = sync_repository.rebuild_dynamic_tables(types)

        # 应该有一个 created（sport）和一个 altered（old 新增 name 列）
        actions = {r["slug"]: r["action"] for r in results}
        assert actions.get("sport") == "created"
        assert actions.get("old") == "altered"


# ==================== 端点测试 ====================


class TestRebuildDynamicTablesEndpoint:
    """POST /api/sync/rebuild-dynamic-tables 端点测试"""

    def test_endpoint_requires_auth(self):
        """未认证请求被拒绝（ValidationError 通过全局异常处理器映射为 422）"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lifeprism.server.api.sync_cloud_api import router
        from lifeprism.utils.exceptions import ValidationError

        app = FastAPI()
        app.include_router(router)

        # 注册 ValidationError 异常处理器（与生产环境一致）
        @app.exception_handler(ValidationError)
        async def validation_error_handler(request, exc):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=422,
                content={"detail": exc.message, "code": exc.code},
            )

        client = TestClient(app)

        response = client.post(
            "/api/sync/rebuild-dynamic-tables",
            json={"types": []},
        )
        # 未提供 Authorization Header，ValidationError 映射为 422
        assert response.status_code == 422

    def test_endpoint_validates_request_body(self):
        """请求体格式校验：缺少 types 字段返回 422"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lifeprism.server.api.sync_cloud_api import router
        from lifeprism.utils.exceptions import ValidationError

        app = FastAPI()
        app.include_router(router)

        # 注册 ValidationError 异常处理器
        @app.exception_handler(ValidationError)
        async def validation_error_handler(request, exc):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=422,
                content={"detail": exc.message, "code": exc.code},
            )

        client = TestClient(app)

        # 缺少 types 字段 → Pydantic 校验失败返回 422
        response = client.post(
            "/api/sync/rebuild-dynamic-tables",
            json={},
        )
        assert response.status_code == 422
