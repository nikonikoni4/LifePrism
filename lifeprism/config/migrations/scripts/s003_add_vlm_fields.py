"""
s003_add_vlm_fields - 新增 VLM 相关字段

v2 → v3：在 settings.yaml 中追加 is_vlm 和 screenshot_monitor 字段。
- is_vlm: Dict[str, bool]，VLM 能力缓存，key 格式为 "provider_id/model_name"
- screenshot_monitor: bool，截图监控开关，默认为 False
已存在该字段的文件视为已应用，跳过修改。
"""
VERSION = 3
NAME = "s003_add_vlm_fields"


def check_if_applied(data: dict) -> bool:
    """is_vlm 和 screenshot_monitor 字段都存在即视为已应用"""
    return "is_vlm" in data and "screenshot_monitor" in data


def upgrade(data: dict) -> dict:
    """
    v2 → v3：写入 is_vlm 和 screenshot_monitor 默认值，所有已有字段原样保留。
    data 是 yaml.safe_load 的原始 dict，返回修改后的 dict。
    """
    data["is_vlm"] = {}
    data["screenshot_monitor"] = False
    data["config_version"] = 3
    return data
