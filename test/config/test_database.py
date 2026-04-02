from lifeprism.config.database import TABLE_CONFIGS

def test_window_events_in_table_configs():
    """测试 window_events 表配置是否存在于 TABLE_CONFIGS 中"""
    assert "window_events" in TABLE_CONFIGS, "window_events 表配置缺失"
