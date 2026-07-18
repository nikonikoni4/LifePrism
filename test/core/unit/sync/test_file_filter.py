"""file_filter 单元测试

测试 seam:
- Seam 1: is_empty_content(content_bytes) -> bool —— 判断内容 strip() 后是否为空
- Seam 2: compute_template_hashes(templates_dir) -> set[str] —— 启动时加载 template_hashes 集合
- Seam 3: should_filter_file(content_bytes, template_hashes) -> bool —— 决定文件是否应被过滤

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-1-empty-and-template-file-filter.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 7、8（用户故事 22-25）
- ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md
- Bug 根因: docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md
"""

import pytest

from lifeprism.sync.hash_utils import compute_file_hash

pytestmark = pytest.mark.core


# ==================== Seam 1: is_empty_content ====================


class TestIsEmptyContent:
    """is_empty_content 判断文件内容 strip() 后是否为空"""

    def test_empty_bytes_is_empty(self):
        """空字节串判定为空"""
        from lifeprism.sync.file_filter import is_empty_content

        assert is_empty_content(b"") is True

    def test_whitespace_only_is_empty(self):
        """仅空格/制表符的内容判定为空（边界场景）"""
        from lifeprism.sync.file_filter import is_empty_content

        assert is_empty_content(b"   ") is True
        assert is_empty_content(b"\t") is True
        assert is_empty_content(b"  \t  ") is True

    def test_newlines_only_is_empty(self):
        """仅换行的内容判定为空（边界场景）"""
        from lifeprism.sync.file_filter import is_empty_content

        assert is_empty_content(b"\n") is True
        assert is_empty_content(b"\n\n\n") is True
        assert is_empty_content(b"\r\n\r\n") is True

    def test_mixed_whitespace_is_empty(self):
        """混合空白字符（空格+换行+制表符）判定为空"""
        from lifeprism.sync.file_filter import is_empty_content

        assert is_empty_content(b"  \n\t \r\n  ") is True

    def test_non_empty_content_is_not_empty(self):
        """有实际内容的文件不判定为空"""
        from lifeprism.sync.file_filter import is_empty_content

        assert is_empty_content(b"hello") is False
        assert is_empty_content("# 标题\n\n正文内容".encode("utf-8")) is False

    def test_content_with_surrounding_whitespace_is_not_empty(self):
        """前后有空白但内部有内容的不判定为空"""
        from lifeprism.sync.file_filter import is_empty_content

        assert is_empty_content(b"  hello  ") is False
        assert is_empty_content("\n\n内容\n\n".encode("utf-8")) is False


# ==================== Seam 2: compute_template_hashes ====================


class TestComputeTemplateHashes:
    """compute_template_hashes 启动时计算 templates/ 目录所有文件 hash"""

    def test_returns_set_of_hashes_for_template_files(self, tmp_path):
        """启动时 template_hashes 集合正确生成（包含所有 template 文件 hash）"""
        from lifeprism.sync.file_filter import compute_template_hashes

        # 准备 templates 目录
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        file_a_content = b"# Template A\n"
        file_b_content = b"# Template B\n"
        (templates_dir / "a.md").write_bytes(file_a_content)
        (templates_dir / "b.md").write_bytes(file_b_content)

        result = compute_template_hashes(templates_dir)

        # 期望：集合包含两个文件的 hash
        assert isinstance(result, set)
        assert compute_file_hash(file_a_content) in result
        assert compute_file_hash(file_b_content) in result
        assert len(result) == 2

    def test_includes_files_in_subdirectories(self, tmp_path):
        """递归扫描 templates/ 子目录下所有文件"""
        from lifeprism.sync.file_filter import compute_template_hashes

        templates_dir = tmp_path / "templates"
        (templates_dir / "user").mkdir(parents=True)
        (templates_dir / "agent" / "chat").mkdir(parents=True)

        root_content = b"root template"
        user_content = b"user template"
        chat_content = b"chat template"

        (templates_dir / "root.md").write_bytes(root_content)
        (templates_dir / "user" / "user.md").write_bytes(user_content)
        (templates_dir / "agent" / "chat" / "bootstrap.md").write_bytes(chat_content)

        result = compute_template_hashes(templates_dir)

        assert compute_file_hash(root_content) in result
        assert compute_file_hash(user_content) in result
        assert compute_file_hash(chat_content) in result
        assert len(result) == 3

    def test_empty_templates_dir_returns_empty_set(self, tmp_path):
        """空 templates 目录返回空集合"""
        from lifeprism.sync.file_filter import compute_template_hashes

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        result = compute_template_hashes(templates_dir)

        assert result == set()
        assert len(result) == 0

    def test_nonexistent_templates_dir_returns_empty_set(self, tmp_path):
        """不存在的 templates 目录返回空集合（边界场景，不抛异常）"""
        from lifeprism.sync.file_filter import compute_template_hashes

        templates_dir = tmp_path / "does_not_exist"

        result = compute_template_hashes(templates_dir)

        assert result == set()

    def test_skips_directories_themselves(self, tmp_path):
        """目录条目本身不被计算 hash（只计算文件）"""
        from lifeprism.sync.file_filter import compute_template_hashes

        templates_dir = tmp_path / "templates"
        (templates_dir / "subdir").mkdir(parents=True)
        (templates_dir / "subdir" / "file.md").write_bytes(b"content")

        result = compute_template_hashes(templates_dir)

        # 仅包含 file.md 的 hash，不包含 subdir 目录本身
        assert len(result) == 1
        assert compute_file_hash(b"content") in result


