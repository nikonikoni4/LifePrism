from lifeprism.monitor.windows_monitor.config import get_default_config

def test_get_default_config():
    config = get_default_config()
    assert config["poll_time"] == 1.0
    assert config["exclude_titles"] == []
    assert config["db_path"] == "window_activity.db"
