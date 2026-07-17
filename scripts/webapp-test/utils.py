"""公共工具函数"""

import os
from datetime import datetime

from config import FULL_PAGE, SCREENSHOT_DIR, VIEWPORT
from playwright.sync_api import Page


def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def get_timestamp() -> str:
    """获取时间戳字符串"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def screenshot_page(page: Page, module: str, name: str, full_page: bool = FULL_PAGE):
    """截图页面的统一方法

    Args:
        page: Playwright Page 对象
        module: 模块名（如 home、settings）
        name: 截图名称（如 full、modal_open）
        full_page: 是否全页面截图
    """
    dir_path = os.path.join(SCREENSHOT_DIR, module)
    ensure_dir(dir_path)

    timestamp = get_timestamp()
    filename = f"{module}_{name}_{timestamp}.png"
    filepath = os.path.join(dir_path, filename)

    page.screenshot(path=filepath, full_page=full_page)
    print(f"Screenshot saved: {filepath}")
    return filepath


def wait_for_page(page: Page, timeout: int = None):
    """等待页面加载完成"""
    from config import WAIT_TIMEOUT

    page.wait_for_load_state("networkidle")
    if timeout:
        page.wait_for_timeout(timeout)
