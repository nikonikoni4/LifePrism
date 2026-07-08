"""同步 API Key 配置管理。

优先从 keyring 读取（本地 Windows），fallback 到 config.yaml（云端 Linux）。
"""

import keyring

from lifeprism.utils import get_logger

logger = get_logger(__name__)

_KEYRING_SERVICE = "LifePrism"
_KEYRING_USERNAME = "sync_api_key"


def get_sync_api_key() -> str | None:
    """获取同步 API Key。

    优先从 keyring 读取，fallback 到 config.yaml 的 sync_api_key 字段。

    Returns:
        API Key 字符串，都不存在时返回 None。
    """
    # 优先从 keyring 读取
    try:
        api_key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        if api_key:
            return api_key
    except Exception as e:
        logger.debug("从 keyring 读取 sync_api_key 失败: %s", e)
    # Fallback: 从 config.yaml 读取 sync_api_key 字段（云端 Linux 部署）
    from lifeprism.config.settings_manager import get_setting

    config_key = get_setting("sync_api_key")
    if config_key:
        logger.debug("keyring 未找到 sync_api_key，已从 config fallback")
        return str(config_key)
    return None


def set_sync_api_key(key: str) -> None:
    """将同步 API Key 写入 keyring。

    Args:
        key: API Key 值
    """
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, key)
