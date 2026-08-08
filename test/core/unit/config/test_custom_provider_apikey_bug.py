"""
Bug C/D 复现测试：custom provider api_key 保存失败 + update_api_key 未检查返回值

背景：
- 历史 Bug C: DEFAULT_PROVIDER_CONFIG 中 custom provider 的 env_key 为空字符串，
  导致 _set_api_key_to_keyring_by_provider 因 username=None 跳过写入 keyring，
  set_api_key 返回 False 但 setting_service.update_api_key 未检查返回值仍打印"已保存"。
- 历史 Bug D: setting_service.update_api_key 不检查 set_api_key 返回值，失败时日志误导。

修复：
- Bug C: custom provider 的 env_key 改为 "api_key_custom"（DEFAULT_PROVIDER_CONFIG + 迁移脚本 p003）
- Bug D: update_api_key 检查 env_key 和 set_api_key 返回值，失败时抛 ValueError

参考:
- docs/history-bugs/ (本次新增)
- lifeprism/config/provider_manager.py: DEFAULT_PROVIDER_CONFIG
- lifeprism/config/migrations/scripts/p003_add_custom_env_key.py
- lifeprism/server/services/setting_service.py: update_api_key
"""

from unittest.mock import patch

import pytest

from lifeprism.config.provider_manager import provider_manager
from lifeprism.server.services import setting_service

pytestmark = pytest.mark.core


# ==================== Bug C: custom provider 的 env_key 修复 ====================


class TestCustomProviderEnvKey:
    """验证 custom provider 的 env_key 已正确配置"""

    def test_custom_env_key_is_not_empty(self):
        """Bug C: custom provider 的 env_key 不能为空字符串"""
        providers = provider_manager._raw_specs
        custom = next(p for p in providers if p.get("name") == "custom")
        assert custom["env_key"], (
            "custom provider 的 env_key 为空会导致 keyring 写入被跳过，"
            "api_key 实际未保存但日志显示'已安全保存'（误导）"
        )

    def test_custom_env_key_value(self):
        """custom provider 的 env_key 应为 'api_key_custom'"""
        providers = provider_manager._raw_specs
        custom = next(p for p in providers if p.get("name") == "custom")
        assert custom["env_key"] == "api_key_custom"

    def test_custom_keyring_username_not_none(self):
        """Bug C: get_keyring_username('custom') 不能返回 None"""
        username = provider_manager.get_keyring_username("custom")
        assert username is not None, (
            "get_keyring_username 返回 None 会导致 _set_api_key_to_keyring_by_provider 跳过写入"
        )
        assert username == "api_key_custom"

    def test_custom_set_and_get_api_key_roundtrip(self):
        """Bug C 复现：custom provider 的 api_key 应能正常保存和读取

        修复前：set_api_key 返回 False，get_api_key 返回 None
        修复后：set_api_key 返回 True，get_api_key 返回保存的值
        """
        test_key = "sk-test-custom-key-for-bug-c-reproduction"

        with patch("keyring.set_password") as mock_set, \
             patch("keyring.get_password") as mock_get:
            mock_get.return_value = test_key

            from lifeprism.config.settings_manager import settings

            # 保存
            success = settings.set_api_key(test_key, "custom")
            assert success is True, "set_api_key 应返回 True（env_key 已配置）"
            mock_set.assert_called_once()
            args = mock_set.call_args[0]
            assert args[1] == "api_key_custom", "应使用 env_key 作为 keyring username"
            assert args[2] == test_key

            # 读取
            retrieved = settings.get_api_key("custom")
            assert retrieved == test_key, "get_api_key 应返回保存的值"


# ==================== Bug C: 迁移脚本 p003 ====================


