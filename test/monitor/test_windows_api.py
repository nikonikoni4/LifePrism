import time
import sys
import os

# 添加项目根目录到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from lifeprism.monitor.windows_monitor.windows_api import (
    get_active_window_handle,
    get_window_title,
    get_app_name,
    get_app_path
)

def test_monitor():
    print("开始监控活动窗口... (按 Ctrl+C 停止)")
    print("-" * 50)
    last_hwnd = None

    try:
        while True:
            hwnd = get_active_window_handle()
            if hwnd != last_hwnd:
                title = get_window_title(hwnd)
                app_name = get_app_name(hwnd)
                app_path = get_app_path(hwnd)

                print(f"HWND: {hwnd}")
                print(f"Title: {title}")
                print(f"App Name: {app_name}")
                print(f"App Path: {app_path}")
                print("-" * 50)

                last_hwnd = hwnd

            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止监控")

if __name__ == "__main__":
    test_monitor()
