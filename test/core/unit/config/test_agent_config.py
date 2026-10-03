"""Agent settings validation and portable guard paths."""

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.core


def test_defaults_and_partial_config(tmp_path):
    from lifeprism.config.agent_config import AgentSettings

    config = AgentSettings.model_validate({"policies": {"llm_retry": {"enabled": False}}})
    assert config.step_limit == 20 and config.max_retry_count == 3
    assert not config.policies.llm_retry.enabled
    assert not config.policies.tool_guard.enabled
    assert config.policies.tool_guard.resolve_paths(tmp_path) == [
        str((tmp_path / name).resolve()) for name in ["user", "diary", "agent"]
    ]


@pytest.mark.parametrize(
    "data",
    [
        {"step_limit": 0},
        {"max_retry_count": -1},
        {"step_limit": True},
        {"policies": {"llm_retry": {"enabled": "false"}}},
        {"policies": {"llm_retry": {"base_delay": -1}}},
        {"policies": {"tool_guard": {"allow_paths": ["../outside"]}}},
        {"policies": {"unknown": {}}},
    ],
)
def test_invalid_config_fails(data):
    from lifeprism.config.agent_config import AgentSettings

    with pytest.raises(ValidationError):
        AgentSettings.model_validate(data)


def test_settings_roundtrip_without_real_config(tmp_path):
    import yaml

    from lifeprism.config.settings_manager import SettingsManager

    manager = object.__new__(SettingsManager)
    manager._config = {}
    manager._config_path = tmp_path / "config.yaml"
    manager.set(
        "agent",
        {"step_limit": 7, "policies": {"tool_guard": {"enabled": True, "allow_paths": ["user"]}}},
    )
    assert manager.agent.step_limit == 7
    saved = yaml.safe_load(manager._config_path.read_text(encoding="utf-8"))
    manager._config = saved
    assert manager.agent.policies.tool_guard.enabled
    assert manager.agent.max_retry_count == 3
    before = manager._config_path.read_bytes()
    with pytest.raises(ValidationError):
        manager.update({"agent": {"step_limit": -1}})
    assert manager._config_path.read_bytes() == before


def test_foreign_absolute_paths_rejected(tmp_path):
    import os

    from lifeprism.config.agent_config import ToolGuardSettings

    foreign = "/srv/data/user" if os.name == "nt" else "D:/data/user"
    with pytest.raises(ValueError):
        ToolGuardSettings(allow_paths=[foreign]).resolve_paths(tmp_path)


def test_empty_guard_list_remains_empty(tmp_path):
    from lifeprism.config.agent_config import ToolGuardSettings

    assert ToolGuardSettings(allow_paths=[]).resolve_paths(tmp_path) == []
