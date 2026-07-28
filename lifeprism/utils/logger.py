import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# lifeprism.log 大小限制与备份数
LIFEPRISM_LOG_MAX_BYTES = 1 * 1024 * 1024  # 1MB
LIFEPRISM_LOG_BACKUP_COUNT = 1  # 仅保留 1 份 lifeprism.old.log

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR

# 单条日志消息最大长度，超出部分截断
MAX_LOG_MESSAGE_LENGTH = 2000


class TruncatingFormatter(logging.Formatter):
    """自定义 Formatter，自动截断超长日志消息，防止图片 base64 等大内容撑爆日志"""

    def __init__(self, fmt=None, datefmt=None, max_length=MAX_LOG_MESSAGE_LENGTH, **kwargs):
        super().__init__(fmt, datefmt, **kwargs)
        self.max_length = max_length

    def format(self, record):
        msg = super().format(record)
        if len(msg) > self.max_length:
            msg = msg[: self.max_length] + f"... [截断, 原始长度 {len(msg)}]"
        return msg


_LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(filename)s func:%(funcName)s line %(lineno)d : %(message)s"
)

# 模块级只配置 StreamHandler（控制台输出）
# FileHandler 由 setup_file_logging() 延迟添加（等 settings_manager 初始化后调用）
# 打包环境（PyInstaller --noconsole）下 sys.stdout 可能为 None 或无 fileno()，需防护
try:
    _stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)  # noqa: SIM115
except Exception:
    # LEGITIMATE: 辅助操作兜底 — 日志配置失败不影响主流程
    _stream = open(os.devnull, mode="w", encoding="utf-8")  # noqa: SIM115

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    handlers=[
        logging.StreamHandler(stream=_stream),
    ],
)
# 替换 basicConfig 默认 Formatter 为 TruncatingFormatter
for _h in logging.getLogger().handlers:
    _h.setFormatter(TruncatingFormatter(_LOG_FORMAT))

_file_handler_added = False
_file_handler: logging.FileHandler | None = None
_uvicorn_file_logging_added = False


class _LifeprismRotatingFileHandler(RotatingFileHandler):
    """lifeprism.log 专用 RotatingFileHandler：1MB 滚动 + 1 份 .old.log 备份。

    stdlib RotatingFileHandler 的备份命名是 `lifeprism.log.1`，无法配置为
    `lifeprism.old.log`。此子类覆盖 doRollover：
    - 关闭当前 stream
    - 用 os.replace 原子覆盖已有的 lifeprism.old.log（旧备份被淘汰）
    - 重新打开 lifeprism.log 写入

    保留 backupCount>0 时父类逻辑未使用（此 handler 固定 backupCount=1），
    覆盖 doRollover 即可实现自定义命名。
    """

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        # 原子改名：原 lifeprism.log → lifeprism.old.log（覆盖已有 .old.log）
        old_log = Path(self.baseFilename).with_suffix(".old.log")
        try:
            # 若目标已存在，先删除（os.replace 在 Windows 上会覆盖，但显式删除更稳妥）
            if os.path.exists(old_log):
                os.remove(old_log)
            os.rename(self.baseFilename, old_log)
        except OSError:
            # LEGITIMATE: 辅助操作兜底 — 改名失败时退化为直接截断重写，不丢日志写入能力
            with open(self.baseFilename, "w", encoding=self.encoding):
                pass
        if not self.delay:
            self.stream = self._open()


