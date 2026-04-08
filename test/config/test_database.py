from lifeprism.config.database import TABLE_CONFIGS


def test_window_events_in_table_configs():
    """测试 window_events 表配置是否存在于 TABLE_CONFIGS 中"""
    assert "window_events" in TABLE_CONFIGS, "window_events 表配置缺失"


def test_screen_captures_table_config():
    """测试 screen_captures 表存在，并包含关键列与索引"""
    assert "screen_captures" in TABLE_CONFIGS, "screen_captures 表配置缺失"
    config = TABLE_CONFIGS["screen_captures"]
    required_columns = {"captured_at", "engaged_segment_id"}
    assert required_columns.issubset(set(config["columns"].keys()))

    index_names = {idx.get("name") for idx in config.get("indexes", []) if isinstance(idx, dict)}
    assert "idx_screen_captures_captured_at" in index_names, "缺少 idx_screen_captures_captured_at 索引"
