"""
云端 pull-files 四端点集成测试 (check / fetch / verify / commit)

测试 seam:
- POST /api/sync/pull-files/check - 按 mtime 过滤返回变更文件的 hash 状态
- POST /api/sync/pull-files/fetch - 按路径返回文件内容 + hash
- POST /api/sync/pull-files/verify - 实时计算 hash（纯只读）
- POST /api/sync/pull-files/commit - 推进云端 parent_hash = current_hash

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 5
"""

import base64
import gzip
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

pytestmark = pytest.mark.core

TEST_API_KEY = "test_sync_key_abc123xyz"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}
WRONG_AUTH_HEADERS = {"Authorization": "Bearer wrong_key"}

TEST_DIR_NAME = "pull_files_phases_test"


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化设置 + 数据库（创建所有表，含 file_sync_state）

    注意：settings.lifeprism_data_path 可能指向 localData（config 文件配置），
    测试文件目录基于 settings.lifeprism_data_path 创建，确保 API 端点能正确读取。

    认证：get_sync_api_key() 在 full 模式下只从 keyring 读取（service="lifeprism"），
    不 fallback 到 config。因此必须用 set_sync_api_key() 写入 keyring。
    """
    from lifeprism.config.settings_manager import KEYRING_SERVICE_NAME, settings

    settings._initialize()

    # 用 set_sync_api_key 写入 keyring（full 模式下的正确路径）
    # 先备份原始 keyring 值，测试后恢复
    import keyring

    _KEYRING_USERNAME = "sync_api_key"
    original_key = None
    try:
        original_key = keyring.get_password(KEYRING_SERVICE_NAME, _KEYRING_USERNAME)
    except Exception:
        pass

    from lifeprism.sync.sync_config import set_sync_api_key

    set_sync_api_key(TEST_API_KEY)

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager

    # 恢复原始 keyring key
    try:
        if original_key is not None:
            keyring.set_password(KEYRING_SERVICE_NAME, _KEYRING_USERNAME, original_key)
        else:
            keyring.delete_password(KEYRING_SERVICE_NAME, _KEYRING_USERNAME)
    except Exception:
        pass


@pytest.fixture(scope="module")
def data_path(initialized_db):
    """返回 settings.lifeprism_data_path（API 端点使用的实际数据路径）"""
    from lifeprism.config.settings_manager import settings

    return settings.lifeprism_data_path.resolve()


@pytest.fixture
def client(initialized_db):
    """创建测试客户端（最小化 FastAPI 应用，仅包含 sync 路由 + 全局异常处理器）"""
    from lifeprism.server.api.sync_cloud_api import router as sync_cloud_router
    from lifeprism.server.errors import to_http_exception
    from lifeprism.utils.exceptions import LWBaseError

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
def clean_test_dir(data_path):
    """为每个测试提供干净的文件目录（基于 settings.lifeprism_data_path）"""
    test_dir = data_path / TEST_DIR_NAME
    if test_dir.exists():
        shutil.rmtree(test_dir)
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


def encode_content(content: str) -> str:
    """gzip 压缩 + base64 编码"""
    compressed = gzip.compress(content.encode("utf-8"))
    return base64.b64encode(compressed).decode("ascii")


def decode_content(encoded: str) -> str:
    """base64 解码 + gzip 解压"""
    compressed = base64.b64decode(encoded)
    return gzip.decompress(compressed).decode("utf-8")


def set_file_mtime(path: Path, iso_time: str) -> None:
    """设置文件的 mtime（ISO 8601 格式，UTC）"""
    dt = datetime.fromisoformat(iso_time)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


# ==================== Pull-Files Check Tests ====================


class TestSyncPullFilesCheck:
    """测试 POST /api/sync/pull-files/check 端点"""

    def test_check_returns_changed_files_with_hashes(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """增量检查：只返回 mtime > last_sync_time 的文件，含 path/parent_hash/current_hash"""
        # Arrange: 创建目录和文件，设置不同的 mtime
        sync_dir = clean_test_dir / "notes"
        sync_dir.mkdir()

        old_file = sync_dir / "old.txt"
        old_file.write_text("old content", encoding="utf-8")
        set_file_mtime(old_file, "2026-07-01T10:00:00+00:00")

        new_file = sync_dir / "new.txt"
        new_file.write_text("new content", encoding="utf-8")
        set_file_mtime(new_file, "2026-07-01T12:00:00+00:00")

        # Act: 检查 11:00 之后修改的文件
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T11:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/notes"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 只返回 new.txt，含 hash 信息
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "all_paths" in data
        assert "sync_time" in data
        assert len(data["files"]) == 1
        file_info = data["files"][0]
        assert file_info["path"] == f"{TEST_DIR_NAME}/notes/new.txt"
        assert "parent_hash" in file_info
        assert "current_hash" in file_info
        # current_hash 应实时计算
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_hash = compute_file_hash(b"new content")
        assert file_info["current_hash"] == expected_hash
        # parent_hash 应为 None（file_sync_state 中无记录）
        assert file_info["parent_hash"] is None
        # all_paths 应包含所有非黑名单文件（old + new）
        assert set(data["all_paths"]) == {
            f"{TEST_DIR_NAME}/notes/old.txt",
            f"{TEST_DIR_NAME}/notes/new.txt",
        }

    def test_check_excludes_chat_history_json(self, client, clean_test_dir, clean_file_sync_state):
        """排除 chat_history.json：即使 mtime 新于 last_sync_time 也不返回"""
        # Arrange: 创建目录，含 chat_history.json 和普通文件
        sync_dir = clean_test_dir / "session"
        sync_dir.mkdir()

        chat_history = sync_dir / "chat_history.json"
        chat_history.write_text('{"history": []}', encoding="utf-8")
        set_file_mtime(chat_history, "2026-07-01T12:00:00+00:00")

        normal_file = sync_dir / "session_001.jsonl"
        normal_file.write_text("line1\n", encoding="utf-8")
        set_file_mtime(normal_file, "2026-07-01T12:00:00+00:00")

        # Act: 检查 11:00 之后修改的文件
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T11:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/session"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 只返回 session_001.jsonl，不返回 chat_history.json
        assert response.status_code == 200
        data = response.json()
        paths = {f["path"] for f in data["files"]}
        assert f"{TEST_DIR_NAME}/session/session_001.jsonl" in paths
        assert f"{TEST_DIR_NAME}/session/chat_history.json" not in paths
        # all_paths 也应排除 chat_history.json
        assert f"{TEST_DIR_NAME}/session/chat_history.json" not in data["all_paths"]
        assert f"{TEST_DIR_NAME}/session/session_001.jsonl" in data["all_paths"]

    def test_check_returns_empty_list_when_no_changes(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """无变更文件时返回空列表（所有文件 mtime <= last_sync_time）"""
        sync_dir = clean_test_dir / "stable"
        sync_dir.mkdir()

        old_file = sync_dir / "old.txt"
        old_file.write_text("old content", encoding="utf-8")
        set_file_mtime(old_file, "2026-07-01T10:00:00+00:00")

        # Act: 检查 12:00 之后修改的文件（文件 mtime 为 10:00，无变更）
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T12:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/stable"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 返回空列表，不报错
        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert "sync_time" in data
        # all_paths 仍应包含所有文件（即使无变更）
        assert f"{TEST_DIR_NAME}/stable/old.txt" in data["all_paths"]

    def test_check_rejects_wrong_api_key(self, client, clean_test_dir):
        """错误 API Key 返回 422"""
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T11:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/notes"],
            },
            headers=WRONG_AUTH_HEADERS,
        )
        assert response.status_code == 422
        body = response.json()
        assert body["error_code"] == "INVALID_SYNC_API_KEY"

    def test_check_rejects_missing_api_key(self, client, clean_test_dir):
        """缺少 Authorization Header 返回 422"""
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T11:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/notes"],
            },
        )
        assert response.status_code == 422

    def test_check_all_paths_excludes_blacklist_and_includes_all_files(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """all_paths 包含所有非黑名单文件，排除 chat_history.json 和 bootstrap.md；
        files 只包含 mtime > last_sync_time 的文件"""
        # Arrange: 创建多种文件，含黑名单文件
        sync_dir = clean_test_dir / "mixed"
        sync_dir.mkdir()

        # 普通文件（新 + 旧）
        new_md = sync_dir / "new.md"
        new_md.write_text("new", encoding="utf-8")
        set_file_mtime(new_md, "2026-07-01T12:00:00+00:00")

        old_jsonl = sync_dir / "old.jsonl"
        old_jsonl.write_text("line\n", encoding="utf-8")
        set_file_mtime(old_jsonl, "2026-07-01T10:00:00+00:00")

        # 黑名单文件
        chat_history = sync_dir / "chat_history.json"
        chat_history.write_text("{}", encoding="utf-8")
        set_file_mtime(chat_history, "2026-07-01T12:00:00+00:00")

        bootstrap = sync_dir / "bootstrap.md"
        bootstrap.write_text("bootstrap", encoding="utf-8")
        set_file_mtime(bootstrap, "2026-07-01T12:00:00+00:00")

        # Act: 检查 11:00 之后修改的文件
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T11:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/mixed"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: files 只包含 mtime > 11:00 的非黑名单文件（new.md）
        assert response.status_code == 200
        data = response.json()
        file_paths = {f["path"] for f in data["files"]}
        assert file_paths == {f"{TEST_DIR_NAME}/mixed/new.md"}

        # all_paths 包含所有非黑名单文件（new.md + old.jsonl），排除黑名单
        all_paths_set = set(data["all_paths"])
        assert f"{TEST_DIR_NAME}/mixed/new.md" in all_paths_set
        assert f"{TEST_DIR_NAME}/mixed/old.jsonl" in all_paths_set
        assert f"{TEST_DIR_NAME}/mixed/chat_history.json" not in all_paths_set
        assert f"{TEST_DIR_NAME}/mixed/bootstrap.md" not in all_paths_set


# ==================== Pull-Files Fetch Tests ====================


class TestSyncPullFilesFetch:
    """测试 POST /api/sync/pull-files/fetch 端点"""

    def test_fetch_returns_content_and_hashes(self, client, clean_test_dir, clean_file_sync_state):
        """按路径返回文件内容（gzip+base64）+ parent_hash + current_hash"""
        # Arrange: 创建文件（用 write_bytes 避免 Windows 换行符转换）
        sync_dir = clean_test_dir / "user"
        sync_dir.mkdir()

        test_file = sync_dir / "user.md"
        original_content = "# 用户档案\n这是用户数据。"
        test_file.write_bytes(original_content.encode("utf-8"))

        rel_path = f"{TEST_DIR_NAME}/user/user.md"

        # Act: fetch 该文件
        response = client.post(
            "/api/sync/pull-files/fetch",
            json={"paths": [rel_path]},
            headers=AUTH_HEADERS,
        )

        # Assert: 返回内容 + hash
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 1
        file_info = data["files"][0]
        assert file_info["path"] == rel_path
        # content 可正确解码为原始内容
        assert decode_content(file_info["content"]) == original_content
        # current_hash 实时计算
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_hash = compute_file_hash(original_content.encode("utf-8"))
        assert file_info["current_hash"] == expected_hash
        # parent_hash 为 None（file_sync_state 中无记录）
        assert file_info["parent_hash"] is None

    def test_fetch_returns_parent_hash_from_state(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """file_sync_state 中有记录时，fetch 返回 parent_hash"""
        sync_dir = clean_test_dir / "diary"
        sync_dir.mkdir()

        test_file = sync_dir / "today.md"
        test_file.write_bytes(b"today diary")

        rel_path = f"{TEST_DIR_NAME}/diary/today.md"

        # 预设 file_sync_state 记录
        from lifeprism.repository.providers import file_sync_state_provider

        file_sync_state_provider.upsert_state(
            file_path=rel_path,
            parent_hash="abc123parent",
            current_hash="def456current",
        )

        # Act
        response = client.post(
            "/api/sync/pull-files/fetch",
            json={"paths": [rel_path]},
            headers=AUTH_HEADERS,
        )

        # Assert: parent_hash 来自 file_sync_state
        assert response.status_code == 200
        data = response.json()
        file_info = data["files"][0]
        assert file_info["parent_hash"] == "abc123parent"
        # current_hash 应实时计算（不使用缓存值 def456current）
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_hash = compute_file_hash(b"today diary")
        assert file_info["current_hash"] == expected_hash

    def test_fetch_skips_nonexistent_paths(self, client, clean_test_dir, clean_file_sync_state):
        """请求路径不存在时跳过（不报错，不返回该文件）"""
        # Arrange: 创建一个存在的文件
        sync_dir = clean_test_dir / "agent"
        sync_dir.mkdir()
        existing_file = sync_dir / "config.json"
        existing_file.write_bytes(b'{"key": "value"}')

        existing_rel = f"{TEST_DIR_NAME}/agent/config.json"
        nonexistent_rel = f"{TEST_DIR_NAME}/agent/missing.json"

        # Act: 同时请求存在和不存在的路径
        response = client.post(
            "/api/sync/pull-files/fetch",
            json={"paths": [existing_rel, nonexistent_rel]},
            headers=AUTH_HEADERS,
        )

        # Assert: 只返回存在的文件，不报错
        assert response.status_code == 200
        data = response.json()
        paths = {f["path"] for f in data["files"]}
        assert existing_rel in paths
        assert nonexistent_rel not in paths
        assert len(data["files"]) == 1

    def test_fetch_skips_nonexistent_all_paths(self, client, clean_test_dir, clean_file_sync_state):
        """所有路径都不存在时返回空列表，不报错"""
        response = client.post(
            "/api/sync/pull-files/fetch",
            json={"paths": [f"{TEST_DIR_NAME}/nope1.txt", f"{TEST_DIR_NAME}/nope2.txt"]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []


# ==================== Pull-Files Verify Tests ====================


class TestSyncPullFilesVerify:
    """测试 POST /api/sync/pull-files/verify 端点"""

    def test_verify_returns_realtime_hash(self, client, clean_test_dir, clean_file_sync_state):
        """实时计算 hash 返回（纯只读，不修改状态）"""
        sync_dir = clean_test_dir / "verify"
        sync_dir.mkdir()

        test_file = sync_dir / "doc.md"
        test_file.write_bytes(b"verify content")

        rel_path = f"{TEST_DIR_NAME}/verify/doc.md"

        response = client.post(
            "/api/sync/pull-files/verify",
            json={"paths": [rel_path]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 1
        file_info = data["files"][0]
        assert file_info["path"] == rel_path
        # 只返回 current_hash，不返回 parent_hash
        assert "current_hash" in file_info
        assert "parent_hash" not in file_info
        # hash 实时计算
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_hash = compute_file_hash(b"verify content")
        assert file_info["current_hash"] == expected_hash

    def test_verify_is_readonly(self, client, clean_test_dir, clean_file_sync_state):
        """verify 不修改 file_sync_state 表（纯只读）"""
        sync_dir = clean_test_dir / "readonly"
        sync_dir.mkdir()

        test_file = sync_dir / "data.txt"
        test_file.write_bytes(b"readonly test")

        rel_path = f"{TEST_DIR_NAME}/readonly/data.txt"

        # 预设 file_sync_state 记录
        from lifeprism.repository.providers import file_sync_state_provider

        file_sync_state_provider.upsert_state(
            file_path=rel_path,
            parent_hash="original_parent",
            current_hash="original_current",
        )

        # Act: 调用 verify
        response = client.post(
            "/api/sync/pull-files/verify",
            json={"paths": [rel_path]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200

        # Assert: file_sync_state 记录未被修改
        state = file_sync_state_provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == "original_parent"
        assert state["current_hash"] == "original_current"

    def test_verify_skips_nonexistent_paths(self, client, clean_test_dir, clean_file_sync_state):
        """verify 路径不存在时跳过"""
        sync_dir = clean_test_dir / "mixed"
        sync_dir.mkdir()
        existing = sync_dir / "exists.txt"
        existing.write_bytes(b"exists")

        existing_rel = f"{TEST_DIR_NAME}/mixed/exists.txt"
        missing_rel = f"{TEST_DIR_NAME}/mixed/missing.txt"

        response = client.post(
            "/api/sync/pull-files/verify",
            json={"paths": [existing_rel, missing_rel]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        paths = {f["path"] for f in data["files"]}
        assert existing_rel in paths
        assert missing_rel not in paths


# ==================== Pull-Files Commit Tests ====================


class TestSyncPullFilesCommit:
    """测试 POST /api/sync/pull-files/commit 端点"""

    def test_commit_advances_parent_hash(self, client, clean_test_dir, clean_file_sync_state):
        """commit 推进 parent_hash = current_hash（实时计算）"""
        sync_dir = clean_test_dir / "commit"
        sync_dir.mkdir()

        test_file = sync_dir / "file.md"
        test_file.write_bytes(b"commit content")

        rel_path = f"{TEST_DIR_NAME}/commit/file.md"

        # 预设 file_sync_state：parent_hash 旧值
        from lifeprism.repository.providers import file_sync_state_provider

        file_sync_state_provider.upsert_state(
            file_path=rel_path,
            parent_hash="old_parent_hash",
            current_hash="old_current_hash",
        )

        # Act: commit
        response = client.post(
            "/api/sync/pull-files/commit",
            json={"paths": [rel_path]},
            headers=AUTH_HEADERS,
        )

        # Assert: 返回 committed 列表，parent_hash = 实时计算的 current_hash
        assert response.status_code == 200
        data = response.json()
        assert "committed" in data
        assert len(data["committed"]) == 1
        committed = data["committed"][0]
        assert committed["path"] == rel_path

        from lifeprism.sync.hash_utils import compute_file_hash

        expected_hash = compute_file_hash(b"commit content")
        assert committed["parent_hash"] == expected_hash

        # Assert: file_sync_state 中 parent_hash 已推进
        state = file_sync_state_provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == expected_hash
        assert state["current_hash"] == expected_hash

    def test_commit_creates_state_for_new_file(self, client, clean_test_dir, clean_file_sync_state):
        """commit 对无 state 记录的文件创建新记录（parent_hash = current_hash）"""
        sync_dir = clean_test_dir / "new"
        sync_dir.mkdir()

        test_file = sync_dir / "new.md"
        test_file.write_bytes(b"new file content")

        rel_path = f"{TEST_DIR_NAME}/new/new.md"

        # Act: commit（file_sync_state 中无记录）
        response = client.post(
            "/api/sync/pull-files/commit",
            json={"paths": [rel_path]},
            headers=AUTH_HEADERS,
        )

        # Assert: 创建了新记录
        assert response.status_code == 200
        data = response.json()
        assert len(data["committed"]) == 1

        from lifeprism.repository.providers import file_sync_state_provider
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_hash = compute_file_hash(b"new file content")

        state = file_sync_state_provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == expected_hash
        assert state["current_hash"] == expected_hash

    def test_commit_skips_nonexistent_paths(self, client, clean_test_dir, clean_file_sync_state):
        """commit 路径不存在时跳过"""
        sync_dir = clean_test_dir / "mixed_commit"
        sync_dir.mkdir()
        existing = sync_dir / "exists.txt"
        existing.write_bytes(b"exists")

        existing_rel = f"{TEST_DIR_NAME}/mixed_commit/exists.txt"
        missing_rel = f"{TEST_DIR_NAME}/mixed_commit/missing.txt"

        response = client.post(
            "/api/sync/pull-files/commit",
            json={"paths": [existing_rel, missing_rel]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        paths = {c["path"] for c in data["committed"]}
        assert existing_rel in paths
        assert missing_rel not in paths


# ==================== Path Traversal Security Tests ====================


class TestSyncPullFilesPathTraversal:
    """测试所有四个端点的路径遍历安全检查"""

    def test_check_rejects_path_traversal(self, client, clean_test_dir, clean_file_sync_state):
        """check 端点拒绝路径遍历攻击（../）"""
        sync_dir = clean_test_dir / "safe"
        sync_dir.mkdir()
        safe_file = sync_dir / "inside.txt"
        safe_file.write_bytes(b"safe content")
        set_file_mtime(safe_file, "2026-07-01T12:00:00+00:00")

        # 尝试用 ../ 访问 clean_test_dir 之外的文件
        response = client.post(
            "/api/sync/pull-files/check",
            json={
                "last_sync_time": "2026-07-01T00:00:00+00:00",
                "directories": [f"{TEST_DIR_NAME}/safe/../../../etc"],
            },
            headers=AUTH_HEADERS,
        )

        # 路径遍历被拒绝，返回空列表或不含外部文件
        assert response.status_code == 200
        data = response.json()
        # 不应返回任何 clean_test_dir 之外的文件
        for f in data["files"]:
            assert not f["path"].startswith("../")
            assert not f["path"].startswith("..")

    def test_fetch_rejects_path_traversal(self, client, clean_test_dir, clean_file_sync_state):
        """fetch 端点拒绝路径遍历攻击"""
        response = client.post(
            "/api/sync/pull-files/fetch",
            json={"paths": ["../../../etc/passwd"]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []

    def test_verify_rejects_path_traversal(self, client, clean_test_dir, clean_file_sync_state):
        """verify 端点拒绝路径遍历攻击"""
        response = client.post(
            "/api/sync/pull-files/verify",
            json={"paths": ["../../../etc/passwd"]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []

    def test_commit_rejects_path_traversal(self, client, clean_test_dir, clean_file_sync_state):
        """commit 端点拒绝路径遍历攻击"""
        response = client.post(
            "/api/sync/pull-files/commit",
            json={"paths": ["../../../etc/passwd"]},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["committed"] == []
