"""
配置迁移 s007: 补齐 v6 之后新增但未落盘的字段

背景：config.yaml 迁移体系建立于 2026-03-23。此后有 4 组字段直接写入
SettingsManager.DEFAULTS，但未提供对应迁移脚本，导致老用户的 config.yaml
停留在 v6，缺少这些字段。读取时由 DEFAULTS 兜底，不会报错，但有两个后果：
1. 配置文件不是完整快照，排查问题时看不到实际生效值
2. config_version=6 无法区分「从未写入 agent 段的旧文件」和「本应含 agent 段的文件」

添加字段（按引入时间）:
- timezone: 用户时区（IANA 标识符），默认 'Asia/Shanghai' (2026-07-12)
- sync.remote_url: 云端服务器地址，默认 '' (2026-07-13)
- sync.connection_mode: 连接方式 http|ssh，默认 'http' (2026-07-26)
- sync.ssh_tunnel.*: SSH 隧道非敏感配置，私钥走 keyring (2026-07-26)
- afk_timeout_media: 媒体播放时的 AFK 上限（秒），默认 3600.0 (2026-08-18)
- agent: Agent 策略配置快照 (2026-10-03)

注意：agent 默认值硬编码为字面量，不导入 AgentSettings。迁移脚本是历史快照，
导入模型会让同一脚本在不同时间产生不同结果。字面量与模型的一致性由
test/core/unit/config/test_migration_s007.py 断言。
"""

import copy
from typing import Any

VERSION = 7
NAME = "s007_add_missing_fields"

# 扁平字段默认值，与 SettingsManager.DEFAULTS 保持一致
_ADDED_FIELDS: dict[str, Any] = {
    "timezone": "Asia/Shanghai",
    "sync.remote_url": "",
    "sync.connection_mode": "http",
    "sync.ssh_tunnel.host": "",
    "sync.ssh_tunnel.port": 22,
    "sync.ssh_tunnel.username": "",
    "sync.ssh_tunnel.local_port": 8102,
    "sync.ssh_tunnel.remote_host": "127.0.0.1",
    "sync.ssh_tunnel.remote_port": 8102,
    "afk_timeout_media": 3600.0,
}

# AgentSettings().model_dump() 的冻结副本
_AGENT_DEFAULT: dict[str, Any] = {
    "step_limit": 20,
    "max_retry_count": 3,
    "policies": {
        "llm_retry": {
            "enabled": True,
            "base_delay": 1.0,
            "multiplier": 2.0,
            "cap": 30.0,
        },
        "tool_guard": {
            "allow_paths": ["user", "diary", "agent"],
        },
    },
}


def check_if_applied(data: dict) -> bool:
    """检查迁移是否已应用：所有新增字段（含 agent 段）都已存在"""
    return all(key in data for key in _ADDED_FIELDS) and "agent" in data


def upgrade(data: dict) -> dict:
    """执行迁移：只补缺失字段，已存在的用户值原样保留"""
    for key, value in _ADDED_FIELDS.items():
        if key not in data:
            data[key] = value

    if "agent" not in data:
        data["agent"] = copy.deepcopy(_AGENT_DEFAULT)

    return data
