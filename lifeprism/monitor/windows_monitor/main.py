import sys
import os
from pathlib import Path
import signal
from lifeprism.utils.logger import get_logger, setup_file_logging
from .config import get_default_config
from .storage import Storage
from .monitor import WindowMonitor

# 配置日志
logger = get_logger("windows_monitor_main")

def main():
    config = get_default_config()

    # 使用项目标准的数据路径
    # 在独立测试时，可能需要手动设置
    try:
        from lifeprism.config.settings_manager import settings
        data_path = Path(settings.lifeprism_data_path)
        db_path = str(data_path / "window_activity.db")
        log_dir = data_path / "debug_logs"
        setup_file_logging(log_dir)
        logger.info(f"使用 settings_manager 路径: {db_path}")
    except (ImportError, AttributeError, Exception) as e:
        # Fallback 到默认路径
        db_path = config.get("db_path", "window_activity.db")
        logger.warning(f"无法从 settings_manager 获取路径，使用默认: {db_path} (错误: {e})")

    storage = Storage(db_path)
    monitor = WindowMonitor(config, storage)

    def handle_signal(sig, frame):
        logger.info("收到信号，正在退出...")
        monitor.stop()
        storage.close()
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
        storage.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
