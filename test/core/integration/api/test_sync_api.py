"""
Sync API 集成测试

测试 seam:
- Seam 4: POST /api/sync/pull - 正常拉取、认证失败、空查询
- Seam 5: POST /api/sync/push - 正常推送、认证失败、空推送、LWW 覆盖

使用最小化 FastAPI 应用测试 sync 路由，避免完整 app lifespan 的副作用。

认证方式：Authorization: Bearer {api_key} HTTP Header
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lifeprism.server.errors import to_http_exception
from lifeprism.utils.exceptions import LWBaseError

pytestmark = pytest.mark.core

TEST_API_KEY = "test_sync_key_abc123xyz"

# 所有请求共用的认证 Header
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}
WRONG_AUTH_HEADERS = {"Authorization": "Bearer wrong_key"}


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings, KEYRING_SERVICE_NAME

    settings._initialize()

    from lifeprism.repository import lw_db_manager

    # 重置 update_at 缓存
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    # 设置测试用 sync_api_key，先备份原始值
    import keyring
    _KEYRING_USERNAME = "sync_api_key"
    original_key = None
    try:
        original_key = keyring.get_password(KEYRING_SERVICE_NAME, _KEYRING_USERNAME)
    except Exception:
        pass

    from lifeprism.config import settings_manager

    settings_manager.set_setting("sync_api_key", TEST_API_KEY)

    yield lw_db_manager

    # 恢复原始 sync_api_key
    try:
        if original_key is not None:
            keyring.set_password(KEYRING_SERVICE_NAME, _KEYRING_USERNAME, original_key)
        else:
            keyring.delete_password(KEYRING_SERVICE_NAME, _KEYRING_USERNAME)
    except Exception:
        pass


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


# ==================== Seam 4: POST /api/sync/pull ====================


class TestSyncPull:
    """测试 POST /api/sync/pull 端点"""

    def test_pull_returns_incremental_data(self, client, initialized_db, clean_sync_tables):
        """正常拉取：返回 last_sync_time 之后的增量数据"""
        # Arrange: 插入测试数据
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-pull-1", "happy", 8, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-pull-2", "calm", 6, "2026-07-01 12:00:00", "2026-07-01 12:00:00"),
            )
            conn.commit()

        # Act
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "2026-07-01 09:00:00",
                "tables": ["mood_entries"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "sync_time" in data
        assert "mood_entries" in data["changes"]
        assert len(data["changes"]["mood_entries"]) == 2
        ids = {row["id"] for row in data["changes"]["mood_entries"]}
        assert ids == {"mood-pull-1", "mood-pull-2"}

    def test_pull_returns_empty_when_no_changes(self, client, initialized_db, clean_sync_tables):
        """空查询：无增量数据时返回空 changes"""
        # Act
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "2099-12-31 23:59:59",
                "tables": ["mood_entries"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["changes"] == {}
        assert "sync_time" in data

    def test_pull_returns_422_on_invalid_api_key(self, client, initialized_db):
        """认证失败：错误的 API Key 返回 422"""
        # Act
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "2026-07-01 00:00:00",
                "tables": ["mood_entries"],
            },
            headers=WRONG_AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"

    def test_pull_returns_422_on_missing_auth_header(self, client, initialized_db):
        """认证失败：缺少 Authorization Header 返回 422"""
        # Act
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "2026-07-01 00:00:00",
                "tables": ["mood_entries"],
            },
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"

    def test_pull_handles_multiple_tables(self, client, initialized_db, clean_sync_tables):
        """多表拉取：同时拉取多个表的增量数据"""
        # Arrange: 插入测试数据到两个表
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO mood_entries (id, mood_type_id, score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("mood-multi", "happy", 7, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("todo-multi", "测试任务", "pool", "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
            )
            conn.commit()

        # Act
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "2026-07-01 09:00:00",
                "tables": ["mood_entries", "todo_list"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "mood_entries" in data["changes"]
        assert "todo_list" in data["changes"]
        assert len(data["changes"]["mood_entries"]) == 1
        assert len(data["changes"]["todo_list"]) == 1


# ==================== Seam 5: POST /api/sync/push ====================


class TestSyncPush:
    """测试 POST /api/sync/push 端点"""

    def test_push_inserts_new_data(self, client, initialized_db, clean_sync_tables):
        """正常推送：插入新数据到数据库"""
        # Act
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {
                    "todo_list": [
                        {
                            "id": "todo-push-1",
                            "content": "推送的任务",
                            "state": "pool",
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 10:00:00",
                        }
                    ]
                },
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 响应正确
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "sync_time" in data

        # Assert: 数据库中有记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM todo_list WHERE id = ?", ("todo-push-1",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "推送的任务"

    def test_push_returns_422_on_invalid_api_key(self, client, initialized_db):
        """认证失败：错误的 API Key 返回 422"""
        # Act
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {"todo_list": []},
            },
            headers=WRONG_AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"

    def test_push_returns_422_on_missing_auth_header(self, client, initialized_db):
        """认证失败：缺少 Authorization Header 返回 422"""
        # Act
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {"todo_list": []},
            },
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"

    def test_push_handles_empty_changes(self, client, initialized_db):
        """空推送：changes 为空时返回 ok"""
        # Act
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {},
            },
            headers=AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "sync_time" in data

    def test_push_overwrites_with_newer_data(self, client, initialized_db, clean_sync_tables):
        """LWW 覆盖：推送 updated_at 更晚的数据应覆盖旧数据"""
        # Arrange: 先推送一条旧数据（updated_at = 10:00:00）
        client.post(
            "/api/sync/push",
            json={
                "changes": {
                    "todo_list": [
                        {
                            "id": "todo-overwrite-api",
                            "content": "原始内容",
                            "state": "pool",
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 10:00:00",
                        }
                    ]
                },
            },
            headers=AUTH_HEADERS,
        )

        # Act: 用相同 id 推送更新的数据（updated_at = 12:00:00）
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {
                    "todo_list": [
                        {
                            "id": "todo-overwrite-api",
                            "content": "覆盖后的内容",
                            "state": "completed",
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 12:00:00",
                        }
                    ]
                },
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 新数据覆盖了旧数据
        assert response.status_code == 200

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?",
                ("todo-overwrite-api",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "覆盖后的内容"
            assert row[1] == "completed"

    def test_push_skips_older_data_with_lww(self, client, initialized_db, clean_sync_tables):
        """LWW 跳过：推送 updated_at 更早的数据不应覆盖新数据"""
        # Arrange: 先推送一条新数据（updated_at = 12:00:00）
        client.post(
            "/api/sync/push",
            json={
                "changes": {
                    "todo_list": [
                        {
                            "id": "todo-lww-api",
                            "content": "新内容",
                            "state": "completed",
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 12:00:00",
                        }
                    ]
                },
            },
            headers=AUTH_HEADERS,
        )

        # Act: 用相同 id 推送更旧的数据（updated_at = 10:00:00）
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {
                    "todo_list": [
                        {
                            "id": "todo-lww-api",
                            "content": "旧内容",
                            "state": "pool",
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 10:00:00",
                        }
                    ]
                },
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 旧数据被跳过，数据库中仍然是新数据
        assert response.status_code == 200

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?",
                ("todo-lww-api",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "新内容"
            assert row[1] == "completed"

    def test_push_handles_multiple_tables(self, client, initialized_db, clean_sync_tables):
        """多表推送：同时推送多个表的数据"""
        # Act
        response = client.post(
            "/api/sync/push",
            json={
                "changes": {
                    "mood_entries": [
                        {
                            "id": "mood-push-multi",
                            "mood_type_id": "happy",
                            "score": 9,
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 10:00:00",
                        }
                    ],
                    "todo_list": [
                        {
                            "id": "todo-push-multi",
                            "content": "多表推送任务",
                            "state": "scheduled",
                            "created_at": "2026-07-01 10:00:00",
                            "updated_at": "2026-07-01 10:00:00",
                        }
                    ],
                },
            },
            headers=AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 200

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT score FROM mood_entries WHERE id = ?", ("mood-push-multi",))
            mood_row = cursor.fetchone()
            assert mood_row is not None
            assert mood_row[0] == 9

            cursor.execute("SELECT content FROM todo_list WHERE id = ?", ("todo-push-multi",))
            todo_row = cursor.fetchone()
            assert todo_row is not None
            assert todo_row[0] == "多表推送任务"
