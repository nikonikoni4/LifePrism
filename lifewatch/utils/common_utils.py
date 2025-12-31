from lifewatch.config.settings_manager import settings 

def is_multipurpose_app(app: str) -> bool:
    """
    判断是否为浏览器应用
    
    Args:
        app: 应用名称，如 "msedge.exe"
    
    Returns:
        bool: True表示是浏览器，False表示是普通应用

    """
    # 去除exe
    app = app.lower().strip().split('.exe')[0]
    return app in settings.multi_purpose_app_names

if __name__ == "__main__":
    print(is_multipurpose_app("msedge.exe"))