"""
Key 读取 Fallback 机制单元测试

验证统一的 Key 读取逻辑：优先从 keyring 读取（本地 Windows），
fallback 到 config.yaml（云端 Linux）。

三个 Seams:
1. provider_manager.get_api_key()
2. WechatAuth._load_token_from_keyring()
3. sync_config.get_sync_api_key()
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
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch("keyring.get_password", return_value="keyring-value"):
            result = provider_manager.get_api_key("aliyun")
            assert result == "keyring-value"

    def test_get_api_key_fallback_to_config(self):
        """keyring 返回 None 时，fallback 到 providers.yaml 的 api_key 字段"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [
            {"name": "aliyun", "env_key": "aliyun_api_key", "api_key": "config-fallback-key"}
        ]
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch("keyring.get_password", return_value=None):
            result = provider_manager.get_api_key("aliyun")
            assert result == "config-fallback-key"

    def test_get_api_key_both_empty_returns_none(self):
        """keyring 和 config 都无值时，返回 None"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [
            {"name": "aliyun", "env_key": "aliyun_api_key"}
        ]
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch("keyring.get_password", return_value=None):
            result = provider_manager.get_api_key("aliyun")
            assert result is None

    def test_get_api_key_no_env_key_returns_none(self):
        """provider 无 env_key（如 custom）时，返回 None"""
        from unittest.mock import patch

        from lifeprism.config.provider_manager import provider_manager

        raw_specs = [
            {"name": "custom", "env_key": "", "api_key": "some-key"}
        ]
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

        with patch("keyring.get_password", return_value="keyring-token"), \
             patch("lifeprism.config.settings_manager.get_setting", return_value="config-token"):
            result = WechatAuth._load_token_from_keyring()
            assert result == "keyring-token"

    def test_wechat_token_fallback_to_config(self):
        """keyring 返回 None 时，fallback 到 config.yaml 的 wechat_token 字段"""
        from unittest.mock import patch

        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch("keyring.get_password", return_value=None), \
             patch("lifeprism.config.settings_manager.get_setting", return_value="config-token"):
            result = WechatAuth._load_token_from_keyring()
            assert result == "config-token"

    def test_wechat_token_both_empty_returns_empty(self):
        """keyring 和 config 都无值时，返回空字符串"""
        from unittest.mock import patch

        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch("keyring.get_password", return_value=None), \
             patch("lifeprism.config.settings_manager.get_setting", return_value=None):
            result = WechatAuth._load_token_from_keyring()
            assert result == ""


# ==================== Seam 3: sync_config.get_sync_api_key() ====================


class TestSyncConfigApiKey:
    """测试 sync_config.get_sync_api_key() 的 keyring → config fallback 逻辑"""

    def test_sync_api_key_from_keyring(self):
        """keyring 有值时，优先返回 keyring 中的值"""
        from unittest.mock import patch

        from lifeprism.sync.sync_config import get_sync_api_key

        with patch("keyring.get_password", return_value="keyring-sync-key"), \
             patch("lifeprism.config.settings_manager.get_setting", return_value="config-sync-key"):
            result = get_sync_api_key()
            assert result == "keyring-sync-key"

    def test_sync_api_key_fallback_to_config(self):
        """keyring 返回 None 时，fallback 到 config.yaml 的 sync_api_key 字段"""
        from unittest.mock import patch

        from lifeprism.sync.sync_config import get_sync_api_key

        with patch("keyring.get_password", return_value=None), \
             patch("lifeprism.config.settings_manager.get_setting", return_value="config-sync-key"):
            result = get_sync_api_key()
            assert result == "config-sync-key"

    def test_sync_api_key_both_empty_returns_none(self):
        """keyring 和 config 都无值时，返回 None"""
        from unittest.mock import patch

        from lifeprism.sync.sync_config import get_sync_api_key

        with patch("keyring.get_password", return_value=None), \
             patch("lifeprism.config.settings_manager.get_setting", return_value=None):
            result = get_sync_api_key()
            assert result is None

    def test_set_sync_api_key_writes_to_keyring(self):
        """set_sync_api_key 将 key 写入 keyring（正确的 service 和 username）"""
        from unittest.mock import patch, call

        from lifeprism.sync.sync_config import set_sync_api_key

        with patch("keyring.set_password") as mock_set:
            set_sync_api_key("my-secret-key")
            mock_set.assert_called_once_with("LifePrism", "sync_api_key", "my-secret-key")
