"""
p001_baseline - providers.yaml 基线迁移

旧格式（providers 为 dict、顶层含 default_provider）与新格式
（providers 为 list、顶层含 allowed_providers）完全不兼容，
直接用 DEFAULT_PROVIDER_CONFIG 重置并标记 v1。
用户数据不受影响：API key 存储在 keyring，不在 yaml 中。
"""
VERSION = 1
NAME = "p001_baseline"


def check_if_applied(data: dict) -> bool:
    """
    新格式满足以下全部条件：
    1. config_version 存在且 >= 1
    2. providers 是 list
    3. allowed_providers 存在
    """
    if not (isinstance(data.get("config_version"), int) and data["config_version"] >= 1):
        return False
    if not isinstance(data.get("providers"), list):
        return False
    if "allowed_providers" not in data:
        return False
    return True


def upgrade(data: dict) -> dict:
    """
    v0 → v1：旧格式直接丢弃，返回 DEFAULT_PROVIDER_CONFIG + config_version。
    API key 在 keyring 中，此处无需迁移。
    """
    from lifeprism.config.provider_manager import DEFAULT_PROVIDER_CONFIG
    new_data = DEFAULT_PROVIDER_CONFIG.copy()
    new_data["config_version"] = 1
    return new_data
