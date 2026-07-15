"""
Key 消费方迁移到 SettingsManager 路由——单元测试

验证三个 Key 消费方统一走 SettingsManager 的 run_mode 路由：
1. sync_config: get/set_sync_api_key → settings.get/set_storage_key("sync_api_key")
2. wechat_auth: token 读写 → settings.get/set_storage_key("wechat_token")
3. provider_manager: get/set_api_key → settings.get/set_storage_key(f"providers.{provider_id}")

验收标准对应的测试：
- 本地模式通过 SettingsManager 读取 keyring 中的 Key
- 云端模式通过 SettingsManager 读取 storage.yaml 中的 Key
- Key 不存在时返回 None（不报错）
- 多 provider 场景（anthropic + deepseek 同时存在，各自独立返回）
- 云端模式 providers.yaml 兜底（storage.yaml 无此 provider → 查 providers.yaml）

参考:
- Issue #27: Key 消费方迁移到 SettingsManager 路由
- Issue #26: storage.yaml 基础设施——SettingsManager 扩展
"""

from unittest.mock import patch

import pytest
import yaml

from lifeprism.config.settings_manager import KEYRING_WECHAT_TOKEN_USERNAME, settings

pytestmark = pytest.mark.core


# ==================== Seam 1: sync_config ====================


class TestSyncConfigKeyMigration:
    """测试 sync_config 模块通过 SettingsManager 路由读写 sync_api_key"""

    def test_sync_config_get_calls_settings_get_storage_key(self):
        """get_sync_api_key 调用 settings.get_storage_key('sync_api_key')"""
        from lifeprism.sync.sync_config import get_sync_api_key

        with patch.object(settings, "get_storage_key", return_value="routed_key") as mock_get:
            result = get_sync_api_key()
            assert result == "routed_key"
            mock_get.assert_called_once_with("sync_api_key")

    def test_sync_config_local_mode_reads_keyring_via_settings(self):
        """本地模式：get_sync_api_key 通过 SettingsManager 从 keyring 读取"""
        from lifeprism.sync.sync_config import get_sync_api_key

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch(
                 "lifeprism.config.settings_manager.keyring.get_password",
                 return_value="kr_sync_key",
             ) as mock_kr:
            result = get_sync_api_key()
            assert result == "kr_sync_key"
            mock_kr.assert_called_once_with("lifeprism", "sync_api_key")

    def test_sync_config_cloud_mode_reads_storage_via_settings(self, tmp_path):
        """云端模式：get_sync_api_key 通过 SettingsManager 从 storage.yaml 读取"""
        from lifeprism.sync.sync_config import get_sync_api_key

        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "storage_sync_key"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = get_sync_api_key()
            assert result == "storage_sync_key"

    def test_sync_config_returns_none_when_no_key(self):
        """Key 不存在时返回 None（不报错）"""
        from lifeprism.sync.sync_config import get_sync_api_key

        with patch.object(settings, "get_storage_key", return_value=None):
            result = get_sync_api_key()
            assert result is None

    def test_sync_config_set_calls_settings_set_storage_key(self):
        """set_sync_api_key 调用 settings.set_storage_key('sync_api_key', value)"""
        from lifeprism.sync.sync_config import set_sync_api_key

        with patch.object(settings, "set_storage_key") as mock_set:
            set_sync_api_key("new_sync_key")
            mock_set.assert_called_once_with("sync_api_key", "new_sync_key")

    def test_sync_config_does_not_call_keyring_directly(self):
        """消费方不直接调用 keyring.get_password"""
        from lifeprism.sync import sync_config

        # 迁移后 sync_config 模块不应再 import keyring
        assert not hasattr(sync_config, "keyring"), (
            "sync_config 模块不应再 import keyring"
        )


# ==================== Seam 2: wechat_auth ====================


class TestWechatAuthKeyMigration:
    """测试 wechat_auth 模块通过 SettingsManager 路由读写 wechat_token"""

    def test_wechat_auth_load_calls_settings_get_storage_key(self):
        """_load_token_from_keyring 调用 settings.get_storage_key('wechat_token')"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch.object(settings, "get_storage_key", return_value="routed_token") as mock_get:
            result = WechatAuth._load_token_from_keyring()
            assert result == "routed_token"
            mock_get.assert_called_once_with("wechat_token")

    def test_wechat_auth_local_mode_reads_keyring_via_settings(self):
        """本地模式：_load_token_from_keyring 通过 SettingsManager 从 keyring 读取"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch(
                 "lifeprism.config.settings_manager.keyring.get_password",
                 return_value="kr_wechat_token",
             ) as mock_kr:
            result = WechatAuth._load_token_from_keyring()
            assert result == "kr_wechat_token"
            mock_kr.assert_called_once_with("lifeprism", KEYRING_WECHAT_TOKEN_USERNAME)

    def test_wechat_auth_cloud_mode_reads_storage_via_settings(self, tmp_path):
        """云端模式：_load_token_from_keyring 通过 SettingsManager 从 storage.yaml 读取"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"wechat_token": "storage_wechat_token"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = WechatAuth._load_token_from_keyring()
            assert result == "storage_wechat_token"

    def test_wechat_auth_returns_empty_string_when_no_token(self):
        """Token 不存在时返回空字符串（保持既有契约，不报错）"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch.object(settings, "get_storage_key", return_value=None):
            result = WechatAuth._load_token_from_keyring()
            assert result == ""

    def test_wechat_auth_save_calls_settings_set_storage_key(self):
        """_save_token_to_keyring 调用 settings.set_storage_key('wechat_token', token)"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch.object(settings, "set_storage_key") as mock_set:
            ok = WechatAuth._save_token_to_keyring("new_wechat_token")
            assert ok is True
            mock_set.assert_called_once_with("wechat_token", "new_wechat_token")

    def test_wechat_auth_save_returns_false_on_exception(self):
        """_save_token_to_keyring 在 SettingsManager 抛异常时返回 False"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        with patch.object(settings, "set_storage_key", side_effect=RuntimeError("boom")):
            ok = WechatAuth._save_token_to_keyring("token")
            assert ok is False