def setup_file_logging(log_dir: Path) -> None:
    """
    为 root logger 添加 FileHandler（RotatingFileHandler，1MB 滚动 + 1 份 .old.log 备份）

    由 settings_manager 初始化完成后调用，传入日志目录路径。
    所有通过 get_logger() 创建的 logger 都会自动继承此 FileHandler。

    设计决策：
    - 限制 lifeprism.log 大小为 1MB，超过时将原文件改名为 lifeprism.old.log，
      再新建 lifeprism.log 继续写入。
    - 仅保留 1 份备份（lifeprism.old.log），再次滚动时旧 .old.log 被覆盖。
    - 启动时不再清空已有 lifeprism.log（追加写入），由 1MB 滚动自然淘汰旧日志。
    - 幂等性：重复调用不会重复添加 handler。

    Args:
        log_dir: 日志目录路径（如 lifeprismData/debug_logs）
    """
    global _file_handler_added, _file_handler
    if _file_handler_added:
        return

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "lifeprism.log"
        file_handler = _LifeprismRotatingFileHandler(
            log_file,
            maxBytes=LIFEPRISM_LOG_MAX_BYTES,
            backupCount=LIFEPRISM_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(TruncatingFormatter(_LOG_FORMAT))
        logging.getLogger().addHandler(file_handler)
        _file_handler = file_handler
        _file_handler_added = True
    except Exception as e:
        # LEGITIMATE: 辅助操作兜底 — 日志配置失败不影响主流程
        print(f"[WARNING] 无法创建日志文件: {e}")


class _OverwritingRotatingFileHandler(RotatingFileHandler):
    """backupCount=0 时真正截断文件的 RotatingFileHandler 子类。

    stdlib RotatingFileHandler 在 backupCount=0 时，doRollover 只关闭并重新打开文件
    （append 模式），不截断，导致文件无限增长。此子类覆盖 doRollover，
    在 backupCount=0 时清空文件重新写，满足"覆盖式滚动"语义。

    保持 backupCount>0 时走父类逻辑（保留 .1/.2/... 备份文件），向后兼容。
    """

    def doRollover(self):
        if self.backupCount > 0:
            super().doRollover()
            return
        # backupCount=0：覆盖式滚动 — 清空文件重新写
        if self.stream:
            self.stream.close()
            self.stream = None
        # 以 'w' 模式打开即截断为 0 字节
        with open(self.baseFilename, "w", encoding=self.encoding):
            pass
        if not self.delay:
            self.stream = self._open()


def setup_sync_logging(log_dir: Path) -> None:
    """
    配置 sync 专用日志（RotatingFileHandler，覆盖式 500KB）

    设计决策（PRD 决策 20）：
    - 利用 Python logging 层级传播：sync_client.py 的 __name__ 为 lifeprism.sync.sync_client，
      是 lifeprism.sync 的子 logger。给 lifeprism.sync logger 附加专用 RotatingFileHandler，
      子 logger 日志会通过 propagate=True（默认）传到此处写入 sync.log，
      同时继续向上传播到 root logger 写入 lifeprism.log + 控制台。
    - sync_client.py / loop.py 无需任何改动（零侵入业务代码）。
    - maxBytes=500KB + backupCount=0：超过 500KB 时清空重写，不保留备份，磁盘占用恒 ≤ 500KB。
      注意：stdlib RotatingFileHandler 在 backupCount=0 时不会截断文件，需用
      _OverwritingRotatingFileHandler 子类覆盖 doRollover 实现真正的"覆盖式"。
    - 启动时不清空 sync.log（_OverwritingRotatingFileHandler 默认 mode='a' 追加），
      由 500KB 滚动自然淘汰旧日志。
    - 幂等性：重复调用不会重复添加 handler，避免重启或多次初始化时累积 handler
      导致同一行日志被多次写入 sync.log。

    Args:
        log_dir: 日志目录路径（与 lifeprism.log 同目录，如 lifeprismData/debug_logs）
    """
    sync_logger = logging.getLogger("lifeprism.sync")
    sync_log = log_dir / "sync.log"
    sync_log_resolved = str(sync_log.resolve())

    # 幂等性检查：若已有 RotatingFileHandler 指向同一 sync.log，则不再添加
    for h in sync_logger.handlers:
        if (
            isinstance(h, RotatingFileHandler)
            and str(Path(h.baseFilename).resolve()) == sync_log_resolved
        ):
            return

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = _OverwritingRotatingFileHandler(
            sync_log,
            maxBytes=500 * 1024,
            backupCount=0,
            encoding="utf-8",
        )
        handler.setFormatter(TruncatingFormatter(_LOG_FORMAT))
        sync_logger.addHandler(handler)
        # propagate 保持默认 True：日志自动传播到 root logger
        # → 同时写入 sync.log + lifeprism.log + 控制台
    except Exception as e:
        # LEGITIMATE: 辅助操作兜底 — 日志配置失败不影响主流程
        print(f"[WARNING] 无法创建 sync 专用日志文件: {e}")


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
