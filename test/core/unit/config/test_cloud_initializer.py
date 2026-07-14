"""
云端配置初始化单元测试

验证 CloudInitializer 的云端启动配置初始化逻辑：
1. 检测 cloud_init.yaml 是否存在
2. 读取 cloud_init.yaml 并验证配置完整性（storage 段 + config 段）
3. 写入 config.yaml（仅非 Key 字段：llm、monitor_type、timezone）
4. 写入 storage.yaml（Key 字段：sync_api_key、wechat_token、providers）via SettingsManager
5. 成功后删除 cloud_init.yaml，失败时保留
6. 强制 monitor_type 为 none

cloud_init.yaml 结构（Issue #28）::
    storage:
      sync_api_key: "..."
      wechat_token: "..."
      providers:           # dict: provider_id -> api_key
        anthropic: "sk-ant-..."
    config:
      llm:
        provider: "anthropic"
        model: "claude-opus-4"
      monitor_type: none
      timezone: Asia/Shanghai

参考:
- Issue #28: .scratch/linux-deployment-discussion/issues-p2/28-cloud-init-storage-segment.md
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
    """完整的 cloud_init.yaml 数据（合法配置，新结构：storage 段 + config 段）"""
    return {
        "storage": {
            "sync_api_key": "lifeprism_sync_test_key",
            "wechat_token": "wx_token_test",
            "providers": {
                "anthropic": "sk-ant-test-key",
            },
        },
        "config": {
            "llm": {
                "provider": "anthropic",
                "model": "claude-opus-4",
            },
            "monitor_type": "none",
            "timezone": "Asia/Shanghai",
        },
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
    - storage.yaml 写入 tmp_path/storage.yaml（通过 settings._config_base_path）
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
    # 设置 _config_base_path 为 tmp_path，使 save_storage_yaml 写入临时路径
    monkeypatch.setattr(settings, "_config_base_path", tmp_path)

    return {
        "data_path": tmp_path,
        "config_path": config_path,
        "providers_path": providers_path,
        "storage_path": tmp_path / "storage.yaml",
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
        _write_cloud_init(tmp_path, {"config": {}})
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

    def test_initialize_writes_storage_yaml(self, setup_paths, cloud_init_data):
        """initialize() 成功后 storage.yaml 被创建（via SettingsManager.save_storage_yaml）"""
        data_path = setup_paths["data_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, cloud_init_data)

        initializer = CloudInitializer(data_path)
        initializer.initialize()

        assert storage_path.exists()
        with open(storage_path, encoding="utf-8") as f:
            storage = yaml.safe_load(f)
        assert storage is not None

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


# ==================== Slice 3: 配置验证（storage 段） ====================


class TestInitializeValidation:
    """测试 CloudInitializer.initialize() 的配置验证逻辑（storage 段必需字段）"""

    def test_initialize_raises_config_error_when_missing_wechat_token(
        self, setup_paths, cloud_init_data
    ):
        """缺少 storage.wechat_token 时抛出 ConfigError"""
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": dict(cloud_init_data["config"]),
        }
        data["storage"].pop("wechat_token")
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="wechat_token"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_missing_sync_api_key(
        self, setup_paths, cloud_init_data
    ):
        """缺少 storage.sync_api_key 时抛出 ConfigError"""
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": dict(cloud_init_data["config"]),
        }
        data["storage"].pop("sync_api_key")
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="sync_api_key"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_missing_llm_provider(
        self, setup_paths, cloud_init_data
    ):
        """缺少 config.llm.provider 时抛出 ConfigError"""
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": {"llm": {"model": "claude-opus-4"}, "monitor_type": "none"},
        }
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="llm.provider"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_missing_llm_model(
        self, setup_paths, cloud_init_data
    ):
        """缺少 config.llm.model 时抛出 ConfigError"""
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": {"llm": {"provider": "anthropic"}, "monitor_type": "none"},
        }
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError, match="llm.model"):
            initializer.initialize()

    def test_initialize_raises_config_error_when_storage_section_missing(
        self, setup_paths, cloud_init_data
    ):
        """缺少整个 storage 段时抛出 ConfigError"""
        data = {"config": dict(cloud_init_data["config"])}
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError):
            initializer.initialize()

    def test_initialize_raises_config_error_when_config_section_missing(
        self, setup_paths, cloud_init_data
    ):
        """缺少整个 config 段时抛出 ConfigError"""
        data = {"storage": dict(cloud_init_data["storage"])}
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError):
            initializer.initialize()

    def test_initialize_does_not_delete_cloud_init_on_validation_failure(
        self, setup_paths, cloud_init_data
    ):
        """验证失败时不删除 cloud_init.yaml（方便用户修复后重试）"""
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": dict(cloud_init_data["config"]),
        }
        data["storage"].pop("wechat_token")
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
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": dict(cloud_init_data["config"]),
        }
        data["storage"].pop("wechat_token")
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
        data = {
            "storage": {"sync_api_key": "key"},  # 缺 wechat_token
            "config": {},  # 缺 llm
        }
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        with pytest.raises(ConfigError) as exc_info:
            initializer.initialize()

        assert "errors" in exc_info.value.details
        errors = exc_info.value.details["errors"]
        assert any("wechat_token" in e for e in errors)
        assert any("llm.provider" in e for e in errors)


# ==================== Slice 3b: storage.providers 空字典处理 ====================


class TestStorageProvidersEmptyDict:
    """测试 storage.providers 为空字典时的处理（Issue #28 验收标准）"""

    def test_initialize_ok_when_providers_empty_dict(self, setup_paths, cloud_init_data):
        """storage.providers 为空字典时正常处理（不报错）"""
        data = {
            "storage": {
                "sync_api_key": "lifeprism_sync_test_key",
                "wechat_token": "wx_token_test",
                "providers": {},
            },
            "config": dict(cloud_init_data["config"]),
        }
        data_path = setup_paths["data_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        # 不应抛出异常
        initializer.initialize()

        # storage.yaml 应被写入，providers 为空字典
        with open(storage_path, encoding="utf-8") as f:
            storage = yaml.safe_load(f)
        assert storage["providers"] == {}

    def test_initialize_ok_when_providers_missing(self, setup_paths, cloud_init_data):
        """storage.providers 字段缺失时正常处理（不报错）"""
        data = {
            "storage": {
                "sync_api_key": "lifeprism_sync_test_key",
                "wechat_token": "wx_token_test",
            },
            "config": dict(cloud_init_data["config"]),
        }
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, data)

        initializer = CloudInitializer(data_path)
        # 不应抛出异常
        initializer.initialize()


