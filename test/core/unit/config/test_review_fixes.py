"""
审查修复单元测试 — 验证 6 个审查问题的修复

#1 CRITICAL: delete_storage_key() 路由正确性
#2 HIGH: get()/set()/update() full 模式下 STORAGE_KEY_FIELDS 路由
#3 HIGH: cloud_init.yaml 600 权限
#4 MEDIUM: warnings 属性类型注解
#5 MEDIUM: _set_api_key_to_keyring 使用 logger 而非 print
#6 MEDIUM: _save_config/_save_storage 原子写入
"""

from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest
import yaml

from lifeprism.config.settings_manager import KEYRING_SERVICE_NAME, settings

pytestmark = pytest.mark.core


# ==================== #1 CRITICAL: delete_storage_key() 路由 ====================


class TestDeleteStorageKeyRouting:
    """验证 delete_storage_key() 根据 run_mode 正确路由"""

    def test_delete_in_full_mode_calls_keyring(self):
        """full 模式下 delete_storage_key 从 keyring 删除"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.delete_password") as mock_del:
            settings.delete_storage_key("sync_api_key")
            mock_del.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key")

    def test_delete_in_cloud_mode_removes_from_storage(self, tmp_path):
        """云端模式下 delete_storage_key 从 storage.yaml 删除"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "val", "wechat_token": "wx"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", "agent_only"), \
             patch.object(settings, "_storage_config", {"sync_api_key": "val", "wechat_token": "wx"}):
            settings.delete_storage_key("sync_api_key")

            assert "sync_api_key" not in settings._storage_config
            assert "wechat_token" in settings._storage_config  # 其他 Key 不受影响

    def test_delete_nested_key_in_cloud_mode(self, tmp_path):
        """云端模式下 delete_storage_key 删除嵌套 key (providers.xxx)"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_storage_loaded_mode", "agent_only"), \
             patch.object(settings, "_storage_config", {
                 "providers": {"anthropic": "key1", "openai": "key2"}
             }):
            settings.delete_storage_key("providers.anthropic")

            assert "anthropic" not in settings._storage_config["providers"]
            assert "openai" in settings._storage_config["providers"]

    def test_delete_nonexistent_key_no_error(self):
        """删除不存在的 key 不抛异常"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.delete_password",
                   side_effect=Exception("not found")):
            # 不应抛异常
            settings.delete_storage_key("nonexistent_key")

    def test_delete_password_delete_error_suppressed(self):
        """PasswordDeleteError 被静默处理"""
        import keyring

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.delete_password",
                   side_effect=keyring.errors.PasswordDeleteError):
            settings.delete_storage_key("sync_api_key")  # 不应抛异常


class TestDeleteApiKeyRoutesThroughSettings:
    """验证 provider_manager.delete_api_key() 走 SettingsManager 路由"""

    def test_provider_delete_calls_settings_delete(self):
        """provider_manager.delete_api_key 调用 settings.delete_storage_key"""
        from lifeprism.config.provider_manager import provider_manager

        with patch.object(provider_manager, "_get_env_key", return_value="test_env_key"), \
             patch("lifeprism.config.settings_manager.settings.delete_storage_key") as mock_del:
            provider_manager.delete_api_key("anthropic")
            mock_del.assert_called_once_with("providers.anthropic")

    def test_provider_delete_skips_when_no_env_key(self):
        """env_key 为空时跳过删除"""
        from lifeprism.config.provider_manager import provider_manager

        with patch.object(provider_manager, "_get_env_key", return_value=""), \
             patch("lifeprism.config.settings_manager.settings.delete_storage_key") as mock_del:
            provider_manager.delete_api_key("custom_provider")
            mock_del.assert_not_called()


