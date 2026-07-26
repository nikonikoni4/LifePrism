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
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("sync_api_key")
            assert result is None


# ==================== Slice 2: 云端模式从 storage.yaml 读取值 ====================


class TestStorageYamlRead:
    """测试云端模式下从 storage.yaml 读取 Key"""

    def test_get_storage_key_reads_sync_api_key_from_storage(self, tmp_path):
        """云端模式下 get_storage_key('sync_api_key') 返回 storage.yaml 中的值"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "N7kX_test_key"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("sync_api_key")
            assert result == "N7kX_test_key"

    def test_get_storage_key_reads_wechat_token_from_storage(self, tmp_path):
        """云端模式下 get_storage_key('wechat_token') 返回 storage.yaml 中的值"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"wechat_token": "wx_token_abc"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("wechat_token")
            assert result == "wx_token_abc"


# ==================== Slice 3: 嵌套 key 读取 ====================


class TestStorageYamlNestedKey:
    """测试嵌套 key（providers.anthropic）的读取"""

    def test_get_storage_key_reads_nested_provider_key(self, tmp_path):
        """get_storage_key('providers.anthropic') 返回嵌套结构中的值"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
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

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("providers.anthropic")
            assert result == "sk-ant-xxx"

    def test_get_storage_key_nested_key_not_exist_returns_none(self, tmp_path):
        """嵌套 key 不存在时返回 None"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"providers": {"anthropic": "sk-ant-xxx"}}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("providers.openai")
            assert result is None


# ==================== Slice 4: set_storage_key 写入 storage.yaml ====================


class TestStorageYamlWrite:
    """测试云端模式下 set_storage_key() 写入 storage.yaml"""

    def test_set_storage_key_writes_sync_api_key_to_file(self, tmp_path):
        """set_storage_key('sync_api_key', ...) 写入 storage.yaml 文件"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            settings.set_storage_key("sync_api_key", "N7kX_new_key")

            storage_path = tmp_path / "config" / "storage.yaml"
            assert storage_path.exists()
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["sync_api_key"] == "N7kX_new_key"

    def test_set_storage_key_writes_nested_provider_key(self, tmp_path):
        """set_storage_key('providers.anthropic', ...) 写入嵌套结构"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            settings.set_storage_key("providers.anthropic", "sk-ant-new")

            storage_path = tmp_path / "config" / "storage.yaml"
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["providers"]["anthropic"] == "sk-ant-new"

    def test_set_storage_key_round_trip(self, tmp_path):
        """写入后读取返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            settings.set_storage_key("wechat_token", "wx_round_trip")
            result = settings.get_storage_key("wechat_token")
            assert result == "wx_round_trip"


# ==================== Slice 5: 文件权限 600 ====================


class TestStorageYamlPermissions:
    """测试 storage.yaml 文件权限设置为 600"""

    def test_set_storage_key_sets_permission_600_on_linux(self, tmp_path):
        """非 Windows 平台写入 storage.yaml 后设置权限 600"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
            patch("lifeprism.config.settings_manager.sys.platform", "linux"),
            patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod,
        ):
            settings.set_storage_key("sync_api_key", "test_key")

            storage_path = tmp_path / "config" / "storage.yaml"
            chmod_calls = [(call.args[0], call.args[1]) for call in mock_chmod.call_args_list]
            assert (storage_path, 0o600) in chmod_calls, (
                f"未找到设置权限 0o600 的调用，实际: {chmod_calls}"
            )

    def test_save_storage_yaml_sets_permission_600_on_linux(self, tmp_path):
        """save_storage_yaml() 在非 Windows 平台设置权限 600"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch("lifeprism.config.settings_manager.sys.platform", "linux"),
            patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod,
        ):
            settings.save_storage_yaml({"sync_api_key": "bulk_key"})

            storage_path = tmp_path / "config" / "storage.yaml"
            chmod_calls = [(call.args[0], call.args[1]) for call in mock_chmod.call_args_list]
            assert (storage_path, 0o600) in chmod_calls

    def test_set_storage_key_does_not_set_permission_on_windows(self, tmp_path):
        """Windows 平台不设置文件权限"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
            patch("lifeprism.config.settings_manager.sys.platform", "win32"),
            patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod,
        ):
            settings.set_storage_key("sync_api_key", "test_key")
            mock_chmod.assert_not_called()


# ==================== Slice 6: 本地模式只读 keyring ====================


