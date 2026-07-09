"""
SyncClient 文件同步集成测试

测试 seam:
- Seam 1: sync_once() - 同时执行数据库和文件同步
- Seam 2: pull_files_from_remote() - 从云端拉取文件并写入本地
- Seam 3: push_files_to_remote() - 推送本地变更文件到云端
- Seam 4: _collect_changed_files() - 收集本地变更文件（单文件/目录递归）
- Seam 5: _write_file() - LWW 冲突解决 + 解码解压 + 设置 mtime

文件内容使用 gzip 压缩 + base64 编码（与 API 端点一致）。
不 mock gzip/base64，验证真实编解码。

参考: test/core/integration/sync/test_sync_client.py
       test/core/integration/api/test_sync_file_api.py
"""

import base64
import gzip
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
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


def _mock_post_factory_for_all(pull_data=None, push_success=True, pull_files=None):
    """构建 httpx.post 的 mock side_effect，区分 4 种同步请求"""

    def _mock_post(*args, **kwargs):
        url = kwargs.get("url", "")
        if "/pull-files" in url:
            return _make_mock_response({"files": pull_files or []})
        elif "/push-files" in url:
            if push_success:
                return _make_mock_response({"status": "ok", "written": 0, "skipped": 0})
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = Exception("HTTP 500 Push-Files Failed")
                return mock_resp
        elif "/pull" in url:
            return _make_mock_response({"changes": pull_data or {}})
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


# ==================== Seam 1: sync_once() 文件同步集成 ====================


class TestSyncOnceIncludesFileSync:
    """Seam 1: sync_once() - 同时执行数据库和文件同步"""

    def test_sync_once_includes_file_sync(
        self, sync_client, initialized_db, clean_tables, clean_file_dir
    ):
        """sync_once 同时执行数据库同步和文件同步"""
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
            sync_client.sync_once(
                tables=["todo_list"], directories=["sync_client_test/"]
            )

        # Assert: 数据库和文件同步都被执行
        assert "pull" in call_order
        assert "push" in call_order
        assert "pull-files" in call_order
        assert "push-files" in call_order
        # 顺序：数据库 pull -> push -> 文件 pull -> push
        assert call_order.index("pull") < call_order.index("push")
        assert call_order.index("push") < call_order.index("pull-files")
        assert call_order.index("pull-files") < call_order.index("push-files")


# ==================== Seam 2: pull_files_from_remote() ====================


class TestPullFilesFromRemote:
    """Seam 2: pull_files_from_remote() - 从云端拉取文件并写入本地"""

    def test_pull_files_writes_to_local(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """拉取文件后写入本地"""
        # Arrange: 准备远程文件内容
        from lifeprism.config.settings_manager import settings

        original_content = "远程文件内容测试"
        remote_file = {
            "path": "sync_client_test/pulled/file.txt",
            "content": encode_content(original_content),
            "mtime": "2026-07-01T12:00:00+00:00",
        }
        mock_response = _make_mock_response({"files": [remote_file]})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # Act
            sync_client.pull_files_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_client_test/"],
            )

        # Assert: 文件已写入本地
        written_file = settings.lifeprism_data_path / "sync_client_test" / "pulled" / "file.txt"
        assert written_file.exists()
        assert written_file.read_text(encoding="utf-8") == original_content


# ==================== Seam 3: push_files_to_remote() ====================


class TestPushFilesToRemote:
    """Seam 3: push_files_to_remote() - 推送本地变更文件到云端"""

    def test_push_files_sends_changed_files(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """推送变更文件到云端"""
        # Arrange: 创建本地文件（mtime > last_sync_time）
        from lifeprism.config.settings_manager import settings

        test_file = settings.lifeprism_data_path / "sync_client_test" / "push_test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("待推送内容", encoding="utf-8")
        set_file_mtime(test_file, "2026-07-01T12:00:00+00:00")

        mock_response = _make_mock_response({"status": "ok", "written": 1, "skipped": 0})

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
        ) as mock_post:
            # Act
            sync_client.push_files_to_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01T00:00:00+00:00",
                directories=["sync_client_test/"],
            )

        # Assert: 请求体包含变更文件
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["url"] == "http://test:8000/api/sync/push-files"
        files = call_args.kwargs["json"]["files"]
        assert len(files) == 1
        assert files[0]["path"] == "sync_client_test/push_test.txt"
        # 验证内容可以正确解码
        decoded = decode_content(files[0]["content"])
        assert decoded == "待推送内容"


# ==================== Seam 4: _collect_changed_files() ====================


