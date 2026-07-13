"""
云端配置初始化单元测试

验证 CloudInitializer 的云端启动配置初始化逻辑：
1. 检测 cloud_init.yaml 是否存在
2. 读取 cloud_init.yaml 并验证配置完整性
3. 写入 config.yaml 和 providers.yaml
4. 成功后删除 cloud_init.yaml，失败时保留
5. 强制 monitor_type 为 none

参考:
- Issue #09: .scratch/linux-deployment-discussion/issues-p2/09-cloud-initializer.md
- PRD: .scratch/linux-deployment-discussion/linux-deployment-prd.md (云端初始化流程)
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from lifeprism.config.cloud_initializer import CloudInitializer
from lifeprism.config.exceptions import ConfigError

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def cloud_init_data():
    """完整的 cloud_init.yaml 数据（合法配置）"""
    return {
        "llm": {
            "provider": "anthropic",
            "model": "claude-opus-4",
        },
        "sync": {
            "enabled": True,
            "api_key": "lifeprism_sync_test_key",
        },
        "wechat_token": "wx_token_test",
        "monitor_type": "none",
        "timezone": "Asia/Shanghai",
        "providers": [
            {
                "name": "anthropic",
                "env_key": "api_key_anthropic",
                "api_key": "sk-ant-test-key",
            }
        ],
    }


@pytest.fixture
def default_providers_config():
    """默认 providers.yaml 配置（模拟 provider_manager 创建的默认配置）"""
    return {
        "allowed_providers": ["anthropic", "openai"],
        "providers": [
            {
                "name": "anthropic",
                "env_key": "api_key_anthropic",
                "display_name": "Anthropic",
                "default_model": "claude-opus-4-5",
                "default_api_base": "",
            },
            {
                "name": "openai",
                "env_key": "api_key_openai",
                "display_name": "OpenAI",
                "default_model": "gpt-4o",
                "default_api_base": "",
            },
        ],
    }


@pytest.fixture
def setup_paths(tmp_path, monkeypatch, default_providers_config):
    """设置临时路径并 mock settings_manager / provider_manager 的路径方法。

    - cloud_init.yaml 写入 tmp_path/cloud_init.yaml
    - config.yaml 写入 tmp_path/config/config.yaml
    - providers.yaml 预创建为默认配置，写入 tmp_path/config/providers.yaml
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.config.provider_manager import provider_manager

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    providers_path = config_dir / "providers.yaml"

    # 预创建 providers.yaml（模拟 provider_manager 已初始化）
    with open(providers_path, "w", encoding="utf-8") as f:
        yaml.dump(default_providers_config, f, allow_unicode=True, sort_keys=False)

    # Mock 路径方法
    monkeypatch.setattr(settings, "get_config_path", lambda: config_path)
    monkeypatch.setattr(provider_manager, "get_config_path", lambda: providers_path)

    return {
        "data_path": tmp_path,
        "config_path": config_path,
        "providers_path": providers_path,
    }


