"""
SyncClient 定时同步集成测试

测试 seam:
- Seam 1: start_scheduled_sync() - 测试后台任务创建
- Seam 2: 并发控制 - _is_syncing == True 时跳过并记录 WARNING
- Seam 3: try...finally - 异常时 _is_syncing 重置为 False
- Seam 4: 失败重试 - 同步失败后下次触发时重试

Mock 策略:
- Mock SyncClient.sync_once() 控制成功/失败
- Mock asyncio.sleep 避免真实等待（调用指定次数后抛 CancelledError 终止循环）
- 使用 caplog fixture 验证日志记录

参考: test/core/integration/sync/test_sync_client.py
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import (
        LWBaseDataProvider,
    )
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def sync_repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo


@pytest.fixture
def sync_client(initialized_db, sync_repository):
    """创建 SyncClient 实例

    定时同步测试不依赖真实数据库交互（sync_once 被 mock），
    但复用 SyncClient 构造以保持与生产代码一致。

    _read_remote_url 默认 patch 为返回有效 url，避免新加的配置检查
    导致 sync_once 被跳过。个别测试需要验证"未配置 url"行为时，
    可在该测试内部重新 patch _read_remote_url 返回空字符串。
    """
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient(db_manager=initialized_db, sync_repository=sync_repository)
    with patch.object(client, "_read_remote_url", return_value="https://example.com"):
        yield client


# ==================== 辅助函数 ====================


def _make_cancelling_sleep(max_calls):
    """创建一个在调用 max_calls 次后抛出 CancelledError 的 mock asyncio.sleep。

    用于让 _run_sync_loop 的无限循环在执行指定次数后干净退出：
    循环每次迭代开头 await asyncio.sleep(...)，
    当调用次数超过 max_calls 时抛出 CancelledError，
    CancelledError 是 BaseException（不会被 except Exception 捕获），
    从而传播出 while 循环终止任务。

    Args:
        max_calls: 允许执行的 sleep 次数（即允许执行的同步迭代次数）

    Returns:
        mock 的 async sleep 函数
    """
    counter = {"n": 0}

    async def _fake_sleep(seconds):
        counter["n"] += 1
        if counter["n"] > max_calls:
            raise asyncio.CancelledError()

    return _fake_sleep


async def _run_loop_until_cancelled(sync_client, interval_seconds=600, max_calls=1):
    """运行 _run_sync_loop 直到被 mock sleep 取消。

    Args:
        sync_client: SyncClient 实例
        interval_seconds: 同步间隔
        max_calls: 允许的 sleep 次数（同步迭代次数）

    Returns:
        抛出 CancelledError 时的任务对象（已结束）
    """
    task = asyncio.create_task(sync_client._run_sync_loop(interval_seconds))
    with patch(
        "lifeprism.sync.sync_client.asyncio.sleep",
        new=_make_cancelling_sleep(max_calls),
    ):
        with pytest.raises(asyncio.CancelledError):
            await task
    return task


# ==================== Seam 1: start_scheduled_sync() ====================


class TestStartScheduledSync:
    """Seam 1: start_scheduled_sync() - 后台任务创建"""

    async def test_start_scheduled_sync_returns_running_task(self, sync_client):
        """start_scheduled_sync 返回一个正在运行的 asyncio.Task"""
        task = sync_client.start_scheduled_sync(interval_seconds=600)

        # Assert: 返回 asyncio.Task 实例
        assert isinstance(task, asyncio.Task)
        # 任务尚未完成（正在运行或等待中）
        assert not task.done()

        # 清理：取消后台任务，避免影响其他测试
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_start_scheduled_sync_default_interval_is_600(self, sync_client):
        """start_scheduled_sync 默认间隔为 600 秒（10 分钟）"""
        # 通过观察传入 _run_sync_loop 的 interval_seconds 间接验证默认值
        with patch.object(sync_client, "_run_sync_loop", new=AsyncMock()) as mock_loop:
            task = sync_client.start_scheduled_sync()

            mock_loop.assert_called_once_with(600)
            # 等待任务结束，避免遗留 pending task
            await task

    async def test_start_scheduled_sync_uses_custom_interval(self, sync_client):
        """start_scheduled_sync 接受自定义间隔参数"""
        with patch.object(sync_client, "_run_sync_loop", new=AsyncMock()) as mock_loop:
            task = sync_client.start_scheduled_sync(interval_seconds=120)

            mock_loop.assert_called_once_with(120)
            await task

    async def test_is_syncing_initializes_to_false(self, sync_client):
        """SyncClient 实例的 _is_syncing 初始值为 False"""
        assert sync_client._is_syncing is False


# ==================== Seam 2: 并发控制 ====================


class TestConcurrencyControl:
    """Seam 2: 并发控制 - _is_syncing == True 时跳过并记录 WARNING"""

    async def test_skips_sync_when_already_syncing(self, sync_client, caplog):
        """_is_syncing 为 True 时跳过本次同步，sync_once 不被调用"""
        # Arrange: 手动将 _is_syncing 置为 True（模拟上次同步未完成）
        sync_client._is_syncing = True
        mock_sync_once = MagicMock()
        caplog.set_level(logging.WARNING, logger="lifeprism.sync.sync_client")

        # Act: 运行一次迭代（sleep 1 次后取消）
        await _run_loop_until_cancelled(sync_client, max_calls=1)

        # Assert: sync_once 未被调用
        # (sync_once 被 patch 前，_is_syncing 检查已跳过)
        # 用 patch 包裹验证：
        # 重新跑一次，这次 mock sync_once
        sync_client._is_syncing = True
        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        mock_sync_once.assert_not_called()

    async def test_logs_warning_when_skipping_sync(self, sync_client, caplog):
        """跳过同步时记录 WARNING: 跳过定时同步（上次同步未完成）"""
        # Arrange
        sync_client._is_syncing = True
        caplog.set_level(logging.WARNING, logger="lifeprism.sync.sync_client")

        # Act
        await _run_loop_until_cancelled(sync_client, max_calls=1)

        # Assert
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("跳过定时同步" in m and "上次同步未完成" in m for m in warning_messages), (
            f"未找到跳过同步的 WARNING 日志，实际: {warning_messages}"
        )

    async def test_does_not_set_is_syncing_when_skipped(self, sync_client, caplog):
        """跳过同步时不修改 _is_syncing 状态（保持 True，等待真正同步完成）"""
        sync_client._is_syncing = True

        await _run_loop_until_cancelled(sync_client, max_calls=1)

        # _is_syncing 仍为 True（跳过路径不触碰 try/finally）
        assert sync_client._is_syncing is True


# ==================== Seam 3: try...finally 重置 ====================


class TestIsSyncingReset:
    """Seam 3: try...finally - 异常时 _is_syncing 重置为 False"""

    async def test_is_syncing_reset_after_exception(self, sync_client, caplog):
        """sync_once 抛异常后 _is_syncing 被重置为 False"""
        # Arrange
        caplog.set_level(logging.ERROR, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(side_effect=RuntimeError("网络错误"))

        # Act
        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        # Assert: _is_syncing 已被重置
        assert sync_client._is_syncing is False

    async def test_logs_error_on_sync_failure(self, sync_client, caplog):
        """同步失败时记录 ERROR（含 exc_info 追踪）"""
        caplog.set_level(logging.ERROR, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(side_effect=RuntimeError("连接超时"))

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("定时同步失败" in r.getMessage() for r in error_records), (
            f"未找到同步失败的 ERROR 日志，实际: {[r.getMessage() for r in error_records]}"
        )
        assert any(r.exc_info and r.exc_info[1] is not None for r in error_records), (
            "ERROR 日志缺少 exc_info（异常追踪）"
        )

    async def test_is_syncing_reset_to_false_on_success(self, sync_client, caplog):
        """同步成功后 _is_syncing 被重置为 False"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(return_value=None)

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        assert sync_client._is_syncing is False

    async def test_loop_continues_after_exception(self, sync_client, caplog):
        """异常不会终止循环：单次失败后循环仍在运行（下次 sleep 取消才退出）"""
        caplog.set_level(logging.ERROR, logger="lifeprism.sync.sync_client")
        # sync_once 每次都抛异常
        mock_sync_once = MagicMock(side_effect=RuntimeError("持续失败"))

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            # 运行 2 次迭代，两次都失败，循环不因异常退出（由 sleep 取消退出）
            await _run_loop_until_cancelled(sync_client, max_calls=2)

        # Assert: sync_once 被调用 2 次（异常未终止循环）
        assert mock_sync_once.call_count == 2
        # _is_syncing 最终仍为 False
        assert sync_client._is_syncing is False


