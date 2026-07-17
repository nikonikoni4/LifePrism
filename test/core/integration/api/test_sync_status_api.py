"""
同步状态查询和手动触发同步 API 集成测试

测试 seam:
- Seam 1: GET /api/sync/status - 返回 last_sync_time、status、remote_url、tables
- Seam 2: GET /api/sync/status - 无 SyncClient 时返回 503
- Seam 3: POST /api/sync/trigger - 触发同步返回 202
- Seam 4: POST /api/sync/trigger - 已在同步中返回 409
- Seam 5: _run_sync_background - 异常处理和 is_syncing 生命周期

使用最小化 FastAPI 应用测试 sync_status 路由，避免完整 app lifespan 的副作用。

Mock 策略:
- Mock SyncClient 的 sync_once()、is_syncing、try_start_sync()、finish_sync()
- Mock settings_manager.get_setting()
- Mock 数据库 COUNT 查询（SyncRepository.count_rows_batch）
"""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lifeprism.server.errors import to_http_exception
from lifeprism.utils.exceptions import LWBaseError

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def mock_sync_client():
    """创建 mock SyncClient

    适配后端变更：
    - is_syncing property 替代 _is_syncing
    - try_start_sync() / finish_sync() 替代直接设置 _is_syncing
    - sync_repository 通过 sync_client 获取
    """
    client = MagicMock()
    client.is_syncing = False
    client.try_start_sync = MagicMock(return_value=True)
    client.finish_sync = MagicMock()
    client.sync_once = MagicMock()
    client.sync_repository = MagicMock()
    return client


@pytest.fixture
def mock_get_setting():
    """Mock settings_manager.get_setting"""
    with patch("lifeprism.server.api.sync_status_api.get_setting") as mock:
        mock.side_effect = lambda key, default=None: {
            "sync.last_sync_time": "2026-07-09T10:30:00",
            "sync.remote_url": "https://example.com/sync",
        }.get(key, default if default is not None else "")
        yield mock


@pytest.fixture
def mock_sync_repository(mock_sync_client):
    """Mock SyncRepository（via sync_client.sync_repository，count_rows_batch 返回固定值）

    适配后端变更：
    - count_rows_batch 替代循环调用 count_rows
    - sync_repository 从 sync_client.sync_repository 获取
    向后兼容：同时 mock 模块级 sync_repository（旧 API）。
    """
    from lifeprism.sync.sync_client import SYNC_TABLES

    mock_repo = mock_sync_client.sync_repository
    mock_repo.count_rows_batch.return_value = {table: 42 for table in SYNC_TABLES}
    mock_repo.count_rows.return_value = 42

    # 向后兼容：如果模块级 sync_repository 仍存在（旧 API），也进行 patch
    import lifeprism.server.api.sync_status_api as api_module

    if hasattr(api_module, "sync_repository"):
        with patch.object(api_module, "sync_repository", mock_repo):
            yield mock_repo
    else:
        yield mock_repo


def _create_test_app(with_sync_client=True, sync_client=None):
    """创建最小化 FastAPI 应用（仅包含 sync_status 路由 + 全局异常处理器）"""
    from lifeprism.server.api.sync_status_api import router as sync_status_router

    test_app = FastAPI()

    @test_app.exception_handler(LWBaseError)
    async def lw_base_error_handler(request: Request, exc: LWBaseError):
        http_exc = to_http_exception(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )

    if with_sync_client:
        test_app.state.sync_client = sync_client

    test_app.include_router(sync_status_router)
    return TestClient(test_app)


@pytest.fixture
def client(mock_sync_client):
    """创建测试客户端（包含 SyncClient）"""
    return _create_test_app(with_sync_client=True, sync_client=mock_sync_client)


@pytest.fixture
def client_without_sync_client():
    """创建测试客户端（不含 SyncClient，用于测试 503）"""
    return _create_test_app(with_sync_client=False)


# ==================== Seam 1 & 2: GET /api/sync/status ====================


