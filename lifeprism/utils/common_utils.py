import sys


def is_dev_environment() -> bool:
    """
    判断是否为开发环境

    Returns:
        bool: True 表示开发环境，False 表示打包环境
    """
    return not getattr(sys, "frozen", False)


def is_multipurpose_app(app: str) -> bool:
    """
    判断是否为浏览器应用

    Args:
        app: 应用名称，如 "msedge.exe"

    Returns:
        bool: True表示是浏览器，False表示是普通应用

    """
    # 延迟导入避免循环依赖
    from lifeprism.config.settings_manager import settings

    # 去除exe
    app = app.lower().strip().split(".exe")[0]
    return app in settings.multi_purpose_app_names


if __name__ == "__main__":
    print(is_multipurpose_app("msedge.exe"))
