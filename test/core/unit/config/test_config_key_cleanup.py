"""
config.yaml Key 字段清理——单元测试（Issue #29）

验证 SettingsManager 的向后兼容迁移逻辑：
1. 本地模式：config.yaml 残留 Key → keyring → 清理 config.yaml
2. 云端模式：config.yaml 残留 Key → storage.yaml → 清理 config.yaml
3. storage.yaml 已存在时跳过迁移，仅清理 config.yaml
4. 迁移后其他配置字段保持不变
5. .gitignore 排除 storage.yaml 和 cloud_init.yaml

参考:
- Issue #29: config.yaml Key 字段清理 + .gitignore
- ADR: docs/adr/2026-07-09-key-fallback-strategy.md
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from lifeprism.config.settings_manager import KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME, settings

pytestmark = pytest.mark.core


# ==================== Slice 1: 本地模式迁移 (config.yaml 残留 Key → keyring) ====================


class TestKeyMigrationLocalMode:
    """测试本地模式 (full) 下 config.yaml 残留 Key 迁移到 keyring"""

    def test_migrate_sync_api_key_to_keyring_in_full_mode(self, tmp_path):
        """本地模式：config.yaml 残留 sync_api_key → 写入 keyring → 从 config.yaml 移除"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"sync_api_key": "legacy_sync_key", "provider": "anthropic"},
                f,
            )

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"sync_api_key": "legacy_sync_key", "provider": "anthropic"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set:
            settings._migrate_keys_from_config()

            # sync_api_key 写入 keyring
            mock_set.assert_called_once_with(
                KEYRING_SERVICE_NAME, "sync_api_key", "legacy_sync_key"
            )
            # config.yaml 中不再包含 sync_api_key
            assert "sync_api_key" not in settings._config

    def test_migrate_wechat_token_to_keyring_in_full_mode(self, tmp_path):
        """本地模式：config.yaml 残留 wechat_token → 写入 keyring → 从 config.yaml 移除"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"wechat_token": "legacy_wx_token"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set:
            settings._migrate_keys_from_config()

            mock_set.assert_called_once_with(
                KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME, "legacy_wx_token"
            )
            assert "wechat_token" not in settings._config

    def test_migrate_writes_config_yaml_without_key_fields(self, tmp_path):
        """迁移后 config.yaml 文件中不再包含 Key 字段"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "legacy_key", "provider": "anthropic"}, f)

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"sync_api_key": "legacy_key", "provider": "anthropic"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password"):
            settings._migrate_keys_from_config()

            with open(config_path, encoding="utf-8") as f:
                saved = yaml.safe_load(f)
            assert "sync_api_key" not in saved
            assert saved.get("provider") == "anthropic"


# ==================== Slice 2: storage.yaml 已存在时跳过迁移，仅清理 config.yaml ====================


class TestKeyMigrationStorageExists:
    """测试 storage.yaml 已存在时跳过迁移，仅清理 config.yaml

    云端场景下，CloudInitializer（Issue #28）先写 storage.yaml，
    然后 SettingsManager 加载时发现 storage.yaml 已存在 → 跳过迁移，仅清理 config.yaml 残留。
    """

    def test_skip_migration_when_storage_yaml_exists(self, tmp_path):
        """storage.yaml 已存在时不写入 keyring，仅从 config.yaml 移除残留 Key"""
        # 预创建 storage.yaml（模拟 CloudInitializer 已写入）
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        storage_path = tmp_path / "config" / "storage.yaml"
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump({"sync_api_key": "already_in_storage"}, f)

        config_path = tmp_path / "config" / "config.yaml"

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"sync_api_key": "legacy_key", "provider": "anthropic"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password") as mock_set:
            settings._migrate_keys_from_config()

            # 不写入 keyring（storage.yaml 已存在，跳过迁移）
            mock_set.assert_not_called()
            # config.yaml 中残留 Key 被清理
            assert "sync_api_key" not in settings._config

    def test_storage_yaml_unchanged_when_already_exists(self, tmp_path):
        """storage.yaml 已存在时其内容不被修改"""
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        storage_path = tmp_path / "config" / "storage.yaml"
        original_storage = {"sync_api_key": "original_storage_key", "wechat_token": "original_wx"}
        with open(storage_path, "w", encoding="utf-8") as f:
            yaml.dump(original_storage, f)

        config_path = tmp_path / "config" / "config.yaml"

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"sync_api_key": "legacy", "wechat_token": "legacy_wx"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password"):
            settings._migrate_keys_from_config()

            # storage.yaml 内容不变
            with open(storage_path, encoding="utf-8") as f:
                storage_data = yaml.safe_load(f)
            assert storage_data == original_storage


