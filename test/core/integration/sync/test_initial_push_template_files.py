"""
首次同步 template 文件推送测试

Bug 背景：
    云端 agent_only 模式跳过 initialize_resources()，依赖本地首次同步全量推送
    来填充 agent/chat/ 等目录。但 _refresh_current_hashes 中的 template_hashes
    过滤（PRD 决策 8）阻止了 hash 命中 templates 的文件进入 file_sync_state
    和推送列表，导致云端永久缺失系统提示词（agent.md/soul.md/tool.md 等）。

设计决策：
    PRD 决策 8 的设计意图是"避免 template 文件触发同步冲突"，作用层应在
    冲突解决路径，而非同步跟踪路径。但完全移除过滤会破坏增量同步场景
    （template 文件被 OVERWRITE_FILE_LIST 覆盖后 hash 仍命中 template_hashes，
    若不过滤会触发不必要的 AI 合并）。

    因此采用"首次同步不过滤，增量同步保留过滤"的方案：
    - _refresh_current_hashes 增加 skip_template_filter 参数
    - _initial_push_files 调用时传 skip_template_filter=True
    - _sync_files_full_flow（增量同步）保持默认 False

Seam：
    SyncClient._initial_push_files(remote_url, api_key, directories)
    公开行为：首次同步推送哪些文件（返回推送文件列表）
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def temp_data_path(tmp_path):
    """临时 lifeprism_data_path，模拟本地数据目录"""
    (tmp_path / "agent" / "chat").mkdir(parents=True)
    (tmp_path / "agent" / "skills").mkdir(parents=True)
    yield tmp_path


@pytest.fixture
def sync_client_bare():
    """创建跳过 __init__ 的 SyncClient 实例（单元测试专用）"""
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient.__new__(SyncClient)
    client.db = MagicMock()
    # 显式置空 _template_hashes 缓存，触发懒加载
    client._template_hashes = None
    yield client


# ==================== Bug 复现测试：首次同步应推送 template 文件 ====================


class TestInitialPushIncludesTemplateFiles:
    """首次同步必须推送 hash 命中 template_hashes 的文件

    Bug：当前 _initial_push_files 复用 _refresh_current_hashes，
    后者无差别过滤所有 template_hashes 命中的文件，导致首次同步
    无法推送系统提示词到云端。
    """

    def test_initial_push_includes_agent_md_matching_template(
        self, temp_data_path, sync_client_bare
    ):
        """首次同步应推送 agent/chat/agent.md（内容与 templates 一致）

        场景：
        - 本地 agent/chat/agent.md 内容 = templates/agent/chat/agent.md 内容
        - hash 命中 template_hashes
        - 首次同步必须推送该文件（云端 agent_only 模式依赖此推送）

        当前 bug：该文件被 template_hashes 过滤，不会出现在推送列表中
        """
        from lifeprism.config.settings_manager import SettingsManager
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 使用真实 templates 内容，确保 hash 命中 template_hashes
        templates_agent_md = Path("templates/agent/chat/agent.md").read_bytes()
        local_agent_md = temp_data_path / "agent" / "chat" / "agent.md"
        local_agent_md.write_bytes(templates_agent_md)

        # 同时放一个非 template 文件，作为对照（应正常推送）
        (temp_data_path / "agent" / "chat" / "user_note.md").write_bytes(
            b"# user custom note\nuser edited content"
        )

        # 验证前提：agent.md 的 hash 确实命中 template_hashes
        template_hashes = sync_client_bare._get_template_hashes()
        agent_md_hash = compute_file_hash(templates_agent_md)
        assert agent_md_hash in template_hashes, "测试前提失败：agent.md hash 应命中 template_hashes"

        # Act: 调用 _initial_push_files（mock 掉 HTTP）
        pushed_paths = []
        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: temp_data_path),
            ),
            patch.object(
                sync_client_bare, "_scan_sync_files",
                return_value=["agent/chat/agent.md", "agent/chat/user_note.md"],
            ),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
            patch.object(sync_client_bare, "_push_files", side_effect=lambda url, key, paths: pushed_paths.extend(paths)),
            patch.object(sync_client_bare, "_advance_local_parent_after_initial_sync"),
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            MockProvider.return_value = mock_provider

            result = sync_client_bare._initial_push_files(
                "http://test:8000", "test-key", ["agent/"]
            )

        # Assert: agent.md 必须出现在推送列表中
        assert "agent/chat/agent.md" in result, (
            "BUG 复现：首次同步未推送 agent.md（被 template_hashes 过滤）"
        )
        assert "agent/chat/agent.md" in pushed_paths, (
            "BUG 复现：agent.md 未实际推送到云端"
        )
        # 对照组：非 template 文件正常推送
        assert "agent/chat/user_note.md" in result

    def test_initial_push_includes_soul_and_tool_md(
        self, temp_data_path, sync_client_bare
    ):
        """首次同步应推送 soul.md 和 tool.md（系统提示词三件套）

        这三个文件是云端 Agent 工作所必需的，缺一不可。
        """
        from lifeprism.config.settings_manager import SettingsManager

        # Arrange: 复制真实 templates 内容
        for filename in ["soul.md", "tool.md"]:
            tmpl_content = Path(f"templates/agent/chat/{filename}").read_bytes()
            (temp_data_path / "agent" / "chat" / filename).write_bytes(tmpl_content)

        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: temp_data_path),
            ),
            patch.object(
                sync_client_bare, "_scan_sync_files",
                return_value=["agent/chat/soul.md", "agent/chat/tool.md"],
            ),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
            patch.object(sync_client_bare, "_push_files"),
            patch.object(sync_client_bare, "_advance_local_parent_after_initial_sync"),
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            MockProvider.return_value = mock_provider

            result = sync_client_bare._initial_push_files(
                "http://test:8000", "test-key", ["agent/"]
            )

        # Assert: 三个系统提示词都必须推送
        assert "agent/chat/soul.md" in result, "soul.md 未推送"
        assert "agent/chat/tool.md" in result, "tool.md 未推送"


# ==================== 回归测试：增量同步仍保留 template_hashes 过滤 ====================


class TestIncrementalSyncStillFiltersTemplateFiles:
    """增量同步（sync_once 路径）应保留 template_hashes 过滤

    设计意图：PRD 决策 8 在增量同步中仍有价值——
    本地 OVERWRITE_FILE_LIST 每次启动覆盖系统提示词为新版本，
    若不过滤会与云端旧版本触发不必要的 AI 合并。
    """

    def test_refresh_current_hashes_default_filters_template(
        self, temp_data_path, sync_client_bare
    ):
        """_refresh_current_hashes 默认行为：过滤 template_hashes 命中的文件

        这是增量同步路径的行为，必须保留。
        """
        from lifeprism.config.settings_manager import SettingsManager
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: agent.md 内容 = templates 内容（hash 命中）
        templates_agent_md = Path("templates/agent/chat/agent.md").read_bytes()
        (temp_data_path / "agent" / "chat" / "agent.md").write_bytes(templates_agent_md)
        # user_note.md 非 template（hash 不命中）
        (temp_data_path / "agent" / "chat" / "user_note.md").write_bytes(
            b"# user custom note"
        )

        with (
            patch.object(
                SettingsManager,
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: temp_data_path),
            ),
            patch.object(
                sync_client_bare, "_scan_sync_files",
                return_value=["agent/chat/agent.md", "agent/chat/user_note.md"],
            ),
            patch(
                "lifeprism.repository.providers.file_sync_state_provider.FileSyncStateProvider"
            ) as MockProvider,
        ):
            mock_provider = MagicMock()
            mock_provider.batch_get_states.return_value = {}
            MockProvider.return_value = mock_provider

            # 默认调用（增量同步路径）
            result = sync_client_bare._refresh_current_hashes(["agent/"])

        # Assert: agent.md 被过滤，user_note.md 保留
        assert "agent/chat/agent.md" not in result, (
            "增量同步应过滤 template_hashes 命中的文件（PRD 决策 8）"
        )
        assert "agent/chat/user_note.md" in result
