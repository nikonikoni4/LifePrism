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
    """初始化设置，确保 lifeprism_data_path 指向测试路径"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.config import settings_manager

    settings_manager.set_setting("sync_api_key", TEST_API_KEY)

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
    """测试 POST /api/sync/push-files 端点"""

    def test_push_files_writes_new_file(self, client, clean_test_dir):
        """推送新文件时写入成功"""
        # Arrange
        encoded_content = encode_content("推送的新文件内容")

        # Act
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/pushed/new_file.txt",
                        "content": encoded_content,
                        "mtime": "2026-07-01T12:00:00+00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 文件已写入
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["written"] == 1
        assert data["skipped"] == 0

        written_file = clean_test_dir / "pushed" / "new_file.txt"
        assert written_file.exists()
        assert written_file.read_text(encoding="utf-8") == "推送的新文件内容"

    def test_push_files_lww_skips_when_local_newer(self, client, clean_test_dir):
        """本地文件 mtime 更新时跳过（LWW）"""
        # Arrange: 创建本地文件，mtime = 12:00（较新）
        local_file = clean_test_dir / "lww_test.txt"
        local_file.write_text("本地新内容", encoding="utf-8")
        set_file_mtime(local_file, "2026-07-01T12:00:00+00:00")

        # Act: 推送相同路径但 mtime = 10:00（较旧）的文件
        encoded_content = encode_content("远程旧内容")
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/lww_test.txt",
                        "content": encoded_content,
                        "mtime": "2026-07-01T10:00:00+00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 本地文件未被覆盖
        assert response.status_code == 200
        data = response.json()
        assert data["written"] == 0
        assert data["skipped"] == 1
        assert local_file.read_text(encoding="utf-8") == "本地新内容"

    def test_push_files_lww_overwrites_when_remote_newer(self, client, clean_test_dir):
        """远程文件 mtime 更新时覆盖本地"""
        # Arrange: 创建本地文件，mtime = 10:00（较旧）
        local_file = clean_test_dir / "lww_overwrite.txt"
        local_file.write_text("本地旧内容", encoding="utf-8")
        set_file_mtime(local_file, "2026-07-01T10:00:00+00:00")

        # Act: 推送相同路径但 mtime = 12:00（较新）的文件
        encoded_content = encode_content("远程新内容")
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/lww_overwrite.txt",
                        "content": encoded_content,
                        "mtime": "2026-07-01T12:00:00+00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 本地文件被覆盖
        assert response.status_code == 200
        data = response.json()
        assert data["written"] == 1
        assert data["skipped"] == 0
        assert local_file.read_text(encoding="utf-8") == "远程新内容"

    def test_push_files_creates_parent_directories(self, client, clean_test_dir):
        """自动创建父目录"""
        # Arrange
        encoded_content = encode_content("深层目录文件")

        # Act: 推送到深层路径
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/deep/nested/dir/file.txt",
                        "content": encoded_content,
                        "mtime": "2026-07-01T12:00:00+00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 父目录已创建，文件已写入
        assert response.status_code == 200
        data = response.json()
        assert data["written"] == 1

        deep_file = clean_test_dir / "deep" / "nested" / "dir" / "file.txt"
        assert deep_file.exists()
        assert deep_file.read_text(encoding="utf-8") == "深层目录文件"

    def test_push_files_sets_mtime(self, client, clean_test_dir):
        """写入后正确设置 mtime"""
        # Arrange
        encoded_content = encode_content("设置mtime的文件")
        target_mtime = "2026-07-01T12:00:00+00:00"

        # Act
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/mtime_test.txt",
                        "content": encoded_content,
                        "mtime": target_mtime,
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )

        # Assert: 文件的 mtime 与推送的 mtime 匹配
        assert response.status_code == 200

        written_file = clean_test_dir / "mtime_test.txt"
        actual_mtime = written_file.stat().st_mtime
        expected_mtime = datetime.fromisoformat(target_mtime).timestamp()
        assert abs(actual_mtime - expected_mtime) < 2  # 允许 2 秒误差

    def test_push_files_requires_api_key(self, client, clean_test_dir):
        """无 API Key 时返回 422"""
        # Act
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_file_api_test/auth_test.txt",
                        "content": encode_content("test"),
                        "mtime": "2026-07-01T12:00:00+00:00",
                    }
                ]
            },
            headers=WRONG_AUTH_HEADERS,
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INVALID_SYNC_API_KEY"


# ==================== 路径遍历安全测试 ====================


class TestPathTraversalSecurity:
    """测试 _is_path_safe() 路径遍历防护"""

    def test_push_files_rejects_path_traversal(self, client, clean_test_dir):
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
                            "mtime": "2026-07-01T12:00:00+00:00",
                        }
                    ]
                },
                headers=AUTH_HEADERS,
            )

            # Assert: 文件未被写入，返回 skipped
            assert response.status_code == 200
            data = response.json()
            assert data["written"] == 0
            assert data["skipped"] == 1
            assert not evil_file.exists()
        finally:
            # 清理：确保恶意文件未被创建
            if evil_file.exists():
                evil_file.unlink()

    def test_push_files_rejects_nested_path_traversal(self, client, clean_test_dir):
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
                            "mtime": "2026-07-01T12:00:00+00:00",
                        }
                    ]
                },
                headers=AUTH_HEADERS,
            )

            # Assert: 文件未被写入，返回 skipped
            assert response.status_code == 200
            data = response.json()
            assert data["written"] == 0
            assert data["skipped"] == 1
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
