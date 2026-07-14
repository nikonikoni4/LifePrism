"""同步 API Key 配置管理。

通过 SettingsManager 的 run_mode 路由读写 sync_api_key：
- 本地模式 (full)：读写 keyring
- 云端模式 (agent_only/web_demo)：读写 storage.yaml

消费方不感知 run_mode，不直接调用 keyring，不直接读 storage.yaml。
"""

from lifeprism.config.settings_manager import settings
from lifeprism.utils import get_logger

logger = get_logger(__name__)

_STORAGE_KEY = "sync_api_key"


def get_sync_api_key() -> str | None:
    """获取同步 API Key。

    通过 SettingsManager.get_storage_key() 路由读取：
    本地模式读 keyring，云端模式读 storage.yaml。

    Returns:
        API Key 字符串，不存在时返回 None。
    """
    return settings.get_storage_key(_STORAGE_KEY)


def set_sync_api_key(key: str) -> None:
    """将同步 API Key 写入持久化存储。

    通过 SettingsManager.set_storage_key() 路由写入：
    本地模式写 keyring，云端模式写 storage.yaml。

    Args:
        key: API Key 值
    """
    settings.set_storage_key(_STORAGE_KEY, key)