class TestP003Migration:
    """验证 p003 迁移脚本正确性"""

    def test_p003_check_if_applied_when_env_key_empty(self):
        """未应用迁移时（env_key 为空），check_if_applied 返回 False"""
        from lifeprism.config.migrations.scripts.p003_add_custom_env_key import (
            check_if_applied,
        )

        data = {
            "config_version": 2,
            "providers": [{"name": "custom", "env_key": ""}],
        }
        assert check_if_applied(data) is False

    def test_p003_check_if_applied_when_env_key_set(self):
        """已应用迁移后（env_key='api_key_custom'），check_if_applied 返回 True"""
        from lifeprism.config.migrations.scripts.p003_add_custom_env_key import (
            check_if_applied,
        )

        data = {
            "config_version": 3,
            "providers": [{"name": "custom", "env_key": "api_key_custom"}],
        }
        assert check_if_applied(data) is True

    def test_p003_upgrade_sets_env_key(self):
        """upgrade 后 custom 的 env_key 应为 'api_key_custom'"""
        from lifeprism.config.migrations.scripts.p003_add_custom_env_key import upgrade

        data = {
            "config_version": 2,
            "providers": [
                {"name": "dashscope", "env_key": "api_key_dashscope"},
                {"name": "custom", "env_key": ""},
            ],
        }
        result = upgrade(data)

        custom = next(p for p in result["providers"] if p["name"] == "custom")
        assert custom["env_key"] == "api_key_custom"
        assert result["config_version"] == 3

    def test_p003_upgrade_idempotent(self):
        """upgrade 应是幂等的：再次执行不会破坏已修复的配置"""
        from lifeprism.config.migrations.scripts.p003_add_custom_env_key import upgrade

        data = {
            "config_version": 3,
            "providers": [{"name": "custom", "env_key": "api_key_custom"}],
        }
        result = upgrade(data)
        custom = next(p for p in result["providers"] if p["name"] == "custom")
        assert custom["env_key"] == "api_key_custom"

    def test_p003_upgrade_preserves_other_providers(self):
        """upgrade 不应影响其他 provider 的 env_key"""
        from lifeprism.config.migrations.scripts.p003_add_custom_env_key import upgrade

        data = {
            "config_version": 2,
            "providers": [
                {"name": "dashscope", "env_key": "api_key_dashscope"},
                {"name": "custom", "env_key": ""},
                {"name": "openai", "env_key": "api_key_openai"},
            ],
        }
        result = upgrade(data)

        dashscope = next(p for p in result["providers"] if p["name"] == "dashscope")
        openai = next(p for p in result["providers"] if p["name"] == "openai")
        assert dashscope["env_key"] == "api_key_dashscope"
        assert openai["env_key"] == "api_key_openai"


# ==================== Bug D: update_api_key 检查返回值 ====================


class TestUpdateApiKeyValidation:
    """Bug D: setting_service.update_api_key 应检查 set_api_key 返回值"""

    def test_update_api_key_raises_when_env_key_empty(self):
        """Bug D 复现：provider 的 env_key 为空时，update_api_key 应抛 ValueError

        修复前：set_api_key 返回 False，但 update_api_key 仍打印"已安全保存"日志
        修复后：update_api_key 提前检查 env_key，为空时抛 ValueError
        """
        # 模拟一个 env_key 为空的 provider
        with patch.object(
            provider_manager, "get_keyring_username", return_value=None
        ), patch.object(
            provider_manager, "get_provider_id", return_value="fake_provider"
        ):
            with pytest.raises(ValueError, match="env_key 未配置"):
                setting_service.update_api_key("sk-fake-key", "fake_provider")

    def test_update_api_key_raises_when_set_api_key_fails(self):
        """Bug D 复现：set_api_key 返回 False 时，update_api_key 应抛 ValueError

        修复前：不检查返回值，日志显示"已安全保存"（误导）
        修复后：检查返回值，失败时抛 ValueError
        """
        with patch.object(
            provider_manager, "get_keyring_username", return_value="api_key_fake"
        ), patch.object(
            provider_manager, "get_provider_id", return_value="fake_provider"
        ), patch.object(
            setting_service.settings, "set_api_key", return_value=False
        ):
            with pytest.raises(ValueError, match="保存失败"):
                setting_service.update_api_key("sk-fake-key", "fake_provider")

    def test_update_api_key_success_when_set_api_key_returns_true(self):
        """正常路径：set_api_key 返回 True 时，update_api_key 返回 True"""
        with patch.object(
            provider_manager, "get_keyring_username", return_value="api_key_custom"
        ), patch.object(
            provider_manager, "get_provider_id", return_value="custom"
        ), patch.object(
            setting_service.settings, "set_api_key", return_value=True
        ) as mock_set:
            result = setting_service.update_api_key("sk-real-key", "custom")
            assert result is True
            mock_set.assert_called_once_with("sk-real-key", "custom")