def _write_cloud_init(data_path: Path, data: dict):
    """将 cloud_init 数据写入临时路径"""
    cloud_init_file = data_path / "cloud_init.yaml"
    with open(cloud_init_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    return cloud_init_file


# ==================== Slice 1: should_initialize() ====================


class TestShouldInitialize:
    """测试 CloudInitializer.should_initialize() 检测 cloud_init.yaml 是否存在"""

    def test_should_initialize_returns_true_when_cloud_init_exists(self, tmp_path):
        """cloud_init.yaml 存在时返回 True"""
        _write_cloud_init(tmp_path, {"llm": {}})
        initializer = CloudInitializer(tmp_path)
        assert initializer.should_initialize() is True

    def test_should_initialize_returns_false_when_cloud_init_not_exists(self, tmp_path):
        """cloud_init.yaml 不存在时返回 False"""
        initializer = CloudInitializer(tmp_path)
        assert initializer.should_initialize() is False


# ==================== Slice 2: initialize() 基本流程 ====================


class TestInitializeBasicFlow:
    """测试 CloudInitializer.initialize() 基本初始化流程"""

    def test_initialize_writes_config_yaml(self, setup_paths, cloud_init_data):
        """initialize() 成功后 config.yaml 被创建并包含基础字段"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        initializer = CloudInitializer(data_path)
        initializer.initialize()

        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_initialize_writes_providers_yaml(self, setup_paths, cloud_init_data):
        """initialize() 成功后 providers.yaml 包含注入的 api_key"""
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, cloud_init_data)

        initializer = CloudInitializer(data_path)
        initializer.initialize()

        assert providers_path.exists()
        with open(providers_path, encoding="utf-8") as f:
            providers_data = yaml.safe_load(f)
        # 对应 provider 的 api_key 应被注入
        anthropic_spec = next(
            p for p in providers_data["providers"] if p["name"] == "anthropic"
        )
        assert anthropic_spec.get("api_key") == "sk-ant-test-key"

    def test_initialize_deletes_cloud_init_on_success(self, setup_paths, cloud_init_data):
        """initialize() 全部成功后删除 cloud_init.yaml"""
        data_path = setup_paths["data_path"]
        cloud_init_file = _write_cloud_init(data_path, cloud_init_data)

        initializer = CloudInitializer(data_path)
        initializer.initialize()

        assert not cloud_init_file.exists()

    def test_initialize_returns_none_on_success(self, setup_paths, cloud_init_data):
        """initialize() 成功时返回 None"""
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, cloud_init_data)

        initializer = CloudInitializer(data_path)
        result = initializer.initialize()

        assert result is None

    def test_initialize_noop_when_cloud_init_absent(self, setup_paths):
        """cloud_init.yaml 不存在时 initialize() 不做任何操作"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        initializer = CloudInitializer(data_path)
        result = initializer.initialize()

        assert result is None
        # config.yaml 不应被创建
        assert not config_path.exists()


# ==================== Slice 3: 配置验证 ====================


class TestInitializeValidation:
    """测试 CloudInitializer.initialize() 的配置验证逻辑"""

    def test_initialize_raises_config_error_when_missing_wechat_token(
        self, setup_paths, cloud_init_data
    ):
        """缺少 wechat_token 时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data.pop("wechat_token")
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="wechat_token"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_missing_sync_api_key(
        self, setup_paths, cloud_init_data
    ):
        """缺少 sync.api_key 时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data["sync"] = {"enabled": True}
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="sync.api_key"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_missing_llm_provider(
        self, setup_paths, cloud_init_data
    ):
        """缺少 llm.provider 时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data["llm"] = {"model": "claude-opus-4"}
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="llm.provider"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_missing_llm_model(
        self, setup_paths, cloud_init_data
    ):
        """缺少 llm.model 时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data["llm"] = {"provider": "anthropic"}
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="llm.model"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_provider_api_key_missing(
        self, setup_paths, cloud_init_data
    ):
        """providers 列表中对应 provider 缺少 api_key 时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data["providers"] = [{"name": "anthropic", "env_key": "api_key_anthropic"}]
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="api_key"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_provider_not_in_providers_list(
        self, setup_paths, cloud_init_data
    ):
        """llm.provider 在 providers 列表中不存在时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data["llm"] = {"provider": "openai", "model": "gpt-4o"}
        data["providers"] = [
            {"name": "anthropic", "env_key": "api_key_anthropic", "api_key": "sk-ant-..."}
        ]
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="openai"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_providers_empty(
        self, setup_paths, cloud_init_data
    ):
        """providers 列表为空时抛出 ConfigError"""
        data = dict(cloud_init_data)
        data["providers"] = []
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="providers"):
            initializer.initialize()

    def test_initialize_does_not_delete_cloud_init_on_validation_failure(
        self, setup_paths, cloud_init_data
    ):
        """验证失败时不删除 cloud_init.yaml（方便用户修复后重试）"""
        data = dict(cloud_init_data)
        data.pop("wechat_token")
        data_path = setup_paths["data_path"]
        cloud_init_file = _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError):
            initializer.initialize()

        # cloud_init.yaml 应仍然存在
        assert cloud_init_file.exists()

    def test_initialize_does_not_write_config_on_validation_failure(
        self, setup_paths, cloud_init_data
    ):
        """验证失败时不写入 config.yaml"""
        data = dict(cloud_init_data)
        data.pop("wechat_token")
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError):
            initializer.initialize()

        # config.yaml 不应被创建（验证在写入之前）
        assert not config_path.exists()

    def test_initialize_config_error_contains_details(
        self, setup_paths, cloud_init_data
    ):
        """ConfigError 的 details 中包含缺失字段列表"""
        data = dict(cloud_init_data)
        data.pop("wechat_token")
        data.pop("llm")
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError) as exc_info:
            initializer.initialize()

        assert "errors" in exc_info.value.details
        errors = exc_info.value.details["errors"]
        assert any("wechat_token" in e for e in errors)
        assert any("llm.provider" in e for e in errors)


