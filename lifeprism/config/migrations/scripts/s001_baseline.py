"""
s001_baseline - settings.yaml 基线迁移

将无版本字段的旧 settings.yaml 标记为 v1。
所有已知字段保留，新增 config_version: 1。
"""
VERSION = 1
NAME = "s001_baseline"


def check_if_applied(data: dict) -> bool:
    """config_version 字段存在且 >= 1 即视为已应用"""
    return isinstance(data.get("config_version"), int) and data["config_version"] >= 1


def upgrade(data: dict) -> dict:
    """
    v0 → v1：仅写入版本号，所有已有字段原样保留。
    data 是 yaml.safe_load 的原始 dict，返回修改后的 dict。
    """
    data["config_version"] = 1
    return data
