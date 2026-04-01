def get_default_config():
    return {
        "poll_time": 1.0,
        "exclude_titles": [],
        "db_path": "dataset/window_activity.db",
        "afk_timeout": 180.0  # 3 minutes, same as ActivityWatch
    }
