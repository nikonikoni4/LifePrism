"""云端配置初始化器

读取 cloud_init.yaml 并写入 config.yaml 和 providers.yaml，
完成云端启动时的配置初始化。

流程:
1. 检测 {data_path}/cloud_init.yaml 是否存在
2. 读取并验证配置完整性
3. 写入 config.yaml（wechat_token、sync_api_key、llm.provider、llm.model、monitor_type: none）
4. 写入 providers.yaml（为对应 provider 注入 api_key 字段）
5. 全部成功后删除 cloud_init.yaml

参考:
- Issue #09: .scratch/linux-deployment-discussion/issues-p2/09-cloud-initializer.md
- PRD: .scratch/linux-deployment-discussion/linux-deployment-prd.md (云端初始化流程)
"""

import os
import sys
from pathlib import Path
from typing import Any

import yaml

from lifeprism.config.exceptions import ConfigError
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class CloudInitializer:
    """云端配置初始化器

    读取 {data_path}/cloud_init.yaml，验证配置完整性后写入
    config.yaml 和 providers.yaml，成功后删除临时文件。

    Attributes:
        _data_path: lifeprism 数据路径
        _cloud_init_path: cloud_init.yaml 文件路径
    """

    def __init__(self, data_path: str | Path) -> None:
        """
        初始化云端配置初始化器

        Args:
            data_path: lifeprism 数据路径，cloud_init.yaml 位于此路径下
        """
        self._data_path = Path(data_path)
        self._cloud_init_path = self._data_path / "cloud_init.yaml"

    def should_initialize(self) -> bool:
        """
        检测 cloud_init.yaml 是否存在

        Returns:
            True 如果 {data_path}/cloud_init.yaml 存在，否则 False
        """
        return self._cloud_init_path.exists()

    # ------------------------------------------------------------------
    # 路径获取（通过 settings_manager / provider_manager 单例，便于测试 mock）
    # ------------------------------------------------------------------

    def _get_config_yaml_path(self) -> Path:
        """获取 config.yaml 路径（来自 settings_manager）"""
        from lifeprism.config.settings_manager import settings

        return settings.get_config_path()

    def _get_providers_yaml_path(self) -> Path:
        """获取 providers.yaml 路径（来自 provider_manager）"""
        from lifeprism.config.provider_manager import provider_manager

        return provider_manager.get_config_path()

    # ------------------------------------------------------------------
    # 初始化主流程
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        执行云端配置初始化

        流程:
        1. 检测 cloud_init.yaml 是否存在，不存在则直接返回
        2. 读取 cloud_init.yaml
        3. 验证配置完整性（失败时抛出 ConfigError，不删除文件）
        4. 写入 config.yaml
        5. 写入 providers.yaml
        6. 全部成功后删除 cloud_init.yaml

        Returns:
            None（成功时）

        Raises:
            ConfigError: 配置验证失败时抛出，cloud_init.yaml 不会被删除
        """
        if not self.should_initialize():
            return

        logger.info(f"检测到 cloud_init.yaml，开始云端配置初始化: {self._cloud_init_path}")

        # 1. 读取 cloud_init.yaml
        cloud_config = self._read_cloud_init()

        # 2. 验证配置完整性（失败时抛出 ConfigError，不删除文件）
        self._validate(cloud_config)

        # 3. 写入 config.yaml
        self._write_config_yaml(cloud_config)

        # 4. 写入 providers.yaml
        self._write_providers_yaml(cloud_config)

        # 5. 全部成功后删除 cloud_init.yaml
        self._cloud_init_path.unlink()
        logger.info("云端配置初始化完成，已删除 cloud_init.yaml")

    def _read_cloud_init(self) -> dict[str, Any]:
        """
        读取 cloud_init.yaml

        Returns:
            解析后的配置字典

        Raises:
            ConfigError: 文件读取或解析失败时抛出
        """
        try:
            with open(self._cloud_init_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ConfigError(
                    message=f"cloud_init.yaml 格式错误: 期望字典，实际 {type(data).__name__}",
                    code="CLOUD_INIT_INVALID_FORMAT",
                )
            return data
        except ConfigError:
            raise
        except (OSError, yaml.YAMLError) as e:
            raise ConfigError(
                message=f"读取 cloud_init.yaml 失败: {e}",
                code="CLOUD_INIT_READ_ERROR",
                cause=e,
            ) from e

    def _validate(self, cloud_config: dict[str, Any]) -> None:
        """
        验证 cloud_init.yaml 配置完整性

        检查必需字段:
        - wechat_token
        - sync.api_key（对应 config.yaml 中的 sync_api_key）
        - llm.provider
        - llm.model
        - providers 列表中对应 provider 的 api_key

        Args:
            cloud_config: cloud_init.yaml 解析后的配置字典

        Raises:
            ConfigError: 验证失败时抛出，details 中包含所有缺失字段
        """
        errors: list[str] = []

        # 检查 wechat_token
        if not cloud_config.get("wechat_token"):
            errors.append("缺少必需字段: wechat_token")

        # 检查 sync.api_key
        sync_config = cloud_config.get("sync") or {}
        if not sync_config.get("api_key"):
            errors.append("缺少必需字段: sync.api_key")

        # 检查 llm.provider 和 llm.model
        llm_config = cloud_config.get("llm") or {}
        provider = llm_config.get("provider")
        if not provider:
            errors.append("缺少必需字段: llm.provider")
        if not llm_config.get("model"):
            errors.append("缺少必需字段: llm.model")

        # 检查 providers 列表中对应 provider 的 api_key
        providers = cloud_config.get("providers") or []
        if not providers:
            errors.append("缺少必需字段: providers（不能为空）")
        elif provider:
            # 将 display_name 转为内部 name（如 "Xiaomi MIMO" → "xiaomi_mimo"）
            # cloud_init.yaml 的 llm.provider 来自本地 settings.get("provider")，
            # 存储的是 display_name；而 providers[].name 是内部 name
            from lifeprism.config.provider_manager import provider_manager

            provider_id = provider_manager.get_provider_id(provider)
            provider_spec = next((p for p in providers if p.get("name") == provider_id), None)
            if provider_spec is None:
                errors.append(f"providers 列表中未找到 llm.provider 对应的 provider: {provider}")
            elif not provider_spec.get("api_key"):
                errors.append(f"providers 列表中 provider '{provider}' 缺少 api_key")

        if errors:
            error_detail = "; ".join(errors)
            logger.error(f"cloud_init.yaml 配置验证失败: {error_detail}")
            raise ConfigError(
                message=f"cloud_init.yaml 配置验证失败: {error_detail}",
                code="CLOUD_INIT_VALIDATION_ERROR",
                details={"errors": errors},
            )

    def _write_config_yaml(self, cloud_config: dict[str, Any]) -> None:
        """
        写入 config.yaml

        写入字段:
        - provider: 来自 cloud_init.llm.provider
        - model: 来自 cloud_init.llm.model
        - wechat_token: 来自 cloud_init.wechat_token
        - sync_api_key: 来自 cloud_init.sync.api_key
        - monitor_type: 强制为 none

        采用合并策略: 读取现有 config.yaml（如存在），更新上述字段后写回。

        Args:
            cloud_config: cloud_init.yaml 解析后的配置字典
        """
        config_path = self._get_config_yaml_path()

        # 读取现有 config.yaml（如存在），否则从空配置开始
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                existing_config = yaml.safe_load(f) or {}
        else:
            existing_config = {}
            config_path.parent.mkdir(parents=True, exist_ok=True)

        # 合并 cloud_init 字段
        llm_config = cloud_config.get("llm") or {}
        sync_config = cloud_config.get("sync") or {}

        existing_config["provider"] = llm_config.get("provider", "")
        existing_config["model"] = llm_config.get("model", "")
        existing_config["wechat_token"] = cloud_config.get("wechat_token", "")
        existing_config["sync_api_key"] = sync_config.get("api_key", "")
        existing_config["monitor_type"] = "none"  # 强制为 none

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                existing_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

        # 云端配置文件权限 600（PRD 安全要求）
        if sys.platform != "win32":
            os.chmod(config_path, 0o600)

        logger.info(
            "已写入 config.yaml: provider=%s, model=%s, wechat_token=***, sync_api_key=***, monitor_type=none",
            existing_config["provider"],
            existing_config["model"],
        )

    def _write_providers_yaml(self, cloud_config: dict[str, Any]) -> None:
        """
        写入 providers.yaml

        为 cloud_init.providers 中列出的 provider 注入 api_key 字段。
        采用合并策略: 读取现有 providers.yaml，更新对应 provider 的 api_key 后写回。

        Args:
            cloud_config: cloud_init.yaml 解析后的配置字典
        """
        providers_path = self._get_providers_yaml_path()

        # 读取现有 providers.yaml（如存在）
        if providers_path.exists():
            with open(providers_path, encoding="utf-8") as f:
                providers_data = yaml.safe_load(f) or {}
        else:
            providers_data = {"allowed_providers": [], "providers": []}
            providers_path.parent.mkdir(parents=True, exist_ok=True)

        existing_providers: list[dict[str, Any]] = providers_data.get("providers", [])

        # 为 cloud_init 中列出的 provider 注入 api_key
        cloud_providers = cloud_config.get("providers") or []
        injected_names: list[str] = []
        for cloud_provider in cloud_providers:
            name = cloud_provider.get("name")
            api_key = cloud_provider.get("api_key")
            if not name:
                continue

            # 查找现有 provider spec
            spec = next((p for p in existing_providers if p.get("name") == name), None)
            if spec is not None:
                spec["api_key"] = api_key
            else:
                # 不存在则追加
                new_spec = dict(cloud_provider)
                existing_providers.append(new_spec)
            injected_names.append(name)

        providers_data["providers"] = existing_providers

        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump(
                providers_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

        # 云端配置文件权限 600（PRD 安全要求）
        if sys.platform != "win32":
            os.chmod(providers_path, 0o600)

        logger.info("已写入 providers.yaml，注入 api_key 的 provider: %s", injected_names)

    # ------------------------------------------------------------------
    # 运行时校验
    # ------------------------------------------------------------------

    def validate_monitor_type(self) -> None:
        """
        强制检查 config.yaml 中 monitor_type 必须为 none

        云端部署（agent_only）不支持 monitor，如果 monitor_type 不是 none，
        自动修正为 none 并记录 WARNING。

        如果 config.yaml 不存在，不做任何操作（首次启动前调用的情况）。
        """
        config_path = self._get_config_yaml_path()

        if not config_path.exists():
            return

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        current = config.get("monitor_type")
        if current == "none":
            return

        # 非 none，自动修正
        logger.warning(
            "monitor_type 当前为 '%s'，云端部署不支持 monitor，强制修正为 'none'",
            current,
        )
        config["monitor_type"] = "none"

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # 云端配置文件权限 600（PRD 安全要求）
        if sys.platform != "win32":
            os.chmod(config_path, 0o600)
