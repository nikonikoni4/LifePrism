"""
Key 读取路由机制单元测试

验证 Key 消费方统一通过 SettingsManager 的 run_mode 路由读写 Key：
- 本地模式 (full)：SettingsManager 内部读 keyring
- 云端模式 (agent_only/web_demo)：SettingsManager 读 storage.yaml

三个 Seams:
1. provider_manager.get_api_key()
2. WechatAuth._load_token_from_keyring()
3. sync_config.get_sync_api_key()

详细迁移测试见 test_key_consumer_migration.py。
"""

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: provider_manager.get_api_key() ====================


class TestProviderManagerGetApiKey:
    """测试 provider_manager.get_api_key() 的 keyring → config fallback 逻辑"""

    def test_get_api_key_from_keyring(self):
        """keyring 有值时，优先返回 keyring 中的值"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [
            {"name": "aliyun", "env_key": "aliyun_api_key", "api_key": "config-fallback-key"}
        ]
        with (
            patch.object(provider_manager, "_raw_specs", raw_specs),
            patch("keyring.get_password", return_value="keyring-value"),
        ):
            result = provider_manager.get_api_key("aliyun")
            assert result == "keyring-value"

    def test_get_api_key_fallback_to_config(self):
        """keyring 返回 None 时，fallback 到 providers.yaml 的 api_key 字段"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [
            {"name": "aliyun", "env_key": "aliyun_api_key", "api_key": "config-fallback-key"}
        ]
        with (
            patch.object(provider_manager, "_raw_specs", raw_specs),
            patch("keyring.get_password", return_value=None),
        ):
            result = provider_manager.get_api_key("aliyun")
            assert result == "config-fallback-key"

    def test_get_api_key_both_empty_returns_none(self):
        """keyring 和 config 都无值时，返回 None"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [{"name": "aliyun", "env_key": "aliyun_api_key"}]
        with (
            patch.object(provider_manager, "_raw_specs", raw_specs),
            patch("keyring.get_password", return_value=None),
        ):
            result = provider_manager.get_api_key("aliyun")
            assert result is None

    def test_get_api_key_no_env_key_returns_none(self):
        """provider 无 env_key（如 custom）时，返回 None"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [{"name": "custom", "env_key": "", "api_key": "some-key"}]
        with patch.object(provider_manager, "_raw_specs", raw_specs):
            result = provider_manager.get_api_key("custom")
            assert result is None


# ==================== Seam 2: WechatAuth._load_token_from_keyring() ====================


class TestWechatAuthLoadTokenFallback:
    """测试 WechatAuth._load_token_from_keyring() 的 keyring → config fallback 逻辑"""

    def test_wechat_token_from_keyring(self):
        """keyring 有值时，优先返回 keyring 中的 token"""
        from unittest.mock import patch

        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with (
            patch("keyring.get_password", return_value="keyring-token"),
            patch("lifeprism.config.settings_manager.get_setting", return_value="config-token"),
        ):
            result = WechatAuth._load_token_from_keyring()
            assert result == "keyring-token"

    def test_wechat_token_cloud_mode_reads_storage_via_settings(self, tmp_path):
        """云端模式：通过 SettingsManager 从 storage.yaml 读取 wechat_token"""
        from unittest.mock import patch

        import yaml

        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"wechat_token": "storage-token"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = WechatAuth._load_token_from_keyring()
            assert result == "storage-token"

    def test_wechat_token_both_empty_returns_empty(self):
        """keyring 和 config 都无值时，返回空字符串"""
        from unittest.mock import patch

        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with (
            patch("keyring.get_password", return_value=None),
            patch("lifeprism.config.settings_manager.get_setting", return_value=None),
        ):
            result = WechatAuth._load_token_from_keyring()
            assert result == ""


# ==================== Seam 3: sync_config.get_sync_api_key() ====================


class TestSyncConfigApiKey:
    """测试 sync_config.get_sync_api_key() 的 keyring → config fallback 逻辑"""

    def test_sync_api_key_from_keyring(self):
        """keyring 有值时，优先返回 keyring 中的值"""
        from unittest.mock import patch

        from lifeprism.sync.sync_config import get_sync_api_key

        with (
            patch("keyring.get_password", return_value="keyring-sync-key"),
            patch("lifeprism.config.settings_manager.get_setting", return_value="config-sync-key"),
        ):
            result = get_sync_api_key()
            assert result == "keyring-sync-key"

    def test_sync_api_key_cloud_mode_reads_storage_via_settings(self, tmp_path):
        """云端模式：通过 SettingsManager 从 storage.yaml 读取 sync_api_key"""
        from unittest.mock import patch

        import yaml

        from lifeprism.config.settings_manager import settings
        from lifeprism.sync.sync_config import get_sync_api_key

        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "storage-sync-key"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = get_sync_api_key()
            assert result == "storage-sync-key"

    def test_sync_api_key_both_empty_returns_none(self):
        """keyring 和 config 都无值时，返回 None"""
        from unittest.mock import patch

        from lifeprism.sync.sync_config import get_sync_api_key

        with (
            patch("keyring.get_password", return_value=None),
            patch("lifeprism.config.settings_manager.get_setting", return_value=None),
        ):
            result = get_sync_api_key()
            assert result is None

    def test_set_sync_api_key_routes_through_settings(self):
        """set_sync_api_key 通过 SettingsManager.set_storage_key 路由写入"""
        from unittest.mock import patch

        from lifeprism.config.settings_manager import settings
        from lifeprism.sync.sync_config import set_sync_api_key

        with patch.object(settings, "set_storage_key") as mock_set:
            set_sync_api_key("my-secret-key")
            mock_set.assert_called_once_with("sync_api_key", "my-secret-key")
