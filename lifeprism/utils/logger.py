import logging
import os
import sys
from pathlib import Path

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR

_LOG_FORMAT = "%(asctime)s %(levelname)s %(filename)s func:%(funcName)s line %(lineno)d : %(message)s"

# 模块级只配置 StreamHandler（控制台输出）
# FileHandler 由 setup_file_logging() 延迟添加（等 settings_manager 初始化后调用）
# 打包环境（PyInstaller --noconsole）下 sys.stdout 可能为 None 或无 fileno()，需防护
try:
    _stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)
except Exception:
    _stream = open(os.devnull, mode='w', encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    handlers=[
        logging.StreamHandler(stream=_stream),
    ]
)

_file_handler_added = False
_file_handler: logging.FileHandler | None = None
_uvicorn_file_logging_added = False


def setup_file_logging(log_dir: Path) -> None:
    """
    为 root logger 添加 FileHandler

    由 settings_manager 初始化完成后调用，传入日志目录路径。
    所有通过 get_logger() 创建的 logger 都会自动继承此 FileHandler。

    Args:
        log_dir: 日志目录路径（如 lifeprismData/debug_logs）
    """
    global _file_handler_added, _file_handler
    if _file_handler_added:
        return

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'lifeprism.log'
        # 每次启动时清空旧日志
        if log_file.exists():
            log_file.write_text('', encoding='utf-8')
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logging.getLogger().addHandler(file_handler)
        _file_handler = file_handler
        _file_handler_added = True
    except Exception as e:
        print(f"[WARNING] 无法创建日志文件: {e}")


def enable_uvicorn_file_logging() -> None:
    """
    在服务器运行阶段将 uvicorn/fastapi 日志写入 lifeprism.log。

    注意：uvicorn.run 会应用自己的日志配置，可能覆盖初始化阶段的 logger 绑定，
    因此在 lifespan 启动时再执行一次绑定，确保 access log 落盘。
    """
    global _uvicorn_file_logging_added
    if _uvicorn_file_logging_added or _file_handler is None:
        return

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.addHandler(_file_handler)

    _uvicorn_file_logging_added = True


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
