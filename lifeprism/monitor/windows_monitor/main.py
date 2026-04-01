import sys
import os
from pathlib import Path
import signal
from lifeprism.utils.logger import get_logger
from lifeprism.monitor.windows_monitor.monitor import WindowMonitor
from lifeprism.storage.providers.window_data_provider import LWWindowDataProvider
from lifeprism.config.settings_manager import settings

# 配置日志
logger = get_logger("windows_monitor_main")

def main():
    # settings_manager 在模块级由 main.py 导入时已经初始化并配置好日志
    # 这里直接使用 Provider
    provider = LWWindowDataProvider()
    monitor = WindowMonitor(provider)

    def handle_signal(sig, frame):
        logger.info("收到信号，正在退出...")
        monitor.stop()
        # Provider 不显式持有持久连接，由 DatabaseManager 管理
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        monitor.run()
    except KeyboardInterrupt:
        handle_signal(None, None)
    except Exception as e:
        logger.error(f"主程序异常退出: {e}")
        monitor.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