# ==================== Slice 3: 云端模式迁移 (config.yaml 残留 Key → storage.yaml) ====================


class TestKeyMigrationCloudMode:
    """测试云端模式 (agent_only/web_demo) 下 config.yaml 残留 Key 迁移到 storage.yaml"""

    def test_migrate_sync_api_key_to_storage_in_cloud_mode(self, tmp_path):
        """云端模式：config.yaml 残留 sync_api_key → 写入 storage.yaml → 从 config.yaml 移除"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # storage.yaml 不存在
        assert not (tmp_path / "config" / "storage.yaml").exists()

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"sync_api_key": "legacy_cloud_key", "provider": "anthropic"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None):
            settings._migrate_keys_from_config()

            # storage.yaml 被创建，包含迁移的 Key
            storage_path = tmp_path / "config" / "storage.yaml"
            assert storage_path.exists()
            with open(storage_path, encoding="utf-8") as f:
                storage_data = yaml.safe_load(f)
            assert storage_data["sync_api_key"] == "legacy_cloud_key"
            # config.yaml 中不再包含 Key 字段
            assert "sync_api_key" not in settings._config

    def test_migrate_wechat_token_to_storage_in_cloud_mode(self, tmp_path):
        """云端模式：config.yaml 残留 wechat_token → 写入 storage.yaml"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"wechat_token": "legacy_wx_cloud"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None):
            settings._migrate_keys_from_config()

            storage_path = tmp_path / "config" / "storage.yaml"
            with open(storage_path, encoding="utf-8") as f:
                storage_data = yaml.safe_load(f)
            assert storage_data["wechat_token"] == "legacy_wx_cloud"
            assert "wechat_token" not in settings._config

    def test_migrate_both_keys_to_storage_in_cloud_mode(self, tmp_path):
        """云端模式：同时迁移 sync_api_key 和 wechat_token 到 storage.yaml"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"sync_api_key": "sync_k", "wechat_token": "wx_k"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None):
            settings._migrate_keys_from_config()

            storage_path = tmp_path / "config" / "storage.yaml"
            with open(storage_path, encoding="utf-8") as f:
                storage_data = yaml.safe_load(f)
            assert storage_data["sync_api_key"] == "sync_k"
            assert storage_data["wechat_token"] == "wx_k"
            assert "sync_api_key" not in settings._config
            assert "wechat_token" not in settings._config


# ==================== Slice 4: 迁移后其他配置字段保持不变 ====================


class TestKeyMigrationPreservesOtherFields:
    """测试迁移后 config.yaml 中其他配置字段保持不变"""

    def test_preserves_provider_and_model_after_migration(self, tmp_path):
        """迁移后 llm.provider 和 llm.model 保持不变"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        original_config = {
            "sync_api_key": "legacy_key",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_base": "https://api.deepseek.com",
        }

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", dict(original_config)), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password"):
            settings._migrate_keys_from_config()

            # 非 Key 字段保持不变
            assert settings._config.get("provider") == "deepseek"
            assert settings._config.get("model") == "deepseek-chat"
            assert settings._config.get("api_base") == "https://api.deepseek.com"

    def test_preserves_timezone_and_monitor_type_after_migration(self, tmp_path):
        """迁移后 timezone 和 monitor_type 保持不变"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {
                 "sync_api_key": "legacy",
                 "wechat_token": "legacy_wx",
                 "timezone": "America/New_York",
                 "monitor_type": "lifeprism",
             }), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password"):
            settings._migrate_keys_from_config()

            assert settings._config.get("timezone") == "America/New_York"
            assert settings._config.get("monitor_type") == "lifeprism"

    def test_preserves_all_non_key_fields_in_saved_file(self, tmp_path):
        """迁移后 config.yaml 文件中所有非 Key 字段保持不变"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {
                 "sync_api_key": "legacy",
                 "wechat_token": "legacy_wx",
                 "provider": "anthropic",
                 "model": "claude-opus-4",
                 "timezone": "Asia/Shanghai",
                 "monitor_type": "none",
                 "user_name": "测试用户",
             }), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch("lifeprism.config.settings_manager.keyring.set_password"):
            settings._migrate_keys_from_config()

            with open(config_path, encoding="utf-8") as f:
                saved = yaml.safe_load(f)
            # Key 字段已移除
            assert "sync_api_key" not in saved
            assert "wechat_token" not in saved
            # 非 Key 字段保持不变
            assert saved["provider"] == "anthropic"
            assert saved["model"] == "claude-opus-4"
            assert saved["timezone"] == "Asia/Shanghai"
            assert saved["monitor_type"] == "none"
            assert saved["user_name"] == "测试用户"

    def test_no_migration_when_no_residual_keys(self, tmp_path):
        """config.yaml 中无残留 Key 字段时不触发迁移（不保存文件）"""
        config_path = tmp_path / "config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"provider": "anthropic", "model": "claude-opus-4"}, f)
        original_mtime = config_path.stat().st_mtime

        with patch.object(settings, "_runtime_config", {"run_mode": "full"}), \
             patch.object(settings, "_config_base_path", tmp_path), \
             patch.object(settings, "_config_path", config_path), \
             patch.object(settings, "_config", {"provider": "anthropic", "model": "claude-opus-4"}), \
             patch.object(settings, "_storage_config", {}), \
             patch.object(settings, "_storage_loaded_mode", None), \
             patch.object(settings, "_save_config") as mock_save:
            settings._migrate_keys_from_config()
            # 无残留 Key 时不调用 _save_config
            mock_save.assert_not_called()