# ==================== Seam 3: should_filter_file ====================


class TestShouldFilterFile:
    """should_filter_file 决定文件是否应被过滤（不写入 file_sync_state）"""

    def test_empty_content_should_filter(self):
        """空文件（strip() 后为空）应被过滤"""
        from lifeprism.sync.file_filter import should_filter_file

        template_hashes: set[str] = set()

        assert should_filter_file(b"", template_hashes) is True
        assert should_filter_file(b"   ", template_hashes) is True
        assert should_filter_file(b"\n\n\n", template_hashes) is True

    def test_empty_content_filters_even_with_empty_template_hashes(self):
        """空内容即使 template_hashes 为空也应过滤（独立判定条件）"""
        from lifeprism.sync.file_filter import should_filter_file

        assert should_filter_file(b"", set()) is True

    def test_template_hash_match_should_filter(self):
        """template hash 命中的文件应被过滤"""
        from lifeprism.sync.file_filter import should_filter_file

        template_content = "# Default Template\n\n初始文档".encode("utf-8")
        template_hashes = {compute_file_hash(template_content)}

        # 与 template 内容完全一致的文件应被过滤
        assert should_filter_file(template_content, template_hashes) is True

    def test_normal_content_not_filtered(self):
        """非空且非 template 的文件正常通过过滤"""
        from lifeprism.sync.file_filter import should_filter_file

        template_content = b"# Default Template"
        template_hashes = {compute_file_hash(template_content)}

        # 用户实际写入的内容（非空且 hash 不在 template_hashes 中）
        user_content = "# 我的日记\n\n今天心情不错".encode("utf-8")
        assert should_filter_file(user_content, template_hashes) is False

    def test_modified_template_content_not_filtered(self):
        """template 文件被修改后 hash 变化，不被过滤（用户已编辑）"""
        from lifeprism.sync.file_filter import should_filter_file

        template_content = "# Default Template\n\n初始内容".encode("utf-8")
        template_hashes = {compute_file_hash(template_content)}

        # 用户修改了 template 复制过来的文件，新增了一行
        modified_content = "# Default Template\n\n初始内容\n用户新增的内容".encode("utf-8")
        assert should_filter_file(modified_content, template_hashes) is False

    def test_template_hash_uses_normalized_hash(self):
        """template hash 比对使用 compute_file_hash（规范化后的 hash）"""
        from lifeprism.sync.file_filter import should_filter_file

        # template 文件原始内容（Windows 行尾）
        template_content_crlf = b"# Template\r\ncontent\r\n"
        # 用户文件内容（Linux 行尾，规范化后 hash 一致）
        user_content_lf = b"# Template\ncontent\n"

        template_hashes = {compute_file_hash(template_content_crlf)}

        # 规范化后 hash 一致，应被过滤（视为 template 文件）
        assert should_filter_file(user_content_lf, template_hashes) is True


# ==================== 集成验证：file_filter 与 compute_file_hash 一致性 ====================


class TestFileFilterHashConsistency:
    """验证 file_filter 模块使用的 hash 与 compute_file_hash 一致"""

    def test_template_hashes_use_same_hash_algorithm_as_scan(self, tmp_path):
        """template_hashes 集合中的 hash 与 _refresh_current_hashes 计算的 hash 算法一致

        这是过滤生效的前提：两边必须用同一个 compute_file_hash 函数，
        否则即便文件内容完全一致，hash 也对不上，过滤失效。
        """
        from lifeprism.sync.file_filter import compute_template_hashes

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_content = b"# Template\n"
        (templates_dir / "template.md").write_bytes(template_content)

        template_hashes = compute_template_hashes(templates_dir)

        # 模拟 _refresh_current_hashes 中的 hash 计算
        scanned_hash = compute_file_hash(template_content)

        assert scanned_hash in template_hashes, (
            "template_hashes 中的 hash 必须与扫描时计算的 hash 一致，"
            "否则过滤逻辑失效"
        )


# ==================== 集成验证：_refresh_current_hashes 过滤生效 ====================