# ==================== Slice 4: monitor_type 强制校验 ====================


class TestMonitorTypeEnforcement:
    """测试 monitor_type 强制为 none 的逻辑"""

    def test_initialize_forces_monitor_type_none_even_if_cloud_init_has_other(
        self, setup_paths, cloud_init_data
    ):
        """cloud_init.yaml 中 monitor_type 非 none 时，config.yaml 中仍强制为 none"""
        data = dict(cloud_init_data)
        data["monitor_type"] = "lifeprism"  # 非 none
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        initializer.initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"

    def test_initialize_forces_monitor_type_none_when_cloud_init_omits_it(
        self, setup_paths, cloud_init_data
    ):
        """cloud_init.yaml 中无 monitor_type 字段时，config.yaml 中仍为 none"""
        data = dict(cloud_init_data)
        data.pop("monitor_type")
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        initializer.initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"


class TestValidateMonitorType:
    """测试 CloudInitializer.validate_monitor_type() 运行时校验"""

    def test_validate_monitor_type_corrects_non_none(self, setup_paths):
        """config.yaml 中 monitor_type 非 none 时，自动修正为 none"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        # 预写入一个 monitor_type 非 none 的 config.yaml
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"monitor_type": "lifeprism", "provider": "anthropic"}, f)

        initializer = CloudInitializer(data_path)
        initializer.validate_monitor_type()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"

    def test_validate_monitor_type_keeps_none(self, setup_paths):
        """config.yaml 中 monitor_type 已为 none 时，不做修改"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"monitor_type": "none", "provider": "anthropic"}, f)

        initializer = CloudInitializer(data_path)
        initializer.validate_monitor_type()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"

    def test_validate_monitor_type_sets_none_when_missing(self, setup_paths):
        """config.yaml 中无 monitor_type 字段时，补充为 none"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"provider": "anthropic"}, f)

        initializer = CloudInitializer(data_path)
        initializer.validate_monitor_type()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"

    def test_validate_monitor_type_noop_when_config_absent(self, setup_paths):
        """config.yaml 不存在时不报错（云端首次启动前）"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        initializer = CloudInitializer(data_path)
        # 不应抛出异常
        initializer.validate_monitor_type()

        assert not config_path.exists()

    def test_validate_monitor_type_preserves_other_fields(self, setup_paths):
        """修正 monitor_type 时保留 config.yaml 中的其他字段"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        config_path.parent.mkdir(parents=True, exist_ok=True)
        original_config = {
            "monitor_type": "lifeprism",
            "provider": "anthropic",
            "model": "claude-opus-4",
            "user_name": "测试用户",
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(original_config, f, allow_unicode=True, sort_keys=False)

        initializer = CloudInitializer(data_path)
        initializer.validate_monitor_type()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"
        assert config["provider"] == "anthropic"
        assert config["model"] == "claude-opus-4"
        assert config["user_name"] == "测试用户"


# ==================== Slice 5: 写入内容正确性 ====================


class TestConfigYamlContent:
    """测试 initialize() 写入 config.yaml 的字段内容"""

    def test_config_yaml_contains_provider(self, setup_paths, cloud_init_data):
        """config.yaml 中 provider 来自 cloud_init.llm.provider"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["provider"] == "anthropic"

    def test_config_yaml_contains_model(self, setup_paths, cloud_init_data):
        """config.yaml 中 model 来自 cloud_init.llm.model"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["model"] == "claude-opus-4"

    def test_config_yaml_contains_wechat_token(self, setup_paths, cloud_init_data):
        """config.yaml 中 wechat_token 来自 cloud_init.wechat_token"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["wechat_token"] == "wx_token_test"

    def test_config_yaml_contains_sync_api_key(self, setup_paths, cloud_init_data):
        """config.yaml 中 sync_api_key 来自 cloud_init.sync.api_key"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["sync_api_key"] == "lifeprism_sync_test_key"

    def test_config_yaml_contains_monitor_type_none(self, setup_paths, cloud_init_data):
        """config.yaml 中 monitor_type 强制为 none"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["monitor_type"] == "none"

    def test_config_yaml_contains_timezone_from_cloud_init(self, setup_paths, cloud_init_data):
        """config.yaml 中 timezone 来自 cloud_init.timezone"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["timezone"] == "Asia/Shanghai"

    def test_config_yaml_timezone_passthrough_custom_value(self, setup_paths, cloud_init_data):
        """cloud_init.yaml 中 timezone 为自定义值（如 America/New_York）时，透传到 config.yaml"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        data = dict(cloud_init_data)
        data["timezone"] = "America/New_York"
        _write_cloud_init(data_path, data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["timezone"] == "America/New_York"

    def test_config_yaml_omits_timezone_when_cloud_init_missing_it(
        self, setup_paths, cloud_init_data
    ):
        """cloud_init.yaml 中无 timezone 字段时，config.yaml 也不写入 timezone（让 DEFAULTS 兜底）"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        data = dict(cloud_init_data)
        data.pop("timezone")
        _write_cloud_init(data_path, data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # timezone 字段不应被写入（由 settings_manager DEFAULTS 兜底为 Asia/Shanghai）
        assert "timezone" not in config

    def test_config_yaml_preserves_existing_timezone_when_cloud_init_missing_it(
        self, setup_paths, cloud_init_data
    ):
        """cloud_init.yaml 无 timezone，但 config.yaml 已有 timezone 时，保留现有值"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        # 预写入已有配置（含 timezone）
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"timezone": "Europe/London", "user_name": "已有用户"},
                f,
                allow_unicode=True,
                sort_keys=False,
            )

        # cloud_init.yaml 不含 timezone
        data = dict(cloud_init_data)
        data.pop("timezone")
        _write_cloud_init(data_path, data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # 保留已有 timezone
        assert config["timezone"] == "Europe/London"

    def test_config_yaml_preserves_existing_fields(self, setup_paths, cloud_init_data):
        """写入 config.yaml 时保留已有字段（合并策略）"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        # 预写入已有配置
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"user_name": "已有用户", "classification_mode": "classify_graph"},
                f,
                allow_unicode=True,
                sort_keys=False,
            )

        _write_cloud_init(data_path, cloud_init_data)
        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # 新字段
        assert config["provider"] == "anthropic"
        assert config["wechat_token"] == "wx_token_test"
        assert config["monitor_type"] == "none"
        # 已有字段保留
        assert config["user_name"] == "已有用户"
        assert config["classification_mode"] == "classify_graph"


class TestProvidersYamlContent:
    """测试 initialize() 写入 providers.yaml 的字段内容"""

    def test_providers_yaml_injects_api_key_to_matching_provider(
        self, setup_paths, cloud_init_data
    ):
        """providers.yaml 中匹配的 provider 被注入 api_key"""
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(providers_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        anthropic = next(p for p in data["providers"] if p["name"] == "anthropic")
        assert anthropic["api_key"] == "sk-ant-test-key"

    def test_providers_yaml_preserves_other_providers(
        self, setup_paths, cloud_init_data
    ):
        """providers.yaml 中未被 cloud_init 涉及的 provider 保持不变"""
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(providers_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # openai 应仍然存在且无 api_key
        openai = next(p for p in data["providers"] if p["name"] == "openai")
        assert "api_key" not in openai or openai.get("api_key") is None

    def test_providers_yaml_preserves_provider_metadata(
        self, setup_paths, cloud_init_data
    ):
        """注入 api_key 时保留 provider 的其他元数据（display_name 等）"""
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(providers_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        anthropic = next(p for p in data["providers"] if p["name"] == "anthropic")
        assert anthropic["display_name"] == "Anthropic"
        assert anthropic["default_model"] == "claude-opus-4-5"
        assert anthropic["env_key"] == "api_key_anthropic"

    def test_providers_yaml_preserves_allowed_providers(
        self, setup_paths, cloud_init_data
    ):
        """providers.yaml 中 allowed_providers 列表保持不变"""
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(providers_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["allowed_providers"] == ["anthropic", "openai"]

    def test_providers_yaml_injects_multiple_providers(self, setup_paths, cloud_init_data):
        """cloud_init.yaml 包含多个 provider 时，全部注入 api_key"""
        data = dict(cloud_init_data)
        data["providers"] = [
            {"name": "anthropic", "env_key": "api_key_anthropic", "api_key": "sk-ant-1"},
            {"name": "openai", "env_key": "api_key_openai", "api_key": "sk-openai-1"},
        ]
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, data)

        CloudInitializer(data_path).initialize()

        with open(providers_path, encoding="utf-8") as f:
            pdata = yaml.safe_load(f)

        anthropic = next(p for p in pdata["providers"] if p["name"] == "anthropic")
        openai = next(p for p in pdata["providers"] if p["name"] == "openai")
        assert anthropic["api_key"] == "sk-ant-1"
        assert openai["api_key"] == "sk-openai-1"


# ==================== Slice 6: 文件权限 600 ====================


class TestFilePermissions:
    """测试云端配置文件权限设置为 600（PRD 安全要求）"""

    def test_config_yaml_sets_permission_600_on_linux(self, setup_paths, cloud_init_data):
        """非 Windows 平台写入 config.yaml 后设置文件权限 600"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        with (
            patch("lifeprism.config.cloud_initializer.sys.platform", "linux"),
            patch("lifeprism.config.cloud_initializer.os.chmod") as mock_chmod,
        ):
            CloudInitializer(data_path).initialize()

        # 验证 os.chmod 被调用且包含对 config.yaml 设置 0o600
        chmod_calls = [
            (call.args[0], call.args[1]) for call in mock_chmod.call_args_list
        ]
        assert (config_path, 0o600) in chmod_calls, (
            f"未找到对 config.yaml 设置权限 0o600 的调用，实际: {chmod_calls}"
        )

    def test_providers_yaml_sets_permission_600_on_linux(self, setup_paths, cloud_init_data):
        """非 Windows 平台写入 providers.yaml 后设置文件权限 600"""
        data_path = setup_paths["data_path"]
        providers_path = setup_paths["providers_path"]
        _write_cloud_init(data_path, cloud_init_data)

        with (
            patch("lifeprism.config.cloud_initializer.sys.platform", "linux"),
            patch("lifeprism.config.cloud_initializer.os.chmod") as mock_chmod,
        ):
            CloudInitializer(data_path).initialize()

        # 验证 os.chmod 被调用且包含对 providers.yaml 设置 0o600
        chmod_calls = [
            (call.args[0], call.args[1]) for call in mock_chmod.call_args_list
        ]
        assert (providers_path, 0o600) in chmod_calls, (
            f"未找到对 providers.yaml 设置权限 0o600 的调用，实际: {chmod_calls}"
        )

    def test_validate_monitor_type_sets_permission_600_on_linux(self, setup_paths):
        """非 Windows 平台 validate_monitor_type 修正后设置文件权限 600"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]

        # 预写入一个 monitor_type 非 none 的 config.yaml
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"monitor_type": "lifeprism", "provider": "anthropic"}, f)

        with (
            patch("lifeprism.config.cloud_initializer.sys.platform", "linux"),
            patch("lifeprism.config.cloud_initializer.os.chmod") as mock_chmod,
        ):
            CloudInitializer(data_path).validate_monitor_type()

        # 验证 os.chmod 被调用且包含对 config.yaml 设置 0o600
        chmod_calls = [
            (call.args[0], call.args[1]) for call in mock_chmod.call_args_list
        ]
        assert (config_path, 0o600) in chmod_calls, (
            f"未找到对 config.yaml 设置权限 0o600 的调用，实际: {chmod_calls}"
        )

    def test_config_yaml_does_not_set_permission_on_windows(self, setup_paths, cloud_init_data):
        """Windows 平台不设置文件权限（sys.platform == win32）"""
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, cloud_init_data)

        with (
            patch("lifeprism.config.cloud_initializer.sys.platform", "win32"),
            patch("lifeprism.config.cloud_initializer.os.chmod") as mock_chmod,
        ):
            CloudInitializer(data_path).initialize()

        # Windows 平台不应调用 os.chmod
        mock_chmod.assert_not_called()
