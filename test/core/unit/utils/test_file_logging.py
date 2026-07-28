"""lifeprism.log 文件日志单元测试

覆盖需求: 限制 lifeprism.log 大小为 1MB，超过时将原文件改名为 lifeprism.old.log，
然后新建 lifeprism.log 继续写入（备份仅保留 1 份，旧的 .old.log 被覆盖）。

测试策略:
- 通过 public seam `setup_file_logging(log_dir)` 验证行为
- 不直接访问 logger.py 内部私有变量
- 每个测试通过 fixture 清理 root logger 的 handlers 与全局幂等 flag，确保隔离
- 使用 tmp_path 避免污染真实数据目录
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from lifeprism.utils import logger as logger_module
from lifeprism.utils.logger import TruncatingFormatter, setup_file_logging


# ---------------------------------------------------------------------------
# Fixtures: 确保 root logger 全局状态在测试间隔离
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_root_file_logging():
    """清理 root logger 的 FileHandler 并重置 logger 模块全局幂等 flag。

    setup_file_logging 内部使用模块级 `_file_handler_added` / `_file_handler`
    实现幂等性，若不在测试间重置，前一个测试添加的 handler 会污染后续测试，
    且后续测试调用 setup_file_logging 会直接 return 不再添加 handler。
    """
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_file_handler_added = logger_module._file_handler_added
    original_file_handler = logger_module._file_handler

    # 移除 root logger 上所有 FileHandler / RotatingFileHandler
    file_handlers_to_remove = [
        h for h in root_logger.handlers
        if isinstance(h, (logging.FileHandler, RotatingFileHandler))
    ]
    for h in file_handlers_to_remove:
        try:
            h.close()
        except Exception:
            pass
        root_logger.removeHandler(h)

    # 重置全局幂等 flag
    logger_module._file_handler_added = False
    logger_module._file_handler = None

    try:
        yield root_logger
    finally:
        # 关闭并清理测试期间添加的 handlers（释放 Windows 文件锁）
        for h in list(root_logger.handlers):
            if isinstance(h, (logging.FileHandler, RotatingFileHandler)):
                try:
                    h.close()
                except Exception:
                    pass
                root_logger.removeHandler(h)
        # 恢复原始状态
        for h in original_handlers:
            if h not in root_logger.handlers:
                root_logger.addHandler(h)
        logger_module._file_handler_added = original_file_handler_added
        logger_module._file_handler = original_file_handler


# ---------------------------------------------------------------------------
# 1. setup_file_logging: RotatingFileHandler 配置
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_file_logging_callable(clean_root_file_logging, tmp_path):
    """setup_file_logging 函数存在且可调用，调用后不抛异常。"""
    setup_file_logging(tmp_path)


@pytest.mark.core
def test_setup_file_logging_adds_rotating_file_handler(clean_root_file_logging, tmp_path):
    """调用后 root logger 新增一个 RotatingFileHandler。"""
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) >= 1, "root logger 应至少有一个 RotatingFileHandler"


@pytest.mark.core
def test_setup_file_logging_maxbytes_1mb(clean_root_file_logging, tmp_path):
    """RotatingFileHandler 的 maxBytes == 1 * 1024 * 1024（1MB）。"""
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) >= 1
    assert rotating_handlers[0].maxBytes == 1 * 1024 * 1024


@pytest.mark.core
def test_setup_file_logging_backupcount_one(clean_root_file_logging, tmp_path):
    """RotatingFileHandler 的 backupCount == 1（保留 1 份 .old.log 备份）。"""
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) >= 1
    assert rotating_handlers[0].backupCount == 1


@pytest.mark.core
def test_setup_file_logging_file_path(clean_root_file_logging, tmp_path):
    """RotatingFileHandler 的文件路径为 {log_dir}/lifeprism.log。"""
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) >= 1

    expected_path = str(tmp_path / "lifeprism.log")
    actual_path = rotating_handlers[0].baseFilename
    # 标准化路径比较（Windows 大小写/分隔符差异）
    assert Path(actual_path).resolve() == Path(expected_path).resolve()


@pytest.mark.core
def test_setup_file_logging_encoding_utf8(clean_root_file_logging, tmp_path):
    """RotatingFileHandler 的 encoding == 'utf-8'。"""
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) >= 1
    assert rotating_handlers[0].encoding == "utf-8"


@pytest.mark.core
def test_setup_file_logging_uses_truncating_formatter(clean_root_file_logging, tmp_path):
    """handler 的 formatter 是 TruncatingFormatter 实例（复用现有 formatter）。"""
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) >= 1
    assert isinstance(rotating_handlers[0].formatter, TruncatingFormatter)


@pytest.mark.core
def test_setup_file_logging_creates_log_dir(clean_root_file_logging, tmp_path):
    """log_dir 不存在时，setup_file_logging 应自动创建目录。"""
    log_dir = tmp_path / "nested" / "debug_logs"
    assert not log_dir.exists()

    setup_file_logging(log_dir)

    assert log_dir.exists(), "setup_file_logging 应创建 log_dir"
    assert (log_dir / "lifeprism.log").exists(), "lifeprism.log 文件应被创建"


# ---------------------------------------------------------------------------
# 2. 启动行为：不清空已有 lifeprism.log
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_file_logging_appends_not_clears(clean_root_file_logging, tmp_path):
    """调用 setup_file_logging 时不清空已有 lifeprism.log 内容（追加写入）。

    场景：应用启动时保留上次启动后的日志，由 1MB 滚动自然淘汰。
    原行为（每次启动清空）已废弃，改为追加 + 1MB 轮转。
    """
    log_file = tmp_path / "lifeprism.log"
    pre_existing_content = "previous session log line\n"
    log_file.write_text(pre_existing_content, encoding="utf-8")

    setup_file_logging(tmp_path)

    content = log_file.read_text(encoding="utf-8")
    assert pre_existing_content in content, (
        f"setup_file_logging 不应清空已有 lifeprism.log，实际内容: {content!r}"
    )


# ---------------------------------------------------------------------------
# 3. 幂等性验证
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_file_logging_idempotent(clean_root_file_logging, tmp_path):
    """多次调用 setup_file_logging 不重复添加 handler（幂等性）。"""
    setup_file_logging(tmp_path)
    setup_file_logging(tmp_path)
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 1, (
        f"重复调用应保持幂等，期望 1 个 RotatingFileHandler，实际 {len(rotating_handlers)} 个"
    )


# ---------------------------------------------------------------------------
# 4. 1MB 轮转验证：超过 1MB 时生成 lifeprism.old.log
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_file_logging_rollover_creates_old_log(clean_root_file_logging, tmp_path):
    """lifeprism.log 超过 1MB 时被改名到 lifeprism.old.log，新日志写入新的 lifeprism.log。

    doRollover 的核心契约：
    1. 原 lifeprism.log 改名为 lifeprism.old.log
    2. 新建 lifeprism.log 继续写入
    3. 原 lifeprism.log 中的内容完整保留到 lifeprism.old.log
    """
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 1
    handler = rotating_handlers[0]

    log_file = tmp_path / "lifeprism.log"
    old_log = tmp_path / "lifeprism.old.log"

    # 第一阶段：写入一条标记日志，便于后续验证 .old.log 内容来源
    marker_before_rollover = "BEFORE-ROLLOVER-MARKER"
    root_logger.warning(marker_before_rollover)
    handler.flush()

    assert log_file.exists()
    assert marker_before_rollover in log_file.read_text(encoding="utf-8")
    assert not old_log.exists(), "轮转前不应存在 lifeprism.old.log"

    # 第二阶段：写入超过 1MB 的数据，触发 doRollover
    # 每条日志约 200 字节 payload，写 6000 条 → 约 1.2MB（超过 1MB）
    big_payload = "X" * 150
    for i in range(6000):
        root_logger.warning("rollover-test %d payload=%s", i, big_payload)
        # 每 500 条 flush 一次，触发 shouldRollover 检查
        if i % 500 == 0:
            handler.flush()
    handler.flush()

    # 验证：lifeprism.old.log 已生成
    assert old_log.exists(), "轮转后应生成 lifeprism.old.log"
    # 验证：lifeprism.old.log 中包含轮转前的标记日志
    old_content = old_log.read_text(encoding="utf-8")
    assert marker_before_rollover in old_content, (
        "lifeprism.old.log 应包含轮转前 lifeprism.log 的内容"
    )
    # 验证：lifeprism.log 仍然存在，且大小不超过 maxBytes 太多
    assert log_file.exists(), "轮转后 lifeprism.log 应继续存在"
    file_size = log_file.stat().st_size
    assert file_size <= 1 * 1024 * 1024 + 1024, (
        f"轮转后 lifeprism.log 大小应受 1MB 限制，实际: {file_size} bytes"
    )


# ---------------------------------------------------------------------------
# 5. 多次轮转：旧的 lifeprism.old.log 被新内容覆盖
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_file_logging_rollover_overwrites_old_log(clean_root_file_logging, tmp_path):
    """多次超过 1MB 时，旧的 lifeprism.old.log 被新内容覆盖（备份仅保留 1 份）。

    场景：
    1. 写入标记 A，触发第一次轮转 → lifeprism.old.log 包含 A
    2. 写入标记 B，触发第二次轮转 → lifeprism.old.log 应包含 B（覆盖旧的 A）
    """
    setup_file_logging(tmp_path)

    root_logger = logging.getLogger()
    rotating_handlers = [
        h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 1
    handler = rotating_handlers[0]

    log_file = tmp_path / "lifeprism.log"
    old_log = tmp_path / "lifeprism.old.log"

    def write_until_rollover(marker: str):
        """写入数据直到触发一次 doRollover（lifeprism.log 大小归零或重写）。"""
        # 记录轮转前的 old_log 修改时间，用于判断是否被覆盖
        old_mtime_before = old_log.stat().st_mtime if old_log.exists() else None

        root_logger.warning(marker)
        # 写入超过 1MB 数据触发轮转
        big_payload = "Y" * 200
        for i in range(6000):
            root_logger.warning("multi-rollover %s %d payload=%s", marker, i, big_payload)
            if i % 200 == 0:
                handler.flush()
        handler.flush()
        return old_mtime_before

    # 第一次轮转：标记 A 进入 lifeprism.old.log
    marker_a = "FIRST-MARKER-A"
    write_until_rollover(marker_a)
    assert old_log.exists(), "第一次轮转后应生成 lifeprism.old.log"
    old_content_after_first = old_log.read_text(encoding="utf-8")
    assert marker_a in old_content_after_first, (
        "第一次轮转后 lifeprism.old.log 应包含 marker A"
    )

    # 第二次轮转：标记 B 应覆盖旧的 .old.log（包含 A 的内容应消失）
    marker_b = "SECOND-MARKER-B"
    write_until_rollover(marker_b)

    assert old_log.exists(), "第二次轮转后 lifeprism.old.log 应仍存在"
    old_content_after_second = old_log.read_text(encoding="utf-8")
    assert marker_b in old_content_after_second, (
        "第二次轮转后 lifeprism.old.log 应包含 marker B（新内容）"
    )
    assert marker_a not in old_content_after_second, (
        "第二次轮转后旧的 marker A 应被覆盖（备份仅保留 1 份）"
    )
