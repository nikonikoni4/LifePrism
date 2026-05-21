"""
配置迁移 s006: 添加 LLM 调用记录器开关

添加字段:
- llm_call_logger_enabled: LLM 调用记录器开关 (默认 False)
"""

VERSION = 6
NAME = "s006_add_llm_call_logger_enabled"


def check_if_applied(data: dict) -> bool:
    """检查迁移是否已应用"""
    return 'llm_call_logger_enabled' in data


def upgrade(data: dict) -> dict:
    """执行迁移"""
    if 'llm_call_logger_enabled' not in data:
        data['llm_call_logger_enabled'] = False

    return data
