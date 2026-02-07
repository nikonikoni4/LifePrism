import logging
from pathlib import Path

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR

_LOG_FORMAT = "%(asctime)s %(levelname)s %(filename)s func:%(funcName)s line %(lineno)d : %(message)s"

# 模块级只配置 StreamHandler（控制台输出）
# FileHandler 由 setup_file_logging() 延迟添加（等 settings_manager 初始化后调用）
logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
    ]
)

_file_handler_added = False


def setup_file_logging(log_dir: Path) -> None:
    """
    为 root logger 添加 FileHandler

    由 settings_manager 初始化完成后调用，传入日志目录路径。
    所有通过 get_logger() 创建的 logger 都会自动继承此 FileHandler。

    Args:
        log_dir: 日志目录路径（如 lifeprismData/debug_logs）
    """
    global _file_handler_added
    if _file_handler_added:
        return

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'lifeprism.log'
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logging.getLogger().addHandler(file_handler)
        _file_handler_added = True
    except Exception as e:
        print(f"[WARNING] 无法创建日志文件: {e}")


def get_logger(name: str, level=None) -> logging.Logger:
    """
    Args:
        name: logger 名称
        level: 输出等级
    """
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(level)
    return logger
