"""
SyncClient 文件同步集成测试

测试 seam:
- Seam 1: sync_once() - 同时执行数据库和文件同步（全流程编排）

文件同步全流程（Phase 1-3）的详细测试见 test_sync_files_full_flow.py。

参考: test/core/integration/sync/test_sync_client.py
       test/core/integration/sync/test_sync_files_full_flow.py
"""

import shutil
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

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
def sync_client(initialized_db, sync_repository):
    """创建 SyncClient 实例"""
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient(db_manager=initialized_db, sync_repository=sync_repository)
    yield client


@pytest.fixture
def clean_tables(initialized_db):
    """清理同步表数据（测试后执行）"""
    sync_tables = ["todo_list"]
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in sync_tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


@pytest.fixture
def clean_file_dir(initialized_db):
    """为每个测试提供干净的文件目录（测试后清理）"""
    from lifeprism.config.settings_manager import settings

    test_dir = settings.lifeprism_data_path / "sync_client_test"
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


# ==================== Helper Functions ====================


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_resp


def _mock_get_setting_factory(
    remote_url="http://test:8000", last_sync_time="2026-07-01T00:00:00+00:00"
):
    """构建 get_setting 的 mock side_effect"""

    def _mock_get_setting(key, default=None):
        if key == "sync.remote_url":
            return remote_url
        elif key == "sync.last_sync_time":
            return last_sync_time
        return default

    return _mock_get_setting


# ==================== Seam 1: sync_once() 文件同步集成 ====================


class TestSyncOnceIncludesFileSync:
    """Seam 1: sync_once() - 同时执行数据库和文件同步"""

    def test_sync_once_includes_file_sync(
        self, sync_client, initialized_db, clean_tables, clean_file_dir
    ):
        """sync_once 同时执行数据库同步和文件同步全流程

        新流程（Issue 33）下文件同步走 _sync_files_full_flow：
        - Pre-sync: _refresh_current_hashes（无 HTTP，扫描本地文件刷新 current_hash）
        - Phase 1: POST /pull-files/check（快照交换）
        - Phase 2a: 11 态矩阵判定
        - Phase 2b/2c: PULL/PUSH（空目录时无操作）
        - Phase 3: verify + commit（无变更时无操作）

        空目录场景下仅触发 check 端点，不触发 fetch/push-files/verify/commit。
        """
        # Arrange: 插入本地增量数据，使 push 实际发送请求
        # updated_at 使用 ISO 8601 格式，确保 > last_sync_time "2026-07-01T00:00:00+00:00"
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-file-sync",
                    "文件同步测试",
                    "pool",
                    "2026-07-01T10:00:00+00:00",
                    "2026-07-01T12:00:00+00:00",
                ),
            )
            conn.commit()

        # Arrange: 记录调用顺序
        call_order = []

        def mock_post_side_effect(*args, **kwargs):
            url = kwargs.get("url", "")
            if "/pull-files" in url:
                call_order.append("pull-files")
                return _make_mock_response({"files": []})
            elif "/push-files" in url:
                call_order.append("push-files")
                return _make_mock_response({"status": "ok", "written": 0, "skipped": 0})
            elif "/pull" in url:
                call_order.append("pull")
                return _make_mock_response({"changes": {}})
            elif "/push" in url:
                call_order.append("push")
                return _make_mock_response({"success": True})
            return _make_mock_response({})

        with (
            patch("lifeprism.sync.sync_client.httpx.post", side_effect=mock_post_side_effect),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting"),
        ):
            # Act
            sync_client.sync_once(tables=["todo_list"], directories=["sync_client_test/"])

        # Assert: 数据库同步和文件同步全流程都被执行
        assert "pull" in call_order
        assert "push" in call_order
        assert "pull-files" in call_order
        # 顺序：数据库 pull -> push -> 文件同步全流程（pull-files/check）
        assert call_order.index("pull") < call_order.index("push")
        assert call_order.index("push") < call_order.index("pull-files")
