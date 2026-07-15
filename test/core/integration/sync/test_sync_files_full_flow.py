"""
SyncClient 文件同步全流程集成测试（Issue 33）

测试 seam:
- Seam 1: SYNC_DIRECTORIES 白名单（4 个目录）
- Seam 2: 文件扫描排除 chat_history.json
- Seam 3: 同步前全量扫描刷新 current_hash
- Seam 4: Phase 1 - 快照交换（POST /pull-files/check）
- Seam 5: Phase 2a - 11 态矩阵判断
- Seam 6: Phase 2b - PULL 文件处理
- Seam 7: Phase 2c - PUSH 文件处理 + CONFLICT 跳过
- Seam 8: Phase 3 - verify + parent_hash 推进
- Seam 9: sync_once() 集成 + 旧方法删除

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1
TDD: 严格 red-green 循环，一个 seam 一个测试一个最小实现
"""

import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

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
def clean_file_dir(initialized_db):
    """为每个测试提供干净的文件目录（测试后清理）"""
    from lifeprism.config.settings_manager import settings

    test_dir = settings.lifeprism_data_path / "sync_full_flow_test"
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def clean_file_sync_state(initialized_db):
    """每个测试前后清理 file_sync_state 表"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()


# ==================== Helper Functions ====================


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_resp


# ==================== Seam 1: SYNC_DIRECTORIES 白名单 ====================


class TestSyncDirectoriesWhitelist:
    """Seam 1: SYNC_DIRECTORIES 更新为 4 个目录（对齐 Agent 工具白名单）"""

    def test_sync_directories_contains_exactly_four_dirs(self):
        """SYNC_DIRECTORIES 应只包含 session/、diary/、agent/、user/"""
        from lifeprism.sync.sync_client import SYNC_DIRECTORIES

        assert SYNC_DIRECTORIES == ["session/", "diary/", "agent/", "user/"]


# ==================== Seam 2: 文件扫描排除 chat_history.json ====================


class TestScanSyncFilesExcludesChatHistory:
    """Seam 2: _scan_sync_files() 扫描文件时排除 chat_history.json"""

    def test_scan_sync_files_excludes_chat_history_json(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """_scan_sync_files 应排除 chat_history.json（dreaming task 写入，云端无 dreaming）"""
        # Arrange: 创建测试目录，包含 chat_history.json 和普通文件
        from lifeprism.config.settings_manager import settings

        test_base = settings.lifeprism_data_path / "sync_full_flow_test"

        # 普通文件
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        (test_base / "user" / "user.md").write_text("用户数据", encoding="utf-8")

        # chat_history.json（应被排除）
        (test_base / "user" / "chat_history.json").write_text("[]", encoding="utf-8")

        # Act: 扫描目录
        files = sync_client._scan_sync_files(["sync_full_flow_test/"])

        # Assert: chat_history.json 不在结果中，普通文件在
        paths = {f for f in files}
        assert "sync_full_flow_test/user/user.md" in paths
        assert "sync_full_flow_test/user/chat_history.json" not in paths


# ==================== Seam 3: 同步前全量扫描刷新 current_hash ====================


class TestRefreshCurrentHashes:
    """Seam 3: _refresh_current_hashes() 扫描所有文件并刷新 file_sync_state.current_hash"""

    def test_refresh_current_hashes_updates_current_hash_for_all_files(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """_refresh_current_hashes 后，file_sync_state 应包含所有文件的 current_hash"""
        # Arrange: 创建测试文件
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        (test_base / "user" / "user.md").write_text("用户数据", encoding="utf-8")
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        (test_base / "diary" / "2026-07-14.md").write_text("日记内容", encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)

        # Act: 刷新 current_hash
        sync_client._refresh_current_hashes(["sync_full_flow_test/"])

        # Assert: file_sync_state 中有两条记录，current_hash 正确
        states = provider.get_all_states("sync_full_flow_test/")
        assert len(states) == 2

        state_map = {s["file_path"]: s for s in states}
        assert "sync_full_flow_test/user/user.md" in state_map
        assert "sync_full_flow_test/diary/2026-07-14.md" in state_map

        # current_hash 应等于实时计算的 hash（已知字面量 "用户数据" 经 compute_file_hash）
        user_hash = compute_file_hash("用户数据".encode("utf-8"))
        assert state_map["sync_full_flow_test/user/user.md"]["current_hash"] == user_hash

        # 新文件 parent_hash 应为 NULL
        assert state_map["sync_full_flow_test/user/user.md"]["parent_hash"] is None


# ==================== Seam 4: Phase 1 - 快照交换 ====================


class TestPullFilesCheck:
    """Seam 4: _pull_files_check() 调用 POST /pull-files/check 获取云端文件 hash 状态"""

    def test_pull_files_check_calls_check_endpoint_and_returns_files(
        self, sync_client, initialized_db
    ):
        """_pull_files_check 应调用 /pull-files/check 并返回远端文件 hash 列表"""
        from unittest.mock import patch

        # Arrange: mock 云端 check 响应
        remote_files = [
            {"path": "user/user.md", "parent_hash": "abc123", "current_hash": "def456"},
            {"path": "diary/2026-07-14.md", "parent_hash": None, "current_hash": "xyz789"},
        ]
        mock_response = _make_mock_response({"files": remote_files, "sync_time": "..."})

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
        ) as mock_post:
            # Act
            result = sync_client._pull_files_check(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["session/", "diary/", "agent/", "user/"],
            )

        # Assert: 调用了 /pull-files/check
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["url"] == "http://test:8000/api/sync/pull-files/check"
        assert call_args.kwargs["json"]["last_sync_time"] == "2026-07-01T00:00:00+00:00"
        assert call_args.kwargs["json"]["directories"] == [
            "session/",
            "diary/",
            "agent/",
            "user/",
        ]
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"

        # Assert: 返回云端文件列表
        assert result == remote_files


# ==================== Seam 5: Phase 2a - 11 态矩阵判断 ====================


# 已知 hash 字面量（独立真值源，A != A1 != A2）
_HASH_A = "hash_aaa"
_HASH_A1 = "hash_a1a1"
_HASH_A2 = "hash_a2a2"


class TestDecideSyncAction:
    """Seam 5: _decide_sync_action() 按 11 态矩阵判定 PULL/PUSH/CONFLICT/SKIP

    参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 1

    参数说明:
      local_parent: 本地 parent_hash（None = 从未同步或文件不存在）
      local_current: 本地 current_hash（None = 文件不存在本地）
      remote_parent: 云端 parent_hash（None = 从未同步或文件不存在）
      remote_current: 云端 current_hash（None = 文件不存在云端）
    """

    @pytest.mark.parametrize(
        "local_parent, local_current, remote_parent, remote_current, expected, row_desc",
        [
            # Row 1: 本地新文件，云端不存在 → PUSH
            (None, _HASH_A1, None, None, "PUSH", "Row1: 本地新文件"),
            # Row 2: 本地不存在，云端新文件 → PULL
            (None, None, None, _HASH_A2, "PULL", "Row2: 云端新文件"),
            # Row 3: 双方都新建同路径，内容不同 → CONFLICT
            (None, _HASH_A1, None, _HASH_A2, "CONFLICT", "Row3: 双方都新建"),
            # Row 4: 本地从未同步（换电脑），云端有历史 → PULL
            (None, _HASH_A1, _HASH_A, _HASH_A, "PULL", "Row4: 换电脑场景"),
            # Row 5: 云端从未同步（新部署空文档），本地有历史 → PUSH
            (_HASH_A, _HASH_A, None, _HASH_A2, "PUSH", "Row5: 空文档覆盖Bug场景"),
            # Row 6: 双方都没改 → SKIP
            (_HASH_A, _HASH_A, _HASH_A, _HASH_A, "SKIP", "Row6: 双方都没改"),
            # Row 7: 仅本地改 → PUSH
            (_HASH_A, _HASH_A1, _HASH_A, _HASH_A, "PUSH", "Row7: 仅本地改"),
            # Row 8: 仅云端改 → PULL
            (_HASH_A, _HASH_A, _HASH_A, _HASH_A1, "PULL", "Row8: 仅云端改"),
            # Row 9: 双方都改且内容不同 → CONFLICT
            (_HASH_A, _HASH_A1, _HASH_A, _HASH_A2, "CONFLICT", "Row9: 双方都改"),
            # Row 10: parent 不一致（网络中断导致） → CONFLICT
            (_HASH_A1, _HASH_A1, _HASH_A2, _HASH_A2, "CONFLICT", "Row10: parent不一致"),
            # Row 11: parent 不一致（用户越界操作） → CONFLICT
            (_HASH_A, _HASH_A1, _HASH_A2, _HASH_A2, "CONFLICT", "Row11: parent不一致"),
        ],
    )
    def test_decide_sync_action_11_state_matrix(
        self,
        sync_client,
        local_parent,
        local_current,
        remote_parent,
        remote_current,
        expected,
        row_desc,
    ):
        """11 态矩阵每种组合应返回正确判定"""
        result = sync_client._decide_sync_action(
            local_parent=local_parent,
            local_current=local_current,
            remote_parent=remote_parent,
            remote_current=remote_current,
        )
        assert result == expected, f"{row_desc}: 期望 {expected}, 实际 {result}"

    @pytest.mark.parametrize(
        "local_parent, local_current, remote_parent, remote_current, expected",
        [
            # Row 3 边界: 双方都新建但内容相同 → SKIP
            (None, _HASH_A1, None, _HASH_A1, "SKIP"),
            # Row 9 边界: 双方都改但内容相同 → SKIP
            (_HASH_A, _HASH_A1, _HASH_A, _HASH_A1, "SKIP"),
        ],
    )
    def test_decide_sync_action_same_content_is_skip(
        self, sync_client, local_parent, local_current, remote_parent, remote_current, expected
    ):
        """双方内容相同时应 SKIP（即使都标记为"改过"）"""
        result = sync_client._decide_sync_action(
            local_parent=local_parent,
            local_current=local_current,
            remote_parent=remote_parent,
            remote_current=remote_current,
        )
        assert result == expected


# ==================== Seam 6: Phase 2b - PULL 文件处理 ====================


class TestPullFilesFetch:
    """Seam 6: _pull_files_fetch() 拉取文件内容 → 写入本地 → 立即更新 current_hash"""

    def test_pull_files_fetch_writes_file_and_updates_current_hash(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """fetch 拉取文件后写入本地，并立即更新 file_sync_state.current_hash"""
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 准备云端返回的文件内容
        file_content = "云端拉取的内容"
        compressed = gzip.compress(file_content.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("ascii")

        remote_files = [
            {
                "path": "sync_full_flow_test/user/user.md",
                "content": encoded,
                "parent_hash": "old_parent_hash",
                "current_hash": compute_file_hash(file_content.encode("utf-8")),
            }
        ]
        mock_response = _make_mock_response({"files": remote_files})

        provider = FileSyncStateProvider(db_manager=initialized_db)

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
        ) as mock_post:
            # Act: 拉取文件
            sync_client._pull_files_fetch(
                remote_url="http://test:8000",
                api_key="test-key",
                paths=["sync_full_flow_test/user/user.md"],
            )

        # Assert: 请求了 /pull-files/fetch
        call_args = mock_post.call_args
        assert call_args.kwargs["url"] == "http://test:8000/api/sync/pull-files/fetch"
        assert call_args.kwargs["json"]["paths"] == ["sync_full_flow_test/user/user.md"]

        # Assert: 文件已写入本地
        local_file = (
            settings.lifeprism_data_path / "sync_full_flow_test" / "user" / "user.md"
        )
        assert local_file.exists()
        assert local_file.read_text(encoding="utf-8") == file_content

        # Assert: file_sync_state 已更新 current_hash（立即更新，实时计算）
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state is not None
        expected_hash = compute_file_hash(file_content.encode("utf-8"))
        assert state["current_hash"] == expected_hash


# ==================== Seam 7: Phase 2c - PUSH 文件处理 ====================


class TestPushFiles:
    """Seam 7: _push_files() 推送本地文件（含 parent_hash + current_hash）到云端"""

    def test_push_files_sends_content_and_hashes(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """_push_files 应推送文件内容 + parent_hash + current_hash"""
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件并设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "agent").mkdir(parents=True, exist_ok=True)
        file_content = "本地待推送内容"
        local_file = test_base / "agent" / "identity.md"
        local_file.write_text(file_content, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        content_hash = compute_file_hash(file_content.encode("utf-8"))
        provider.upsert_state(
            file_path="sync_full_flow_test/agent/identity.md",
            parent_hash="old_parent_hash",
            current_hash=content_hash,
        )

        mock_response = _make_mock_response({
            "results": [{"path": "sync_full_flow_test/agent/identity.md", "action": "accepted"}],
            "sync_time": "...",
        })

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
        ) as mock_post:
            # Act: 推送文件
            sync_client._push_files(
                remote_url="http://test:8000",
                api_key="test-key",
                paths=["sync_full_flow_test/agent/identity.md"],
            )

        # Assert: 调用了 /push-files
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["url"] == "http://test:8000/api/sync/push-files"

        # Assert: 请求体包含 path, content, parent_hash, current_hash
        files_payload = call_args.kwargs["json"]["files"]
        assert len(files_payload) == 1
        item = files_payload[0]
        assert item["path"] == "sync_full_flow_test/agent/identity.md"
        assert item["parent_hash"] == "old_parent_hash"
        assert item["current_hash"] == content_hash

        # Assert: content 可以正确解码
        compressed = base64.b64decode(item["content"])
        decoded = gzip.decompress(compressed).decode("utf-8")
        assert decoded == file_content


# ==================== Seam 8: Phase 3 - verify + parent_hash 推进 ====================


class TestVerifyAndAdvanceParent:
    """Seam 8: _verify_and_advance_parent() 一致性校验 + parent_hash 推进"""

    def test_verify_consistent_advances_parent_hash(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """hash 一致时：本地 + 云端 parent_hash 推进为 current_hash"""
        from unittest.mock import patch

        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange: 设置 file_sync_state（parent_hash 旧值，current_hash 新值）
        provider = FileSyncStateProvider(db_manager=initialized_db)
        current_hash = "new_hash_after_sync"
        provider.upsert_state(
            file_path="sync_full_flow_test/user/user.md",
            parent_hash="old_parent_hash",
            current_hash=current_hash,
        )

        # mock verify 响应：云端 hash 与本地一致
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/user/user.md", "current_hash": current_hash}]
        })
        # mock commit 响应
        commit_response = _make_mock_response({
            "committed": [{"path": "sync_full_flow_test/user/user.md", "parent_hash": current_hash}]
        })

        responses = [verify_response, commit_response]

        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=responses
        ) as mock_post:
            # Act
            sync_client._verify_and_advance_parent(
                remote_url="http://test:8000",
                api_key="test-key",
                paths=["sync_full_flow_test/user/user.md"],
            )

        # Assert: 调用了 verify + commit 两个端点
        assert mock_post.call_count == 2
        urls = [call.kwargs["url"] for call in mock_post.call_args_list]
        assert "http://test:8000/api/sync/pull-files/verify" in urls
        assert "http://test:8000/api/sync/pull-files/commit" in urls

        # Assert: 本地 parent_hash 已推进为 current_hash
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state["parent_hash"] == current_hash
        assert state["current_hash"] == current_hash

    def test_verify_inconsistent_does_not_advance_parent_hash(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """hash 不一致时：parent_hash 不推进，不调用 commit"""
        from unittest.mock import patch

        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange
        provider = FileSyncStateProvider(db_manager=initialized_db)
        old_parent = "old_parent_hash"
        local_current = "local_hash_value"
        cloud_hash = "different_cloud_hash"
        provider.upsert_state(
            file_path="sync_full_flow_test/user/user.md",
            parent_hash=old_parent,
            current_hash=local_current,
        )

        # mock verify 响应：云端 hash 与本地不一致
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/user/user.md", "current_hash": cloud_hash}]
        })

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=verify_response
        ) as mock_post:
            # Act
            sync_client._verify_and_advance_parent(
                remote_url="http://test:8000",
                api_key="test-key",
                paths=["sync_full_flow_test/user/user.md"],
            )

        # Assert: 只调用了 verify，未调用 commit
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["url"] == "http://test:8000/api/sync/pull-files/verify"

        # Assert: parent_hash 未推进
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state["parent_hash"] == old_parent


# ==================== Seam 9: _sync_files_full_flow 全流程编排 ====================


class TestSyncFilesFullFlow:
    """Seam 9: _sync_files_full_flow() 编排 Phase 1-3 完整流程"""

    def test_full_flow_pull_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程 PULL 场景：远端修改文件，本地未改 → 拉取并推进 parent_hash"""
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（旧内容），设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        old_content = "旧内容"
        new_content = "云端新内容"
        local_file = test_base / "user" / "user.md"
        local_file.write_text(old_content, encoding="utf-8")

        old_hash = compute_file_hash(old_content.encode("utf-8"))
        new_hash = compute_file_hash(new_content.encode("utf-8"))

        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path="sync_full_flow_test/user/user.md",
            parent_hash=old_hash,
            current_hash=old_hash,
        )

        # Mock 各阶段 HTTP 响应
        # Phase 1 check: 远端返回变更文件（远端改了）
        check_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/user/user.md",
                "parent_hash": old_hash,
                "current_hash": new_hash,
            }],
            "sync_time": "...",
        })
        # Phase 2b fetch: 返回新内容
        compressed = gzip.compress(new_content.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("ascii")
        fetch_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/user/user.md",
                "content": encoded,
                "parent_hash": old_hash,
                "current_hash": new_hash,
            }]
        })
        # Phase 3 verify: 返回一致 hash
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/user/user.md", "current_hash": new_hash}]
        })
        # Phase 3 commit
        commit_response = _make_mock_response({
            "committed": [{"path": "sync_full_flow_test/user/user.md", "parent_hash": new_hash}]
        })

        responses = [check_response, fetch_response, verify_response, commit_response]

        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=responses
        ) as mock_post:
            # Act: 执行全流程
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_full_flow_test/"],
            )

        # Assert: 调用了 check → fetch → verify → commit（4 次调用）
        assert mock_post.call_count == 4
        urls = [call.kwargs["url"] for call in mock_post.call_args_list]
        assert urls[0] == "http://test:8000/api/sync/pull-files/check"
        assert urls[1] == "http://test:8000/api/sync/pull-files/fetch"
        assert urls[2] == "http://test:8000/api/sync/pull-files/verify"
        assert urls[3] == "http://test:8000/api/sync/pull-files/commit"

        # Assert: 本地文件已更新为新内容
        assert local_file.read_text(encoding="utf-8") == new_content

        # Assert: parent_hash 已推进为 new_hash
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state["parent_hash"] == new_hash
        assert state["current_hash"] == new_hash

    def test_full_flow_push_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程 PUSH 场景：本地修改文件，远端未改 → 推送并推进 parent_hash

        Row 7: local_parent=A, local_current=A1, remote_parent=A, remote_current=A → PUSH
        """
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（已修改内容），设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "agent").mkdir(parents=True, exist_ok=True)
        old_content = "旧内容"
        new_content = "本地修改内容"
        local_file = test_base / "agent" / "identity.md"
        local_file.write_text(new_content, encoding="utf-8")

        old_hash = compute_file_hash(old_content.encode("utf-8"))
        new_hash = compute_file_hash(new_content.encode("utf-8"))

        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path="sync_full_flow_test/agent/identity.md",
            parent_hash=old_hash,
            current_hash=old_hash,
        )

        # Mock: check 返回空（远端无变更）→ PUSH → verify → commit
        check_response = _make_mock_response({"files": []})
        push_response = _make_mock_response({
            "results": [{"path": "sync_full_flow_test/agent/identity.md", "action": "accepted"}]
        })
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/agent/identity.md", "current_hash": new_hash}]
        })
        commit_response = _make_mock_response({
            "committed": [{"path": "sync_full_flow_test/agent/identity.md", "parent_hash": new_hash}]
        })

        responses = [check_response, push_response, verify_response, commit_response]

        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=responses
        ) as mock_post:
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_full_flow_test/"],
            )

        # Assert: check → push-files → verify → commit（4 次）
        assert mock_post.call_count == 4
        urls = [call.kwargs["url"] for call in mock_post.call_args_list]
        assert urls[0] == "http://test:8000/api/sync/pull-files/check"
        assert urls[1] == "http://test:8000/api/sync/push-files"
        assert urls[2] == "http://test:8000/api/sync/pull-files/verify"
        assert urls[3] == "http://test:8000/api/sync/pull-files/commit"

        # Assert: parent_hash 已推进为 new_hash
        state = provider.get_state("sync_full_flow_test/agent/identity.md")
        assert state["parent_hash"] == new_hash
        assert state["current_hash"] == new_hash

    def test_full_flow_skip_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程 SKIP 场景：双方都未改 → 仅 check，无 fetch/push/verify/commit

        Row 6: local_parent=A, local_current=A, remote_parent=A, remote_current=A → SKIP
        """
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（未修改），设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        content = "未修改内容"
        content_hash = compute_file_hash(content.encode("utf-8"))
        local_file = test_base / "user" / "user.md"
        local_file.write_text(content, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path="sync_full_flow_test/user/user.md",
            parent_hash=content_hash,
            current_hash=content_hash,
        )

        # Mock: check 返回空（远端无变更）
        check_response = _make_mock_response({"files": []})

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=check_response
        ) as mock_post:
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_full_flow_test/"],
            )

        # Assert: 仅 check 调用（1 次），无 fetch/push/verify/commit
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["url"] == "http://test:8000/api/sync/pull-files/check"

        # Assert: parent_hash 未变
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state["parent_hash"] == content_hash
        assert state["current_hash"] == content_hash

    def test_full_flow_conflict_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程 CONFLICT 场景：双方都改且内容不同 → 跳过，仅 check

        Row 9: local_parent=A, local_current=A1, remote_parent=A, remote_current=A2 → CONFLICT
        CONFLICT 文件跳过推送（仅记录日志），不触发 fetch/push/verify/commit。
        """
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（已修改），设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        old_content = "旧内容"
        local_new_content = "本地修改内容"
        remote_new_content = "云端修改内容"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(local_new_content, encoding="utf-8")

        old_hash = compute_file_hash(old_content.encode("utf-8"))
        local_new_hash = compute_file_hash(local_new_content.encode("utf-8"))
        remote_new_hash = compute_file_hash(remote_new_content.encode("utf-8"))

        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path="sync_full_flow_test/diary/2026-07-14.md",
            parent_hash=old_hash,
            current_hash=old_hash,
        )

        # Mock: check 返回远端变更（远端也改了）
        check_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/diary/2026-07-14.md",
                "parent_hash": old_hash,
                "current_hash": remote_new_hash,
            }],
            "sync_time": "...",
        })

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=check_response
        ) as mock_post:
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_full_flow_test/"],
            )

        # Assert: 仅 check 调用（1 次），CONFLICT 不触发 fetch/push/verify/commit
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["url"] == "http://test:8000/api/sync/pull-files/check"

        # Assert: parent_hash 未推进（CONFLICT 不处理）
        state = provider.get_state("sync_full_flow_test/diary/2026-07-14.md")
        assert state["parent_hash"] == old_hash
        # current_hash 被 _refresh_current_hashes 更新为本地新内容的 hash
        assert state["current_hash"] == local_new_hash

    def test_full_flow_change_computer_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程换电脑场景（Row #4）：本地从未同步（parent=NULL），云端有历史 → PULL

        Row 4: local_parent=NULL, local_current=A1, remote_parent=A, remote_current=A → PULL
        本地文件内容与云端不同，拉取云端内容覆盖本地。
        """
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（内容与云端不同），无 file_sync_state（新机器）
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        local_content = "本地已有内容"
        cloud_content = "云端内容"
        local_file = test_base / "user" / "user.md"
        local_file.write_text(local_content, encoding="utf-8")

        cloud_hash = compute_file_hash(cloud_content.encode("utf-8"))

        # Mock: check 返回云端文件（有 parent_hash 历史）
        check_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/user/user.md",
                "parent_hash": cloud_hash,
                "current_hash": cloud_hash,
            }],
            "sync_time": "...",
        })
        # fetch 返回云端内容
        compressed = gzip.compress(cloud_content.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("ascii")
        fetch_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/user/user.md",
                "content": encoded,
                "parent_hash": cloud_hash,
                "current_hash": cloud_hash,
            }]
        })
        # verify: 云端 hash 与本地一致（fetch 后本地已有云端内容）
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/user/user.md", "current_hash": cloud_hash}]
        })
        commit_response = _make_mock_response({
            "committed": [{"path": "sync_full_flow_test/user/user.md", "parent_hash": cloud_hash}]
        })

        responses = [check_response, fetch_response, verify_response, commit_response]

        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=responses
        ) as mock_post:
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="",  # 首次同步
                directories=["sync_full_flow_test/"],
            )

        # Assert: check → fetch → verify → commit（4 次）
        assert mock_post.call_count == 4
        urls = [call.kwargs["url"] for call in mock_post.call_args_list]
        assert urls[0] == "http://test:8000/api/sync/pull-files/check"
        assert urls[1] == "http://test:8000/api/sync/pull-files/fetch"
        assert urls[2] == "http://test:8000/api/sync/pull-files/verify"
        assert urls[3] == "http://test:8000/api/sync/pull-files/commit"

        # Assert: 本地文件已被云端内容覆盖
        assert local_file.read_text(encoding="utf-8") == cloud_content

        # Assert: parent_hash 已推进为 cloud_hash
        provider = FileSyncStateProvider(db_manager=initialized_db)
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state["parent_hash"] == cloud_hash
        assert state["current_hash"] == cloud_hash

    def test_full_flow_empty_doc_bug_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程空文档覆盖 Bug 场景（Row #5）：云端新部署空文档（parent=NULL），本地有历史 → PUSH

        Row 5: local_parent=A, local_current=A, remote_parent=NULL, remote_current=A2 → PUSH
        本地推送有内容的文件，不会反向被云端空文档覆盖。
        """
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（有内容），设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        local_content = "本地有内容"
        local_file = test_base / "user" / "user.md"
        local_file.write_text(local_content, encoding="utf-8")

        local_hash = compute_file_hash(local_content.encode("utf-8"))
        cloud_empty_hash = compute_file_hash("".encode("utf-8"))

        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path="sync_full_flow_test/user/user.md",
            parent_hash=local_hash,
            current_hash=local_hash,
        )

        # Mock: check 返回云端空文档（parent_hash=NULL，新部署）
        check_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/user/user.md",
                "parent_hash": None,
                "current_hash": cloud_empty_hash,
            }],
            "sync_time": "...",
        })
        push_response = _make_mock_response({
            "results": [{"path": "sync_full_flow_test/user/user.md", "action": "accepted"}]
        })
        # verify: 云端推送后已有本地内容
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/user/user.md", "current_hash": local_hash}]
        })
        commit_response = _make_mock_response({
            "committed": [{"path": "sync_full_flow_test/user/user.md", "parent_hash": local_hash}]
        })

        responses = [check_response, push_response, verify_response, commit_response]

        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=responses
        ) as mock_post:
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_full_flow_test/"],
            )

        # Assert: check → push-files → verify → commit（4 次）
        assert mock_post.call_count == 4
        urls = [call.kwargs["url"] for call in mock_post.call_args_list]
        assert urls[0] == "http://test:8000/api/sync/pull-files/check"
        assert urls[1] == "http://test:8000/api/sync/push-files"
        assert urls[2] == "http://test:8000/api/sync/pull-files/verify"
        assert urls[3] == "http://test:8000/api/sync/pull-files/commit"

        # Assert: 本地文件未被覆盖（仍有内容）
        assert local_file.read_text(encoding="utf-8") == local_content

        # Assert: parent_hash = local_hash（推送成功后推进）
        state = provider.get_state("sync_full_flow_test/user/user.md")
        assert state["parent_hash"] == local_hash
        assert state["current_hash"] == local_hash

    def test_full_flow_phase3_fail_scenario(
        self, sync_client, initialized_db, clean_file_dir, clean_file_sync_state
    ):
        """全流程 Phase 3 失败场景：PULL 后 verify hash 不一致 → 不推进 parent_hash

        Row 8: local_parent=A, local_current=A, remote_parent=A, remote_current=A1 → PULL
        fetch 后本地 current_hash=A1，但 verify 返回云端 hash 与本地不一致 → 不 commit。
        """
        import base64
        import gzip
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件（旧内容），设置 file_sync_state
        test_base = settings.lifeprism_data_path / "sync_full_flow_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        old_content = "旧内容"
        new_content = "云端新内容"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(old_content, encoding="utf-8")

        old_hash = compute_file_hash(old_content.encode("utf-8"))
        new_hash = compute_file_hash(new_content.encode("utf-8"))

        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path="sync_full_flow_test/diary/2026-07-14.md",
            parent_hash=old_hash,
            current_hash=old_hash,
        )

        # Mock: check 返回远端变更 → PULL
        check_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/diary/2026-07-14.md",
                "parent_hash": old_hash,
                "current_hash": new_hash,
            }],
            "sync_time": "...",
        })
        # fetch 返回新内容
        compressed = gzip.compress(new_content.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("ascii")
        fetch_response = _make_mock_response({
            "files": [{
                "path": "sync_full_flow_test/diary/2026-07-14.md",
                "content": encoded,
                "parent_hash": old_hash,
                "current_hash": new_hash,
            }]
        })
        # verify 返回不一致的 hash（Phase 3 失败）
        different_hash = "completely_different_hash_value"
        verify_response = _make_mock_response({
            "files": [{"path": "sync_full_flow_test/diary/2026-07-14.md", "current_hash": different_hash}]
        })

        responses = [check_response, fetch_response, verify_response]

        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=responses
        ) as mock_post:
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_full_flow_test/"],
            )

        # Assert: check → fetch → verify（3 次），无 commit
        assert mock_post.call_count == 3
        urls = [call.kwargs["url"] for call in mock_post.call_args_list]
        assert urls[0] == "http://test:8000/api/sync/pull-files/check"
        assert urls[1] == "http://test:8000/api/sync/pull-files/fetch"
        assert urls[2] == "http://test:8000/api/sync/pull-files/verify"

        # Assert: 本地文件已被 fetch 更新为新内容
        assert local_file.read_text(encoding="utf-8") == new_content

        # Assert: parent_hash 未推进（仍为 old_hash）
        state = provider.get_state("sync_full_flow_test/diary/2026-07-14.md")
        assert state["parent_hash"] == old_hash
        # current_hash 被 fetch 更新为 new_hash
        assert state["current_hash"] == new_hash