# ==================== Slice 4: monitor_type 强制校验 ====================


class TestMonitorTypeEnforcement:
    """测试 monitor_type 强制为 none 的逻辑"""

    def test_initialize_forces_monitor_type_none_even_if_cloud_init_has_other(
        self, setup_paths, cloud_init_data
    ):
        """cloud_init.yaml 中 monitor_type 非 none 时，config.yaml 中仍强制为 none"""
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": dict(cloud_init_data["config"]),
        }
        data["config"]["monitor_type"] = "lifeprism"  # 非 none
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
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": {
                "llm": dict(cloud_init_data["config"]["llm"]),
                "timezone": "Asia/Shanghai",
            },
        }
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


# ==================== Slice 5: config.yaml 写入内容正确性 ====================


class TestConfigYamlContent:
    """测试 initialize() 写入 config.yaml 的字段内容（仅非 Key 字段）"""

    def test_config_yaml_contains_provider(self, setup_paths, cloud_init_data):
        """config.yaml 中 provider 来自 cloud_init.config.llm.provider"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["provider"] == "anthropic"

    def test_config_yaml_contains_model(self, setup_paths, cloud_init_data):
        """config.yaml 中 model 来自 cloud_init.config.llm.model"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["model"] == "claude-opus-4"

    def test_config_yaml_does_not_contain_wechat_token(self, setup_paths, cloud_init_data):
        """config.yaml 中不包含 wechat_token（Key 字段写入 storage.yaml）"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "wechat_token" not in config

    def test_config_yaml_does_not_contain_sync_api_key(self, setup_paths, cloud_init_data):
        """config.yaml 中不包含 sync_api_key（Key 字段写入 storage.yaml）"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "sync_api_key" not in config

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
        """config.yaml 中 timezone 来自 cloud_init.config.timezone"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["timezone"] == "Asia/Shanghai"

    def test_config_yaml_timezone_passthrough_custom_value(self, setup_paths, cloud_init_data):
        """cloud_init.yaml 中 timezone 为自定义值时，透传到 config.yaml"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": dict(cloud_init_data["config"]),
        }
        data["config"]["timezone"] = "America/New_York"
        _write_cloud_init(data_path, data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["timezone"] == "America/New_York"

    def test_config_yaml_omits_timezone_when_cloud_init_missing_it(
        self, setup_paths, cloud_init_data
    ):
        """cloud_init.yaml 中无 timezone 字段时，config.yaml 也不写入 timezone"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": {
                "llm": dict(cloud_init_data["config"]["llm"]),
                "monitor_type": "none",
            },
        }
        _write_cloud_init(data_path, data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # timezone 字段不应被写入（由 settings_manager DEFAULTS 兜底）
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
        data = {
            "storage": dict(cloud_init_data["storage"]),
            "config": {
                "llm": dict(cloud_init_data["config"]["llm"]),
                "monitor_type": "none",
            },
        }
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
        assert config["monitor_type"] == "none"
        # 已有字段保留
        assert config["user_name"] == "已有用户"
        assert config["classification_mode"] == "classify_graph"


# ==================== Slice 6: storage.yaml 写入内容正确性 ====================


class TestStorageYamlContent:
    """测试 initialize() 写入 storage.yaml 的字段内容（via SettingsManager.save_storage_yaml）"""

    def test_storage_yaml_contains_sync_api_key(self, setup_paths, cloud_init_data):
        """storage.yaml 中 sync_api_key 来自 cloud_init.storage.sync_api_key"""
        data_path = setup_paths["data_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(storage_path, encoding="utf-8") as f:
            storage = yaml.safe_load(f)
        assert storage["sync_api_key"] == "lifeprism_sync_test_key"

    def test_storage_yaml_contains_wechat_token(self, setup_paths, cloud_init_data):
        """storage.yaml 中 wechat_token 来自 cloud_init.storage.wechat_token"""
        data_path = setup_paths["data_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(storage_path, encoding="utf-8") as f:
            storage = yaml.safe_load(f)
        assert storage["wechat_token"] == "wx_token_test"

    def test_storage_yaml_contains_providers_dict(self, setup_paths, cloud_init_data):
        """storage.yaml 中 providers 是字典（provider_id -> api_key）"""
        data_path = setup_paths["data_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(storage_path, encoding="utf-8") as f:
            storage = yaml.safe_load(f)
        assert isinstance(storage["providers"], dict)
        assert storage["providers"]["anthropic"] == "sk-ant-test-key"

    def test_storage_yaml_written_via_settings_manager(self, setup_paths, cloud_init_data):
        """storage.yaml 通过 SettingsManager.save_storage_yaml() 写入（不直接写文件）"""
        data_path = setup_paths["data_path"]
        _write_cloud_init(data_path, cloud_init_data)

        with patch(
            "lifeprism.config.settings_manager.settings.save_storage_yaml"
        ) as mock_save:
            CloudInitializer(data_path).initialize()

        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert saved_data["sync_api_key"] == "lifeprism_sync_test_key"
        assert saved_data["wechat_token"] == "wx_token_test"
        assert saved_data["providers"]["anthropic"] == "sk-ant-test-key"


# ==================== Slice 7: config 段和 storage 段分离写入 ====================


class TestConfigAndStorageSeparation:
    """测试 cloud_init.yaml 中 config 段和 storage 段同时存在时正确分离写入"""

    def test_config_and_storage_written_to_separate_files(
        self, setup_paths, cloud_init_data
    ):
        """config 段写入 config.yaml，storage 段写入 storage.yaml，互不污染"""
        data_path = setup_paths["data_path"]
        config_path = setup_paths["config_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, cloud_init_data)

        CloudInitializer(data_path).initialize()

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        with open(storage_path, encoding="utf-8") as f:
            storage = yaml.safe_load(f)

        # config.yaml 包含非 Key 字段
        assert config["provider"] == "anthropic"
        assert config["model"] == "claude-opus-4"
        assert config["monitor_type"] == "none"
        # config.yaml 不包含 Key 字段
        assert "sync_api_key" not in config
        assert "wechat_token" not in config
        assert "providers" not in config

        # storage.yaml 包含 Key 字段
        assert storage["sync_api_key"] == "lifeprism_sync_test_key"
        assert storage["wechat_token"] == "wx_token_test"
        assert "anthropic" in storage["providers"]
        # storage.yaml 不包含非 Key 字段
        assert "provider" not in storage
        assert "model" not in storage
        assert "monitor_type" not in storage
        assert "timezone" not in storage


# ==================== Slice 8: 文件权限 600 ====================


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

    def test_storage_yaml_sets_permission_600_on_linux(self, setup_paths, cloud_init_data):
        """非 Windows 平台写入 storage.yaml 后设置文件权限 600（通过 SettingsManager）"""
        data_path = setup_paths["data_path"]
        storage_path = setup_paths["storage_path"]
        _write_cloud_init(data_path, cloud_init_data)

        with (
            patch("lifeprism.config.settings_manager.sys.platform", "linux"),
            patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod,
        ):
            CloudInitializer(data_path).initialize()

        # 验证 os.chmod 被调用且包含对 storage.yaml 设置 0o600
        chmod_calls = [
            (call.args[0], call.args[1]) for call in mock_chmod.call_args_list
        ]
        assert (storage_path, 0o600) in chmod_calls, (
            f"未找到对 storage.yaml 设置权限 0o600 的调用，实际: {chmod_calls}"
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
            patch("lifeprism.config.cloud_initializer.os.chmod") as mock_chmod_ci,
            patch("lifeprism.config.settings_manager.sys.platform", "win32"),
            patch("lifeprism.config.settings_manager.os.chmod") as mock_chmod_sm,
        ):
            CloudInitializer(data_path).initialize()

        # Windows 平台不应调用 os.chmod
        mock_chmod_ci.assert_not_called()
        mock_chmod_sm.assert_not_called()
