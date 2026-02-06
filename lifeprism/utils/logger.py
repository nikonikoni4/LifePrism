import logging
import os
import sys
from pathlib import Path

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR


def _get_log_file_path() -> Path:
    """
    获取日志文件路径

    - 打包模式：customData/debug_logs/lifeprism.log
    - 开发模式：项目根目录/lifeprism.log
    """
    # 判断是否为打包环境
    if getattr(sys, 'frozen', False):
        # 打包环境：使用 customData/debug_logs
        custom_data_env = os.environ.get('CUSTOM_DATA_PATH')
        if custom_data_env:
            custom_data_path = Path(custom_data_env)
        else:
            # 后备：通过 exe 路径推算
            # sys.executable = .../LifePrism/app/resources/backend/lifeprism-backend.exe
            backend_dir = Path(sys.executable).parent   # .../app/resources/backend
            app_dir = backend_dir.parent.parent          # .../app
            root_dir = app_dir.parent                    # .../LifePrism
            custom_data_path = root_dir / 'customData'

        log_dir = custom_data_path / 'debug_logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / 'lifeprism.log'
    else:
        # 开发环境：项目根目录
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / 'lifeprism.log'


_LOG_FILE = _get_log_file_path()
_file_mode = 'a'

# logging全局唯一配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(filename)s func:%(funcName)s line %(lineno)d : %(message)s",
    handlers=[
        logging.StreamHandler(),  # 控制台输出
        logging.FileHandler(_LOG_FILE, mode=_file_mode, encoding='utf-8'),  # 文件输出，追加写入
    ]
)


def get_logger(name: str, level=None) -> logging.Logger:
    """
    args:
        name: 输入logger名称
        level: 输出等级

    """

    logger = logging.getLogger(name)
    if level:
        logger.setLevel(level)
    return logger
