"""
storage.yaml 基础设施单元测试

验证 SettingsManager 的 storage.yaml 加载/保存/路由逻辑：
1. 云端模式：storage.yaml 不存在时 get_storage_key() 返回 None
2. 云端模式：storage.yaml 存在时 get_storage_key() 返回对应值
3. 云端模式：嵌套 key（providers.anthropic）正确读取
4. 云端模式：set_storage_key() 写入 storage.yaml
5. 云端模式：写入后文件权限为 600
6. 本地模式：只读 keyring，不加载/不创建 storage.yaml
7. save_storage_yaml() 批量写入
8. get()/set() 根据 run_mode 路由 Key 类字段

参考:
- ADR: docs/adr/2026-07-09-key-fallback-strategy.md v1.2
- Issue #26: storage.yaml 基础设施——SettingsManager 扩展
"""

from unittest.mock import patch

import pytest
import yaml

from lifeprism.config.settings_manager import (
    KEYRING_SERVICE_NAME,
    settings,
)

pytestmark = pytest.mark.core


# ==================== Slice 1: storage.yaml 不存在时返回 None ====================


class TestStorageYamlNotExists:
    """测试云端模式下 storage.yaml 不存在时的行为"""

    def test_get_storage_key_returns_none_when_storage_not_exist(self, tmp_path):
        """云端模式下 storage.yaml 不存在时，get_storage_key() 返回 None（不报错）"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get_storage_key("sync_api_key")
            assert result is None


# ==================== Slice 2: 云端模式从 storage.yaml 读取值 ====================


class TestStorageYamlRead:
    """测试云端模式下从 storage.yaml 读取 Key"""

    def test_get_storage_key_reads_sync_api_key_from_storage(self, tmp_path):
        """云端模式下 get_storage_key('sync_api_key') 返回 storage.yaml 中的值"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "N7kX_test_key"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get_storage_key("sync_api_key")
            assert result == "N7kX_test_key"

    def test_get_storage_key_reads_wechat_token_from_storage(self, tmp_path):
        """云端模式下 get_storage_key('wechat_token') 返回 storage.yaml 中的值"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"wechat_token": "wx_token_abc"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get_storage_key("wechat_token")
            assert result == "wx_token_abc"


# ==================== Slice 3: 嵌套 key 读取 ====================


class TestStorageYamlNestedKey:
    """测试嵌套 key（providers.anthropic）的读取"""

    def test_get_storage_key_reads_nested_provider_key(self, tmp_path):
        """get_storage_key('providers.anthropic') 返回嵌套结构中的值"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "sync_api_key": "N7kX...",
                    "providers": {
                        "anthropic": "sk-ant-xxx",
                        "deepseek": "sk-ds-yyy",
                    },
                },
                f,
            )

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get_storage_key("providers.anthropic")
            assert result == "sk-ant-xxx"

    def test_get_storage_key_nested_key_not_exist_returns_none(self, tmp_path):
        """嵌套 key 不存在时返回 None"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"providers": {"anthropic": "sk-ant-xxx"}}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get_storage_key("providers.openai")
            assert result is None


# ==================== Slice 4: set_storage_key 写入 storage.yaml ====================


class TestStorageYamlWrite:
    """测试云端模式下 set_storage_key() 写入 storage.yaml"""

    def test_set_storage_key_writes_sync_api_key_to_file(self, tmp_path):
        """set_storage_key('sync_api_key', ...) 写入 storage.yaml 文件"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            settings.set_storage_key("sync_api_key", "N7kX_new_key")

            storage_path = tmp_path / "storage.yaml"
            assert storage_path.exists()
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["sync_api_key"] == "N7kX_new_key"

    def test_set_storage_key_writes_nested_provider_key(self, tmp_path):
        """set_storage_key('providers.anthropic', ...) 写入嵌套结构"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            settings.set_storage_key("providers.anthropic", "sk-ant-new")

            storage_path = tmp_path / "storage.yaml"
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["providers"]["anthropic"] == "sk-ant-new"

    def test_set_storage_key_round_trip(self, tmp_path):
        """写入后读取返回写入的值"""
        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            settings.set_storage_key("wechat_token", "wx_round_trip")
            result = settings.get_storage_key("wechat_token")
            assert result == "wx_round_trip"


# ==================== Slice 5: 文件权限 600 ====================


class TestStorageYamlPermissions:
    """测试 storage.yaml 文件权限设置为 600"""

    def test_set_storage_key_sets_permission_600_on_linux(self, tmp_path):
        """非 Windows 平台写入 storage.yaml 后设置权限 600"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}), \
             patch("lifeprism.config.settings_manager.sys.platform", "linux"), \
             patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod:
            settings.set_storage_key("sync_api_key", "test_key")

            storage_path = tmp_path / "storage.yaml"
            chmod_calls = [
                (call.args[0], call.args[1]) for call in mock_chmod.call_args_list
            ]
            assert (storage_path, 0o600) in chmod_calls, (
                f"未找到设置权限 0o600 的调用，实际: {chmod_calls}"
            )

    def test_save_storage_yaml_sets_permission_600_on_linux(self, tmp_path):
        """save_storage_yaml() 在非 Windows 平台设置权限 600"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch("lifeprism.config.settings_manager.sys.platform", "linux"), \
             patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod:
            settings.save_storage_yaml({"sync_api_key": "bulk_key"})

            storage_path = tmp_path / "storage.yaml"
            chmod_calls = [
                (call.args[0], call.args[1]) for call in mock_chmod.call_args_list
            ]
            assert (storage_path, 0o600) in chmod_calls

    def test_set_storage_key_does_not_set_permission_on_windows(self, tmp_path):
        """Windows 平台不设置文件权限"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}), \
             patch("lifeprism.config.settings_manager.sys.platform", "win32"), \
             patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod:
            settings.set_storage_key("sync_api_key", "test_key")
            mock_chmod.assert_not_called()


