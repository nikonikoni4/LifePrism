import os
import sys
from pathlib import Path


def get_custom_data_path() -> Path:
    """
    获取 customData 目录路径

    优先级:
    1. 环境变量 CUSTOM_DATA_PATH（由 Electron 传入）
    2. 打包环境：基于 sys.executable 推算
    3. 开发环境：frontend/customData

    Returns:
        Path: customData 目录的路径
    """
    # 1. 优先使用环境变量
    custom_data_env = os.environ.get('CUSTOM_DATA_PATH')
    if custom_data_env:
        return Path(custom_data_env)

    # 2. 打包环境：通过 exe 路径推算
    if getattr(sys, 'frozen', False):
        # sys.executable = .../LifePrism/app/resources/backend/lifeprism-backend.exe
        backend_dir = Path(sys.executable).parent   # .../app/resources/backend
        app_dir = backend_dir.parent.parent          # .../app
        root_dir = app_dir.parent                    # .../LifePrism
        return root_dir / 'customData'

    # 3. 开发环境
    return Path("frontend/customData")


def is_dev_environment() -> bool:
    """
    判断是否为开发环境

    Returns:
        bool: True 表示开发环境，False 表示打包环境
    """
    return not getattr(sys, 'frozen', False)


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
    app = app.lower().strip().split('.exe')[0]
    return app in settings.multi_purpose_app_names

if __name__ == "__main__":
    print(is_multipurpose_app("msedge.exe"))