class TestSyncStatus:
    """测试 GET /api/sync/status 端点"""

    def test_get_status_returns_last_sync_time(
        self, client, mock_get_setting, mock_sync_repository
    ):
        """Seam 1: 返回 last_sync_time"""
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["last_sync_time"] == "2026-07-09T10:30:00"

    def test_get_status_returns_idle_status(
        self, client, mock_sync_client, mock_get_setting, mock_sync_repository
    ):
        """Seam 1: is_syncing=False 时返回 idle"""
        mock_sync_client.is_syncing = False
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"

    def test_get_status_returns_syncing_status(
        self, client, mock_sync_client, mock_get_setting, mock_sync_repository
    ):
        """Seam 1: is_syncing=True 时返回 syncing"""
        mock_sync_client.is_syncing = True
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "syncing"

    def test_get_status_returns_remote_url(self, client, mock_get_setting, mock_sync_repository):
        """Seam 1: 返回 remote_url"""
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["remote_url"] == "https://example.com/sync"

    def test_get_status_returns_table_counts(self, client, mock_get_setting, mock_sync_repository):
        """Seam 1: 返回各表记录数（通过 count_rows_batch 批量查询）"""
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        # mock_count_rows_batch 返回 42 for all tables
        assert data["tables"]["mood_entries"] == 42
        assert data["tables"]["diary"] == 42
        # 验证所有 SYNC_TABLES 都有计数
        from lifeprism.sync.sync_client import SYNC_TABLES

        for table in SYNC_TABLES:
            assert table in data["tables"], f"表 {table} 缺少计数"

    def test_get_status_calls_count_rows_batch(
        self, client, mock_get_setting, mock_sync_repository
    ):
        """Seam 1: 验证调用 count_rows_batch（而非逐表 count_rows）"""
        response = client.get("/api/sync/status")
        assert response.status_code == 200
        mock_sync_repository.count_rows_batch.assert_called_once()

    def test_get_status_returns_503_without_sync_client(self, client_without_sync_client):
        """Seam 2: 无 SyncClient 时返回 503"""
        response = client_without_sync_client.get("/api/sync/status")
        assert response.status_code == 503


# ==================== Seam 3 & 4: POST /api/sync/trigger ====================


class TestSyncTrigger:
    """测试 POST /api/sync/trigger 端点"""

    def test_trigger_returns_202(self, client, mock_sync_client):
        """Seam 3: try_start_sync() 返回 True 时触发同步返回 202，并验证核心副作用"""
        mock_sync_client.try_start_sync.return_value = True
        response = client.post("/api/sync/trigger")
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "同步已触发"
        assert data["status"] == "syncing"

        # 等待后台线程执行
        time.sleep(0.1)

        # 验证核心副作用：sync_once 被调用
        mock_sync_client.sync_once.assert_called_once()
        # 验证 finish_sync 被调用（is_syncing 生命周期重置）
        mock_sync_client.finish_sync.assert_called_once()

    def test_trigger_calls_try_start_sync(self, client, mock_sync_client):
        """Seam 3: 验证调用 try_start_sync()（原子并发控制）"""
        mock_sync_client.try_start_sync.return_value = True
        client.post("/api/sync/trigger")
        mock_sync_client.try_start_sync.assert_called_once()

    def test_trigger_returns_409_when_syncing(self, client, mock_sync_client):
        """Seam 4: try_start_sync() 返回 False（已在同步中）时返回 409"""
        mock_sync_client.try_start_sync.return_value = False
        response = client.post("/api/sync/trigger")
        assert response.status_code == 409
        data = response.json()
        assert data["message"] == "同步正在进行中"
        assert data["status"] == "syncing"

    def test_trigger_does_not_start_thread_when_syncing(self, client, mock_sync_client):
        """Seam 4: 已在同步中时不启动后台线程、不调用 sync_once"""
        mock_sync_client.try_start_sync.return_value = False
        client.post("/api/sync/trigger")
        mock_sync_client.sync_once.assert_not_called()

    def test_trigger_returns_503_without_sync_client(self, client_without_sync_client):
        """无 SyncClient 时返回 503"""
        response = client_without_sync_client.post("/api/sync/trigger")
        assert response.status_code == 503


# ==================== Seam 5: _run_sync_background 单元测试 ====================


class TestRunSyncBackground:
    """测试 _run_sync_background 函数的异常处理和 is_syncing 生命周期

    _run_sync_background 是后台线程执行同步的核心函数，
    包含 try/except/finally 确保 finish_sync 在异常时也能被调用。
    """

    def test_run_sync_background_calls_sync_once(self, mock_sync_client):
        """验证 _run_sync_background 调用了 sync_once"""
        from lifeprism.server.api.sync_status_api import _run_sync_background

        _run_sync_background(mock_sync_client)
        mock_sync_client.sync_once.assert_called_once()

    def test_run_sync_background_resets_is_syncing_on_success(self, mock_sync_client):
        """成功后 finish_sync 被调用"""
        from lifeprism.server.api.sync_status_api import _run_sync_background

        _run_sync_background(mock_sync_client)
        mock_sync_client.finish_sync.assert_called_once()

    def test_run_sync_background_resets_is_syncing_on_exception(self, mock_sync_client):
        """异常后 finish_sync 仍被调用"""
        from lifeprism.server.api.sync_status_api import _run_sync_background

        mock_sync_client.sync_once.side_effect = RuntimeError("同步失败")
        _run_sync_background(mock_sync_client)
        mock_sync_client.finish_sync.assert_called_once()

    def test_run_sync_background_logs_error_on_exception(self, mock_sync_client, caplog):
        """异常时记录 ERROR 日志"""
        from lifeprism.server.api.sync_status_api import _run_sync_background

        mock_sync_client.sync_once.side_effect = RuntimeError("同步失败")
        with caplog.at_level(logging.ERROR):
            _run_sync_background(mock_sync_client)

        assert any("手动触发同步失败" in record.message for record in caplog.records)
