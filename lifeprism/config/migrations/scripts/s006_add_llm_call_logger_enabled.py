"""
配置迁移 s006: 添加定时任务相关配置

添加字段:
- llm_call_logger_enabled: LLM 调用记录器开关 (默认 False)
- auto_diary_summary: 每日自动总结日记 (默认 False)
- auto_summary_session: 自动总结会话 (默认 False)
- auto_update_memory: 自动更新记忆 (默认 False)
"""

VERSION = 6
NAME = "s006_add_llm_call_logger_enabled"


def check_if_applied(data: dict) -> bool:
    """检查迁移是否已应用"""
    return (
        "llm_call_logger_enabled" in data
        and "auto_diary_summary" in data
        and "auto_summary_session" in data
        and "auto_update_memory" in data
    )


def upgrade(data: dict) -> dict:
    """执行迁移"""
    if "llm_call_logger_enabled" not in data:
        data["llm_call_logger_enabled"] = False

    if "auto_diary_summary" not in data:
        data["auto_diary_summary"] = False

    if "auto_summary_session" not in data:
        data["auto_summary_session"] = False

    if "auto_update_memory" not in data:
        data["auto_update_memory"] = False

    return data
