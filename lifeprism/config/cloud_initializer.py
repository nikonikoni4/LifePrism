"""云端配置初始化器

读取 cloud_init.yaml 并写入 config.yaml 和 storage.yaml，
完成云端启动时的配置初始化。

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
        api_base: "https://api.anthropic.com/v1"  # 可选，CustomProvider 路由时必需
      monitor_type: none
      timezone: Asia/Shanghai

流程:
1. 检测 {data_path}/cloud_init.yaml 是否存在
2. 读取并验证配置完整性（storage 段 + config 段）
3. 写入 config.yaml（仅非 Key 字段：llm、monitor_type、timezone）
4. 写入 storage.yaml（Key 字段：sync_api_key、wechat_token、providers）via SettingsManager
5. 全部成功后删除 cloud_init.yaml

参考:
- Issue #28: .scratch/linux-deployment-discussion/issues-p2/28-cloud-init-storage-segment.md
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
    config.yaml（非 Key 字段）和 storage.yaml（Key 字段，via SettingsManager），
    成功后删除临时文件。

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
    # 路径获取（通过 settings_manager 单例，便于测试 mock）
    # ------------------------------------------------------------------

    def _get_config_yaml_path(self) -> Path:
        """获取 config.yaml 路径（来自 settings_manager）"""
        from lifeprism.config.settings_manager import settings

        return settings.get_config_path()

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
        4. 写入 config.yaml（仅非 Key 字段）
        5. 写入 storage.yaml（Key 字段，via SettingsManager.save_storage_yaml）
        6. 全部成功后删除 cloud_init.yaml

        Returns:
            None（成功时）

        Raises:
            ConfigError: 配置验证失败时抛出，cloud_init.yaml 不会被删除
        """
        if not self.should_initialize():
            return

        logger.info("检测到 cloud_init.yaml，开始云端配置初始化: %s", self._cloud_init_path)

        # 1. 读取 cloud_init.yaml
        cloud_config = self._read_cloud_init()

        # 2. 验证配置完整性（失败时抛出 ConfigError，不删除文件）
        self._validate(cloud_config)

        # 3. 写入 config.yaml（仅非 Key 字段）
        self._write_config_yaml(cloud_config)

        # 4. 写入 storage.yaml（Key 字段，via SettingsManager）
        self._write_storage_yaml(cloud_config)

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
        验证 cloud_init.yaml 配置完整性（storage 段 + config 段）

        检查必需字段:
        - storage.sync_api_key（必需）
        - storage.wechat_token（必需）
        - config.llm.provider（必需）
        - config.llm.model（必需）

        可选字段:
        - storage.providers：空字典或缺失均不报错

        Args:
            cloud_config: cloud_init.yaml 解析后的配置字典

        Raises:
            ConfigError: 验证失败时抛出，details 中包含所有缺失字段
        """
        errors: list[str] = []

        # 检查 storage 段
        storage_config = cloud_config.get("storage") or {}
        if not isinstance(storage_config, dict):
            errors.append(f"storage 段格式错误: 期望字典，实际 {type(storage_config).__name__}")
            storage_config = {}

        # 检查 storage.sync_api_key（必需）
        if not storage_config.get("sync_api_key"):
            errors.append("缺少必需字段: storage.sync_api_key")

        # 检查 storage.wechat_token（必需）
        if not storage_config.get("wechat_token"):
            errors.append("缺少必需字段: storage.wechat_token")

        # 检查 config 段
        config_section = cloud_config.get("config") or {}
        if not isinstance(config_section, dict):
            errors.append(f"config 段格式错误: 期望字典，实际 {type(config_section).__name__}")
            config_section = {}

        # 检查 config.llm.provider 和 config.llm.model
        llm_config = config_section.get("llm") or {}
        if not llm_config.get("provider"):
            errors.append("缺少必需字段: config.llm.provider")
        if not llm_config.get("model"):
            errors.append("缺少必需字段: config.llm.model")

        if errors:
            error_detail = "; ".join(errors)
            logger.error("cloud_init.yaml 配置验证失败: %s", error_detail)
            raise ConfigError(
                message=f"cloud_init.yaml 配置验证失败: {error_detail}",
                code="CLOUD_INIT_VALIDATION_ERROR",
                details={"errors": errors},
            )

    def _write_config_yaml(self, cloud_config: dict[str, Any]) -> None:
        """
        写入 config.yaml（仅非 Key 字段）

        写入字段:
        - provider: 来自 cloud_init.config.llm.provider
        - model: 来自 cloud_init.config.llm.model
        - api_base: 来自 cloud_init.config.llm.api_base（可选，CustomProvider 路由时必需）
        - monitor_type: 强制为 none
        - timezone: 来自 cloud_init.config.timezone（如存在）

        不写入 Key 字段（sync_api_key、wechat_token、providers），
        这些字段由 _write_storage_yaml 写入 storage.yaml。

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

        # 合并 cloud_init.config 字段（仅非 Key 字段）
        config_section = cloud_config.get("config") or {}
        llm_config = config_section.get("llm") or {}

        existing_config["provider"] = llm_config.get("provider", "")
        existing_config["model"] = llm_config.get("model", "")
        # api_base 为可选字段，仅在 cloud_init.yaml 显式提供时才写入 config.yaml，
        # 否则保留 config.yaml 已有值或让 CustomProvider 使用默认值
        api_base_from_cloud = llm_config.get("api_base")
        if api_base_from_cloud:
            existing_config["api_base"] = api_base_from_cloud
        existing_config["monitor_type"] = "none"  # 强制为 none
        # 透传 timezone（cloud_init.yaml 中已有此字段，由 cloud_config_generator 写入）
        # 仅在 cloud_init.yaml 显式提供 timezone 时才写入 config.yaml，
        # 否则保留 config.yaml 已有值或让 settings_manager DEFAULTS 兜底
        timezone_from_cloud = config_section.get("timezone")
        if timezone_from_cloud:
            existing_config["timezone"] = timezone_from_cloud

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                existing_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

        # 云端配置文件权限 600（PRD 安全要求）
        if sys.platform != "win32":
            os.chmod(config_path, 0o600)

        logger.info(
            "已写入 config.yaml: provider=%s, model=%s, api_base=%s, monitor_type=none, timezone=%s",
            existing_config["provider"],
            existing_config["model"],
            existing_config.get("api_base", "(未设置)"),
            existing_config.get("timezone", "(未设置)"),
        )

    def _write_storage_yaml(self, cloud_config: dict[str, Any]) -> None:
        """
        写入 storage.yaml（Key 字段，via SettingsManager.save_storage_yaml）

        写入字段（来自 cloud_init.storage）:
        - sync_api_key
        - wechat_token
        - providers: dict[provider_id, api_key]

        通过 SettingsManager 的 public 接口 save_storage_yaml() 写入，
        保证权限 600 和文件结构一致。SettingsManager 管理所有 storage.yaml
        的生命周期，外部模块不直接写文件。

        Args:
            cloud_config: cloud_init.yaml 解析后的配置字典
        """
        from lifeprism.config.settings_manager import settings

        storage_config = cloud_config.get("storage") or {}

        # 构建 storage.yaml 数据（确保 providers 为 dict）
        storage_data: dict[str, Any] = {
            "sync_api_key": storage_config.get("sync_api_key", ""),
            "wechat_token": storage_config.get("wechat_token", ""),
            "providers": storage_config.get("providers") or {},
        }

        # 通过 SettingsManager public 接口写入（保证权限 600）
        settings.save_storage_yaml(storage_data)

        logger.info(
            "已写入 storage.yaml: sync_api_key=***, wechat_token=***, providers_count=%d",
            len(storage_data["providers"]),
        )

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