class TestCollectChangedFiles:
    """Seam 4: _collect_changed_files() - 收集本地变更文件"""

    def test_collect_changed_files_single_file(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """单文件（account.json）特殊处理：直接检查并编码"""
        # Arrange: 创建单文件
        from lifeprism.config.settings_manager import settings

        file_path = settings.lifeprism_data_path / "sync_client_test" / "account.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text('{"wechat_id": "test123"}', encoding="utf-8")
        set_file_mtime(file_path, "2026-07-01T12:00:00+00:00")

        # Act: 传入单文件路径（不是目录）
        files = sync_client._collect_changed_files(
            last_sync_time="2026-07-01T00:00:00+00:00",
            directories=["sync_client_test/account.json"],
        )

        # Assert: 单文件被收集
        assert len(files) == 1
        assert files[0]["path"] == "sync_client_test/account.json"
        # 验证内容可以解码
        decoded = decode_content(files[0]["content"])
        assert decoded == '{"wechat_id": "test123"}'

    def test_collect_changed_files_directory_recursive(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """目录递归收集：遍历子目录中的所有文件"""
        # Arrange: 创建目录结构
        from lifeprism.config.settings_manager import settings

        base = settings.lifeprism_data_path / "sync_client_test" / "recursive"
        base.mkdir(parents=True, exist_ok=True)

        file1 = base / "file1.txt"
        file1.write_text("文件1", encoding="utf-8")
        set_file_mtime(file1, "2026-07-01T12:00:00+00:00")

        subdir = base / "subdir"
        subdir.mkdir()
        file2 = subdir / "file2.txt"
        file2.write_text("文件2", encoding="utf-8")
        set_file_mtime(file2, "2026-07-01T12:00:00+00:00")

        # Act
        files = sync_client._collect_changed_files(
            last_sync_time="2026-07-01T00:00:00+00:00",
            directories=["sync_client_test/recursive"],
        )

        # Assert: 两个文件都被收集（包含子目录中的文件）
        paths = {f["path"] for f in files}
        assert "sync_client_test/recursive/file1.txt" in paths
        assert "sync_client_test/recursive/subdir/file2.txt" in paths
        assert len(files) == 2

    def test_should_sync_file_skips_old_files(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """测试 mtime <= last_sync_time 的文件被跳过"""
        # Arrange: 创建文件，mtime 设置为过去时间 (10:00)
        from lifeprism.config.settings_manager import settings

        old_file = settings.lifeprism_data_path / "sync_client_test" / "old.txt"
        old_file.parent.mkdir(parents=True, exist_ok=True)
        old_file.write_text("旧文件内容", encoding="utf-8")
        set_file_mtime(old_file, "2026-07-01T10:00:00+00:00")

        # 同时创建一个新文件，mtime 为 12:00（比 last_sync_time 新）
        new_file = settings.lifeprism_data_path / "sync_client_test" / "new.txt"
        new_file.write_text("新文件内容", encoding="utf-8")
        set_file_mtime(new_file, "2026-07-01T12:00:00+00:00")

        # last_sync_time 为 11:00（比旧文件新，比新文件旧）
        # Act: 调用 _collect_changed_files
        files = sync_client._collect_changed_files(
            last_sync_time="2026-07-01T11:00:00+00:00",
            directories=["sync_client_test/"],
        )

        # Assert: 旧文件不在结果列表中，新文件在结果列表中
        paths = {f["path"] for f in files}
        assert "sync_client_test/old.txt" not in paths
        assert "sync_client_test/new.txt" in paths
        assert len(files) == 1

    def test_should_sync_file_skips_equal_mtime(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """测试 mtime == last_sync_time 的文件也被跳过（严格大于才同步）"""
        # Arrange: 创建文件，mtime 与 last_sync_time 完全相同
        from lifeprism.config.settings_manager import settings

        same_time_file = settings.lifeprism_data_path / "sync_client_test" / "same.txt"
        same_time_file.parent.mkdir(parents=True, exist_ok=True)
        same_time_file.write_text("同时刻文件", encoding="utf-8")
        set_file_mtime(same_time_file, "2026-07-01T12:00:00+00:00")

        # Act: last_sync_time 与文件 mtime 相同
        files = sync_client._collect_changed_files(
            last_sync_time="2026-07-01T12:00:00+00:00",
            directories=["sync_client_test/"],
        )

        # Assert: 文件不在结果列表中（mtime 不严格大于 last_sync_time）
        paths = {f["path"] for f in files}
        assert "sync_client_test/same.txt" not in paths
        assert len(files) == 0


# ==================== Seam 5: _write_file() LWW 冲突解决 ====================


class TestWriteFileLWW:
    """Seam 5: _write_file() - Last-Write-Wins 冲突解决"""

    def test_write_file_lww_skips_when_local_newer(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """LWW：本地文件更新时跳过远程文件"""
        # Arrange: 创建本地文件，mtime = 12:00（较新）
        from lifeprism.config.settings_manager import settings

        local_file = settings.lifeprism_data_path / "sync_client_test" / "lww_skip.txt"
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_text("本地新内容", encoding="utf-8")
        set_file_mtime(local_file, "2026-07-01T12:00:00+00:00")

        # 远程文件 mtime = 10:00（较旧）
        file_item = {
            "path": "sync_client_test/lww_skip.txt",
            "content": encode_content("远程旧内容"),
            "mtime": "2026-07-01T10:00:00+00:00",
        }

        # Act
        result = sync_client._write_file(file_item)

        # Assert: 跳过，本地文件未被覆盖
        assert result is False
        assert local_file.read_text(encoding="utf-8") == "本地新内容"

    def test_write_file_lww_overwrites_when_remote_newer(
        self, sync_client, initialized_db, clean_file_dir
    ):
        """LWW：远程文件更新时覆盖本地文件"""
        # Arrange: 创建本地文件，mtime = 10:00（较旧）
        from lifeprism.config.settings_manager import settings

        local_file = settings.lifeprism_data_path / "sync_client_test" / "lww_overwrite.txt"
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_text("本地旧内容", encoding="utf-8")
        set_file_mtime(local_file, "2026-07-01T10:00:00+00:00")

        # 远程文件 mtime = 12:00（较新）
        file_item = {
            "path": "sync_client_test/lww_overwrite.txt",
            "content": encode_content("远程新内容"),
            "mtime": "2026-07-01T12:00:00+00:00",
        }

        # Act
        result = sync_client._write_file(file_item)

        # Assert: 覆盖本地文件
        assert result is True
        assert local_file.read_text(encoding="utf-8") == "远程新内容"