# ==================== Slice 5: .gitignore 排除敏感配置文件 ====================


class TestGitignoreExcludesSensitiveFiles:
    """测试 .gitignore 排除 storage.yaml 和 cloud_init.yaml（Issue #29）"""

    @staticmethod
    def _read_gitignore() -> str:
        """读取项目根目录的 .gitignore 内容"""
        gitignore_path = Path(__file__).resolve().parents[4] / ".gitignore"
        return gitignore_path.read_text(encoding="utf-8")

    def test_gitignore_excludes_storage_yaml(self):
        """ .gitignore 中显式排除 storage.yaml（承载 Key 字段）"""
        content = self._read_gitignore()
        assert "storage.yaml" in content, (
            ".gitignore 应显式排除 storage.yaml（承载 sync_api_key/wechat_token/providers Key）"
        )

    def test_gitignore_excludes_cloud_init_yaml(self):
        """ .gitignore 中排除 cloud_init.yaml（云端初始化临时文件，含 Key）"""
        content = self._read_gitignore()
        assert "cloud_init.yaml" in content, (
            ".gitignore 应排除 cloud_init.yaml（云端初始化临时文件，含 Key）"
        )

    def test_gitignore_excludes_config_yaml(self):
        """ .gitignore 中排除 config.yaml（用户配置文件）"""
        content = self._read_gitignore()
        # config.yaml 被 *.yaml 通配或显式排除
        assert "config.yaml" in content or "*.yaml" in content, (
            ".gitignore 应排除 config.yaml（直接或通过 *.yaml 通配）"
        )


# ==================== Slice 6: DEFAULTS 无 Key 字段 + cloud_config_generator 无 Key 字段 ====================


class TestDefaultsAndSchemaClean:
    """验证 config.yaml DEFAULTS 和 cloud_config_generator config 段无 Key 字段"""

    def test_defaults_does_not_contain_sync_api_key(self):
        """DEFAULTS 中不包含 sync_api_key"""
        assert "sync_api_key" not in settings.DEFAULTS

    def test_defaults_does_not_contain_wechat_token(self):
        """DEFAULTS 中不包含 wechat_token"""
        assert "wechat_token" not in settings.DEFAULTS

    def test_defaults_does_not_contain_provider_api_keys(self):
        """DEFAULTS 中不包含 provider API Key 字段（如 anthropic_api_key）"""
        for key in settings.DEFAULTS:
            # api_key 是主 Key（保留，走 keyring/ENV），不在此清理范围
            if key == "api_key":
                continue
            # 不应有 {provider}_api_key 形式的字段
            assert not key.endswith("_api_key") or key == "api_key", (
                f"DEFAULTS 中不应包含 provider API Key 字段: {key}"
            )

    def test_cloud_config_generator_config_section_has_no_key_fields(self):
        """cloud_config_generator 的 config 段不包含 Key 字段"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        with patch("lifeprism.config.cloud_config_generator.settings") as mock_settings, \
             patch("lifeprism.config.cloud_config_generator.provider_manager") as mock_pm, \
             patch("lifeprism.config.cloud_config_generator.get_sync_api_key", return_value="sync_k"), \
             patch("lifeprism.config.cloud_config_generator.set_sync_api_key"), \
             patch("lifeprism.llm.channel.wechat.auth.WechatAuth._load_token_from_keyring", return_value="wx"):
            mock_settings.get.side_effect = lambda key, default=None: {
                "provider": "anthropic",
                "model": "claude-opus-4",
                "timezone": "Asia/Shanghai",
            }.get(key, default if default is not None else "")
            mock_settings.lifeprism_data_path = Path("/tmp")
            mock_pm.get_all_providers.return_value = []
            mock_pm._get_env_key.return_value = ""
            mock_pm.get_api_key.return_value = None

            path, _ = generator.generate_cloud_config()
            config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            config_section = config["config"]
            assert "sync_api_key" not in config_section
            assert "wechat_token" not in config_section
            assert "providers" not in config_section
