"""_fetch_remote_base_content 单元测试（Issue 4 代码审查 Issue 4 补充）

测试 seam: SyncClient._fetch_remote_base_content —— 从 backups/docs/ 查找
parent_hash 对应的 base content（diff3 三方合并的 common ancestor）。

覆盖场景（代码审查 Issue 4 指出的缺口）：
- parent_hash=None → 返回 None
- backups/docs/ 目录不存在 → 返回 None
- 单个备份目录中 hash 匹配 → 返回内容
- 单个备份目录中 hash 不匹配 → 返回 None
- 多个备份目录：最新的匹配优先（降序遍历）
- 多个备份目录均不匹配 → 返回 None
- 备份中文件不存在 → 跳过该备份
- 读取文件失败（OSError）→ 跳过并继续

参考:
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md 决策 2
- 代码: lifeprism/sync/sync_client.py:1606
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.core


@pytest.fixture
def sync_client():
    """创建 SyncClient 实例（仅需要 _fetch_remote_base_content 方法）"""
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient.__new__(SyncClient)
    return client


@pytest.fixture
def backup_dir(tmp_path):
    """创建 backups/docs/ 目录结构"""
    docs_root = tmp_path / "backups" / "docs"
    docs_root.mkdir(parents=True)
    return docs_root


class TestFetchRemoteBaseContent:
    """_fetch_remote_base_content 从备份目录查找 base content"""

    def test_parent_hash_none_returns_none(self, sync_client):
        """parent_hash=None → 返回 None（从未同步）"""
        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash=None,
        )
        assert result is None

    @patch("lifeprism.config.settings_manager.settings")
    def test_backup_dir_not_exist_returns_none(self, mock_settings, sync_client, tmp_path):
        """backups/docs/ 目录不存在 → 返回 None"""
        mock_settings.lifeprism_data_path = tmp_path

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash="abc123",
        )
        assert result is None

    @patch("lifeprism.config.settings_manager.settings")
    def test_single_backup_hash_match_returns_content(self, mock_settings, sync_client, backup_dir, tmp_path):
        """单个备份目录中 hash 匹配 → 返回文件内容"""
        mock_settings.lifeprism_data_path = tmp_path

        # 创建备份目录
        ts_dir = backup_dir / "2026-07-17T03-00-00"
        ts_dir.mkdir()

        # 写入备份文件（用 write_bytes 避免 Windows \r\n 转换）
        content = "line1\nline2\nline3\n"
        file_path = ts_dir / "agent" / "behavior.md"
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(content.encode("utf-8"))

        # 计算正确的 hash
        from lifeprism.sync.hash_utils import compute_file_hash

        correct_hash = compute_file_hash(content.encode("utf-8"))

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash=correct_hash,
        )
        assert result == content

    @patch("lifeprism.config.settings_manager.settings")
    def test_single_backup_hash_mismatch_returns_none(self, mock_settings, sync_client, backup_dir, tmp_path):
        """单个备份目录中 hash 不匹配 → 返回 None"""
        mock_settings.lifeprism_data_path = tmp_path

        ts_dir = backup_dir / "2026-07-17T03-00-00"
        ts_dir.mkdir()

        content = "some content\n"
        file_path = ts_dir / "agent" / "behavior.md"
        file_path.parent.mkdir(parents=True)
        file_path.write_text(content, encoding="utf-8")

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash="wrong_hash_value",
        )
        assert result is None

    @patch("lifeprism.config.settings_manager.settings")
    def test_newest_matching_backup_returned_first(self, mock_settings, sync_client, backup_dir, tmp_path):
        """多个备份目录：最新的匹配优先（降序遍历）"""
        mock_settings.lifeprism_data_path = tmp_path

        # 创建 3 个备份目录（时间戳降序创建）
        for i, ts in enumerate(["2026-07-15T03-00-00", "2026-07-16T03-00-00", "2026-07-17T03-00-00"]):
            ts_dir = backup_dir / ts
            ts_dir.mkdir()
            file_path = ts_dir / "agent" / "behavior.md"
            file_path.parent.mkdir(parents=True)
            # 每个备份内容不同（用 write_bytes 避免 Windows \r\n 转换）
            file_path.write_bytes(f"content version {i}\n".encode("utf-8"))

        # 计算最新备份的 hash
        from lifeprism.sync.hash_utils import compute_file_hash

        newest_content = "content version 2\n"
        newest_hash = compute_file_hash(newest_content.encode("utf-8"))

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash=newest_hash,
        )
        # 应返回最新备份的内容
        assert result == newest_content

    @patch("lifeprism.config.settings_manager.settings")
    def test_all_backups_mismatch_returns_none(self, mock_settings, sync_client, backup_dir, tmp_path):
        """多个备份目录均不匹配 → 返回 None"""
        mock_settings.lifeprism_data_path = tmp_path

        for ts in ["2026-07-15T03-00-00", "2026-07-16T03-00-00", "2026-07-17T03-00-00"]:
            ts_dir = backup_dir / ts
            ts_dir.mkdir()
            file_path = ts_dir / "agent" / "behavior.md"
            file_path.parent.mkdir(parents=True)
            file_path.write_bytes(f"content for {ts}\n".encode("utf-8"))

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash="nonexistent_hash",
        )
        assert result is None

    @patch("lifeprism.config.settings_manager.settings")
    def test_file_not_in_backup_skipped(self, mock_settings, sync_client, backup_dir, tmp_path):
        """备份中文件不存在 → 跳过该备份，继续下一个"""
        mock_settings.lifeprism_data_path = tmp_path

        # 第一个备份目录不含目标文件
        ts1 = backup_dir / "2026-07-16T03-00-00"
        ts1.mkdir()
        (ts1 / "diary").mkdir()
        (ts1 / "diary" / "2026-07-16.md").write_text("diary\n", encoding="utf-8")

        # 第二个备份目录含目标文件
        ts2 = backup_dir / "2026-07-17T03-00-00"
        ts2.mkdir()
        content = "base content\n"
        file_path = ts2 / "agent" / "behavior.md"
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(content.encode("utf-8"))

        from lifeprism.sync.hash_utils import compute_file_hash

        correct_hash = compute_file_hash(content.encode("utf-8"))

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash=correct_hash,
        )
        assert result == content

    @patch("lifeprism.config.settings_manager.settings")
    def test_older_backup_match_returned_when_newer_mismatch(self, mock_settings, sync_client, backup_dir, tmp_path):
        """最新备份不匹配但旧备份匹配 → 返回旧备份内容"""
        mock_settings.lifeprism_data_path = tmp_path

        from lifeprism.sync.hash_utils import compute_file_hash

        # 最新备份（不匹配）
        ts_new = backup_dir / "2026-07-17T03-00-00"
        ts_new.mkdir()
        new_content = "newest version\n"
        file_new = ts_new / "agent" / "behavior.md"
        file_new.parent.mkdir(parents=True)
        file_new.write_bytes(new_content.encode("utf-8"))

        # 旧备份（匹配）
        ts_old = backup_dir / "2026-07-15T03-00-00"
        ts_old.mkdir()
        old_content = "older version\n"
        file_old = ts_old / "agent" / "behavior.md"
        file_old.parent.mkdir(parents=True)
        file_old.write_bytes(old_content.encode("utf-8"))

        old_hash = compute_file_hash(old_content.encode("utf-8"))

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash=old_hash,
        )
        assert result == old_content

    @patch("lifeprism.config.settings_manager.settings")
    def test_empty_backup_dir_returns_none(self, mock_settings, sync_client, backup_dir, tmp_path):
        """空备份目录（无子目录）→ 返回 None"""
        mock_settings.lifeprism_data_path = tmp_path

        result = sync_client._fetch_remote_base_content(
            file_path="agent/behavior.md",
            parent_hash="some_hash",
        )
        assert result is None
