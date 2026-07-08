"""
CloudConfigGenerator 单元测试

验证云端配置生成逻辑：从 keyring 读取所有 Key（LLM/微信/同步），
生成完整的 cloud_init.yaml。

测试 Seams:
1. CloudConfigGenerator.generate_cloud_config() 公开接口
   - 测试从 keyring 读取已有 Key（key_is_new = false）
   - 测试 keyring 无 Key 时生成新 Key（key_is_new = true）
   - 测试生成完整配置（包含所有 Provider）
   - 测试 monitor_type 强制覆盖为 none
   - 测试文件保存路径正确
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.core

# ==================== 测试数据 ====================

PROVIDERS = [
    {
        "name": "anthropic",
        "display_name": "Anthropic",
        "default_model": "claude-opus-4",
        "default_api_base": "",
        "has_api_key": True,
    },
    {
        "name": "deepseek",
        "display_name": "DeepSeek",
        "default_model": "deepseek-chat",
        "default_api_base": "",
        "has_api_key": True,
    },
]

API_KEYS = {
    "anthropic": "sk-ant-xxx",
    "deepseek": "sk-ds-xxx",
}

ENV_KEYS = {
    "anthropic": "api_key_anthropic",
    "deepseek": "api_key_deepseek",
}


# ==================== Fixture ====================


@pytest.fixture
def mock_env(tmp_path):
    """统一 mock 所有外部依赖，返回可配置的 mock 对象字典。

    默认场景：keyring 已有同步 Key，所有 provider 都有 Key。
    """
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "provider": "anthropic",
        "model": "claude-opus-4",
    }.get(key, default if default is not None else "")
    mock_settings.lifeprism_data_path = tmp_path

    mock_pm = MagicMock()
    mock_pm.get_all_providers.return_value = PROVIDERS
    mock_pm.get_api_key.side_effect = lambda name: API_KEYS.get(name)
    mock_pm._get_env_key.side_effect = lambda name: ENV_KEYS.get(name, "")

    mock_get_sync = MagicMock(return_value="existing-sync-key")
    mock_set_sync = MagicMock()

    patches = [
        patch(
            "lifeprism.config.cloud_config_generator.settings",
            mock_settings,
        ),
        patch(
            "lifeprism.config.cloud_config_generator.provider_manager",
            mock_pm,
        ),
        patch(
            "lifeprism.config.cloud_config_generator.get_sync_api_key",
            mock_get_sync,
        ),
        patch(
            "lifeprism.config.cloud_config_generator.set_sync_api_key",
            mock_set_sync,
        ),
        patch(
            "lifeprism.llm.channel.wechat.auth.WechatAuth._load_token_from_keyring",
            return_value="wx-token-xxx",
        ),
    ]

    for p in patches:
        p.start()

    yield {
        "settings": mock_settings,
        "provider_manager": mock_pm,
        "get_sync_api_key": mock_get_sync,
        "set_sync_api_key": mock_set_sync,
        "tmp_path": tmp_path,
    }

    for p in patches:
        p.stop()


# ==================== 测试类 ====================


class TestCloudConfigGeneratorReadsExistingKey:
    """测试从 keyring 读取已有同步 Key 的场景"""

    def test_key_is_new_false_when_existing_key(self, mock_env):
        """keyring 已有同步 Key 时，key_is_new = False"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, key_is_new = generator.generate_cloud_config()

        assert key_is_new is False

    def test_set_sync_api_key_not_called_when_existing(self, mock_env):
        """已有 Key 时不调用 set_sync_api_key"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        generator.generate_cloud_config()

        mock_env["set_sync_api_key"].assert_not_called()

    def test_existing_key_written_to_yaml(self, mock_env):
        """已有的同步 Key 被写入 YAML 配置文件"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert config["sync"]["api_key"] == "existing-sync-key"


class TestCloudConfigGeneratorGeneratesNewKey:
    """测试 keyring 无同步 Key 时生成新 Key 的场景"""

    def test_key_is_new_true_when_no_key(self, mock_env):
        """keyring 无同步 Key 时，生成新 Key，key_is_new = True"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        mock_env["get_sync_api_key"].return_value = None

        generator = CloudConfigGenerator()
        path, key_is_new = generator.generate_cloud_config()

        assert key_is_new is True

    def test_set_sync_api_key_called_when_no_key(self, mock_env):
        """无 Key 时调用 set_sync_api_key 保存新 Key"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        mock_env["get_sync_api_key"].return_value = None

        generator = CloudConfigGenerator()
        generator.generate_cloud_config()

        mock_env["set_sync_api_key"].assert_called_once()

    def test_generated_key_is_random_and_long_enough(self, mock_env):
        """生成的 Key 是随机字符串且长度足够（32 字节 base64 ~43 字符）"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        mock_env["get_sync_api_key"].return_value = None

        generator = CloudConfigGenerator()
        generator.generate_cloud_config()

        saved_key = mock_env["set_sync_api_key"].call_args[0][0]
        assert isinstance(saved_key, str)
        assert len(saved_key) >= 32

    def test_generated_key_written_to_yaml(self, mock_env):
        """新生成的 Key 被写入 YAML 配置文件"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        mock_env["get_sync_api_key"].return_value = None

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        saved_key = mock_env["set_sync_api_key"].call_args[0][0]
        assert config["sync"]["api_key"] == saved_key


