"""Sync 专用日志（sync.log）单元测试

覆盖 Issue 6: 新增 Sync 专用日志文件（sync.log，500KB 覆盖式滚动）

测试策略:
- 通过 public seam `setup_sync_logging(log_dir)` 验证行为
- 不直接访问 logger.py 内部私有变量
- 每个测试通过 fixture 清理 `lifeprism.sync` logger 的 handlers，确保隔离
- 使用 tmp_path 避免污染真实数据目录
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from lifeprism.utils.logger import TruncatingFormatter, setup_sync_logging


# ---------------------------------------------------------------------------
# Fixtures: 确保 logger 全局状态在测试间隔离
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_sync_logger():
    """清理 lifeprism.sync logger 的 handlers，确保测试隔离。

    lifeprism.sync logger 是全局对象，若不在测试间清理，
    前一个测试添加的 handler 会污染后续测试。
    """
    sync_logger = logging.getLogger("lifeprism.sync")
    original_handlers = list(sync_logger.handlers)
    original_propagate = sync_logger.propagate

    # 清空 handlers
    sync_logger.handlers.clear()

    try:
        yield sync_logger
    finally:
        # 关闭并清理测试期间添加的 handlers（释放 Windows 文件锁）
        for h in list(sync_logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            sync_logger.removeHandler(h)
        # 恢复原始状态
        for h in original_handlers:
            sync_logger.addHandler(h)
        sync_logger.propagate = original_propagate


# ---------------------------------------------------------------------------
# 1. setup_sync_logging 函数: 基础行为
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_sync_logging_callable(clean_sync_logger, tmp_path):
    """setup_sync_logging 函数存在且可调用，调用后不抛异常。"""
    # 调用即验证可调用性（使用 tmp_path 避免污染当前目录）
    setup_sync_logging(tmp_path)


@pytest.mark.core
def test_setup_sync_logging_adds_rotating_file_handler(clean_sync_logger, tmp_path):
    """调用后 lifeprism.sync logger 新增一个 RotatingFileHandler。"""
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) >= 1, "lifeprism.sync logger 应至少有一个 RotatingFileHandler"


@pytest.mark.core
def test_setup_sync_logging_maxbytes_500kb(clean_sync_logger, tmp_path):
    """RotatingFileHandler 的 maxBytes == 500 * 1024（500KB）。"""
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) >= 1
    assert rotating_handlers[0].maxBytes == 500 * 1024


@pytest.mark.core
def test_setup_sync_logging_backupcount_zero(clean_sync_logger, tmp_path):
    """RotatingFileHandler 的 backupCount == 0（覆盖式，不保留备份文件）。"""
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) >= 1
    assert rotating_handlers[0].backupCount == 0


@pytest.mark.core
def test_setup_sync_logging_file_path(clean_sync_logger, tmp_path):
    """RotatingFileHandler 的文件路径为 {log_dir}/sync.log。"""
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) >= 1

    expected_path = str(tmp_path / "sync.log")
    actual_path = rotating_handlers[0].baseFilename
    # 标准化路径比较（Windows 大小写/分隔符差异）
    assert Path(actual_path).resolve() == Path(expected_path).resolve()


@pytest.mark.core
def test_setup_sync_logging_encoding_utf8(clean_sync_logger, tmp_path):
    """RotatingFileHandler 的 encoding == 'utf-8'（与现有 FileHandler 一致）。"""
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) >= 1
    assert rotating_handlers[0].encoding == "utf-8"


@pytest.mark.core
def test_setup_sync_logging_uses_truncating_formatter(clean_sync_logger, tmp_path):
    """handler 的 formatter 是 TruncatingFormatter 实例（复用现有 formatter）。"""
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) >= 1
    assert isinstance(rotating_handlers[0].formatter, TruncatingFormatter)


@pytest.mark.core
def test_setup_sync_logging_creates_log_dir(tmp_path):
    """log_dir 不存在时，setup_sync_logging 应自动创建目录。"""
    # tmp_path 本身存在，但子目录不存在
    log_dir = tmp_path / "nested" / "debug_logs"
    assert not log_dir.exists()

    setup_sync_logging(log_dir)

    assert log_dir.exists(), "setup_sync_logging 应创建 log_dir"
    assert (log_dir / "sync.log").exists(), "sync.log 文件应被创建"


# ---------------------------------------------------------------------------
# 2. 幂等性验证
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_sync_logging_idempotent(clean_sync_logger, tmp_path):
    """多次调用 setup_sync_logging 不重复添加 handler（幂等性）。

    场景：应用重启或多次初始化时，不应累积多个 sync.log handler，
    否则同一行日志会被多次写入 sync.log。
    """
    setup_sync_logging(tmp_path)
    setup_sync_logging(tmp_path)
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) == 1, (
        f"重复调用应保持幂等，期望 1 个 RotatingFileHandler，实际 {len(rotating_handlers)} 个"
    )


# ---------------------------------------------------------------------------
# 3. propagate 验证（层级传播的基础）
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_sync_logger_propagate_true_default(clean_sync_logger):
    """lifeprism.sync logger 的 propagate 默认为 True。

    propagate=True 是日志同时写入 sync.log + lifeprism.log + 控制台的关键。
    setup_sync_logging 不应修改此属性。
    """
    # 此时 clean_sync_logger 已经清空 handlers，但 propagate 应保持默认 True
    assert logging.getLogger("lifeprism.sync").propagate is True


@pytest.mark.core
def test_sync_child_logger_propagate_true_default(clean_sync_logger):
    """lifeprism.sync.sync_client logger 的 propagate 默认为 True。

    sync_client.py 通过 __name__ 获取 logger，是 lifeprism.sync 的子 logger，
    其日志会自动传播到 lifeprism.sync logger（被 sync.log 捕获）。
    """
    child_logger = logging.getLogger("lifeprism.sync.sync_client")
    assert child_logger.propagate is True


@pytest.mark.core
def test_setup_sync_logging_does_not_disable_propagate(clean_sync_logger, tmp_path):
    """调用 setup_sync_logging 后，lifeprism.sync logger 仍保持 propagate=True。"""
    setup_sync_logging(tmp_path)
    assert logging.getLogger("lifeprism.sync").propagate is True


# ---------------------------------------------------------------------------
# 4. 层级传播验证：日志同时写入 sync.log + lifeprism.log
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_sync_log_writes_to_sync_log_file(clean_sync_logger, tmp_path):
    """在 lifeprism.sync.sync_client logger 输出日志，sync.log 应包含该日志。"""
    setup_sync_logging(tmp_path)

    child_logger = logging.getLogger("lifeprism.sync.sync_client")
    test_message = "test sync log message - sync.log capture"
    child_logger.warning(test_message)

    # 强制 flush 确保写入磁盘
    for h in logging.getLogger("lifeprism.sync").handlers:
        h.flush()

    sync_log_path = tmp_path / "sync.log"
    assert sync_log_path.exists(), "sync.log 应被创建"
    content = sync_log_path.read_text(encoding="utf-8")
    assert test_message in content, f"sync.log 应包含日志消息，实际内容: {content!r}"


@pytest.mark.core
def test_sync_log_propagates_to_lifeprism_log(clean_sync_logger, tmp_path):
    """在 lifeprism.sync.sync_client logger 输出日志，lifeprism.log 也应包含该日志。

    验证 propagate 链：sync_client → lifeprism.sync → lifeprism → root
    root logger 上的 FileHandler 会写入 lifeprism.log。
    """
    # 1. 设置 sync 专用日志
    setup_sync_logging(tmp_path)

    # 2. 手动为 root logger 添加 FileHandler（指向 tmp_path/lifeprism.log）
    #    不调用 setup_file_logging（其内部有全局幂等性 flag，会指向其他路径）
    lifeprism_log_path = tmp_path / "lifeprism.log"
    root_file_handler = logging.FileHandler(lifeprism_log_path, mode="a", encoding="utf-8")
    root_file_handler.setFormatter(TruncatingFormatter("%(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(root_file_handler)

    try:
        child_logger = logging.getLogger("lifeprism.sync.sync_client")
        test_message = "test sync log message - lifeprism.log propagation"
        child_logger.warning(test_message)

        # 强制 flush 所有 handler
        for h in logging.getLogger("lifeprism.sync").handlers:
            h.flush()
        root_file_handler.flush()

        # 验证 lifeprism.log 包含该日志
        assert lifeprism_log_path.exists(), "lifeprism.log 应被创建"
        lifeprism_content = lifeprism_log_path.read_text(encoding="utf-8")
        assert test_message in lifeprism_content, (
            f"lifeprism.log 应包含 sync_client 的日志（propagate 生效），"
            f"实际内容: {lifeprism_content!r}"
        )
    finally:
        root_logger.removeHandler(root_file_handler)
        root_file_handler.close()


@pytest.mark.core
def test_sync_log_does_not_capture_non_sync_loggers(clean_sync_logger, tmp_path):
    """非 lifeprism.sync 子树的 logger 输出不应写入 sync.log。

    例如 lifeprism.llm.xxx 的日志不应出现在 sync.log 中，
    确保 sync.log 是同步过程的"纯净化"视图。
    """
    setup_sync_logging(tmp_path)

    # 用一个非 sync 子树的 logger 输出
    other_logger = logging.getLogger("lifeprism.llm.some_module")
    other_message = "this should NOT appear in sync.log"
    other_logger.warning(other_message)

    # 同时用 sync 子 logger 输出
    sync_logger = logging.getLogger("lifeprism.sync.sync_client")
    sync_message = "this SHOULD appear in sync.log"
    sync_logger.warning(sync_message)

    # 强制 flush
    for h in logging.getLogger("lifeprism.sync").handlers:
        h.flush()

    sync_log_path = tmp_path / "sync.log"
    content = sync_log_path.read_text(encoding="utf-8")
    assert sync_message in content, "sync.log 应包含 sync 子 logger 的日志"
    assert other_message not in content, "sync.log 不应包含非 sync 子树的日志"


# ---------------------------------------------------------------------------
# 5. 追加写入验证：不清空已有 sync.log
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_sync_logging_appends_not_clears(clean_sync_logger, tmp_path):
    """调用 setup_sync_logging 时不清空已有 sync.log 内容（追加写入）。

    场景：应用启动时保留上次启动后的同步日志，由 500KB 滚动自然淘汰。
    """
    # 预先创建 sync.log 并写入内容
    sync_log_path = tmp_path / "sync.log"
    pre_existing_content = "previous session sync log line\n"
    sync_log_path.write_text(pre_existing_content, encoding="utf-8")

    # 调用 setup_sync_logging
    setup_sync_logging(tmp_path)

    # 验证原有内容仍在
    content = sync_log_path.read_text(encoding="utf-8")
    assert pre_existing_content in content, (
        f"setup_sync_logging 不应清空已有 sync.log，实际内容: {content!r}"
    )


# ---------------------------------------------------------------------------
# 6. 覆盖式滚动验证：超过 500KB 时清空重写
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_sync_log_rolling_over_500kb(clean_sync_logger, tmp_path):
    """sync.log 超过 500KB 时被清空重写（覆盖式滚动）。

    backupCount=0 + maxBytes=500KB：当写入使文件超过 500KB 时，
    RotatingFileHandler 会清空文件重新写，不保留备份。
    """
    setup_sync_logging(tmp_path)

    sync_logger = logging.getLogger("lifeprism.sync")
    # 找到 RotatingFileHandler
    rotating_handlers = [h for h in sync_logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating_handlers) == 1
    handler = rotating_handlers[0]

    # 写入超过 500KB 的数据
    # 每条日志约 200 字节，写 3000 条 → 约 600KB
    big_payload = "X" * 150  # 每条 ~150 字节 payload
    for i in range(3000):
        sync_logger.warning("msg %d payload=%s", i, big_payload)
        # 每 100 条 flush 一次，触发 shouldRollover 检查
        if i % 100 == 0:
            handler.flush()

    handler.flush()

    # 验证：文件存在且大小不超过 maxBytes 太多（覆盖式滚动应限制大小）
    sync_log_path = tmp_path / "sync.log"
    assert sync_log_path.exists(), "sync.log 应存在"
    file_size = sync_log_path.stat().st_size
    # RotatingFileHandler 在 backupCount=0 时，超过 maxBytes 后会清空重写
    # 文件大小应远小于 600KB（理论上应接近或小于 maxBytes）
    assert file_size <= 500 * 1024 + 1024, (
        f"覆盖式滚动应限制 sync.log 大小，实际大小: {file_size} bytes"
    )


# ---------------------------------------------------------------------------
# 7. 与现有 logger 兼容性验证
# ---------------------------------------------------------------------------


@pytest.mark.core
def test_setup_sync_logging_does_not_modify_root_handlers(clean_sync_logger, tmp_path):
    """setup_sync_logging 不应修改 root logger 的 handlers（不破坏现有 lifeprism.log 行为）。"""
    root_logger = logging.getLogger()
    original_root_handlers = list(root_logger.handlers)

    setup_sync_logging(tmp_path)

    # root logger 的 handlers 不应被修改
    assert list(root_logger.handlers) == original_root_handlers, (
        "setup_sync_logging 不应修改 root logger 的 handlers"
    )


@pytest.mark.core
def test_setup_sync_logging_does_not_add_handler_to_child_logger(clean_sync_logger, tmp_path):
    """setup_sync_logging 只给 lifeprism.sync logger 添加 handler，
    不应给 lifeprism.sync.sync_client 等子 logger 添加 handler。

    子 logger 通过 propagate 机制将日志传到 lifeprism.sync，
    而不是直接持有 handler。
    """
    setup_sync_logging(tmp_path)

    child_logger = logging.getLogger("lifeprism.sync.sync_client")
    assert len(child_logger.handlers) == 0, (
        "子 logger 不应直接持有 handler，应通过 propagate 传播"
    )