class TestRefreshCurrentHashesFilterIntegration:
    """验证 SyncClient._refresh_current_hashes 正确应用 file_filter 过滤

    测试 seam: _refresh_current_hashes(directories) -> list[str]
    验证 acceptance criteria: "触发同步后 file_sync_state 表中无空文件和 template 文件记录"

    通过 mock FileSyncStateProvider 捕获 batch_upsert_states 调用参数，
    验证空文件和 template 文件不出现在 upsert 列表中。
    """

    def test_empty_files_not_written_to_file_sync_state(self, tmp_path):
        """空文件不写入 file_sync_state（PRD 决策 7）"""
        from unittest.mock import MagicMock, patch

        from lifeprism.config.settings_manager import SettingsManager
        from lifeprism.sync.sync_client import SyncClient

        # 准备测试文件：1 个空文件 + 1 个非空文件
        (tmp_path / "diary").mkdir()
        (tmp_path / "diary" / "empty.md").write_bytes(b"")
        (tmp_path / "diary" / "normal.md").write_bytes("# 正常内容\n".encode("utf-8"))

        client = SyncClient.__new__(SyncClient)
        client.db = MagicMock()
        # 直接注入空 template_hashes，隔离 template 过滤逻辑
        client._template_hashes = set()

        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: tmp_path),
            ),
            patch.object(
                client,
                "_scan_sync_files",
                return_value=["diary/empty.md", "diary/normal.md"],
            ),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            mock_provider.batch_upsert_states = MagicMock()
            MockProvider.return_value = mock_provider

            result = client._refresh_current_hashes(["diary/"])

            # 返回值不含空文件
            assert "diary/empty.md" not in result
            assert "diary/normal.md" in result

            # upsert 调用中不含空文件
            mock_provider.batch_upsert_states.assert_called_once()
            upserted = mock_provider.batch_upsert_states.call_args[0][0]
            upserted_paths = [item["file_path"] for item in upserted]
            assert "diary/empty.md" not in upserted_paths
            assert "diary/normal.md" in upserted_paths

    def test_template_files_not_written_to_file_sync_state(self, tmp_path):
        """template hash 命中的文件不写入 file_sync_state（PRD 决策 8）"""
        from unittest.mock import MagicMock, patch

        from lifeprism.config.settings_manager import SettingsManager
        from lifeprism.sync.sync_client import SyncClient

        # 准备测试文件：1 个 template 文件 + 1 个用户文件
        template_content = "# Default Template\n\n初始文档".encode("utf-8")
        user_content = "# 用户日记\n\n今天天气不错".encode("utf-8")
        (tmp_path / "diary").mkdir()
        (tmp_path / "diary" / "template_copy.md").write_bytes(template_content)
        (tmp_path / "diary" / "user.md").write_bytes(user_content)

        client = SyncClient.__new__(SyncClient)
        client.db = MagicMock()
        # 注入 template_hashes，包含 template_content 的 hash
        client._template_hashes = {compute_file_hash(template_content)}

        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: tmp_path),
            ),
            patch.object(
                client,
                "_scan_sync_files",
                return_value=["diary/template_copy.md", "diary/user.md"],
            ),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            mock_provider.batch_upsert_states = MagicMock()
            MockProvider.return_value = mock_provider

            result = client._refresh_current_hashes(["diary/"])

            # 返回值不含 template 文件
            assert "diary/template_copy.md" not in result
            assert "diary/user.md" in result

            # upsert 调用中不含 template 文件
            mock_provider.batch_upsert_states.assert_called_once()
            upserted = mock_provider.batch_upsert_states.call_args[0][0]
            upserted_paths = [item["file_path"] for item in upserted]
            assert "diary/template_copy.md" not in upserted_paths
            assert "diary/user.md" in upserted_paths

    def test_whitespace_only_files_not_written_to_file_sync_state(self, tmp_path):
        """仅空格/换行的文件不写入 file_sync_state（边界场景，PRD 决策 7）"""
        from unittest.mock import MagicMock, patch

        from lifeprism.config.settings_manager import SettingsManager
        from lifeprism.sync.sync_client import SyncClient

        # 准备测试文件：仅空格 + 仅换行 + 正常文件
        (tmp_path / "diary").mkdir()
        (tmp_path / "diary" / "spaces.md").write_bytes(b"   \t  ")
        (tmp_path / "diary" / "newlines.md").write_bytes(b"\n\n\r\n")
        (tmp_path / "diary" / "normal.md").write_bytes("内容".encode("utf-8"))

        client = SyncClient.__new__(SyncClient)
        client.db = MagicMock()
        client._template_hashes = set()

        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: tmp_path),
            ),
            patch.object(
                client,
                "_scan_sync_files",
                return_value=[
                    "diary/spaces.md",
                    "diary/newlines.md",
                    "diary/normal.md",
                ],
            ),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            mock_provider.batch_upsert_states = MagicMock()
            MockProvider.return_value = mock_provider

            result = client._refresh_current_hashes(["diary/"])

            # 仅 normal.md 通过过滤
            assert "diary/spaces.md" not in result
            assert "diary/newlines.md" not in result
            assert "diary/normal.md" in result
            assert len(result) == 1
