"""UTC 时区迁移 - API 层时间参数解析和响应序列化集成测试

测试 seam:
- POST /api/sync/pull: last_sync_time 参数解析（naive/aware）和 sync_time 响应格式
- POST /api/sync/push: sync_time 响应格式
- POST /api/sync/heartbeat: server_time 响应格式
- POST /api/sync/pull-files: last_sync_time 参数解析（naive/aware）
- POST /api/sync/push-files: mtime 参数解析（naive/aware）和 sync_time 响应格式

验证内容（参考 Issue #9 Acceptance criteria）:
1. 时间参数解析已统一使用 datetime.fromisoformat()（通过 parse_iso_to_aware）
2. 时间参数已验证是 aware datetime（naive 输入被假设为 UTC）
3. 响应时间字段是 ISO 8601 格式（带 +00:00 时区标识）
"""

import base64
import gzip
import re
import shutil
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

pytestmark = pytest.mark.core

TEST_API_KEY = "test_sync_key_abc123xyz"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}

# ISO 8601 UTC 格式正则：YYYY-MM-DDTHH:MM:SS.ffffff+00:00
ISO_8601_UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}\+00:00$"


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_settings(test_data_path):
    """初始化设置，确保 lifeprism_data_path 指向测试路径"""
    from lifeprism.config import settings_manager
    from lifeprism.config.settings_manager import settings
    from lifeprism.sync.sync_config import set_sync_api_key

    settings._initialize()
    # 优先写入 keyring（get_sync_api_key 优先从 keyring 读取）
    try:
        set_sync_api_key(TEST_API_KEY)
    except Exception:
        pass
    # 同时写入 config 作为 fallback
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
    test_dir = test_data_path / "sync_time_parsing_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


def encode_content(content: str) -> str:
    """gzip 压缩 + base64 编码"""
    compressed = gzip.compress(content.encode("utf-8"))
    return base64.b64encode(compressed).decode("ascii")


def set_file_mtime(path, iso_time: str) -> None:
    """设置文件的 mtime（ISO 8601 格式）"""
    dt = datetime.fromisoformat(iso_time)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = dt.timestamp()
    import os

    os.utime(path, (ts, ts))


# ==================== 响应格式验证 ====================


