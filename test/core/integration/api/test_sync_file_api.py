"""
文件同步 API 集成测试

测试 seam:
- POST /api/sync/pull-files - 从云端拉取增量文件
- POST /api/sync/push-files - 推送本地文件到云端

使用最小化 FastAPI 应用测试 sync 路由，避免完整 app lifespan 的副作用。

认证方式：Authorization: Bearer {api_key} HTTP Header
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

# 所有请求共用的认证 Header
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}
WRONG_AUTH_HEADERS = {"Authorization": "Bearer wrong_key"}


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_settings(test_data_path):
    """初始化设置，确保 lifeprism_data_path 指向测试路径，并初始化数据库"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    # 覆盖 lifeprism_data_path 指向测试路径
    # （config.yaml 可能配置了不同的路径，但文件同步测试需要 test_data_path）
    settings._lifeprism_data_path = test_data_path

    # 设置测试用 sync_api_key
    # 注意：必须使用 set_sync_api_key() 而非 set_setting()，
    # 因为 get_sync_api_key() 在 full 模式下从 keyring 读取，
    # 而 set_setting() 在 full 模式下写入 config.yaml（不路由到 keyring）
    from lifeprism.sync.sync_config import set_sync_api_key

    set_sync_api_key(TEST_API_KEY)

    # 初始化数据库（file_sync_state 表需要存在）
    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import (
        LWBaseDataProvider,
    )
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield settings


@pytest.fixture
def client(initialized_settings):
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
def clean_test_dir(test_data_path):
    """为每个测试提供干净的文件目录"""
    test_dir = test_data_path / "sync_file_api_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def clean_file_sync_state(initialized_settings):
    """每个测试前后清理 file_sync_state 表"""
    from lifeprism.repository import lw_db_manager

    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()
    yield
    with lw_db_manager.get_connection() as conn:
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


# ==================== Pull-Files Tests ====================


