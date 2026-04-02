"""
s002_add_monitor_type - 新增 monitor_type 字段

v1 → v2：在 settings.yaml 中追加 monitor_type 字段，默认值为 'lifeprism'。
已存在该字段的文件视为已应用，跳过修改。
"""
VERSION = 2
NAME = "s002_add_monitor_type"


def check_if_applied(data: dict) -> bool:
    """monitor_type 字段已存在即视为已应用"""
    return "monitor_type" in data


def upgrade(data: dict) -> dict:
    """
    v1 → v2：写入 monitor_type 默认值，所有已有字段原样保留。
    data 是 yaml.safe_load 的原始 dict，返回修改后的 dict。
    """
    data["monitor_type"] = "lifeprism"
    data["config_version"] = 2
    return data