# ==================== Seam 4: 失败重试 ====================


class TestFailureRetry:
    """Seam 4: 失败重试 - 同步失败后下次定时触发时自动重试"""

    async def test_retries_on_next_trigger_after_failure(self, sync_client, caplog):
        """第一次失败、第二次成功：sync_once 被调用两次"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")
        # 第一次抛异常，第二次成功
        mock_sync_once = MagicMock(side_effect=[RuntimeError("首次失败"), None])

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=2)

        # Assert: 两次都被调用
        assert mock_sync_once.call_count == 2

    async def test_logs_error_then_success_after_retry(self, sync_client, caplog):
        """重试场景下日志：先 ERROR（失败）后 INFO（完成）"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(side_effect=[RuntimeError("首次失败"), None])

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=2)

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        info_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("定时同步失败" in r.getMessage() for r in error_records), (
            "未找到同步失败的 ERROR 日志"
        )
        assert any(r.exc_info and r.exc_info[1] is not None for r in error_records), (
            "ERROR 日志缺少 exc_info（异常追踪）"
        )
        assert any("定时同步完成" in m for m in info_messages)

    async def test_is_syncing_reset_between_attempts(self, sync_client, caplog):
        """每次尝试之间 _is_syncing 都被正确重置（不会卡在 True）"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")
        # 记录每次 sync_once 调用时 _is_syncing 的值
        observed_is_syncing = []

        def _spy_sync_once(*args, **kwargs):
            observed_is_syncing.append(sync_client._is_syncing)
            if len(observed_is_syncing) == 1:
                raise RuntimeError("首次失败")
            return None

        mock_sync_once = MagicMock(side_effect=_spy_sync_once)

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=2)

        # 进入 sync_once 时 _is_syncing 必须为 True（已加锁）
        assert observed_is_syncing == [True, True]
        # 结束后 _is_syncing 必须为 False
        assert sync_client._is_syncing is False

    async def test_consecutive_failures_keep_retrying(self, sync_client, caplog):
        """连续失败 3 次后仍然在第 4 次触发时重试（不放弃）"""
        caplog.set_level(logging.ERROR, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(
            side_effect=[
                RuntimeError("失败1"),
                RuntimeError("失败2"),
                RuntimeError("失败3"),
                None,
            ]
        )

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=4)

        assert mock_sync_once.call_count == 4
        # 三次 ERROR 日志
        error_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_messages) == 3
        # 最终 _is_syncing 为 False
        assert sync_client._is_syncing is False


# ==================== 成功路径日志（补充） ====================


class TestSuccessLogging:
    """补充：成功路径的 INFO 日志记录"""

    async def test_logs_start_and_complete_on_success(self, sync_client, caplog):
        """成功同步时记录 INFO: 定时同步开始 / 定时同步完成"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(return_value=None)

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        info_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("定时同步开始" in m for m in info_messages), (
            f"未找到 '定时同步开始' INFO 日志，实际: {info_messages}"
        )
        assert any("定时同步完成" in m and "耗时" in m for m in info_messages), (
            f"未找到 '定时同步完成' INFO 日志，实际: {info_messages}"
        )

    async def test_complete_log_contains_duration(self, sync_client, caplog):
        """完成日志包含耗时信息（耗时 {duration}s）"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")
        mock_sync_once = MagicMock(return_value=None)

        with patch.object(sync_client, "sync_once", new=mock_sync_once):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        info_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        complete_msgs = [m for m in info_messages if "定时同步完成" in m]
        assert len(complete_msgs) == 1
        # 完成日志格式：定时同步完成，耗时 {duration}s
        assert "耗时" in complete_msgs[0]
        assert complete_msgs[0].rstrip().endswith("s")


# ==================== Seam 5: 未配置 remote_url 时跳过同步 ====================


class TestMissingRemoteUrl:
    """Seam 5: sync.remote_url 未配置时跳过本次同步（不取消整个定时任务）"""

    async def test_skips_sync_when_url_empty(self, sync_client, caplog):
        """_read_remote_url 返回空字符串时跳过本次，sync_once 不被调用"""
        # Arrange: 重新 patch _read_remote_url 返回空字符串
        mock_sync_once = MagicMock()
        caplog.set_level(logging.DEBUG, logger="lifeprism.sync.sync_client")

        with patch.object(sync_client, "_read_remote_url", return_value=""):
            with patch.object(sync_client, "sync_once", new=mock_sync_once):
                await _run_loop_until_cancelled(sync_client, max_calls=1)

        # Assert: sync_once 未被调用
        mock_sync_once.assert_not_called()
        # 日志包含跳过提示（源码使用 logger.debug，需捕获 DEBUG 级别）
        debug_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("未配置 sync.remote_url" in m for m in debug_messages), (
            f"未找到跳过提示日志，实际: {[r.getMessage() for r in caplog.records]}"
        )

    async def test_skips_sync_when_url_none(self, sync_client, caplog):
        """_read_remote_url 返回 None（被 helper 转为 ""）时同样跳过"""
        mock_sync_once = MagicMock()
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")

        with patch.object(sync_client, "_read_remote_url", return_value=None):
            with patch.object(sync_client, "sync_once", new=mock_sync_once):
                await _run_loop_until_cancelled(sync_client, max_calls=1)

        mock_sync_once.assert_not_called()

    async def test_loop_continues_after_url_configured(
        self, sync_client, initialized_db, sync_repository, caplog
    ):
        """url 为空时跳过，配置 url 后下次定时自动开始同步"""
        # Arrange: 第一次返回空，第二次返回有效 url
        url_values = iter(["", "https://example.com"])
        mock_sync_once = MagicMock()
        caplog.set_level(logging.DEBUG, logger="lifeprism.sync.sync_client")

        def _side_effect():
            return next(url_values)

        with patch.object(sync_client, "_read_remote_url", side_effect=_side_effect):
            with patch.object(sync_client, "sync_once", new=mock_sync_once):
                await _run_loop_until_cancelled(sync_client, max_calls=2)

        # Assert: 第一次跳过，第二次执行 sync_once
        assert mock_sync_once.call_count == 1
        # "未配置 sync.remote_url" 在源码中为 logger.debug
        debug_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("未配置 sync.remote_url" in m for m in debug_messages)
        info_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("定时同步开始" in m for m in info_messages)

    async def test_does_not_set_is_syncing_when_skipped(self, sync_client, caplog):
        """url 为空时跳过不会设置 _is_syncing（不占用锁）"""
        caplog.set_level(logging.INFO, logger="lifeprism.sync.sync_client")

        with patch.object(sync_client, "_read_remote_url", return_value=""):
            await _run_loop_until_cancelled(sync_client, max_calls=1)

        # _is_syncing 应保持 False（没有进入 try_start_sync 分支）
        assert sync_client._is_syncing is False


class TestSyncOnceValidation:
    """Seam 5 补充: sync_once 入口对未配置 url/api_key 的防御性检查"""

    def test_sync_once_raises_when_url_empty(self, sync_client):
        """sync_once 在 remote_url 为空时抛出 ValidationError"""
        from lifeprism.utils.exceptions import ValidationError

        with patch(
            "lifeprism.config.settings_manager.get_setting",
            return_value="",
        ):
            with patch(
                "lifeprism.sync.sync_config.get_sync_api_key",
                return_value="some_key",
            ):
                with pytest.raises(ValidationError, match="sync.remote_url 未配置"):
                    sync_client.sync_once()

    def test_sync_once_raises_when_api_key_empty(self, sync_client):
        """sync_once 在 api_key 为空时抛出 ValidationError"""
        from lifeprism.utils.exceptions import ValidationError

        with patch(
            "lifeprism.config.settings_manager.get_setting",
            return_value="https://example.com",
        ):
            with patch(
                "lifeprism.sync.sync_config.get_sync_api_key",
                return_value="",
            ):
                with pytest.raises(ValidationError, match="sync_api_key 未配置"):
                    sync_client.sync_once()
