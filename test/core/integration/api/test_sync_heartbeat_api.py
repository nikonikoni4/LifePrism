"""
心跳 API + Pull 心跳更新集成测试

测试 seam:
- Issue #17: POST /api/sync/heartbeat - 心跳/生命周期事件端点
- Issue #18: POST /api/sync/pull - 心跳副作用（复用同步请求作为心跳）

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

TEST_API_KEY = "test_heartbeat_key_abc123xyz"

# 所有请求共用的认证 Header
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings, KEYRING_SERVICE_NAME

    settings._initialize()

    from lifeprism.repository import lw_db_manager

    # 重置 update_at 缓存
    from lifeprism.repository.base_providers.lw_base_data_provider import (
        LWBaseDataProvider,
    )
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
def reset_heartbeat():
    """每个测试前重置心跳管理器状态，避免测试间互相影响"""
    from lifeprism.sync.heartbeat_manager import heartbeat_manager

    heartbeat_manager._last_heartbeat = None
    heartbeat_manager._last_event = None
    yield
    heartbeat_manager._last_heartbeat = None
    heartbeat_manager._last_event = None


# ==================== Issue #17: POST /api/sync/heartbeat ====================


class TestSyncHeartbeat:
    """测试 POST /api/sync/heartbeat 端点"""

    def test_heartbeat_online_sets_event(self, client, reset_heartbeat):
        """发送 online 事件后 is_local_online() 返回 True"""
        # Arrange: 初始状态为离线
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        assert heartbeat_manager.is_local_online() is False

        # Act: 发送 online 事件
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "online"},
            headers=AUTH_HEADERS,
        )

        # Assert: 在线状态变为 True
        assert response.status_code == 200
        assert heartbeat_manager.is_local_online() is True

    def test_heartbeat_offline_sets_event(self, client, reset_heartbeat):
        """发送 offline 事件后 is_local_online() 返回 False"""
        # Arrange: 先设为 online
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True

        # Act: 发送 offline 事件
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "offline"},
            headers=AUTH_HEADERS,
        )

        # Assert: 在线状态变为 False
        assert response.status_code == 200
        assert heartbeat_manager.is_local_online() is False

    def test_heartbeat_ping_updates_heartbeat(self, client, reset_heartbeat):
        """发送 ping 事件后 is_local_online() 返回 True"""
        # Arrange: 初始状态为离线
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        assert heartbeat_manager.is_local_online() is False

        # Act: 发送 ping 事件
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "ping"},
            headers=AUTH_HEADERS,
        )

        # Assert: 心跳已更新，在线状态变为 True
        assert response.status_code == 200
        assert heartbeat_manager.is_local_online() is True

    def test_heartbeat_invalid_event_returns_422(self, client, reset_heartbeat):
        """无效事件类型返回 422 且错误码为 INVALID_HEARTBEAT_EVENT"""
        # Act: 发送无效事件类型
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "invalid_event"},
            headers=AUTH_HEADERS,
        )

        # Assert: 返回 422 且错误码为 INVALID_HEARTBEAT_EVENT
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_HEARTBEAT_EVENT"

    def test_heartbeat_requires_api_key(self, client, reset_heartbeat):
        """无 API Key 时返回 422"""
        # Act: 不带认证 Header
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "ping"},
        )

        # Assert: 返回 422（认证失败）
        assert response.status_code == 422

    def test_heartbeat_returns_server_time(self, client, reset_heartbeat):
        """响应包含 server_time 字段"""
        # Act: 发送 ping 事件
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "ping"},
            headers=AUTH_HEADERS,
        )

        # Assert: 响应包含 server_time
        assert response.status_code == 200
        data = response.json()
        assert "server_time" in data
        assert data["status"] == "ok"


# ==================== Issue #18: POST /api/sync/pull 心跳副作用 ====================


class TestSyncPullHeartbeat:
    """测试 POST /api/sync/pull 的心跳副作用（复用同步请求作为心跳）"""

    def test_pull_updates_heartbeat(self, client, initialized_db, reset_heartbeat):
        """发送 pull 请求后 is_local_online() 返回 True"""
        # Arrange: 初始状态为离线
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        assert heartbeat_manager.is_local_online() is False

        # Act: 发送 pull 请求
        response = client.post(
            "/api/sync/pull",
            json={
                "last_sync_time": "2026-07-01 00:00:00",
                "tables": ["mood_entries"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 心跳已更新，在线状态变为 True
        assert response.status_code == 200
        assert heartbeat_manager.is_local_online() is True

    def test_pull_heartbeat_before_query(self, client, initialized_db, reset_heartbeat):
        """心跳更新在查询之前执行（即使查询出错，心跳也已更新）"""
        # Arrange
        from unittest.mock import patch

        from lifeprism.server.api import sync_cloud_api
        from lifeprism.sync.heartbeat_manager import heartbeat_manager
        from lifeprism.utils.exceptions import DataAccessError

        assert heartbeat_manager.is_local_online() is False

        # Mock query_incremental 抛出异常
        with patch.object(
            sync_cloud_api.sync_repository,
            "query_incremental",
            side_effect=DataAccessError(message="查询失败"),
        ):
            # Act: pull 请求会因查询异常返回 500，但心跳应已更新
            response = client.post(
                "/api/sync/pull",
                json={
                    "last_sync_time": "2026-07-01 00:00:00",
                    "tables": ["mood_entries"],
                },
                headers=AUTH_HEADERS,
            )

        # Assert: 响应为 500（查询失败），但心跳已更新（在查询之前执行）
        assert response.status_code == 500
        assert heartbeat_manager.is_local_online() is True

    def test_consecutive_pulls_keep_online(self, client, initialized_db, reset_heartbeat):
        """连续 pull 请求保持在线状态"""
        # Arrange
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        # Act: 连续发送 3 次 pull 请求
        for _ in range(3):
            client.post(
                "/api/sync/pull",
                json={
                    "last_sync_time": "2026-07-01 00:00:00",
                    "tables": ["mood_entries"],
                },
                headers=AUTH_HEADERS,
            )

        # Assert: 仍然在线
        assert heartbeat_manager.is_local_online() is True