class TestCloudConfigGeneratorCompleteConfig:
    """测试生成完整配置"""

    def test_includes_all_providers(self, mock_env):
        """生成的配置包含所有有 Key 的 Provider"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert "providers" in config
        assert len(config["providers"]) == 2

        names = [p["name"] for p in config["providers"]]
        assert "anthropic" in names
        assert "deepseek" in names

    def test_provider_has_name_env_key_api_key(self, mock_env):
        """每个 provider 包含 name、env_key、api_key 三个字段"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for p in config["providers"]:
            assert "name" in p
            assert "env_key" in p
            assert "api_key" in p

    def test_provider_api_key_correct(self, mock_env):
        """provider 的 api_key 值正确"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        key_map = {p["name"]: p["api_key"] for p in config["providers"]}
        assert key_map["anthropic"] == "sk-ant-xxx"
        assert key_map["deepseek"] == "sk-ds-xxx"

    def test_includes_llm_section(self, mock_env):
        """配置包含 llm 部分（provider 和 model）"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert config["llm"]["provider"] == "anthropic"
        assert config["llm"]["model"] == "claude-opus-4"

    def test_includes_sync_section(self, mock_env):
        """配置包含 sync 部分（enabled 和 api_key）"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert config["sync"]["enabled"] is True
        assert config["sync"]["api_key"] == "existing-sync-key"

    def test_includes_wechat_token(self, mock_env):
        """配置包含微信 Token"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert config["wechat_token"] == "wx-token-xxx"

    def test_skips_provider_without_api_key(self, mock_env):
        """没有 API Key 的 provider 不包含在配置中"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        # 添加一个没有 Key 的 provider
        extra_provider = {
            "name": "openai",
            "display_name": "OpenAI",
            "default_model": "",
            "default_api_base": "",
            "has_api_key": True,
        }
        mock_env["provider_manager"].get_all_providers.return_value = (
            PROVIDERS + [extra_provider]
        )
        mock_env["provider_manager"].get_api_key.side_effect = lambda name: API_KEYS.get(
            name
        )  # openai 返回 None
        mock_env["provider_manager"]._get_env_key.side_effect = lambda name: ENV_KEYS.get(
            name, "api_key_openai" if name == "openai" else ""
        )

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        names = [p["name"] for p in config["providers"]]
        assert "anthropic" in names
        assert "deepseek" in names
        assert "openai" not in names

    def test_skips_provider_without_env_key(self, mock_env):
        """没有 env_key 的 provider（如 custom）不包含在配置中"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        # 添加一个没有 env_key 的 provider
        no_env_provider = {
            "name": "custom",
            "display_name": "Custom",
            "default_model": "",
            "default_api_base": "",
            "has_api_key": False,
        }
        mock_env["provider_manager"].get_all_providers.return_value = (
            PROVIDERS + [no_env_provider]
        )
        mock_env["provider_manager"]._get_env_key.side_effect = lambda name: ENV_KEYS.get(
            name, ""
        )  # custom 返回 ""

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        names = [p["name"] for p in config["providers"]]
        assert "custom" not in names


class TestCloudConfigGeneratorMonitorType:
    """测试 monitor_type 强制覆盖"""

    def test_monitor_type_forced_to_none(self, mock_env):
        """monitor_type 强制覆盖为 none"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert config["monitor_type"] == "none"

    def test_monitor_type_none_even_if_settings_has_lifeprism(self, mock_env):
        """即使 settings 中 monitor_type 为 lifeprism，输出仍为 none"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        # 让 settings.get("monitor_type") 返回 "lifeprism"
        original_side_effect = mock_env["settings"].get.side_effect

        def get_side_effect(key, default=None):
            if key == "monitor_type":
                return "lifeprism"
            return original_side_effect(key, default)

        mock_env["settings"].get.side_effect = get_side_effect

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert config["monitor_type"] == "none"


class TestCloudConfigGeneratorFilePath:
    """测试文件保存路径"""

    def test_saves_to_cloud_init_yaml(self, mock_env):
        """文件保存到 {lifeprism_data_path}/cloud_init.yaml"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        expected_path = str(mock_env["tmp_path"] / "cloud_init.yaml")
        assert path == expected_path

    def test_file_exists_after_generation(self, mock_env):
        """生成后文件确实存在"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        path, _ = generator.generate_cloud_config()

        assert Path(path).exists()

    def test_returns_path_and_key_is_new_tuple(self, mock_env):
        """返回值为 (path: str, key_is_new: bool) 元组"""
        from lifeprism.config.cloud_config_generator import CloudConfigGenerator

        generator = CloudConfigGenerator()
        result = generator.generate_cloud_config()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], bool)
