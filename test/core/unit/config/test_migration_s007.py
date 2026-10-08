"""测试 s007 配置迁移：补齐 v6 之后新增但未落盘的字段

覆盖三类断言：
1. check_if_applied / upgrade 的基本语义
2. 迁移字面量与 SettingsManager.DEFAULTS、AgentSettings 不漂移
3. 真实迁移链路上 v6 文件被升级到 v7 且幂等
"""

from pathlib import Path

import pytest
import yaml

from lifeprism.config.migrations.config_migrator import run_config_migrations
from lifeprism.config.migrations.scripts import SETTINGS_MIGRATIONS, s007_add_missing_fields

pytestmark = pytest.mark.core


def _v6_config() -> dict:
    """模拟老用户 config.yaml：版本停在 v6，缺少 s007 负责的字段"""
    return {
        "user_name": "老用户",
        "provider": "DeepSeek",
        "model": "deepseek-flash",
        "monitor_type": "none",
        "is_vlm": {},
        "screenshot_monitor": False,
        "screen_analysis_ignore": [],
        "llm_call_logger_enabled": True,
        "auto_diary_summary": True,
        "auto_summary_session": True,
        "auto_update_memory": True,
        "config_version": 6,
    }


def test_check_if_applied_false_when_fields_missing():
    """空配置和部分字段缺失时，迁移未应用"""
    assert s007_add_missing_fields.check_if_applied({}) is False
    partial = dict(s007_add_missing_fields._ADDED_FIELDS)
    partial.pop("timezone")
    assert s007_add_missing_fields.check_if_applied(partial) is False
    # 扁平字段齐全但缺 agent 段，仍视为未应用
    assert (
        s007_add_missing_fields.check_if_applied(dict(s007_add_missing_fields._ADDED_FIELDS))
        is False
    )


def test_check_if_applied_true_when_all_present():
    """扁平字段与 agent 段齐全时，迁移已应用"""
    data = dict(s007_add_missing_fields._ADDED_FIELDS)
    data["agent"] = s007_add_missing_fields._AGENT_DEFAULT
    assert s007_add_missing_fields.check_if_applied(data) is True


def test_upgrade_fills_missing_fields_with_defaults():
    """空配置经迁移后，每个字段的值与 SettingsManager.DEFAULTS 一致"""
    from lifeprism.config.settings_manager import SettingsManager

    result = s007_add_missing_fields.upgrade({})

    for key in s007_add_missing_fields._ADDED_FIELDS:
        assert key in result, f"迁移未写入 {key}"
        assert result[key] == SettingsManager.DEFAULTS[key], f"{key} 与 DEFAULTS 不一致"
    assert result["agent"] == SettingsManager.DEFAULTS["agent"]


def test_upgrade_preserves_existing_values():
    """已存在的用户值原样保留，不被默认值覆盖"""
    data = {
        "timezone": "America/New_York",
        "afk_timeout_media": 600.0,
        "sync.connection_mode": "ssh",
        "sync.ssh_tunnel.host": "10.0.0.1",
        "agent": {"step_limit": 7, "policies": {"tool_guard": {"allow_paths": ["user"]}}},
        "other_field": "value",
    }
    result = s007_add_missing_fields.upgrade(data)

    assert result["timezone"] == "America/New_York"
    assert result["afk_timeout_media"] == 600.0
    assert result["sync.connection_mode"] == "ssh"
    assert result["sync.ssh_tunnel.host"] == "10.0.0.1"
    assert result["agent"]["step_limit"] == 7
    assert result["other_field"] == "value"
    # 用户未设置的字段仍被补齐
    assert result["sync.remote_url"] == ""
    assert result["sync.ssh_tunnel.port"] == 22


def test_upgrade_agent_literal_matches_agent_settings():
    """agent 硬编码字面量必须能被 AgentSettings 校验通过，防止模型演进后漂移"""
    from lifeprism.config.agent_config import AgentSettings

    assert AgentSettings.model_validate(s007_add_missing_fields._AGENT_DEFAULT).model_dump() == (
        s007_add_missing_fields._AGENT_DEFAULT
    )


def test_upgrade_agent_literal_is_isolated_between_calls():
    """两次迁移结果互不影响，避免共享可变字面量"""
    first = s007_add_missing_fields.upgrade({})
    first["agent"]["policies"]["tool_guard"]["allow_paths"].append("polluted")
    first["agent"]["step_limit"] = 999

    second = s007_add_missing_fields.upgrade({})

    assert second["agent"]["step_limit"] == 20
    assert second["agent"]["policies"]["tool_guard"]["allow_paths"] == ["user", "diary", "agent"]
    assert s007_add_missing_fields._AGENT_DEFAULT["step_limit"] == 20


def test_v6_file_upgraded_to_v7_on_disk(tmp_path: Path):
    """真实迁移链路：v6 文件被升级到 v7，字段落盘，且生成备份"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(_v6_config(), allow_unicode=True), encoding="utf-8")

    result = run_config_migrations(config_path, SETTINGS_MIGRATIONS)

    assert result["config_version"] == 7
    on_disk = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert on_disk["config_version"] == 7
    for key in s007_add_missing_fields._ADDED_FIELDS:
        assert key in on_disk, f"{key} 未落盘"
    assert on_disk["agent"]["step_limit"] == 20
    assert on_disk["user_name"] == "老用户"
    assert list(tmp_path.glob("config.backup-v6-*.yaml")), "未生成迁移前备份"


def test_v7_file_is_left_untouched(tmp_path: Path):
    """已到 v7 的文件不再重写、不再生成备份（幂等）"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(_v6_config(), allow_unicode=True), encoding="utf-8")
    run_config_migrations(config_path, SETTINGS_MIGRATIONS)
    after_first = config_path.read_text(encoding="utf-8")
    backups_after_first = len(list(tmp_path.glob("config.backup-*.yaml")))

    result = run_config_migrations(config_path, SETTINGS_MIGRATIONS)

    assert result["config_version"] == 7
    assert config_path.read_text(encoding="utf-8") == after_first
    assert len(list(tmp_path.glob("config.backup-*.yaml"))) == backups_after_first
