"""
Activity API 端到端集成测试

测试 seam（PRD Testing Decisions §S3）:
- /activity/logs/{id} - 日志详情返回字段一致（含 category_name / sub_category_name）
- /activity/manage/logs/batch - 批量删除后记录消失 + deletion_log 有墓碑
- /activity/stats - 统计端点数据结构一致

使用最小化 FastAPI 应用测试 activity 路由，避免完整 app lifespan 的副作用。
参考: test/core/integration/api/test_sync_api.py 的测试模式

数据写入通道：
- 行为日志插入走 _generic_insert（create_computer_usage），保证 hash_id 存在
- 删除走 _generic_batch_delete（batch_delete_computer_usage），保证写墓碑到 deletion_log
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lifeprism.server.errors import to_http_exception
from lifeprism.utils.exceptions import LWBaseError

pytestmark = pytest.mark.core

# 测试用时间常量（UTC ISO 8601 格式，与 API 入参与 DB 存储格式一致）
TEST_DATE = "2026-07-13"
TEST_START_TIME = "2026-07-13T10:00:00+00:00"
TEST_END_TIME = "2026-07-13T10:30:00+00:00"


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 和 timestamps 缓存，确保读取最新表结构
    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def client(initialized_db):
    """创建测试客户端（最小化 FastAPI 应用，仅包含 activity 路由 + 全局异常处理器）"""
    from lifeprism.server.api.activity_api import router as activity_router

    test_app = FastAPI()

    @test_app.exception_handler(LWBaseError)
    async def lw_base_error_handler(request: Request, exc: LWBaseError):
        http_exc = to_http_exception(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )

    test_app.include_router(activity_router)

    return TestClient(test_app)


@pytest.fixture
def clean_tables(initialized_db):
    """清理测试表数据（teardown 阶段执行，避免测试间状态污染）"""
    yield
    tables = [
        "user_app_behavior_log",
        "category",
        "sub_category",
        "deletion_log",
    ]
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


# ==================== 辅助函数 ====================


def _insert_behavior_log(
    initialized_db,
    *,
    start_time=TEST_START_TIME,
    end_time=TEST_END_TIME,
    duration=1800,
    app="chrome.exe",
    title="测试窗口",
    category_id=None,
    sub_category_id=None,
):
    """通过 _generic_insert 通道插入 user_app_behavior_log 记录

    使用 computer_usage_repository.create_computer_usage → _generic_insert，
    确保 hash_id 自动生成（user_app_behavior_log 在 HASH_ID_PREFIXES 中，前缀 awbl-）。

    Returns:
        dict: 创建后的完整记录（含 id）
    """
    from lifeprism.repository import computer_usage_repository

    data = {
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "app": app,
        "title": title,
    }
    if category_id is not None:
        data["category_id"] = category_id
    if sub_category_id is not None:
        data["sub_category_id"] = sub_category_id

    return computer_usage_repository.create_computer_usage(data)


def _insert_category(initialized_db, category_id, name, color="#5B8FF9"):
    """插入 category 记录（元数据，使用原始 SQL 即可）"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO category (id, name, color) VALUES (?, ?, ?)",
            (category_id, name, color),
        )
        conn.commit()