# ==================== Seam 3: provider_manager ====================


def _make_raw_specs(*names_with_env: tuple[str, str]) -> list[dict]:
    """构造 raw_specs 测试数据，每项 (name, env_key)"""
    return [{"name": n, "env_key": e} for n, e in names_with_env]


class TestProviderManagerKeyMigration:
    """测试 provider_manager 通过 SettingsManager 路由读写 providers.{id} key"""

    def test_provider_manager_key_get_calls_settings_get_storage_key(self):
        """get_api_key 调用 settings.get_storage_key(f'providers.{provider_id}')"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("anthropic", "api_key_anthropic"))
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "get_storage_key", return_value="routed_provider_key") as mock_get:
            result = provider_manager.get_api_key("anthropic")
            assert result == "routed_provider_key"
            mock_get.assert_called_once_with("providers.anthropic")

    def test_provider_manager_key_local_mode_reads_keyring_via_settings(self):
        """本地模式：get_api_key 通过 SettingsManager 从 keyring 读取（按 provider 路由）"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("anthropic", "api_key_anthropic"))
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch(
                 "lifeprism.config.settings_manager.keyring.get_password",
                 return_value="kr_anthropic_key",
             ) as mock_kr:
            result = provider_manager.get_api_key("anthropic")
            assert result == "kr_anthropic_key"
            mock_kr.assert_called_once_with("lifeprism", "api_key_anthropic")

    def test_provider_manager_key_cloud_mode_reads_storage_via_settings(self, tmp_path):
        """云端模式：get_api_key 通过 SettingsManager 从 storage.yaml 读取嵌套 providers key"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("anthropic", "api_key_anthropic"))
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"providers": {"anthropic": "sk-ant-storage"}}, f)

        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = provider_manager.get_api_key("anthropic")
            assert result == "sk-ant-storage"

    def test_provider_manager_key_returns_none_when_no_key(self):
        """Key 不存在时返回 None（不报错）"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("anthropic", "api_key_anthropic"))
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "get_storage_key", return_value=None):
            # providers.yaml 中也无 api_key 字段
            result = provider_manager.get_api_key("anthropic")
            assert result is None

    def test_provider_manager_key_returns_none_when_no_env_key(self):
        """provider 无 env_key（如 custom）时返回 None"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("custom", ""))
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "get_storage_key") as mock_get:
            result = provider_manager.get_api_key("custom")
            assert result is None
            mock_get.assert_not_called()

    def test_provider_manager_key_multi_provider_independent(self):
        """多 provider 场景：anthropic + deepseek 同时存在，各自独立返回"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(
            ("anthropic", "api_key_anthropic"),
            ("deepseek", "api_key_deepseek"),
        )
        # 模拟 storage.yaml 中分别存有各自 key
        storage_map = {
            "providers.anthropic": "sk-ant-multi",
            "providers.deepseek": "sk-ds-multi",
        }

        def fake_get(key_name):
            return storage_map.get(key_name)

        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "get_storage_key", side_effect=fake_get):
            assert provider_manager.get_api_key("anthropic") == "sk-ant-multi"
            assert provider_manager.get_api_key("deepseek") == "sk-ds-multi"

    def test_provider_manager_key_cloud_fallback_to_providers_yaml(self, tmp_path):
        """云端模式 providers.yaml 兜底：storage.yaml 无此 provider → 查 providers.yaml"""
        from lifeprism.config.provider_manager import provider_manager

        # providers.yaml 中 anthropic 配有 api_key 字段（云端部署写入）
        raw_specs = [
            {"name": "anthropic", "env_key": "api_key_anthropic", "api_key": "yaml-fallback-key"}
        ]
        # storage.yaml 不含 providers.anthropic
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "other"}, f)

        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = provider_manager.get_api_key("anthropic")
            assert result == "yaml-fallback-key"

    def test_provider_manager_key_set_calls_settings_set_storage_key(self):
        """set_api_key 调用 settings.set_storage_key(f'providers.{provider_id}', value)"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("anthropic", "api_key_anthropic"))
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "set_storage_key") as mock_set:
            provider_manager.set_api_key("anthropic", "sk-new")
            mock_set.assert_called_once_with("providers.anthropic", "sk-new")

    def test_provider_manager_key_set_skips_when_no_env_key(self):
        """provider 无 env_key 时 set_api_key 不调用 SettingsManager"""
        from lifeprism.config.provider_manager import provider_manager

        raw_specs = _make_raw_specs(("custom", ""))
        with patch.object(provider_manager, "_raw_specs", raw_specs), \
             patch.object(settings, "set_storage_key") as mock_set:
            provider_manager.set_api_key("custom", "sk-irrelevant")
            mock_set.assert_not_called()