class TestSyncPullFiles:
    """测试 POST /api/sync/pull-files 端点"""

    def test_pull_files_returns_changed_files(self, client, clean_test_dir):
        """增量拉取：只返回 mtime > last_sync_time 的文件"""
        # Arrange: 创建目录和文件，设置不同的 mtime
        sync_dir = clean_test_dir / "notes"
        sync_dir.mkdir()

        old_file = sync_dir / "old.txt"
        old_file.write_text("old content", encoding="utf-8")
        set_file_mtime(old_file, "2026-07-01T10:00:00+00:00")

        new_file = sync_dir / "new.txt"
        new_file.write_text("new content", encoding="utf-8")
        set_file_mtime(new_file, "2026-07-01T12:00:00+00:00")

        # Act: 拉取 11:00 之后修改的文件
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T11:00:00+00:00",
                "directories": ["sync_file_api_test/notes"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 只返回 new.txt
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "sync_time" in data
        paths = {f["path"] for f in data["files"]}
        assert "sync_file_api_test/notes/new.txt" in paths
        assert "sync_file_api_test/notes/old.txt" not in paths

    def test_pull_files_gzip_base64_encoding(self, client, clean_test_dir):
        """验证返回的内容可以正确解码（gzip 解压 + base64 解码后等于原始内容）"""
        # Arrange: 创建文件
        sync_dir = clean_test_dir / "encoded"
        sync_dir.mkdir()

        test_file = sync_dir / "test.txt"
        original_content = "这是一段测试内容，用于验证 gzip + base64 编码"
        test_file.write_text(original_content, encoding="utf-8")
        set_file_mtime(test_file, "2026-07-01T12:00:00+00:00")

        # Act
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T00:00:00+00:00",
                "directories": ["sync_file_api_test/encoded"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 解码后等于原始内容
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 1
        decoded_content = decode_content(data["files"][0]["content"])
        assert decoded_content == original_content

    def test_pull_files_nonexistent_directory_skipped(self, client, clean_test_dir):
        """目录不存在时跳过，不报错"""
        # Act: 请求一个不存在的目录
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T00:00:00+00:00",
                "directories": ["sync_file_api_test/nonexistent_dir"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 返回空文件列表，不报错
        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert "sync_time" in data

    def test_pull_files_requires_api_key(self, client, clean_test_dir):
        """无 API Key 时返回 422"""
        # Act
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T00:00:00+00:00",
                "directories": ["sync_file_api_test"],
            },
            headers=WRONG_AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"

    def test_pull_files_first_sync_empty_last_sync_time(self, client, clean_test_dir):
        """首次同步：last_sync_time 为空字符串时拉取全部文件，不崩溃"""
        # Arrange: 创建目录和文件
        sync_dir = clean_test_dir / "first_sync"
        sync_dir.mkdir()

        file_a = sync_dir / "a.txt"
        file_a.write_text("content a", encoding="utf-8")
        set_file_mtime(file_a, "2026-07-01T10:00:00+00:00")

        file_b = sync_dir / "b.txt"
        file_b.write_text("content b", encoding="utf-8")
        set_file_mtime(file_b, "2026-07-01T12:00:00+00:00")

        # Act: 首次同步，last_sync_time 为空字符串
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "",
                "directories": ["sync_file_api_test/first_sync"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 返回全部文件，不崩溃
        assert response.status_code == 200
        data = response.json()
        paths = {f["path"] for f in data["files"]}
        assert "sync_file_api_test/first_sync/a.txt" in paths
        assert "sync_file_api_test/first_sync/b.txt" in paths
        assert len(data["files"]) == 2

    def test_pull_files_supports_single_file(self, client, clean_test_dir):
        """单文件路径：直接拉取单个文件（如 channel/wechat/account.json）"""
        # Arrange: 创建单文件
        single_file = clean_test_dir / "config.json"
        single_file.write_text('{"key": "value"}', encoding="utf-8")
        set_file_mtime(single_file, "2026-07-01T12:00:00+00:00")

        # Act: 请求拉取单文件路径
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T00:00:00+00:00",
                "directories": ["sync_file_api_test/config.json"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 返回该单文件
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["path"] == "sync_file_api_test/config.json"
        decoded = decode_content(data["files"][0]["content"])
        assert decoded == '{"key": "value"}'

    def test_pull_files_single_file_respects_last_sync_time(self, client, clean_test_dir):
        """单文件路径：mtime <= last_sync_time 时跳过"""
        # Arrange: 创建单文件，mtime = 10:00
        single_file = clean_test_dir / "skip.json"
        single_file.write_text("old", encoding="utf-8")
        set_file_mtime(single_file, "2026-07-01T10:00:00+00:00")

        # Act: last_sync_time = 12:00（比文件 mtime 新）
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T12:00:00+00:00",
                "directories": ["sync_file_api_test/skip.json"],
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 文件被跳过
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 0


# ==================== Push-Files Tests ====================


class TestSyncPushFiles:
    """测试 POST /api/sync/push-files 端点（Issue 32: hash-based 同步）"""

    def test_push_files_accepts_hash_schema_and_returns_results(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """推送文件使用 parent_hash + current_hash 字段（无 mtime），返回 results 格式

        验收标准：
        - FilePushItem 新增 parent_hash + current_hash 字段
        - FilePushItem 移除 mtime 字段
        - Response 包含 results 字段（每文件的 action）
        """
        # Arrange
        encoded_content = encode_content("推送的新文件内容")

        # Act: 使用新 schema（parent_hash + current_hash，无 mtime）
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/pushed/new_file.txt",
                        "content": encoded_content,
                        "parent_hash": None,
                        "current_hash": "client_computed_hash_abc",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 响应 200，包含 results 字段
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "sync_time" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["path"] == "sync_file_api_test/pushed/new_file.txt"
        assert data["results"][0]["action"] == "accepted"

        # 文件已写入
        written_file = clean_test_dir / "pushed" / "new_file.txt"
        assert written_file.exists()
        assert written_file.read_text(encoding="utf-8") == "推送的新文件内容"

    def test_push_files_requires_api_key(self, client, clean_test_dir, clean_file_sync_state):
        """无 API Key 时返回 422"""
        # Act
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/auth_test.txt",
                        "content": encode_content("test"),
                        "parent_hash": None,
                        "current_hash": "hash_abc",
                    }
                ]
            },
            headers=WRONG_AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"

    def test_push_files_new_file_cloud_computes_hash_and_updates_state(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """新文件推送：云端写入后自行计算 current_hash 并插入 file_sync_state（parent_hash=NULL）

        验收标准：
        - 云端写入文件后立即调用 compute_file_hash 计算 current_hash
        - 新文件（file_sync_state 中无记录）插入：parent_hash=NULL, current_hash=云端计算值
        - 云端的 current_hash 不使用客户端传入的 current_hash（不信任客户端）
        """
        # Arrange: 推送新文件，客户端 current_hash 是一个明显的假值
        content = "云端 hash 计算测试内容"
        encoded_content = encode_content(content)
        client_fake_hash = "CLIENT_FAKE_HASH_SHOULD_BE_IGNORED"

        # Act
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/hash_test/new.txt",
                        "content": encoded_content,
                        "parent_hash": None,
                        "current_hash": client_fake_hash,
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 响应成功
        assert response.status_code == 200

        # Assert: file_sync_state 中已插入记录
        from lifeprism.repository.providers import file_sync_state_provider

        state = file_sync_state_provider.get_state("sync_file_api_test/hash_test/new.txt")
        assert state is not None, "新文件推送后 file_sync_state 应有记录"

        # Assert: parent_hash 为 None（新文件，push-files 不推进 parent_hash）
        assert state["parent_hash"] is None, "新文件 parent_hash 应为 None"

        # Assert: current_hash 是云端计算的值，而非客户端传入的假值
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_cloud_hash = compute_file_hash(content.encode("utf-8"))
        assert state["current_hash"] == expected_cloud_hash, (
            "云端 current_hash 应由 compute_file_hash(content_bytes) 计算，不信任客户端值"
        )
        assert state["current_hash"] != client_fake_hash, (
            "云端 current_hash 不应等于客户端传入的假值"
        )

    def test_push_files_existing_record_preserves_parent_hash(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """已有记录推送：只更新 current_hash，不修改 parent_hash

        验收标准：
        - file_sync_state 中已有记录（parent_hash 已设值）时，推送文件更新
        - parent_hash 保持原值不变（push-files 不推进 parent_hash，那是 commit 端点的职责）
        - current_hash 更新为云端新计算的值
        """
        # Arrange: 预置一条已有记录（模拟之前已 commit 过的文件）
        from lifeprism.repository.providers import file_sync_state_provider

        existing_parent_hash = "previously_committed_parent_hash_abc"
        old_current_hash = "old_current_hash_will_be_replaced"
        file_path_rel = "sync_file_api_test/existing/update.txt"
        file_sync_state_provider.upsert_state(
            file_path=file_path_rel,
            parent_hash=existing_parent_hash,
            current_hash=old_current_hash,
        )

        # Act: 推送该文件的新内容
        new_content = "更新后的文件内容"
        encoded_content = encode_content(new_content)
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": file_path_rel,
                        "content": encoded_content,
                        "parent_hash": None,
                        "current_hash": "client_hash_ignored",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 响应成功
        assert response.status_code == 200

        # Assert: file_sync_state 中 parent_hash 保持不变
        state = file_sync_state_provider.get_state(file_path_rel)
        assert state is not None, "已有记录不应被删除"
        assert state["parent_hash"] == existing_parent_hash, (
            "已有记录的 parent_hash 应保持不变，push-files 不推进 parent_hash"
        )

        # Assert: current_hash 已更新为云端新计算的值
        from lifeprism.sync.hash_utils import compute_file_hash

        expected_new_hash = compute_file_hash(new_content.encode("utf-8"))
        assert state["current_hash"] == expected_new_hash, "current_hash 应更新为云端新计算的值"
        assert state["current_hash"] != old_current_hash, "current_hash 不应保持旧值"


# ==================== 路径遍历安全测试 ====================


class TestPathTraversalSecurity:
    """测试 _is_path_safe() 路径遍历防护"""

    def test_push_files_rejects_path_traversal(self, client, clean_test_dir, clean_file_sync_state):
        """测试路径遍历攻击被拒绝"""
        # Arrange: 构造恶意路径，尝试写到 data_path 之外
        from lifeprism.config.settings_manager import settings

        data_path = settings.lifeprism_data_path.resolve()
        evil_file = data_path.parent / "evil_traversal_test.txt"
        # 确保测试前文件不存在
        if evil_file.exists():
            evil_file.unlink()

        encoded_content = encode_content("恶意内容")

        try:
            # Act: 发送 push-files 请求，使用路径遍历
            response = client.post(
                "/api/sync/push-files",
                json={
                    "files": [
                        {
                            "path": "../evil_traversal_test.txt",
                            "content": encoded_content,
                            "parent_hash": None,
                            "current_hash": "hash_abc",
                        }
                    ]
                },
                headers=AUTH_HEADERS,
            )

            # Assert: 文件未被写入，恶意路径不在 results 中
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            paths = {r["path"] for r in data["results"]}
            assert "../evil_traversal_test.txt" not in paths
            assert not evil_file.exists()
        finally:
            # 清理：确保恶意文件未被创建
            if evil_file.exists():
                evil_file.unlink()

    def test_push_files_rejects_nested_path_traversal(
        self, client, clean_test_dir, clean_file_sync_state
    ):
        """测试嵌套路径遍历攻击被拒绝（../../etc/evil 模式）"""
        # Arrange: 构造嵌套恶意路径
        from lifeprism.config.settings_manager import settings

        data_path = settings.lifeprism_data_path.resolve()
        evil_file = data_path.parent.parent / "evil_nested.txt"
        if evil_file.exists():
            evil_file.unlink()

        encoded_content = encode_content("嵌套恶意内容")

        try:
            # Act: 使用 ../../ 嵌套路径遍历
            response = client.post(
                "/api/sync/push-files",
                json={
                    "files": [
                        {
                            "path": "../../evil_nested.txt",
                            "content": encoded_content,
                            "parent_hash": None,
                            "current_hash": "hash_abc",
                        }
                    ]
                },
                headers=AUTH_HEADERS,
            )

            # Assert: 文件未被写入，恶意路径不在 results 中
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            paths = {r["path"] for r in data["results"]}
            assert "../../evil_nested.txt" not in paths
            assert not evil_file.exists()
        finally:
            if evil_file.exists():
                evil_file.unlink()

    def test_pull_files_path_traversal_not_in_results(self, client, clean_test_dir):
        """测试 pull-files 不会返回 data_path 之外的文件"""
        # Arrange: 在 data_path 之外创建文件
        from lifeprism.config.settings_manager import settings

        data_path = settings.lifeprism_data_path.resolve()
        outside_file = data_path.parent / "outside_secret.txt"
        outside_file.write_text("data_path 之外的机密文件", encoding="utf-8")
        set_file_mtime(outside_file, "2026-07-01T12:00:00+00:00")

        try:
            # Act: 发送 pull-files 请求，尝试通过路径遍历访问外部文件
            response = client.post(
                "/api/sync/pull-files",
                json={
                    "last_sync_time": "2026-07-01T00:00:00+00:00",
                    "directories": ["../"],
                },
                headers=AUTH_HEADERS,
            )

            # Assert: 该文件不在返回结果中
            assert response.status_code == 200
            data = response.json()
            paths = {f["path"] for f in data["files"]}
            assert "outside_secret.txt" not in paths
            assert "../outside_secret.txt" not in paths
        finally:
            # 清理外部文件
            if outside_file.exists():
                outside_file.unlink()
