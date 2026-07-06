"""
p002_add_xiaomi_mimo - 添加小米 Mimo provider（Token Plan 和普通版本）

在 allowed_providers 和 providers 列表中添加两个 xiaomi_mimo 配置：
1. xiaomi_mimo_token_plan - Token Plan 版本
2. xiaomi_mimo - 普通版本
"""

VERSION = 2
NAME = "p002_add_xiaomi_mimo"


def check_if_applied(data: dict) -> bool:
    """
    检查是否已应用：
    1. config_version >= 2
    2. allowed_providers 中包含 xiaomi_mimo_token_plan 和 xiaomi_mimo
    3. providers 列表中存在这两个配置
    """
    if not (isinstance(data.get("config_version"), int) and data["config_version"] >= 2):
        return False

    allowed = data.get("allowed_providers", [])
    if "xiaomi_mimo_token_plan" not in allowed or "xiaomi_mimo" not in allowed:
        return False

    providers = data.get("providers", [])
    has_token_plan = any(p.get("name") == "xiaomi_mimo_token_plan" for p in providers)
    has_normal = any(p.get("name") == "xiaomi_mimo" for p in providers)

    return has_token_plan and has_normal


def upgrade(data: dict) -> dict:
    """
    v1 → v2：添加两个 xiaomi_mimo provider 配置
    """
    # 1. 在 allowed_providers 中添加（在 custom 之后）
    allowed_providers = data.get("allowed_providers", [])

    if "xiaomi_mimo_token_plan" not in allowed_providers:
        if "custom" in allowed_providers:
            idx = allowed_providers.index("custom") + 1
            allowed_providers.insert(idx, "xiaomi_mimo_token_plan")
        else:
            allowed_providers.insert(0, "xiaomi_mimo_token_plan")

    if "xiaomi_mimo" not in allowed_providers:
        # 在 xiaomi_mimo_token_plan 之后插入
        if "xiaomi_mimo_token_plan" in allowed_providers:
            idx = allowed_providers.index("xiaomi_mimo_token_plan") + 1
            allowed_providers.insert(idx, "xiaomi_mimo")
        else:
            allowed_providers.insert(0, "xiaomi_mimo")

    data["allowed_providers"] = allowed_providers

    # 2. 在 providers 列表中添加配置
    providers = data.get("providers", [])

    # Token Plan 版本配置
    if not any(p.get("name") == "xiaomi_mimo_token_plan" for p in providers):
        token_plan_config = {
            "name": "xiaomi_mimo_token_plan",
            "keywords": ["mimo", "xiaomi", "token-plan", "tokenplan"],
            "env_key": "api_key_xiaomi_mimo_token_plan",
            "display_name": "Xiaomi MIMO (Token Plan)",
            "litellm_prefix": "",
            "skip_prefixes": [],
            "env_extras": [],
            "is_gateway": False,
            "is_local": False,
            "detect_by_key_prefix": "",
            "detect_by_base_keyword": "token-plan-cn.xiaomimimo",
            "default_api_base": "https://token-plan-cn.xiaomimimo.com/v1",
            "strip_model_prefix": False,
            "litellm_kwargs": {},
            "model_overrides": [],
            "is_oauth": False,
            "is_direct": True,
            "supports_prompt_caching": False,
            "default_model": "mimo-v2-omni",
        }

        # 在 azure_openai 之后插入
        insert_idx = None
        for i, p in enumerate(providers):
            if p.get("name") == "azure_openai":
                insert_idx = i + 1
                break

        if insert_idx is not None:
            providers.insert(insert_idx, token_plan_config)
        else:
            providers.insert(0, token_plan_config)

    # 普通版本配置
    if not any(p.get("name") == "xiaomi_mimo" for p in providers):
        normal_config = {
            "name": "xiaomi_mimo",
            "keywords": ["mimo", "xiaomi"],
            "env_key": "api_key_xiaomi_mimo",
            "display_name": "Xiaomi MIMO",
            "litellm_prefix": "",
            "skip_prefixes": [],
            "env_extras": [],
            "is_gateway": False,
            "is_local": False,
            "detect_by_key_prefix": "",
            "detect_by_base_keyword": "api.xiaomimimo",
            "default_api_base": "https://api.xiaomimimo.com/v1",
            "strip_model_prefix": False,
            "litellm_kwargs": {},
            "model_overrides": [],
            "is_oauth": False,
            "is_direct": True,
            "supports_prompt_caching": False,
            "default_model": "mimo-v2-omni",
        }

        # 在 xiaomi_mimo_token_plan 之后插入
        insert_idx = None
        for i, p in enumerate(providers):
            if p.get("name") == "xiaomi_mimo_token_plan":
                insert_idx = i + 1
                break

        if insert_idx is not None:
            providers.insert(insert_idx, normal_config)
        else:
            providers.insert(0, normal_config)

    data["providers"] = providers

    # 3. 更新 config_version
    data["config_version"] = 2

    return data