class TestSyncTimeResponseFormat:
    """验证所有同步 API 响应中的时间字段是 ISO 8601 UTC 格式"""

    def test_pull_response_sync_time_is_iso8601_utc(self, client):
        """POST /api/sync/pull 响应的 sync_time 是 ISO 8601 UTC 格式"""
        response = client.post(
            "/api/sync/pull",
            json={"last_sync_time": "2099-12-31T23:59:59+00:00", "tables": []},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        sync_time = response.json()["sync_time"]
        assert re.match(ISO_8601_UTC_PATTERN, sync_time), (
            f"sync_time '{sync_time}' 不符合 ISO 8601 UTC 格式"
        )
        # 验证可被 fromisoformat 解析为 aware datetime
        parsed = datetime.fromisoformat(sync_time)
        assert parsed.tzinfo is not None

    def test_push_response_sync_time_is_iso8601_utc(self, client):
        """POST /api/sync/push 响应的 sync_time 是 ISO 8601 UTC 格式"""
        response = client.post(
            "/api/sync/push",
            json={"changes": {}},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        sync_time = response.json()["sync_time"]
        assert re.match(ISO_8601_UTC_PATTERN, sync_time)

    def test_heartbeat_response_server_time_is_iso8601_utc(self, client):
        """POST /api/sync/heartbeat 响应的 server_time 是 ISO 8601 UTC 格式"""
        response = client.post(
            "/api/sync/heartbeat",
            json={"event": "ping"},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        server_time = response.json()["server_time"]
        assert re.match(ISO_8601_UTC_PATTERN, server_time)

    def test_pull_files_response_sync_time_is_iso8601_utc(self, client, clean_test_dir):
        """POST /api/sync/pull-files 响应的 sync_time 是 ISO 8601 UTC 格式"""
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2099-12-31T23:59:59+00:00",
                "directories": ["sync_time_parsing_test"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        sync_time = response.json()["sync_time"]
        assert re.match(ISO_8601_UTC_PATTERN, sync_time)

    def test_push_files_response_sync_time_is_iso8601_utc(self, client, clean_test_dir):
        """POST /api/sync/push-files 响应的 sync_time 是 ISO 8601 UTC 格式"""
        response = client.post(
            "/api/sync/push-files",
            json={"files": []},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        sync_time = response.json()["sync_time"]
        assert re.match(ISO_8601_UTC_PATTERN, sync_time)


# ==================== 时间参数解析验证 ====================


class TestPullFilesLastSyncTimeParsing:
    """验证 POST /api/sync/pull-files 的 last_sync_time 参数解析

    API 层应能处理：
    - 带 UTC 时区标识: "2026-07-01T10:00:00+00:00"
    - 不带时区（naive）: "2026-07-01T10:00:00"（应被假设为 UTC）
    """

    def test_naive_last_sync_time_treated_as_utc(self, client, clean_test_dir):
        """naive last_sync_time 应被假设为 UTC，不崩溃"""
        # 创建文件 mtime = 12:00 UTC
        test_file = clean_test_dir / "naive_test.txt"
        test_file.write_text("content", encoding="utf-8")
        set_file_mtime(test_file, "2026-07-01T12:00:00+00:00")

        # 使用 naive last_sync_time = 11:00（应被假设为 UTC 11:00）
        # 文件 mtime 12:00 > 11:00，应被返回
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T11:00:00",
                "directories": ["sync_time_parsing_test"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        paths = {f["path"] for f in response.json()["files"]}
        assert "sync_time_parsing_test/naive_test.txt" in paths

    def test_naive_last_sync_time_filters_correctly(self, client, clean_test_dir):
        """naive last_sync_time 过滤行为正确（文件 mtime <= last_sync_time 被跳过）"""
        # 创建文件 mtime = 10:00 UTC
        old_file = clean_test_dir / "old.txt"
        old_file.write_text("old", encoding="utf-8")
        set_file_mtime(old_file, "2026-07-01T10:00:00+00:00")

        # 使用 naive last_sync_time = 12:00（应被假设为 UTC 12:00）
        # 文件 mtime 10:00 <= 12:00，应被跳过
        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T12:00:00",
                "directories": ["sync_time_parsing_test"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        paths = {f["path"] for f in response.json()["files"]}
        assert "sync_time_parsing_test/old.txt" not in paths

    def test_aware_last_sync_time_with_z_suffix(self, client, clean_test_dir):
        """带 Z 后缀的 last_sync_time 应正确解析"""
        test_file = clean_test_dir / "z_suffix.txt"
        test_file.write_text("content", encoding="utf-8")
        set_file_mtime(test_file, "2026-07-01T12:00:00+00:00")

        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T11:00:00Z",
                "directories": ["sync_time_parsing_test"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        paths = {f["path"] for f in response.json()["files"]}
        assert "sync_time_parsing_test/z_suffix.txt" in paths

    def test_empty_last_sync_time_returns_all_files(self, client, clean_test_dir):
        """空字符串 last_sync_time 表示首次同步，返回全部文件"""
        file_a = clean_test_dir / "a.txt"
        file_a.write_text("a", encoding="utf-8")
        set_file_mtime(file_a, "2026-07-01T10:00:00+00:00")

        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "",
                "directories": ["sync_time_parsing_test"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert len(response.json()["files"]) == 1


class TestPushFilesMtimeParsing:
    """验证 POST /api/sync/push-files 的 mtime 参数解析

    API 层应能处理：
    - 带 UTC 时区标识: "2026-07-01T10:00:00+00:00"
    - 不带时区（naive）: "2026-07-01T10:00:00"（应被假设为 UTC）
    """

    def test_naive_mtime_treated_as_utc(self, client, clean_test_dir):
        """naive mtime 应被假设为 UTC，正确写入文件"""
        encoded = encode_content("test content")
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_time_parsing_test/naive_mtime.txt",
                        "content": encoded,
                        "mtime": "2026-07-01T12:00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["written"] == 1

        # 验证文件 mtime 被正确设置
        written_file = clean_test_dir / "naive_mtime.txt"
        expected_mtime = datetime.fromisoformat("2026-07-01T12:00:00+00:00").timestamp()
        actual_mtime = written_file.stat().st_mtime
        assert abs(actual_mtime - expected_mtime) < 2

    def test_aware_mtime_preserves_timezone(self, client, clean_test_dir):
        """带时区标识的 mtime 应正确解析"""
        encoded = encode_content("test content")
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_time_parsing_test/aware_mtime.txt",
                        "content": encoded,
                        "mtime": "2026-07-01T12:00:00+00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["written"] == 1

    def test_naive_mtime_lww_comparison_correct(self, client, clean_test_dir):
        """naive mtime 与本地文件 mtime 比较正确（LWW）"""
        # 创建本地文件 mtime = 12:00 UTC
        local_file = clean_test_dir / "lww_naive.txt"
        local_file.write_text("local", encoding="utf-8")
        set_file_mtime(local_file, "2026-07-01T12:00:00+00:00")

        # 推送 naive mtime = 10:00（应被假设为 UTC 10:00，比本地 12:00 旧）
        encoded = encode_content("remote")
        response = client.post(
            "/api/sync/push-files",
            json={
                "files": [
                    {
                        "path": "sync_time_parsing_test/lww_naive.txt",
                        "content": encoded,
                        "mtime": "2026-07-01T10:00:00",
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        # 本地较新，应跳过
        assert response.json()["written"] == 0
        assert response.json()["skipped"] == 1
        assert local_file.read_text(encoding="utf-8") == "local"


# ==================== pull-files 响应中 mtime 格式验证 ====================


class TestPullFilesResponseMtimeFormat:
    """验证 pull-files 响应中的 mtime 字段是 ISO 8601 UTC 格式"""

    def test_response_mtime_is_iso8601_utc(self, client, clean_test_dir):
        """pull-files 响应中每个文件的 mtime 是 ISO 8601 UTC 格式"""
        test_file = clean_test_dir / "mtime_format.txt"
        test_file.write_text("content", encoding="utf-8")
        set_file_mtime(test_file, "2026-07-01T12:00:00+00:00")

        response = client.post(
            "/api/sync/pull-files",
            json={
                "last_sync_time": "2026-07-01T00:00:00+00:00",
                "directories": ["sync_time_parsing_test"],
            },
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        files = response.json()["files"]
        assert len(files) == 1
        mtime = files[0]["mtime"]
        # mtime 应是 ISO 8601 格式且带 UTC 时区标识
        assert "+00:00" in mtime, f"mtime '{mtime}' 应包含 UTC 时区标识"
        parsed = datetime.fromisoformat(mtime)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