# ==================== Slice 6: 本地模式只读 keyring ====================


class TestStorageYamlFullMode:
    """测试本地模式 (full) 下只读 keyring，不碰 storage.yaml"""

    def test_get_storage_key_reads_from_keyring_in_full_mode(self, tmp_path):
        """full 模式下 get_storage_key() 从 keyring 读取"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.get_password", return_value="kr_value") as mock_kr:
            result = settings.get_storage_key("sync_api_key")
            assert result == "kr_value"
            mock_kr.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key")

    def test_get_storage_key_returns_none_when_keyring_empty_in_full_mode(self, tmp_path):
        """full 模式下 keyring 无值时返回 None"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch("lifeprism.config.settings_manager.keyring.get_password", return_value=None):
            result = settings.get_storage_key("sync_api_key")
            assert result is None

    def test_full_mode_does_not_create_storage_yaml(self, tmp_path):
        """full 模式下 set_storage_key() 不创建 storage.yaml 文件"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set:
            settings.set_storage_key("sync_api_key", "kr_write_val")
            mock_set.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key", "kr_write_val")
            # storage.yaml 不应被创建
            assert not (tmp_path / "storage.yaml").exists()

    def test_full_mode_get_storage_key_does_not_load_storage_file(self, tmp_path):
        """full 模式下 get_storage_key() 不读取 storage.yaml 文件"""
        # 预创建 storage.yaml，验证 full 模式不读取它
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "storage_value"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch("lifeprism.config.settings_manager.keyring.get_password", return_value="kr_value"):
            result = settings.get_storage_key("sync_api_key")
            # 应返回 keyring 的值，而非 storage.yaml 的值
            assert result == "kr_value"


# ==================== Slice 7: save_storage_yaml public 接口 ====================


class TestSaveStorageYaml:
    """测试 save_storage_yaml() 批量写入接口"""

    def test_save_storage_yaml_writes_complete_data(self, tmp_path):
        """save_storage_yaml() 将完整数据写入 storage.yaml"""
        data = {
            "sync_api_key": "N7kX_bulk",
            "wechat_token": "wx_bulk",
            "providers": {
                "anthropic": "sk-ant-bulk",
                "deepseek": "sk-ds-bulk",
            },
        }
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path):
            settings.save_storage_yaml(data)

            storage_path = tmp_path / "storage.yaml"
            assert storage_path.exists()
            with open(storage_path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            assert loaded == data

    def test_save_storage_yaml_round_trip_read(self, tmp_path):
        """save_storage_yaml() 写入后，get_storage_key() 能读回值"""
        data = {
            "sync_api_key": "N7kX_rt",
            "providers": {"anthropic": "sk-ant-rt"},
        }
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path):
            settings.save_storage_yaml(data)
            assert settings.get_storage_key("sync_api_key") == "N7kX_rt"
            assert settings.get_storage_key("providers.anthropic") == "sk-ant-rt"


# ==================== Slice 8: get()/set() 根据 run_mode 路由 ====================


class TestGetSetRouting:
    """测试 get()/set() 根据 run_mode 路由 Key 类字段"""

    def test_get_sync_api_key_from_storage_in_cloud_mode(self, tmp_path):
        """云端模式下 get('sync_api_key') 从 storage.yaml 读取"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "via_get_method"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get("sync_api_key")
            assert result == "via_get_method"

    def test_get_wechat_token_from_storage_in_cloud_mode(self, tmp_path):
        """云端模式下 get('wechat_token') 从 storage.yaml 读取"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"wechat_token": "wx_via_get"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get("wechat_token")
            assert result == "wx_via_get"

    def test_get_sync_api_key_not_in_storage_returns_none_in_cloud_mode(self, tmp_path):
        """云端模式下 storage.yaml 无 sync_api_key 时 get() 返回 None"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            result = settings.get("sync_api_key")
            assert result is None

    def test_set_sync_api_key_to_storage_in_cloud_mode(self, tmp_path):
        """云端模式下 set('sync_api_key', ...) 写入 storage.yaml"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}):
            settings.set("sync_api_key", "set_via_set_method")

            storage_path = tmp_path / "storage.yaml"
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["sync_api_key"] == "set_via_set_method"

    def test_get_api_key_not_routed_to_storage_in_cloud_mode(self, tmp_path):
        """api_key 字段不路由到 storage.yaml，保持现有 ENV_VAR + keyring 路径"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"api_key": "should_not_read_this"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_config", {}), \
             patch("lifeprism.config.settings_manager.keyring.get_password", return_value=None):
            # api_key 不从 storage.yaml 读取（storage.yaml 中无 api_key 字段）
            result = settings.get("api_key")
            assert result != "should_not_read_this"

    def test_full_mode_get_sync_api_key_not_from_storage(self, tmp_path):
        """full 模式下 get('sync_api_key') 不从 storage.yaml 读取"""
        storage_path = tmp_path / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "storage_value"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config", {}):
            result = settings.get("sync_api_key")
            # full 模式不应读取 storage.yaml 中的值
            assert result != "storage_value"
