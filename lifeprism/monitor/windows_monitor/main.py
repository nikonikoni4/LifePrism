import sys
import signal
from lifeprism.utils.logger import get_logger
from lifeprism.monitor.windows_monitor.runtime import build_monitor_runtime

# 配置日志
logger = get_logger("windows_monitor_main")

def main():
    runtime = build_monitor_runtime()

    def handle_signal(sig, frame):
        logger.info("收到信号，正在退出...")
        runtime.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        runtime.start()
    except KeyboardInterrupt:
        handle_signal(None, None)
    except Exception as e:
        logger.error("主程序异常退出: error=%s", e)
        runtime.stop()
        sys.exit(1)

def start_monitor_process():
    """
    创建并返回一个监控进程实例
    """
    import multiprocessing
    # 使用 multiprocessing.Process 包装 main 函数
    # 注意：在 Windows 上，必须确保 target 函数所在的模块可以被安全导入
    process = multiprocessing.Process(target=main, name="LifePrism-Monitor")
    process.start()
    logger.info("监控进程已启动 (PID: %s)", process.pid)
    return process


if __name__ == "__main__":
    main()
