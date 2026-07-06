"""
配置迁移 s004: 添加监控配置项

添加字段:
- active_screenshot_frequency_level: 截图频率等级 (默认2)
- screenshot_retention_days: 截图保留天数 (默认7)
"""

VERSION = 4
NAME = "s004_add_monitor_config"


def check_if_applied(data: dict) -> bool:
    """检查迁移是否已应用"""
    return "active_screenshot_frequency_level" in data and "screenshot_retention_days" in data


def upgrade(data: dict) -> dict:
    """执行迁移"""
    if "active_screenshot_frequency_level" not in data:
        data["active_screenshot_frequency_level"] = 2

    if "screenshot_retention_days" not in data:
        data["screenshot_retention_days"] = 7

    return data