class TestStorageYamlFullMode:
    """测试本地模式 (full) 下只读 keyring，不碰 storage.yaml"""

    def test_get_storage_key_reads_from_keyring_in_full_mode(self, tmp_path):
        """full 模式下 get_storage_key() 从 keyring 读取"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch(
                "lifeprism.config.settings_manager.keyring.get_password", return_value="kr_value"
            ) as mock_kr,
        ):
            result = settings.get_storage_key("sync_api_key")
            assert result == "kr_value"
            mock_kr.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key")

    def test_get_storage_key_returns_none_when_keyring_empty_in_full_mode(self, tmp_path):
        """full 模式下 keyring 无值时返回 None"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch("lifeprism.config.settings_manager.keyring.get_password", return_value=None),
        ):
            result = settings.get_storage_key("sync_api_key")
            assert result is None

    def test_full_mode_does_not_create_storage_yaml(self, tmp_path):
        """full 模式下 set_storage_key() 不创建 storage.yaml 文件"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set,
        ):
            settings.set_storage_key("sync_api_key", "kr_write_val")
            mock_set.assert_called_once_with(KEYRING_SERVICE_NAME, "sync_api_key", "kr_write_val")
            # storage.yaml 不应被创建
            assert not (tmp_path / "config" / "storage.yaml").exists()

    def test_full_mode_get_storage_key_does_not_load_storage_file(self, tmp_path):
        """full 模式下 get_storage_key() 不读取 storage.yaml 文件"""
        # 预创建 storage.yaml，验证 full 模式不读取它
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "storage_value"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch(
                "lifeprism.config.settings_manager.keyring.get_password", return_value="kr_value"
            ),
        ):
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
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
        ):
            settings.save_storage_yaml(data)

            storage_path = tmp_path / "config" / "storage.yaml"
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
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
        ):
            settings.save_storage_yaml(data)
            assert settings.get_storage_key("sync_api_key") == "N7kX_rt"
            assert settings.get_storage_key("providers.anthropic") == "sk-ant-rt"


# ==================== Slice 8: get()/set() 根据 run_mode 路由 ====================


class TestGetSetRouting:
    """测试 get()/set() 根据 run_mode 路由 Key 类字段"""

    def test_get_sync_api_key_from_storage_in_cloud_mode(self, tmp_path):
        """云端模式下 get('sync_api_key') 从 storage.yaml 读取"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "via_get_method"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get("sync_api_key")
            assert result == "via_get_method"

    def test_get_wechat_token_from_storage_in_cloud_mode(self, tmp_path):
        """云端模式下 get('wechat_token') 从 storage.yaml 读取"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"wechat_token": "wx_via_get"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get("wechat_token")
            assert result == "wx_via_get"

    def test_get_sync_api_key_not_in_storage_returns_none_in_cloud_mode(self, tmp_path):
        """云端模式下 storage.yaml 无 sync_api_key 时 get() 返回 None"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get("sync_api_key")
            assert result is None

    def test_set_sync_api_key_to_storage_in_cloud_mode(self, tmp_path):
        """云端模式下 set('sync_api_key', ...) 写入 storage.yaml"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            settings.set("sync_api_key", "set_via_set_method")

            storage_path = tmp_path / "config" / "storage.yaml"
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["sync_api_key"] == "set_via_set_method"

    def test_get_api_key_not_routed_to_storage_in_cloud_mode(self, tmp_path):
        """api_key 字段不路由到 storage.yaml，保持现有 ENV_VAR + keyring 路径"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"api_key": "should_not_read_this"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
            patch.object(settings, "_config", {}),
            patch("lifeprism.config.settings_manager.keyring.get_password", return_value=None),
        ):
            # api_key 不从 storage.yaml 读取（storage.yaml 中无 api_key 字段）
            result = settings.get("api_key")
            assert result != "should_not_read_this"

    def test_full_mode_get_sync_api_key_not_from_storage(self, tmp_path):
        """full 模式下 get('sync_api_key') 不从 storage.yaml 读取"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "storage_value"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_config", {}),
        ):
            result = settings.get("sync_api_key")
            # full 模式不应读取 storage.yaml 中的值
            assert result != "storage_value"


# ==================== Slice 9: SSH 隧道配置字段默认值 ====================


class TestSshTunnelConfigDefaults:
    """测试 SSH 隧道相关配置字段的默认值（参考 Issue #02）"""

    def test_sync_connection_mode_default_is_http(self):
        """sync.connection_mode 默认值为 'http'"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.connection_mode") == "http"

    def test_sync_ssh_tunnel_host_default_is_empty_string(self):
        """sync.ssh_tunnel.host 默认值为空字符串"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.ssh_tunnel.host") == ""

    def test_sync_ssh_tunnel_port_default_is_22(self):
        """sync.ssh_tunnel.port 默认值为 22"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.ssh_tunnel.port") == 22

    def test_sync_ssh_tunnel_username_default_is_empty_string(self):
        """sync.ssh_tunnel.username 默认值为空字符串"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.ssh_tunnel.username") == ""

    def test_sync_ssh_tunnel_local_port_default_is_8102(self):
        """sync.ssh_tunnel.local_port 默认值为 8102"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.ssh_tunnel.local_port") == 8102

    def test_sync_ssh_tunnel_remote_host_default_is_127_0_0_1(self):
        """sync.ssh_tunnel.remote_host 默认值为 '127.0.0.1'"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.ssh_tunnel.remote_host") == "127.0.0.1"

    def test_sync_ssh_tunnel_remote_port_default_is_8102(self):
        """sync.ssh_tunnel.remote_port 默认值为 8102"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config", {}),
        ):
            assert settings.get("sync.ssh_tunnel.remote_port") == 8102


# ==================== Slice 10: SSH 隧道配置字段读写 ====================


class TestSshTunnelConfigReadWrite:
    """测试 sync.ssh_tunnel.* 6 个字段 + sync.connection_mode 可正常读写"""

    def test_set_and_get_sync_connection_mode(self, tmp_path):
        """set('sync.connection_mode', 'ssh') 后 get 返回 'ssh'，并写入 config.yaml"""
        config_path = tmp_path / "config" / "config.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", config_path),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.connection_mode", "ssh", save=False)
            assert settings.get("sync.connection_mode") == "ssh"

    def test_set_and_get_sync_ssh_tunnel_host(self, tmp_path):
        """set('sync.ssh_tunnel.host', ...) 后 get 返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", tmp_path / "config.yaml"),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.ssh_tunnel.host", "1.2.3.4", save=False)
            assert settings.get("sync.ssh_tunnel.host") == "1.2.3.4"

    def test_set_and_get_sync_ssh_tunnel_port(self, tmp_path):
        """set('sync.ssh_tunnel.port', ...) 后 get 返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", tmp_path / "config.yaml"),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.ssh_tunnel.port", 2222, save=False)
            assert settings.get("sync.ssh_tunnel.port") == 2222

    def test_set_and_get_sync_ssh_tunnel_username(self, tmp_path):
        """set('sync.ssh_tunnel.username', ...) 后 get 返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", tmp_path / "config.yaml"),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.ssh_tunnel.username", "lifeprism", save=False)
            assert settings.get("sync.ssh_tunnel.username") == "lifeprism"

    def test_set_and_get_sync_ssh_tunnel_local_port(self, tmp_path):
        """set('sync.ssh_tunnel.local_port', ...) 后 get 返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", tmp_path / "config.yaml"),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.ssh_tunnel.local_port", 9000, save=False)
            assert settings.get("sync.ssh_tunnel.local_port") == 9000

    def test_set_and_get_sync_ssh_tunnel_remote_host(self, tmp_path):
        """set('sync.ssh_tunnel.remote_host', ...) 后 get 返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", tmp_path / "config.yaml"),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.ssh_tunnel.remote_host", "10.0.0.1", save=False)
            assert settings.get("sync.ssh_tunnel.remote_host") == "10.0.0.1"

    def test_set_and_get_sync_ssh_tunnel_remote_port(self, tmp_path):
        """set('sync.ssh_tunnel.remote_port', ...) 后 get 返回写入的值"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", tmp_path / "config.yaml"),
            patch.object(settings, "_config", {}),
        ):
            settings.set("sync.ssh_tunnel.remote_port", 8103, save=False)
            assert settings.get("sync.ssh_tunnel.remote_port") == 8103

    def test_sync_ssh_tunnel_fields_persisted_to_config_yaml(self, tmp_path):
        """sync.ssh_tunnel.* 字段写入 config.yaml 文件（非 storage.yaml）"""
        config_path = tmp_path / "config" / "config.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", config_path),
            patch.object(settings, "_config", {}),
            patch("lifeprism.config.settings_manager.keyring.set_password"),
        ):
            settings.set("sync.connection_mode", "ssh")
            settings.set("sync.ssh_tunnel.host", "192.168.1.1")
            settings.set("sync.ssh_tunnel.port", 22)
            settings.set("sync.ssh_tunnel.username", "deploy")
            settings.set("sync.ssh_tunnel.local_port", 8102)
            settings.set("sync.ssh_tunnel.remote_host", "127.0.0.1")
            settings.set("sync.ssh_tunnel.remote_port", 8102)

            assert config_path.exists()
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["sync.connection_mode"] == "ssh"
            assert data["sync.ssh_tunnel.host"] == "192.168.1.1"
            assert data["sync.ssh_tunnel.port"] == 22
            assert data["sync.ssh_tunnel.username"] == "deploy"
            assert data["sync.ssh_tunnel.local_port"] == 8102
            assert data["sync.ssh_tunnel.remote_host"] == "127.0.0.1"
            assert data["sync.ssh_tunnel.remote_port"] == 8102


# ==================== Slice 11: ssh_tunnel_private_key 存储路由 ====================


class TestSshTunnelPrivateKeyStorageRoute:
    """测试 ssh_tunnel_private_key 走 keyring/storage.yaml 路由（参考 Issue #02）"""

    def test_set_ssh_tunnel_private_key_to_keyring_in_full_mode(self, tmp_path):
        """full 模式下 set_storage_key('ssh_tunnel_private_key', pem) 写入 keyring"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set,
        ):
            pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
            settings.set_storage_key("ssh_tunnel_private_key", pem)
            mock_set.assert_called_once_with(
                KEYRING_SERVICE_NAME, "ssh_tunnel_private_key", pem
            )

    def test_get_ssh_tunnel_private_key_from_keyring_in_full_mode(self, tmp_path):
        """full 模式下 get_storage_key('ssh_tunnel_private_key') 从 keyring 读取"""
        pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch(
                "lifeprism.config.settings_manager.keyring.get_password", return_value=pem
            ) as mock_kr,
        ):
            result = settings.get_storage_key("ssh_tunnel_private_key")
            assert result == pem
            mock_kr.assert_called_once_with(KEYRING_SERVICE_NAME, "ssh_tunnel_private_key")

    def test_get_ssh_tunnel_private_key_returns_none_in_agent_only_when_not_exist(
        self, tmp_path
    ):
        """agent_only 模式下 storage.yaml 无此字段时返回 None"""
        # storage.yaml 不存在，模拟云端未配置 SSH 隧道场景
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("ssh_tunnel_private_key")
            assert result is None

    def test_get_ssh_tunnel_private_key_returns_none_in_agent_only_when_field_missing(
        self, tmp_path
    ):
        """agent_only 模式下 storage.yaml 存在但无私钥字段时返回 None"""
        storage_path = tmp_path / "config" / "storage.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "other_key"}, f)

        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            result = settings.get_storage_key("ssh_tunnel_private_key")
            assert result is None

    def test_set_ssh_tunnel_private_key_to_storage_yaml_in_cloud_mode(self, tmp_path):
        """agent_only 模式下 set_storage_key 写入 storage.yaml"""
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}),
            patch.object(settings, "_config_base_path", tmp_path),
            patch.object(settings, "_storage_loaded_mode", None),
            patch.object(settings, "_storage_config", {}),
        ):
            pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
            settings.set_storage_key("ssh_tunnel_private_key", pem)

            storage_path = tmp_path / "config" / "storage.yaml"
            assert storage_path.exists()
            with open(storage_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["ssh_tunnel_private_key"] == pem

    def test_ssh_tunnel_private_key_not_in_config_yaml(self, tmp_path):
        """set('ssh_tunnel_private_key', pem) 不写入 config.yaml（走 storage 路由）"""
        config_path = tmp_path / "config" / "config.yaml"
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        # 预先写入普通配置，确保 config.yaml 存在
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"user_name": "alice", "sync.remote_url": "http://example.com"}, f)

        pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch.object(settings, "_config_path", config_path),
            patch.object(
                settings,
                "_config",
                {"user_name": "alice", "sync.remote_url": "http://example.com"},
            ),
            patch("lifeprism.config.settings_manager.keyring.set_password") as mock_kr_set,
        ):
            settings.set("ssh_tunnel_private_key", pem)

            # keyring 被调用（走 storage 路由）
            mock_kr_set.assert_called_once_with(
                KEYRING_SERVICE_NAME, "ssh_tunnel_private_key", pem
            )
            # config.yaml 不应包含私钥字段（仍只有普通配置）
            assert config_path.exists()
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert "ssh_tunnel_private_key" not in data
            # 普通配置仍正常持久化
            assert data.get("user_name") == "alice"

    def test_get_ssh_tunnel_private_key_via_get_method_in_full_mode(self, tmp_path):
        """full 模式下 get('ssh_tunnel_private_key') 走 keyring 路由"""
        pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
        with (
            patch.object(settings, "_runtime_config", {"run_mode": "full"}),
            patch(
                "lifeprism.config.settings_manager.keyring.get_password", return_value=pem
            ),
        ):
            result = settings.get("ssh_tunnel_private_key")
            assert result == pem

    def test_ssh_tunnel_private_key_registered_in_storage_key_fields(self):
        """ssh_tunnel_private_key 应注册到 STORAGE_KEY_FIELDS"""
        assert "ssh_tunnel_private_key" in settings.STORAGE_KEY_FIELDS

    def test_ssh_tunnel_private_key_registered_in_keyring_username_map(self):
        """ssh_tunnel_private_key 应在 STORAGE_KEY_TO_KEYRING_USERNAME 中注册映射"""
        assert (
            settings.STORAGE_KEY_TO_KEYRING_USERNAME.get("ssh_tunnel_private_key")
            == "ssh_tunnel_private_key"
        )
