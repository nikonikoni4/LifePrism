"""
SyncClient 集成测试

测试 seam:
- Seam 1: sync_once() - 测试完整同步流程
- Seam 2: pull_from_remote() - 拉取新记录、覆盖未修改记录、保留本地更新记录
- Seam 3: push_to_remote() - 推送本地变更
- Seam 4: 原子性保证 - 部分失败时不更新 last_sync_time

参考: test/core/integration/repository/test_sync_repository.py
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

    # 重置 update_at 缓存（确保测试使用最新配置）
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
    sync_tables = [
        "mood_entries",
        "todo_list",
        "goal",
        "diary",
        "timeline_custom_block",
        "user_app_behavior_log",
    ]
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in sync_tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


@pytest.fixture
def clean_file_dir(initialized_db):
    """为每个测试提供干净的文件目录（测试后清理）

    使用独立测试目录 sync_client_test/，避免扫描真实数据文件（session/diary/agent/user）
    导致文件同步全流程产生额外的 PULL/PUSH/verify 调用。
    """
    from lifeprism.config.settings_manager import settings

    test_dir = settings.lifeprism_data_path / "sync_client_test"
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_resp


# ==================== Seam 2: pull_from_remote() ====================


class TestPullFromRemoteInsertNew:
    """Seam 2a: pull_from_remote() - 拉取新记录"""

    def test_pull_inserts_new_record_into_empty_table(
        self, sync_client, initialized_db, clean_tables
    ):
        """拉取：远程新记录写入空表"""
        # Arrange: mock httpx.post 返回一条新记录
        remote_row = {
            "id": "todo-pull-001",
            "content": "远程任务",
            "state": "pool",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # Act
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list"],
            )

        # Assert: 本地数据库有该记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content FROM todo_list WHERE id = ?", ("todo-pull-001",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "todo-pull-001"
            assert row[1] == "远程任务"

    def test_pull_inserts_multiple_new_records(self, sync_client, initialized_db, clean_tables):
        """拉取：多条远程新记录写入本地"""
        # Arrange
        remote_rows = [
            {
                "id": "todo-multi-001",
                "content": "任务A",
                "state": "pool",
                "created_at": "2026-07-01 10:00:00",
                "updated_at": "2026-07-01 10:00:00",
            },
            {
                "id": "todo-multi-002",
                "content": "任务B",
                "state": "scheduled",
                "created_at": "2026-07-01 11:00:00",
                "updated_at": "2026-07-01 11:00:00",
            },
        ]
        mock_response = _make_mock_response({"changes": {"todo_list": remote_rows}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list"],
            )

        # Assert
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM todo_list")
            assert cursor.fetchone()[0] == 2

    def test_pull_sends_correct_request_body(self, sync_client, initialized_db, clean_tables):
        """拉取：HTTP 请求体包含 last_sync_time、tables、offset 和 limit（分批格式）"""
        mock_response = _make_mock_response({"changes": {}})

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
        ) as mock_post:
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="my-api-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list", "diary"],
            )

        # Assert: 分批拉取，每张表各发一次请求（空表只发一次）
        assert mock_post.call_count == 2
        # 验证每次请求的 URL、认证头和分批参数
        requested_tables = []
        for call in mock_post.call_args_list:
            assert call.kwargs["url"] == "http://test:8000/api/sync/pull"
            assert call.kwargs["json"]["last_sync_time"] == "2026-07-01 00:00:00"
            assert call.kwargs["json"]["offset"] == 0
            assert call.kwargs["json"]["limit"] == 1000
            assert call.kwargs["headers"]["Authorization"] == "Bearer my-api-key"
            requested_tables.extend(call.kwargs["json"]["tables"])
        # 两张表都已被请求
        assert set(requested_tables) == {"todo_list", "diary"}

    def test_pull_handles_empty_remote_data(self, sync_client, initialized_db, clean_tables):
        """拉取：远程无数据时不报错"""
        mock_response = _make_mock_response({"changes": {}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # Act: 不应抛出异常
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list"],
            )

        # Assert: 本地无数据
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM todo_list")
            assert cursor.fetchone()[0] == 0


class TestPullFromRemoteConflictResolution:
    """Seam 2b: pull_from_remote() - Last-Write-Wins 冲突解决"""

    def test_pull_overwrites_local_unmodified_record(
        self, sync_client, initialized_db, clean_tables
    ):
        """冲突解决：本地未修改（updated_at <= last_sync_time）→ 远程覆盖本地"""
        # Arrange: 本地已有一条记录，updated_at 在 last_sync_time 之前
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-conflict-001",
                    "本地原始内容",
                    "pool",
                    "2026-07-01 09:00:00",
                    "2026-07-01 09:00:00",
                ),
            )
            conn.commit()

        # 远程来了同 id 的记录，内容不同
        remote_row = {
            "id": "todo-conflict-001",
            "content": "远程更新内容",
            "state": "completed",
            "created_at": "2026-07-01 09:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = 09:30:00，本地 updated_at = 09:00:00 <= last_sync_time → 本地未修改
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 09:30:00",
                tables=["todo_list"],
            )

        # Assert: 本地被远程覆盖
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-conflict-001",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "远程更新内容"
            assert row[1] == "completed"

    def test_pull_preserves_local_modified_record_when_local_newer(
        self, sync_client, initialized_db, clean_tables
    ):
        """冲突解决：本地已修改且本地更新时间更晚 → 保留本地"""
        # Arrange: 本地已修改记录（updated_at > last_sync_time），且本地 updated_at > 远程 updated_at
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-conflict-002",
                    "本地修改后的内容",
                    "scheduled",
                    "2026-07-01 09:00:00",
                    "2026-07-01 12:00:00",
                ),
            )
            conn.commit()

        # 远程记录 updated_at = 11:00:00 < 本地 12:00:00
        remote_row = {
            "id": "todo-conflict-002",
            "content": "远程较旧的内容",
            "state": "pool",
            "created_at": "2026-07-01 09:00:00",
            "updated_at": "2026-07-01 11:00:00",
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = 10:00:00，本地 updated_at = 12:00:00 > last_sync_time → 本地已修改
            # 远程 updated_at = 11:00:00 < 本地 12:00:00 → 保留本地
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 10:00:00",
                tables=["todo_list"],
            )

        # Assert: 本地保留，未被远程覆盖
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-conflict-002",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "本地修改后的内容"
            assert row[1] == "scheduled"

    def test_pull_overwrites_local_when_remote_newer(
        self, sync_client, initialized_db, clean_tables
    ):
        """冲突解决：本地已修改但远程更新时间更晚 → 远程覆盖本地"""
        # Arrange: 本地已修改记录（updated_at > last_sync_time），但远程 updated_at > 本地 updated_at
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-conflict-003",
                    "本地修改后的内容",
                    "scheduled",
                    "2026-07-01 09:00:00",
                    "2026-07-01 11:00:00",
                ),
            )
            conn.commit()

        # 远程记录 updated_at = 12:00:00 > 本地 11:00:00
        remote_row = {
            "id": "todo-conflict-003",
            "content": "远程更新的内容",
            "state": "completed",
            "created_at": "2026-07-01 09:00:00",
            "updated_at": "2026-07-01 12:00:00",
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = 10:00:00，本地 updated_at = 11:00:00 > last_sync_time → 本地已修改
            # 远程 updated_at = 12:00:00 > 本地 11:00:00 → 远程覆盖本地
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 10:00:00",
                tables=["todo_list"],
            )

        # Assert: 本地被远程覆盖
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-conflict-003",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "远程更新的内容"
            assert row[1] == "completed"


# ==================== Seam 3: push_to_remote() ====================


class TestPushToRemote:
    """Seam 3: push_to_remote() - 推送本地变更"""

    def test_push_sends_local_incremental_changes(self, sync_client, initialized_db, clean_tables):
        """推送：本地增量数据通过 HTTP POST 发送到远程"""
        # Arrange: 本地插入增量数据
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("todo-push-001", "推送任务", "pool", "2026-07-01 10:00:00", "2026-07-01 11:00:00"),
            )
            conn.commit()

        mock_response = _make_mock_response({"success": True})

        with (
            patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response) as mock_post,
            patch(
                "lifeprism.config.settings_manager.get_setting", return_value="2026-07-01 00:00:00"
            ),
        ):
            sync_client.push_to_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                tables=["todo_list"],
            )

        # Assert: httpx.post 被调用，请求体包含增量数据
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["url"] == "http://test:8000/api/sync/push"
        tables_data = call_args.kwargs["json"]["changes"]
        assert "todo_list" in tables_data
        assert len(tables_data["todo_list"]) == 1
        assert tables_data["todo_list"][0]["id"] == "todo-push-001"

    def test_push_sends_correct_authorization_header(
        self, sync_client, initialized_db, clean_tables
    ):
        """推送：HTTP 请求包含正确的认证头"""
        # Arrange: 插入一条增量数据使 push 实际发送请求
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-push-auth",
                    "认证测试",
                    "pool",
                    "2026-07-01 10:00:00",
                    "2026-07-01 11:00:00",
                ),
            )
            conn.commit()

        mock_response = _make_mock_response({"success": True})

        with (
            patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response) as mock_post,
            patch(
                "lifeprism.config.settings_manager.get_setting", return_value="2026-07-01 00:00:00"
            ),
        ):
            sync_client.push_to_remote(
                remote_url="http://test:8000",
                api_key="my-push-key",
                tables=["todo_list"],
            )

        call_args = mock_post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer my-push-key"

    def test_push_handles_no_local_changes(self, sync_client, initialized_db, clean_tables):
        """推送：本地无增量数据时不发送请求"""
        mock_response = _make_mock_response({"success": True})

        with (
            patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response) as mock_post,
            patch(
                "lifeprism.config.settings_manager.get_setting", return_value="2026-07-01 00:00:00"
            ),
        ):
            sync_client.push_to_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                tables=["todo_list"],
            )

        # 无增量数据时不发送 POST 请求
        mock_post.assert_not_called()

    def test_push_only_sends_incremental_changes(self, sync_client, initialized_db, clean_tables):
        """推送：只发送 updated_at > last_sync_time 的记录"""
        # Arrange: 插入两条记录，一条在 last_sync_time 之前，一条之后
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("todo-old", "旧任务", "pool", "2026-07-01 08:00:00", "2026-07-01 08:00:00"),
            )
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("todo-new", "新任务", "pool", "2026-07-01 10:00:00", "2026-07-01 12:00:00"),
            )
            conn.commit()

        mock_response = _make_mock_response({"success": True})

        with (
            patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response) as mock_post,
            patch(
                "lifeprism.config.settings_manager.get_setting", return_value="2026-07-01 10:00:00"
            ),
        ):
            sync_client.push_to_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                tables=["todo_list"],
            )

        # Assert: 只推送了 todo-new（updated_at = 12:00:00 > last_sync_time = 10:00:00）
        tables_data = mock_post.call_args.kwargs["json"]["changes"]
        assert len(tables_data["todo_list"]) == 1
        assert tables_data["todo_list"][0]["id"] == "todo-new"


# ==================== Seam 1: sync_once() ====================


def _mock_get_setting_factory(remote_url="http://test:8000", last_sync_time="2026-07-01 00:00:00"):
    """构建 get_setting 的 mock side_effect"""

    def _mock_get_setting(key, default=None):
        if key == "sync.remote_url":
            return remote_url
        elif key == "sync.last_sync_time":
            return last_sync_time
        return default

    return _mock_get_setting


def _mock_post_factory(pull_data=None, push_success=True):
    """构建 httpx.post 的 mock side_effect，区分 4 种同步请求

    - /pull-files -> {"files": []}
    - /push-files -> {"status": "ok"}
    - /pull -> {"changes": pull_data}
    - /push -> {"success": True} 或 500 错误
    """

    def _mock_post(*args, **kwargs):
        url = kwargs.get("url", "")
        if "/pull-files" in url:
            return _make_mock_response({"files": []})
        elif "/push-files" in url:
            if push_success:
                return _make_mock_response({"status": "ok", "written": 0, "skipped": 0})
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = Exception("HTTP 500 Push Failed")
                return mock_resp
        elif "/pull" in url:
            resp = _make_mock_response({"changes": pull_data or {}})
            return resp
        elif "/push" in url:
            if push_success:
                return _make_mock_response({"success": True})
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = Exception("HTTP 500 Push Failed")
                return mock_resp
        return _make_mock_response({})

    return _mock_post


class TestSyncOnce:
    """Seam 1: sync_once() - 完整同步流程"""

    def test_sync_once_executes_pull_then_push(
        self, sync_client, initialized_db, clean_tables, clean_file_dir
    ):
        """完整同步：先 Pull 再 Push，文件同步全流程在数据库同步之后

        新流程（Issue 33）下文件同步走 _sync_files_full_flow：
        - Pre-sync: _refresh_current_hashes（无 HTTP，扫描本地文件刷新 current_hash）
        - Phase 1: POST /pull-files/check（快照交换）
        - Phase 2a: 11 态矩阵判定
        - Phase 2b/2c: PULL/PUSH（空目录时无操作）
        - Phase 3: verify + commit（无变更时无操作）

        空目录场景下仅触发 check 端点，不触发 fetch/push-files/verify/commit。
        """
        # Arrange: 插入本地增量数据，使 push 实际发送请求
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-sync-order",
                    "同步顺序测试",
                    "pool",
                    "2026-07-01 10:00:00",
                    "2026-07-01 12:00:00",
                ),
            )
            conn.commit()

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
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            sync_client.sync_once(tables=["todo_list"], directories=["sync_client_test/"])

        # Assert: 数据库 pull -> push -> 文件同步全流程（pull-files/check）
        # 空目录场景下文件同步仅触发 check 端点，不触发 fetch/push-files/verify/commit
        assert call_order == ["pull", "push", "pull-files"]
        # set_setting 被调用（更新 last_sync_time）
        mock_set_setting.assert_called_once()

    def test_sync_once_updates_last_sync_time_on_success(
        self, sync_client, initialized_db, clean_tables
    ):
        """完整同步：成功后更新 last_sync_time"""
        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            sync_client.sync_once(tables=["todo_list"])

        mock_set_setting.assert_called_once()
        args = mock_set_setting.call_args
        assert args.args[0] == "sync.last_sync_time"
        # last_sync_time 应该是一个非空时间字符串
        assert args.args[1] is not None
        assert len(args.args[1]) > 0

    def test_sync_once_writes_iso8601_last_sync_time(
        self, sync_client, initialized_db, clean_tables
    ):
        """完整同步：last_sync_time 使用 ISO 8601 格式（包含 T 分隔符）"""
        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            sync_client.sync_once(tables=["todo_list"])

        mock_set_setting.assert_called_once()
        args = mock_set_setting.call_args
        assert args.args[0] == "sync.last_sync_time"
        # ISO 8601 格式包含 T 分隔符（如 2026-07-09T14:30:00.123456）
        last_sync_time = args.args[1]
        assert "T" in last_sync_time, (
            f"last_sync_time 应为 ISO 8601 格式（包含 T 分隔符），实际: {last_sync_time}"
        )

    def test_sync_once_reads_config_from_settings(self, sync_client, initialized_db, clean_tables):
        """完整同步：从 settings 读取 remote_url、api_key、last_sync_time"""
        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ) as mock_post,
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(
                    remote_url="http://my-remote:9000",
                    last_sync_time="2026-06-01 00:00:00",
                ),
            ) as mock_get_setting,
            patch(
                "lifeprism.sync.sync_config.get_sync_api_key",
                return_value="my-secret-key",
            ) as mock_api_key,
            patch("lifeprism.config.settings_manager.set_setting"),
        ):
            sync_client.sync_once(tables=["todo_list"])

        # Assert: get_setting 被调用了 sync.remote_url 和 sync.last_sync_time
        get_setting_calls = [call.args[0] for call in mock_get_setting.call_args_list]
        assert "sync.remote_url" in get_setting_calls
        assert "sync.last_sync_time" in get_setting_calls

        # Assert: get_sync_api_key 被调用
        mock_api_key.assert_called_once()

        # Assert: HTTP 请求使用了配置的 URL 和 API Key
        for call in mock_post.call_args_list:
            url = call.kwargs.get("url", "")
            assert "http://my-remote:9000" in url
            assert call.kwargs["headers"]["Authorization"] == "Bearer my-secret-key"

    def test_sync_once_uses_default_tables_when_none(
        self, sync_client, initialized_db, clean_tables
    ):
        """完整同步：tables=None 时使用默认 SYNC_TABLES（动态表对比返回空）"""
        with (
            patch.object(sync_client, "_check_cloud_initialized", return_value=True),
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ) as mock_post,
            patch(
                "lifeprism.sync.sync_client.httpx.get",
                side_effect=lambda *args, **kwargs: _make_mock_response({"types": []}),
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting"),
        ):
            sync_client.sync_once()

        # Assert: 分批拉取使用了默认表列表（每张表单独请求）
        pull_calls = [
            c for c in mock_post.call_args_list if c.kwargs["url"].endswith("/api/sync/pull")
        ]
        assert len(pull_calls) > 0
        # 汇总所有 pull 请求中请求的表名
        all_requested_tables = set()
        for call in pull_calls:
            all_requested_tables.update(call.kwargs["json"]["tables"])
        assert len(all_requested_tables) > 0
        assert "todo_list" in all_requested_tables
        assert "diary" in all_requested_tables


# ==================== Seam 5: 动态表定义对比 ====================


class TestSyncDynamicTablesDefinitions:
    """Seam 5: _sync_dynamic_tables_definitions - 双向建表"""

    def test_cloud_has_local_missing_creates_local_tables(
        self, sync_client, initialized_db, clean_tables
    ):
        """云端有本地没有的 slug → 本地建表（只执行 DDL，不写 meta）"""
        # 清理可能遗留的自定义记录类型
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_record_fields")
            cursor.execute("DELETE FROM custom_record_types")
            conn.commit()

        cloud_types = [
            {"slug": "cloud_only", "fields": [{"field_key": "score", "field_type": "integer"}]},
            {"slug": "reading_log", "fields": [{"field_key": "book_name", "field_type": "text"}]},
        ]

        def mock_get(*args, **kwargs):
            return _make_mock_response({"types": cloud_types})

        with (
            patch(
                "lifeprism.sync.sync_client.httpx.get",
                side_effect=mock_get,
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting"),
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ),
        ):
            # 本地只有 reading_log（通过初始化后查询 custom_record_types 确认）
            # 因为 initialized_db 初始化时可能没有自定义记录类型，
            # cloud_only 不在本地定义中，应触发 _create_local_dynamic_tables
            dynamic_table_names = sync_client._sync_dynamic_tables_definitions(
                "http://test:8000", "test-key"
            )

        # 产出应包含两个动态表
        assert "custom_cloud_only" in dynamic_table_names
        assert "custom_reading_log" in dynamic_table_names

        # 验证本地确实建了 cloud_only 表
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_cloud_only'"
            )
            assert cursor.fetchone() is not None, "custom_cloud_only 表应已被创建"

        # 验证没有写 meta 数据
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM custom_record_types WHERE slug='cloud_only'")
            assert cursor.fetchone()[0] == 0, "DDL 建表不应写入 custom_record_types"

        # 清理测试创建的表
        with initialized_db.get_connection() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS custom_cloud_only")
            conn.commit()

    def test_local_has_cloud_missing_triggers_remote_rebuild(
        self, sync_client, initialized_db, clean_tables
    ):
        """本地有云端没有的 slug → 调用 _rebuild_remote_dynamic_tables"""
        # 清理可能遗留的自定义记录类型
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_record_fields")
            cursor.execute("DELETE FROM custom_record_types")
            conn.commit()

        call_order = []

        # 本地插入一条自定义记录类型（模拟本地有动态表，云端没有）
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "crt-local-only",
                    "本地独有",
                    "local_only",
                    "",
                    "2026-07-01 10:00:00",
                    "2026-07-01 10:00:00",
                ),
            )
            cursor.execute(
                "INSERT INTO custom_record_fields (id, type_id, field_name, field_key, field_type, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "crf-local-1",
                    "crt-local-only",
                    "备注",
                    "note",
                    "text",
                    1,
                    "2026-07-01 10:00:00",
                    "2026-07-01 10:00:00",
                ),
            )
            conn.commit()

        def mock_get(*args, **kwargs):
            call_order.append("get-definitions")
            return _make_mock_response({"types": []})

        def mock_post(*args, **kwargs):
            url = kwargs.get("url", "")
            if "rebuild-dynamic-tables" in url:
                call_order.append("rebuild")
            return _make_mock_response({"rebuilt": [{"slug": "local_only", "action": "created"}]})

        with (
            patch(
                "lifeprism.sync.sync_client.httpx.get",
                side_effect=mock_get,
            ),
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=mock_post,
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting"),
        ):
            dynamic_table_names = sync_client._sync_dynamic_tables_definitions(
                "http://test:8000", "test-key"
            )

        assert "get-definitions" in call_order
        assert "rebuild" in call_order, "本地有动态表时云端无时应触发远端重建"
        assert len(dynamic_table_names) > 0

    def test_both_sides_have_same_slugs_no_action(self, sync_client, initialized_db, clean_tables):
        """两端 slug 完全一致 → 不触发建表，直接返回并集"""
        # 清理可能遗留的自定义记录类型
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_record_fields")
            cursor.execute("DELETE FROM custom_record_types")
            conn.commit()

        call_order = []

        def mock_get(*args, **kwargs):
            return _make_mock_response(
                {
                    "types": [
                        {
                            "slug": "reading_log",
                            "fields": [{"field_key": "book_name", "field_type": "text"}],
                        },
                    ]
                }
            )

        def mock_post(*args, **kwargs):
            url = kwargs.get("url", "")
            if "rebuild-dynamic-tables" in url:
                call_order.append("rebuild-called")
            return _make_mock_response({})

        with (
            patch(
                "lifeprism.sync.sync_client.httpx.get",
                side_effect=mock_get,
            ),
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=mock_post,
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting"),
        ):
            dynamic_table_names = sync_client._sync_dynamic_tables_definitions(
                "http://test:8000", "test-key"
            )

        assert "rebuild-called" not in call_order, "两端 slug 一致时不应触发 rebuild"

        # 验证返回的并集去重
        assert len(dynamic_table_names) == len(set(dynamic_table_names)), "返回列表不应有重复表名"

    def test_cloud_get_fails_raises_exception(self, sync_client):
        """云端定义接口失败 → 抛异常，不丢失 call_stack"""

        def mock_get_fail(*args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
            return mock_resp

        with (
            patch(
                "lifeprism.sync.sync_client.httpx.get",
                side_effect=mock_get_fail,
            ),
        ):
            with pytest.raises(Exception):
                sync_client._sync_dynamic_tables_definitions("http://test:8000", "test-key")


# ==================== Seam 4: 原子性保证 ====================


class TestSyncOnceAtomicity:
    """Seam 4: 原子性保证 - 部分失败时不更新 last_sync_time"""

    def test_sync_once_does_not_update_last_sync_time_on_pull_failure(
        self, sync_client, initialized_db, clean_tables
    ):
        """原子性：Pull 失败时不更新 last_sync_time"""

        def mock_post_side_effect(*args, **kwargs):
            url = kwargs.get("url", "")
            if "/pull" in url:
                # pull 失败
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = Exception("HTTP 500 Pull Failed")
                return mock_resp
            return _make_mock_response({})

        with (
            patch("lifeprism.sync.sync_client.httpx.post", side_effect=mock_post_side_effect),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            # Act: sync_once 应该抛出异常
            with pytest.raises(Exception, match="Pull Failed"):
                sync_client.sync_once(tables=["todo_list"])

        # Assert: last_sync_time 未被更新
        mock_set_setting.assert_not_called()

    def test_sync_once_does_not_update_last_sync_time_on_push_failure(
        self, sync_client, initialized_db, clean_tables
    ):
        """原子性：Push 失败时不更新 last_sync_time"""
        # Arrange: 插入本地增量数据，使 push 实际发送请求并触发失败
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-push-fail-sync",
                    "Push失败测试",
                    "pool",
                    "2026-07-01 10:00:00",
                    "2026-07-01 12:00:00",
                ),
            )
            conn.commit()

        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(push_success=False),
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            with pytest.raises(Exception, match="Push Failed"):
                sync_client.sync_once(tables=["todo_list"])

        # Assert: last_sync_time 未被更新
        mock_set_setting.assert_not_called()

    def test_sync_once_pull_data_is_persisted_before_push(
        self, sync_client, initialized_db, clean_tables
    ):
        """原子性：Pull 写入的数据在 Push 之前已持久化"""
        # Pull 返回一条新记录
        remote_row = {
            "id": "todo-atomic-001",
            "content": "原子性测试任务",
            "state": "pool",
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }

        def mock_post_side_effect(*args, **kwargs):
            url = kwargs.get("url", "")
            if "/pull-files" in url:
                return _make_mock_response({"files": []})
            elif "/push-files" in url:
                return _make_mock_response({"status": "ok", "written": 0, "skipped": 0})
            elif "/pull" in url:
                return _make_mock_response({"changes": {"todo_list": [remote_row]}})
            elif "/push" in url:
                # 在 push 时验证本地已有 pull 写入的数据
                with initialized_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM todo_list WHERE id = ?", ("todo-atomic-001",)
                    )
                    count = cursor.fetchone()[0]
                    assert count == 1, "Pull 数据应在 Push 之前已持久化"
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
            sync_client.sync_once(tables=["todo_list"])


# ==================== Seam 5: 多类主键表同步 ====================


class TestPullMultiPrimaryKeyTables:
    """Seam 5: 多类主键表同步 - Category A/B/C"""

    def test_pull_syncs_diary_table_category_a(self, sync_client, initialized_db, clean_tables):
        """多类主键：diary 表同步（Category A，TEXT 主键 date）"""
        remote_row = {
            "date": "2026-07-01",
            "mood": "happy",
            "importance": "important",
            "custom_tags": "[]",
            "word_count": 100,
            "ai_summary": None,
            "diary_source_hash": None,
            "created_at": "2026-07-01 10:00:00",
            "updated_at": "2026-07-01 10:00:00",
        }
        mock_response = _make_mock_response({"changes": {"diary": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["diary"],
            )

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, mood, word_count FROM diary WHERE date = ?",
                ("2026-07-01",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "2026-07-01"
            assert row[1] == "happy"
            assert row[2] == 100

    def test_pull_diary_conflict_resolution_uses_date_pk(
        self, sync_client, initialized_db, clean_tables
    ):
        """多类主键：diary 表冲突解决使用 date 作为主键"""
        # Arrange: 本地已有一条 diary 记录（未修改）
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO diary (date, mood, word_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("2026-07-02", "calm", 50, "2026-07-02 08:00:00", "2026-07-02 08:00:00"),
            )
            conn.commit()

        # 远程来了同 date 的记录（内容不同）
        remote_row = {
            "date": "2026-07-02",
            "mood": "very_happy",
            "importance": "normal",
            "custom_tags": "[]",
            "word_count": 200,
            "ai_summary": "远程总结",
            "diary_source_hash": None,
            "created_at": "2026-07-02 08:00:00",
            "updated_at": "2026-07-02 10:00:00",
        }
        mock_response = _make_mock_response({"changes": {"diary": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = 09:00:00，本地 updated_at = 08:00:00 <= last_sync_time -> 覆盖
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-02 09:00:00",
                tables=["diary"],
            )

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT mood, word_count, ai_summary FROM diary WHERE date = ?",
                ("2026-07-02",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "very_happy"
            assert row[1] == 200
            assert row[2] == "远程总结"

    def test_pull_syncs_user_app_behavior_log_category_b(
        self, sync_client, initialized_db, clean_tables
    ):
        """多类主键：user_app_behavior_log 表同步（Category B，AUTOINCREMENT + UNIQUE(app, start_time)）"""
        # Arrange: 本地先插入一条记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_app_behavior_log "
                "(start_time, end_time, duration, app, title, is_multipurpose_app, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "2026-07-08 10:00:00",
                    "2026-07-08 11:00:00",
                    60,
                    "chrome.exe",
                    "Google Chrome",
                    0,
                    "2026-07-08 10:00:00",
                    "2026-07-08 10:00:00",
                ),
            )
            conn.commit()

        # 远程返回相同 (app, start_time) 但不同数据的记录（远程 id 与本地不同）
        remote_row = {
            "id": 999,
            "start_time": "2026-07-08 10:00:00",
            "end_time": "2026-07-08 11:30:00",
            "duration": 90,
            "app": "chrome.exe",
            "title": "Google Chrome - Updated",
            "is_multipurpose_app": 1,
            "category_id": None,
            "sub_category_id": None,
            "link_to_goal_id": None,
            "created_at": "2026-07-08 10:00:00",
            "updated_at": "2026-07-08 12:00:00",
        }
        mock_response = _make_mock_response({"changes": {"user_app_behavior_log": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-08 00:00:00",
                tables=["user_app_behavior_log"],
            )

        # Assert: 本地记录被覆盖（通过 UNIQUE(app, start_time) 约束判重）
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT duration, title, is_multipurpose_app FROM user_app_behavior_log "
                "WHERE app = ? AND start_time = ?",
                ("chrome.exe", "2026-07-08 10:00:00"),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 90  # duration 被覆盖
            assert row[1] == "Google Chrome - Updated"
            assert row[2] == 1  # is_multipurpose_app 被覆盖

    def test_pull_syncs_timeline_custom_block_category_c(
        self, sync_client, initialized_db, clean_tables
    ):
        """多类主键：timeline_custom_block 表同步（Category C，AUTOINCREMENT + UNIQUE(start_time)）"""
        remote_row = {
            "id": 888,
            "start_time": "2026-07-08T14:00:00",
            "end_time": "2026-07-08T15:30:00",
            "duration": 90,
            "content": "远程自定义时间块",
            "todo_id": None,
            "color": "#5B8FF9",
            "category_id": None,
            "sub_category_id": None,
            "created_at": "2026-07-08 14:00:00",
            "updated_at": "2026-07-08 14:00:00",
        }
        mock_response = _make_mock_response({"changes": {"timeline_custom_block": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-08 00:00:00",
                tables=["timeline_custom_block"],
            )

        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, duration, color FROM timeline_custom_block WHERE start_time = ?",
                ("2026-07-08T14:00:00",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "远程自定义时间块"
            assert row[1] == 90
            assert row[2] == "#5B8FF9"

    def test_pull_syncs_multiple_tables_in_one_request(
        self, sync_client, initialized_db, clean_tables
    ):
        """多表同步：一次 pull 请求处理多张表的数据"""
        remote_data = {
            "changes": {
                "todo_list": [
                    {
                        "id": "todo-multi-table-001",
                        "content": "任务1",
                        "state": "pool",
                        "created_at": "2026-07-01 10:00:00",
                        "updated_at": "2026-07-01 10:00:00",
                    }
                ],
                "diary": [
                    {
                        "date": "2026-07-01",
                        "mood": "happy",
                        "importance": "normal",
                        "custom_tags": "[]",
                        "word_count": 50,
                        "ai_summary": None,
                        "diary_source_hash": None,
                        "created_at": "2026-07-01 10:00:00",
                        "updated_at": "2026-07-01 10:00:00",
                    }
                ],
            }
        }
        mock_response = _make_mock_response(remote_data)

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list", "diary"],
            )

        # Assert: 两张表都有数据
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM todo_list")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM diary")
            assert cursor.fetchone()[0] == 1
