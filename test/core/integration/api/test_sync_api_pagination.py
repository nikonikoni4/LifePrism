"""
Sync API 分页拉取集成测试

测试 seam:
- POST /api/sync/pull 端点的 offset / limit 分页参数

测试用例:
1. API 接受 offset/limit 参数并正常返回
2. API 返回分页后的结果（limit 截断 + offset 跳过）

参考: test/core/integration/api/test_sync_api.py
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lifeprism.server.errors import to_http_exception
from lifeprism.utils.exceptions import LWBaseError

pytestmark = pytest.mark.core

TEST_API_KEY = "test_sync_pagination_key_abc123xyz"

# 所有请求共用的认证 Header
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    # 设置测试用 sync_api_key
    from lifeprism.config import settings_manager

    settings_manager.set_setting("sync_api_key", TEST_API_KEY)

    yield lw_db_manager


@pytest.fixture
def client(initialized_db):
    """创建测试客户端（最小化 FastAPI 应用，仅包含 sync 路由 + 全局异常处理器）"""
    from lifeprism.server.api.sync_cloud_api import router as sync_cloud_router

    test_app = FastAPI()

    @test_app.exception_handler(LWBaseError)
    async def lw_base_error_handler(request: Request, exc: LWBaseError):
        http_exc = to_http_exception(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )

    test_app.include_router(sync_cloud_router)

    return TestClient(test_app)


@pytest.fixture
def clean_sync_tables(initialized_db):
    """清理同步表中的测试数据"""
    yield
    sync_tables = [
        "mood_entries",
        "todo_list",
        "goal",
        "diary",
    ]
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in sync_tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


# ==================== 辅助函数 ====================


def _insert_mood_rows(initialized_db, count: int, base_time: str = "2026-07-01"):
    """批量插入 mood_entries 记录，updated_at 递增

    Args:
        initialized_db: 数据库管理器
        count: 插入记录数
        base_time: 日期前缀（不含时间部分）
    """
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for i in range(count):
            hour = 10 + i  # 从 10:00:00 开始递增
            timestamp = f"{base_time} {hour:02d}:00:00"
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"mood-api-page-{i:03d}", "happy", 5 + i, timestamp, timestamp),
            )
        conn.commit()


# ==================== 分页拉取测试 ====================


class TestSyncPullPagination:
    """测试 POST /api/sync/pull 端点的分页参数"""

    def test_sync_pull_accepts_offset_and_limit(self, client, initialized_db, clean_sync_tables):
        """API 接受 offset/limit 参数：请求带分页参数返回 200"""
        # Arrange: 插入 5 条记录
        _insert_mood_rows(initialized_db, 5)

        # Act: 带 offset=0, limit=3 请求
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "",
                "tables": ["mood_entries"],
                "offset": 0,
                "limit": 3,
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 200 且返回 3 条记录
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "mood_entries" in data["changes"]
        assert len(data["changes"]["mood_entries"]) == 3

    def test_sync_pull_returns_paginated_results(self, client, initialized_db, clean_sync_tables):
        """API 返回分页结果：offset 跳过 + limit 截断，跨页合并等于全部"""
        # Arrange: 插入 10 条记录
        _insert_mood_rows(initialized_db, 10)

        # Act: 分两页请求
        response1 = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "",
                "tables": ["mood_entries"],
                "offset": 0,
                "limit": 5,
            },
            headers=AUTH_HEADERS,
        )
        response2 = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "",
                "tables": ["mood_entries"],
                "offset": 5,
                "limit": 5,
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 两页各 5 条，ID 不重复，合并覆盖全部 10 条
        assert response1.status_code == 200
        assert response2.status_code == 200

        page1 = response1.json()["changes"]["mood_entries"]
        page2 = response2.json()["changes"]["mood_entries"]

        assert len(page1) == 5
        assert len(page2) == 5

        all_ids = {row["id"] for row in page1} | {row["id"] for row in page2}
        assert len(all_ids) == 10
        expected_ids = {f"mood-api-page-{i:03d}" for i in range(10)}
        assert all_ids == expected_ids

    def test_sync_pull_without_pagination_returns_all(self, client, initialized_db, clean_sync_tables):
        """API 不传分页参数：向后兼容，返回全部记录"""
        # Arrange: 插入 5 条记录
        _insert_mood_rows(initialized_db, 5)

        # Act: 不传 offset/limit（向后兼容）
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "",
                "tables": ["mood_entries"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 返回全部 5 条记录
        assert response.status_code == 200
        data = response.json()
        assert len(data["changes"]["mood_entries"]) == 5

    def test_sync_pull_rejects_zero_limit(self, client, initialized_db, clean_sync_tables):
        """limit=0 被拒绝：返回 422（防止客户端误判为最后一批导致静默数据丢失）"""
        # Arrange: 插入 3 条记录
        _insert_mood_rows(initialized_db, 3)

        # Act: limit=0
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "",
                "tables": ["mood_entries"],
                "limit": 0,
            },
            headers=AUTH_HEADERS,
        )

        # Assert: Pydantic 验证失败返回 422
        assert response.status_code == 422

    def test_sync_pull_rejects_negative_offset(self, client, initialized_db, clean_sync_tables):
        """offset=-1 被拒绝：返回 422（分页偏移量不能为负）"""
        # Arrange: 插入 3 条记录
        _insert_mood_rows(initialized_db, 3)

        # Act: offset=-1
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "",
                "tables": ["mood_entries"],
                "offset": -1,
            },
            headers=AUTH_HEADERS,
        )

        # Assert: Pydantic 验证失败返回 422
        assert response.status_code == 422
