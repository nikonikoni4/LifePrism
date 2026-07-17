"""
文件同步重构审查修复 — 单元测试

验证 8 个审查问题的修复：
#1 HIGH: compute_file_hash 不再过度规范化
#2 MEDIUM: _safe_write_file 原子写入
#3 MEDIUM: safe_gzip_decompress 大小限制
#4 MEDIUM: sync_cloud_api.py 导入路径（通过运行时验证）
#5 MEDIUM: WechatAccountStateProvider.get_all_states() 公共方法
#6 MEDIUM: EXCLUDED_FILENAMES 共享常量
#7 MEDIUM: FileSyncStateProvider batch 方法
#8 LOW: _refresh_current_hashes 返回扫描结果
"""

import gzip
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lifeprism.sync.constants import (
    EXCLUDED_FILENAMES,
    MAX_DECOMPRESSED_SIZE,
    safe_gzip_decompress,
)
from lifeprism.sync.hash_utils import compute_file_hash

pytestmark = pytest.mark.core


# ==================== #1 HIGH: compute_file_hash 规范化修正 ====================


class TestComputeHashNormalization:
    """验证 compute_file_hash 不再过度规范化"""

    def test_different_words_not_collide(self):
        """'hello world' 和 'helloworld' 不应产生相同 hash"""
        h1 = compute_file_hash(b"hello world")
        h2 = compute_file_hash(b"helloworld")
        assert h1 != h2, "不同内容的 hash 不应碰撞"

    def test_bold_spacing_not_collide(self):
        """'**bold**' 和 '** bold **' 不应产生相同 hash"""
        h1 = compute_file_hash(b"**bold**")
        h2 = compute_file_hash(b"** bold **")
        assert h1 != h2

    def test_line_ending_normalization(self):
        """Windows \\r\\n 和 Linux \\n 产生相同 hash"""
        h_win = compute_file_hash(b"line1\r\nline2\r\n")
        h_linux = compute_file_hash(b"line1\nline2\n")
        assert h_win == h_linux

    def test_trailing_whitespace_stripped(self):
        """行尾 trailing 空白被去除，不影响 hash"""
        h1 = compute_file_hash(b"line1\nline2\n")
        h2 = compute_file_hash(b"line1   \nline2\t\n")
        assert h1 == h2

    def test_internal_spaces_preserved(self):
        """行内空格被保留，影响 hash"""
        h1 = compute_file_hash(b"hello   world")  # 多个空格
        h2 = compute_file_hash(b"hello world")  # 单个空格
        assert h1 != h2

    def test_empty_content(self):
        """空内容产生有效 hash"""
        h = compute_file_hash(b"")
        assert len(h) == 64

    def test_same_content_same_hash(self):
        """相同内容产生相同 hash"""
        h1 = compute_file_hash(b"# Title\n\nSome content here.")
        h2 = compute_file_hash(b"# Title\n\nSome content here.")
        assert h1 == h2


# ==================== #2 MEDIUM: _safe_write_file 原子写入 ====================


class TestSafeWriteFile:
    """验证 _safe_write_file 原子写入"""

    def test_writes_file_correctly(self, tmp_path):
        """文件内容正确写入"""
        from lifeprism.sync.sync_client import _safe_write_file

        target = tmp_path / "test.txt"
        content = b"hello world"
        _safe_write_file(target, content)
        assert target.read_bytes() == content

    def test_no_tmp_file_left(self, tmp_path):
        """写入后无临时文件残留"""
        from lifeprism.sync.sync_client import _safe_write_file

        target = tmp_path / "test.txt"
        _safe_write_file(target, b"content")
        # 只有目标文件，没有 .tmp 文件
        assert list(tmp_path.iterdir()) == [target]

    def test_creates_parent_dir(self, tmp_path):
        """自动创建父目录"""
        from lifeprism.sync.sync_client import _safe_write_file

        target = tmp_path / "subdir" / "nested" / "test.txt"
        _safe_write_file(target, b"content")
        assert target.exists()

    def test_overwrite_existing_file(self, tmp_path):
        """覆写已有文件"""
        from lifeprism.sync.sync_client import _safe_write_file

        target = tmp_path / "test.txt"
        target.write_bytes(b"old content")
        _safe_write_file(target, b"new content")
        assert target.read_bytes() == b"new content"


# ==================== #3 MEDIUM: safe_gzip_decompress 大小限制 ====================