def _insert_sub_category(initialized_db, sub_id, category_id, name):
    """插入 sub_category 记录（元数据，使用原始 SQL 即可）"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sub_category (id, category_id, name) VALUES (?, ?, ?)",
            (sub_id, category_id, name),
        )
        conn.commit()


def _refresh_category_cache():
    """刷新 ComputerUsageAggregator 的分类名称缓存

    get_activity_log_detail 走 get_computer_usage_by_id_with_names → _enrich_with_names，
    依赖聚合器的 _category_map / _sub_category_map 缓存（__init__ 时初始化一次）。
    插入新分类后必须刷新缓存，否则 category_name / sub_category_name 为空。
    """
    from lifeprism.repository import computer_usage_repository

    computer_usage_repository._refresh_cache()


def _get_hash_id(initialized_db, record_id):
    """查询 user_app_behavior_log 记录的 hash_id（墓碑 record_id 用 hash_id）"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT hash_id FROM user_app_behavior_log WHERE id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def _count_records(initialized_db, table_name, where_clause="", params=()):
    """查询单表记录数（用于断言）"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        sql = f"SELECT COUNT(*) FROM {table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


# ==================== Seam 1: GET /activity/logs/{id} ====================


class TestActivityLogDetail:
    """测试 GET /activity/logs/{log_id} 端点 - 日志详情返回字段一致"""

    def test_returns_all_required_fields_with_category_names(
        self, client, initialized_db, clean_tables
    ):
        """日志详情返回字段一致：含 category_id / sub_category_id / category / sub_category"""
        # Arrange: 插入分类元数据
        _insert_category(initialized_db, "cat-detail-1", "工作")
        _insert_sub_category(initialized_db, "sub-detail-1", "cat-detail-1", "编程")
        _refresh_category_cache()

        # Arrange: 通过 _generic_insert 插入行为日志（保证 hash_id 存在）
        record = _insert_behavior_log(
            initialized_db,
            app="code.exe",
            title="main.py - VSCode",
            category_id="cat-detail-1",
            sub_category_id="sub-detail-1",
        )
        log_id = str(record["id"])

        # Act: GET /activity/logs/{id}
        response = client.get(f"/activity/logs/{log_id}")

        # Assert: 响应正确，包含所有必需字段
        assert response.status_code == 200
        data = response.json()

        # 核心字段
        assert data["id"] == log_id
        assert data["app"] == "code.exe"
        assert data["title"] == "main.py - VSCode"
        assert data["duration"] == 1800
        assert data["start_time"] == TEST_START_TIME
        assert data["end_time"] == TEST_END_TIME

        # 分类字段（含 category_name / sub_category_name）
        assert data["category_id"] == "cat-detail-1"
        assert data["sub_category_id"] == "sub-detail-1"
        assert data["category"] == "工作"
        assert data["sub_category"] == "编程"

    def test_returns_404_when_not_found(self, client, initialized_db, clean_tables):
        """不存在的日志 ID 返回 404"""
        # Act
        response = client.get("/activity/logs/999999")

        # Assert
        assert response.status_code == 404


# ==================== Seam 2: DELETE /activity/manage/logs/batch ====================


class TestBatchDeleteLogs:
    """测试 DELETE /activity/manage/logs/batch 端点 - 批量删除后记录消失 + deletion_log 有墓碑"""

    def test_batch_delete_removes_records_and_writes_tombstones(
        self, client, initialized_db, clean_tables
    ):
        """批量删除：记录从 user_app_behavior_log 消失 + deletion_log 写入墓碑（record_id=hash_id）"""
        # Arrange: 通过 _generic_insert 插入 3 条记录（每条自动生成 hash_id）
        records = []
        for i in range(3):
            record = _insert_behavior_log(
                initialized_db,
                start_time=f"2026-07-13T1{i:02d}:00:00+00:00",
                end_time=f"2026-07-13T1{i:02d}:30:00+00:00",
                app=f"app-{i}.exe",
                title=f"窗口-{i}",
            )
            records.append(record)

        log_ids = [str(r["id"]) for r in records]
        hash_ids = [_get_hash_id(initialized_db, r["id"]) for r in records]

        # 验证测试前提：3 条记录都已写入，hash_id 都已生成
        assert _count_records(initialized_db, "user_app_behavior_log") == 3
        assert all(h is not None and h.startswith("awbl-") for h in hash_ids)

        # Act: DELETE /activity/manage/logs/batch?log_ids=1&log_ids=2&log_ids=3
        # 走 _generic_batch_delete 通道，保证写墓碑
        response = client.delete(
            "/activity/manage/logs/batch",
            params=[("log_ids", lid) for lid in log_ids],
        )

        # Assert: 响应正确
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["deleted_count"] == 3

        # Assert: 记录从 user_app_behavior_log 消失
        assert _count_records(initialized_db, "user_app_behavior_log") == 0

        # Assert: deletion_log 有 3 条墓碑，target_table = user_app_behavior_log
        tombstone_count = _count_records(
            initialized_db,
            "deletion_log",
            "target_table = ?",
            ("user_app_behavior_log",),
        )
        assert tombstone_count == 3

        # Assert: 墓碑 record_id 使用 hash_id（AUTOINCREMENT 表的墓碑用 hash_id）
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT record_id FROM deletion_log WHERE target_table = ?",
                ("user_app_behavior_log",),
            )
            tombstone_record_ids = {row[0] for row in cursor.fetchall()}

        assert tombstone_record_ids == set(hash_ids)

    def test_batch_delete_partial_when_some_not_exist(self, client, initialized_db, clean_tables):
        """部分删除：部分 ID 不存在时，只删除存在的记录并写对应数量墓碑"""
        # Arrange: 只插入 1 条记录
        record = _insert_behavior_log(
            initialized_db,
            app="partial.exe",
            title="部分删除测试",
        )
        existing_id = str(record["id"])
        hash_id = _get_hash_id(initialized_db, record["id"])

        # Act: 删除 1 条存在的 + 1 条不存在的
        response = client.delete(
            "/activity/manage/logs/batch",
            params=[("log_ids", existing_id), ("log_ids", "999999")],
        )

        # Assert: 响应正确（deleted_count = 1）
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["deleted_count"] == 1

        # Assert: 记录消失
        assert _count_records(initialized_db, "user_app_behavior_log") == 0

        # Assert: 只有 1 条墓碑
        tombstone_count = _count_records(
            initialized_db,
            "deletion_log",
            "target_table = ?",
            ("user_app_behavior_log",),
        )
        assert tombstone_count == 1

        # Assert: 墓碑 record_id 是存在的记录的 hash_id
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT record_id FROM deletion_log WHERE target_table = ?",
                ("user_app_behavior_log",),
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == hash_id


# ==================== Seam 3: GET /activity/stats ====================


class TestActivityStats:
    """测试 GET /activity/stats 端点 - 统计端点数据结构一致"""

    def test_stats_returns_consistent_structure(self, client, initialized_db, clean_tables):
        """统计端点返回数据结构一致：query 回显 + top_app / top_title 列表结构"""
        # Arrange: 插入测试数据（不同 app + title，用于 top_app / top_title 聚合）
        _insert_behavior_log(
            initialized_db,
            start_time="2026-07-13T09:00:00+00:00",
            end_time="2026-07-13T10:00:00+00:00",
            duration=3600,
            app="chrome.exe",
            title="Google - 搜索",
        )
        _insert_behavior_log(
            initialized_db,
            start_time="2026-07-13T10:00:00+00:00",
            end_time="2026-07-13T11:00:00+00:00",
            duration=3600,
            app="code.exe",
            title="main.py - VSCode",
        )
        _insert_behavior_log(
            initialized_db,
            start_time="2026-07-13T11:00:00+00:00",
            end_time="2026-07-13T11:30:00+00:00",
            duration=1800,
            app="chrome.exe",
            title="GitHub - 代码仓库",
        )

        # Act: GET /activity/stats（只请求 top_app + top_title 模块，避免 category/color 依赖）
        response = client.get(
            "/activity/stats",
            params={
                "date": TEST_DATE,
                "include": "top_app,top_title",
            },
        )

        # Assert: 响应正确
        assert response.status_code == 200
        data = response.json()

        # Assert: query 字段回显查询参数
        assert "query" in data
        assert data["query"]["date"] == TEST_DATE
        assert data["query"]["history_number"] == 15
        assert data["query"]["future_number"] == 14

        # Assert: top_app 数据结构一致（list[TopAppData]）
        assert "top_app" in data
        assert isinstance(data["top_app"], list)
        assert len(data["top_app"]) > 0
        for item in data["top_app"]:
            assert "name" in item
            assert "duration" in item
            assert "percentage" in item

        # Assert: top_title 数据结构一致（list[TopTitleData]）
        assert "top_title" in data
        assert isinstance(data["top_title"], list)
        assert len(data["top_title"]) > 0
        for item in data["top_title"]:
            assert "name" in item
            assert "duration" in item
            assert "percentage" in item

        # Assert: 未请求的模块为 null（include 按需返回）
        assert data.get("activity_summary") is None
        assert data.get("time_overview") is None

    def test_stats_returns_empty_when_no_data(self, client, initialized_db, clean_tables):
        """无数据时统计端点返回空列表，结构仍一致"""
        # Act
        response = client.get(
            "/activity/stats",
            params={
                "date": TEST_DATE,
                "include": "top_app,top_title",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert data["top_app"] == []
        assert data["top_title"] == []