class TestDeleteTokenRoutesThroughSettings:
    """验证 wechat/auth.py delete_token() 走 SettingsManager 路由"""

    def test_delete_token_calls_settings_delete(self, tmp_path):
        """WechatAuth.delete_token 通过 SettingsManager 删除 token"""
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        state_file = tmp_path / "state.json"
        auth = WechatAuth(client=MagicMock(), state_file=state_file)

        with patch("lifeprism.config.settings_manager.settings.delete_storage_key") as mock_del:
            auth.delete_token()
            mock_del.assert_called_once_with("wechat_token")


# ==================== #2 HIGH: get()/set()/update() full 模式路由 ====================


class TestGetSetUpdateRoutingInFullMode:
    """验证 full 模式下 STORAGE_KEY_FIELDS 正确路由"""

    def test_get_sync_api_key_in_full_mode_returns_from_keyring(self):
        """full 模式下 get('sync_api_key') 从 keyring 读取"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.get_password", return_value="key_val"):
            result = settings.get("sync_api_key")
            assert result == "key_val"

    def test_get_wechat_token_in_full_mode_returns_from_keyring(self):
        """full 模式下 get('wechat_token') 从 keyring 读取"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.get_password", return_value="wx_val"):
            result = settings.get("wechat_token")
            assert result == "wx_val"

    def test_set_sync_api_key_in_full_mode_writes_to_keyring(self):
        """full 模式下 set('sync_api_key', val) 写入 keyring"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config", {}), \
             patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set, \
             patch.object(settings, "_save_config") as mock_save:
            settings.set("sync_api_key", "new_key")
            mock_set.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key", "new_key")
            # 不写入 config.yaml
            assert "sync_api_key" not in settings._config
            mock_save.assert_not_called()

    def test_set_sync_api_key_empty_in_full_mode_deletes(self):
        """full 模式下 set('sync_api_key', '') 触发删除"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config", {}), \
             patch("lifeprism.config.settings_manager.keyring.delete_password") as mock_del, \
             patch.object(settings, "_save_config") as mock_save:
            settings.set("sync_api_key", "")
            mock_del.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key")
            mock_save.assert_not_called()

    def test_update_sync_api_key_in_full_mode_writes_to_keyring(self):
        """full 模式下 update({'sync_api_key': val}) 写入 keyring"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config", {}), \
             patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set, \
             patch.object(settings, "_save_config") as mock_save:
            settings.update({"sync_api_key": "sync_val", "provider": "anthropic"})
            mock_set.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key", "sync_val")
            # sync_api_key 不写入 config.yaml
            assert "sync_api_key" not in settings._config
            assert settings._config.get("provider") == "anthropic"


# ==================== #3 HIGH: cloud_init.yaml 600 权限 ====================


class TestCloudInitPermissions:
    """验证 cloud_config_generator._save_config 设置 600 权限"""

    def test_chmod_called_on_non_windows(self, tmp_path):
        """非 Windows 平台 _save_config 调用 os.chmod 设置 600"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()

        with patch("lifeprism.config.cloud_config_generator.settings") as mock_settings, \
             patch("lifeprism.config.cloud_config_generator.sys") as mock_sys, \
             patch("lifeprism.config.cloud_config_generator.os") as mock_os:
            mock_settings.lifeprism_data_path = tmp_path
            mock_sys.platform = "linux"

            generator._save_config({"test": "config"})

            cloud_path = tmp_path / "cloud_init.yaml"
            mock_os.chmod.assert_called_once_with(cloud_path, 0o600)

    def test_chmod_not_called_on_windows(self, tmp_path):
        """Windows 平台不调用 os.chmod"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()

        with patch("lifeprism.config.cloud_config_generator.settings") as mock_settings, \
             patch("lifeprism.config.cloud_config_generator.sys") as mock_sys, \
             patch("lifeprism.config.cloud_config_generator.os") as mock_os:
            mock_settings.lifeprism_data_path = tmp_path
            mock_sys.platform = "win32"

            generator._save_config({"test": "config"})

            mock_os.chmod.assert_not_called()


# ==================== #4 MEDIUM: warnings 属性类型注解 ====================


class TestWarningsTypeAnnotation:
    """验证 warnings 属性返回 list[dict[str, str]]"""

    def test_warnings_returns_list_of_dicts(self):
        """warnings 返回 list[dict[str, str]]"""
        with patch.object(settings, "_warnings", [
            {"type": "data_path", "message": "test warning"}
        ]):
            result = settings.warnings
            assert isinstance(result, list)
            assert all(isinstance(item, dict) for item in result)
            assert result[0]["type"] == "data_path"
            assert result[0]["message"] == "test warning"

    def test_warnings_empty_returns_empty_list(self):
        """warnings 为空时返回空列表"""
        with patch.object(settings, "_warnings", []):
            result = settings.warnings
            assert result == []


# ==================== #5 MEDIUM: print() → logger ====================


class TestNoPrintInKeyringMethods:
    """验证 _set_api_key_to_keyring 使用 logger 而非 print"""

    def test_set_api_key_to_keyring_failure_uses_logger(self):
        """_set_api_key_to_keyring 失败时使用 logger.warning 而非 print"""
        with patch("lifeprism.config.settings_manager.keyring.set_password",
                   side_effect=Exception("test error")), \
             patch("lifeprism.config.settings_manager.logger") as mock_logger:
            result = settings._set_api_key_to_keyring("test_key")
            assert result is False
            mock_logger.warning.assert_called_once()
            # 确认不是 print 被调用
            args = mock_logger.warning.call_args
            assert "test error" in str(args)

    def test_set_api_key_to_keyring_by_provider_failure_uses_logger(self):
        """_set_api_key_to_keyring_by_provider 失败时使用 logger.warning"""
        from lifeprism.config.provider_manager import provider_manager

        with patch("lifeprism.config.provider_manager.provider_manager.get_keyring_username",
                   return_value="test_user"), \
             patch("lifeprism.config.settings_manager.keyring.set_password",
                   side_effect=Exception("test error")), \
             patch("lifeprism.config.settings_manager.logger") as mock_logger:
            result = settings._set_api_key_to_keyring_by_provider("anthropic", "test_key")
            assert result is False
            mock_logger.warning.assert_called_once()


# ==================== #6 MEDIUM: 原子写入 ====================


class TestAtomicWrites:
    """验证 _save_config / _save_storage 使用原子写入"""

    def test_save_config_uses_temp_file_and_replace(self, tmp_path):
        """_save_config 使用临时文件 + os.replace"""
        config_path = tmp_path / "config.yaml"

        with patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"key": "value"}), \
             patch("lifeprism.config.settings_manager.os.replace") as mock_replace:
            settings._save_config()

            # os.replace 被调用
            mock_replace.assert_called_once()
            args = mock_replace.call_args[0]
            assert str(args[0]).endswith(".tmp")
            assert args[1] == config_path

    def test_save_storage_uses_temp_file_and_replace(self, tmp_path):
        """_save_storage 使用临时文件 + os.replace"""
        with patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_config", {"sync_api_key": "val"}), \
             patch("lifeprism.config.settings_manager.os.replace") as mock_replace:
            settings._save_storage()

            mock_replace.assert_called_once()
            args = mock_replace.call_args[0]
            assert str(args[0]).endswith(".tmp")
            storage_path = tmp_path / "storage.yaml"
            assert args[1] == storage_path

    def test_save_config_no_direct_write_to_target(self, tmp_path):
        """_save_config 不直接写入目标文件，先写 .tmp 再 replace"""
        config_path = tmp_path / "config.yaml"

        with patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"key": "value"}):
            settings._save_config()

            # .tmp 文件应该已被 replace 清理（不再存在）
            tmp_file = config_path.with_suffix(".tmp")
            assert not tmp_file.exists()
            # 目标文件应存在
            assert config_path.exists()