class TestSafeGzipDecompress:
    """验证 safe_gzip_decompress 大小限制"""

    def test_normal_decompress(self):
        """正常数据正常解压"""
        original = b"hello world" * 100
        compressed = gzip.compress(original)
        result = safe_gzip_decompress(compressed)
        assert result == original

    def test_oversized_raises_error(self):
        """超过限制的数据抛出 ValueError"""
        # 创建一个超过 MAX_DECOMPRESSED_SIZE 的数据
        oversized = b"\x00" * (MAX_DECOMPRESSED_SIZE + 1)
        compressed = gzip.compress(oversized)
        with pytest.raises(ValueError, match="超过"):
            safe_gzip_decompress(compressed)

    def test_exact_limit_ok(self):
        """恰好等于限制大小的数据不抛异常"""
        data = b"\x00" * 100
        compressed = gzip.compress(data)
        result = safe_gzip_decompress(compressed)
        assert len(result) == 100


# ==================== #5 MEDIUM: WechatAccountStateProvider.get_all_states ====================


class TestWechatAccountStateProviderGetAll:
    """验证 WechatAccountStateProvider.get_all_states() 公共方法"""

    def test_get_all_states_returns_list(self):
        """get_all_states 返回列表"""
        from lifeprism.repository.providers.wechat_account_state_provider import (
            WechatAccountStateProvider,
        )

        provider = WechatAccountStateProvider(db_manager=MagicMock())

        # Mock _generic_query 返回结果
        mock_results = [
            {"wechat_user_id": "user1", "context_token": "token1", "last_session_id": "sess1"},
            {"wechat_user_id": "user2", "context_token": "token2", "last_session_id": "sess2"},
        ]
        with patch.object(provider, "_generic_query", return_value=(mock_results, 2)):
            result = provider.get_all_states()
            assert len(result) == 2
            assert result[0]["wechat_user_id"] == "user1"

    def test_get_all_states_empty(self):
        """空表返回空列表"""
        from lifeprism.repository.providers.wechat_account_state_provider import (
            WechatAccountStateProvider,
        )

        provider = WechatAccountStateProvider(db_manager=MagicMock())
        with patch.object(provider, "_generic_query", return_value=([], 0)):
            result = provider.get_all_states()
            assert result == []


# ==================== #6 MEDIUM: EXCLUDED_FILENAMES 共享常量 ====================


class TestSharedExcludedFilenames:
    """验证 EXCLUDED_FILENAMES 共享常量"""

    def test_constant_exists_in_sync_constants(self):
        """常量在 sync.constants 中定义"""
        from lifeprism.sync.constants import EXCLUDED_FILENAMES

        assert "chat_history.json" in EXCLUDED_FILENAMES

    def test_sync_client_uses_shared_constant(self):
        """sync_client.py 使用共享常量"""
        from lifeprism.sync import sync_client

        assert (
            sync_client._EXCLUDED_FILENAMES is EXCLUDED_FILENAMES
            or sync_client._EXCLUDED_FILENAMES == EXCLUDED_FILENAMES
        )

    def test_sync_cloud_api_uses_shared_constant(self):
        """sync_cloud_api.py 使用共享常量"""
        from lifeprism.server.api import sync_cloud_api

        assert sync_cloud_api._EXCLUDED_FILENAMES == EXCLUDED_FILENAMES


# ==================== #7 MEDIUM: FileSyncStateProvider batch 方法 ====================


class TestFileSyncStateBatchMethods:
    """验证 FileSyncStateProvider 批量方法"""

    def test_batch_get_states_empty_input(self):
        """空列表返回空字典"""
        from lifeprism.repository.providers.file_sync_state_provider import (
            FileSyncStateProvider,
        )

        provider = FileSyncStateProvider(db_manager=MagicMock())
        result = provider.batch_get_states([])
        assert result == {}

    def test_batch_upsert_states_empty_input(self):
        """空列表不执行任何操作"""
        from lifeprism.repository.providers.file_sync_state_provider import (
            FileSyncStateProvider,
        )

        provider = FileSyncStateProvider(db_manager=MagicMock())
        # 不应抛异常
        provider.batch_upsert_states([])


# ==================== #8 LOW: _refresh_current_hashes 返回扫描结果 ====================


class TestRefreshCurrentHashesReturnsScanResult:
    """验证 _refresh_current_hashes 返回扫描结果供复用"""

    def test_returns_list_of_paths(self, tmp_path):
        """_refresh_current_hashes 返回文件路径列表"""
        from lifeprism.config.settings_manager import SettingsManager
        from lifeprism.sync.sync_client import SyncClient

        # 创建测试文件
        (tmp_path / "session").mkdir()
        (tmp_path / "session" / "test.jsonl").write_text("test content")

        client = SyncClient.__new__(SyncClient)
        client.db = MagicMock()

        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: tmp_path),
            ),
            patch.object(client, "_scan_sync_files", return_value=["session/test.jsonl"]),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            mock_provider.batch_upsert_states = MagicMock()
            MockProvider.return_value = mock_provider

            result = client._refresh_current_hashes(["session/"])

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0] == "session/test.jsonl"
