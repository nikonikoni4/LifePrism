"""
p003_add_custom_env_key - 为 custom provider 补充 env_key

历史问题：DEFAULT_PROVIDER_CONFIG 中 custom provider 的 env_key 为空字符串，
导致 SettingsManager._set_api_key_to_keyring_by_provider() 因 username=None 跳过写入，
用户在前端输入的 api_key 实际未保存到 keyring，但 setting_service 未检查返回值
仍打印"已安全保存"日志（误导）。读取时 provider_manager.get_api_key("custom")
也因 env_key 为空直接返回 None，最终 create_llm_client 用 "no-key" 调用 API
报 "API key format is incorrect"。

修复：将 custom provider 的 env_key 从 "" 改为 "api_key_custom"，使其与其他
provider 一致走 keyring 保存/读取流程。
"""

VERSION = 3
NAME = "p003_add_custom_env_key"


def check_if_applied(data: dict) -> bool:
    """
    检查是否已应用：
    1. config_version >= 3
    2. providers 中 custom 的 env_key == "api_key_custom"
    """
    if not (isinstance(data.get("config_version"), int) and data["config_version"] >= 3):
        return False

    providers = data.get("providers", [])
    for p in providers:
        if p.get("name") == "custom":
            return p.get("env_key") == "api_key_custom"
    return False


def upgrade(data: dict) -> dict:
    """
    v2 → v3：为 custom provider 补充 env_key="api_key_custom"
    """
    providers = data.get("providers", [])
    for p in providers:
        if p.get("name") == "custom":
            p["env_key"] = "api_key_custom"
            break

    data["providers"] = providers
    data["config_version"] = 3
    return data
