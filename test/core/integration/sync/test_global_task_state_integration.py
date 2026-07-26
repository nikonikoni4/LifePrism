"""GlobalTaskState 集成互斥逻辑测试

验证 ADR docs/adr/2026-07-25-global-task-state.md 决策 3/4/5 的集成互斥行为。

覆盖 5 处集成互斥逻辑（Issue 3 补充测试）：
- schedule_service._dreaming: 10点任务超时降级 + 异常路径 release() + if acquired 守卫
- schedule_service._process_session_message: 4h 任务超时返回
- sync_client._run_sync_loop: try_acquire 失败调 send_ping + continue / sync_once 异常 release
- main._start_sync_on_startup: try_acquire 失败调 send_ping
- sync_status_api._run_sync_background: try_acquire 失败调 send_ping

Mock 策略:
- Mock GlobalTaskState 类方法 try_acquire / release 控制返回值与验证调用次数
  （避免直接 patch LazySingleton 代理对象，因 __getattr__/__setattr__ 转发复杂）
- 真实场景测试（acquired=True）：使用真实 GlobalTaskState 实例，验证调用后状态回到 IDLE
- Mock SyncService.incremental_sync / dreaming / process_session_message / backup_service.backup_documents
- Mock SyncClient.sync_once / send_ping

参考:
- ADR: docs/adr/2026-07-25-global-task-state.md 决策 3/4/5
- 审查报告: docs/generated/023/2026-07-25-code-review-global-task-state.md Issue 3
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def reset_global_task_state():
    """每个测试前重置 GlobalTaskState 单例状态为 IDLE

    避免前一个测试遗留 LOCAL_TASK/CLOUD_SYNC 状态影响后续测试。
    """
    from lifeprism.server.services.global_task_state import (
        TaskState,
        global_task_state,
    )

    instance = global_task_state._ensure_initialized()
    with instance._cond:
        instance._state = TaskState.IDLE
    yield instance
    # 测试后清理
    with instance._cond:
        instance._state = TaskState.IDLE


# ==================== Seam 1: _dreaming 超时降级 + 异常路径 ====================


class TestDreamingTimeoutDegradation:
    """Seam 1: _dreaming 超时降级路径

    验证 ADR 决策 5：
    - acquired=False 时跳过 incremental_sync（依赖云端数据）
    - dreaming 仍执行（不依赖云端）
    - backup_documents 仍执行（备份本地数据）
    - finally 中 if acquired 守卫不调用 release()
    """

    @pytest.mark.asyncio
    async def test_dreaming_timeout_skips_incremental_sync(
        self, reset_global_task_state
    ):
        """超时降级：acquired=False 时跳过 incremental_sync"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import GlobalTaskState

        with (
            patch.object(
                GlobalTaskState, "try_acquire", return_value=False
            ),
            patch(
                "lifeprism.server.services.schedule_service.SyncService"
            ) as mock_sync_service_cls,
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", new=AsyncMock()
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            await schedule_service._dreaming()

        # Assert: SyncService 未被实例化（incremental_sync 跳过）
        mock_sync_service_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_dreaming_timeout_still_executes_dreaming(
        self, reset_global_task_state
    ):
        """超时降级：dreaming 仍执行（不依赖云端）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import GlobalTaskState

        with (
            patch.object(
                GlobalTaskState, "try_acquire", return_value=False
            ),
            patch(
                "lifeprism.server.services.schedule_service.SyncService"
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming",
                new=AsyncMock(),
            ) as mock_dreaming,
            patch.object(
                BackupService, "backup_documents", new=AsyncMock()
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            await schedule_service._dreaming()

        # Assert: dreaming 被调用
        mock_dreaming.assert_called_once()

    @pytest.mark.asyncio
    async def test_dreaming_timeout_still_executes_backup(
        self, reset_global_task_state
    ):
        """超时降级：backup_documents 仍执行（备份本地数据）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import GlobalTaskState

        mock_backup = AsyncMock()
        with (
            patch.object(
                GlobalTaskState, "try_acquire", return_value=False
            ),
            patch(
                "lifeprism.server.services.schedule_service.SyncService"
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", mock_backup
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            await schedule_service._dreaming()

        # Assert: backup_documents 被调用
        mock_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_dreaming_timeout_does_not_call_release(
        self, reset_global_task_state
    ):
        """关键守卫：acquired=False 时 finally 不调用 release()

        验证 ADR 决策 2 执行序列图的超时分支：
        '不调用 release()（关键守卫：if acquired: release()）'

        若超时后另一线程已获取 CLOUD_SYNC，错误调用 release() 会把 CLOUD_SYNC
        重置为 IDLE，破坏互斥语义。
        """
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import GlobalTaskState

        with (
            patch.object(
                GlobalTaskState, "try_acquire", return_value=False
            ),
            patch.object(
                GlobalTaskState, "release"
            ) as mock_release,
            patch(
                "lifeprism.server.services.schedule_service.SyncService"
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", new=AsyncMock()
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            await schedule_service._dreaming()

        # Assert: release 未被调用（关键守卫 if acquired: release()）
        mock_release.assert_not_called()


class TestDreamingAcquiredPath:
    """Seam 1: _dreaming 成功获取路径（使用真实 GlobalTaskState 状态）"""

    @pytest.mark.asyncio
    async def test_dreaming_acquired_executes_incremental_sync(
        self, reset_global_task_state
    ):
        """成功获取：执行 incremental_sync（真实 IDLE 状态）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService

        mock_sync_service = MagicMock()
        mock_sync_service.incremental_sync = AsyncMock(
            return_value={"message": "ok"}
        )

        with (
            patch(
                "lifeprism.server.services.schedule_service.SyncService",
                return_value=mock_sync_service,
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", new=AsyncMock()
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            await schedule_service._dreaming()

        # Assert: incremental_sync 被调用
        mock_sync_service.incremental_sync.assert_called_once_with(auto_classify=True)

    @pytest.mark.asyncio
    async def test_dreaming_acquired_releases_state(self, reset_global_task_state):
        """成功获取：finally 调用 release()，状态回到 IDLE（真实状态验证）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        with (
            patch(
                "lifeprism.server.services.schedule_service.SyncService",
                return_value=MagicMock(incremental_sync=AsyncMock(return_value={})),
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", new=AsyncMock()
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            await schedule_service._dreaming()

        # Assert: 状态回到 IDLE（证明 release 被调用）
        assert global_task_state.current_state == TaskState.IDLE


class TestDreamingExceptionRelease:
    """Seam 1: _dreaming 异常路径 release() 调用

    验证 incremental_sync / dreaming / backup_documents 抛异常时
    release() 在 finally 中被正确调用（acquired=True 场景）。
    使用真实 GlobalTaskState 状态验证 release 被调用（状态回到 IDLE）。
    """

    @pytest.mark.asyncio
    async def test_dreaming_release_on_incremental_sync_exception(
        self, reset_global_task_state
    ):
        """异常路径：incremental_sync 抛异常时 release 仍被调用（状态回到 IDLE）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        mock_sync_service = MagicMock()
        mock_sync_service.incremental_sync = AsyncMock(
            side_effect=RuntimeError("sync failed")
        )

        with (
            patch(
                "lifeprism.server.services.schedule_service.SyncService",
                return_value=mock_sync_service,
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", new=AsyncMock()
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            # incremental_sync 异常被 _dreaming 内部 try/except 捕获，不传播
            await schedule_service._dreaming()

        # Assert: 状态回到 IDLE（异常路径下 finally 仍执行 release）
        assert global_task_state.current_state == TaskState.IDLE

    @pytest.mark.asyncio
    async def test_dreaming_release_on_backup_exception(
        self, reset_global_task_state
    ):
        """异常路径：backup_documents 抛异常时 release 仍被调用（状态回到 IDLE）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.backup_service import BackupService
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        mock_backup = AsyncMock(side_effect=RuntimeError("backup failed"))
        with (
            patch(
                "lifeprism.server.services.schedule_service.SyncService",
                return_value=MagicMock(incremental_sync=AsyncMock(return_value={})),
            ),
            patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                new=AsyncMock(),
            ),
            patch(
                "lifeprism.server.services.schedule_service.dreaming", new=AsyncMock()
            ),
            patch.object(
                BackupService, "backup_documents", mock_backup
            ),
            patch("lifeprism.server.services.schedule_service.settings") as mock_settings,
        ):
            mock_settings.auto_diary_summary = True
            mock_settings.auto_update_memory = True

            # backup 异常被 _dreaming 内部 try/except 捕获，不传播
            await schedule_service._dreaming()

        # Assert: 状态回到 IDLE（异常路径下 finally 仍执行 release）
        assert global_task_state.current_state == TaskState.IDLE


# ==================== Seam 2: _process_session_message 超时返回 ====================


class TestProcessSessionMessageTimeout:
    """Seam 2: _process_session_message 超时返回

    验证 ADR 决策 3：4h 任务超时跳过本次
    """

    @pytest.mark.asyncio
    async def test_process_session_message_timeout_returns_early(
        self, reset_global_task_state
    ):
        """超时：acquired=False 时 early return，不执行 process_session_message"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.global_task_state import GlobalTaskState

        with (
            patch.object(
                GlobalTaskState, "try_acquire", return_value=False
            ),
            patch.object(
                GlobalTaskState, "release"
            ) as mock_release,
            patch(
                "lifeprism.server.services.schedule_service.process_session_message",
                new=AsyncMock(),
            ) as mock_psm,
        ):
            await schedule_service._process_session_message()

        # Assert: process_session_message 未被调用
        mock_psm.assert_not_called()
        # Assert: release 未被调用（early return 前未获取锁）
        mock_release.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_session_message_acquired_executes_and_releases(
        self, reset_global_task_state
    ):
        """成功获取：执行 process_session_message 后 release（真实状态验证）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        with (
            patch(
                "lifeprism.server.services.schedule_service.process_session_message",
                new=AsyncMock(),
            ) as mock_psm,
        ):
            await schedule_service._process_session_message()

        # Assert: process_session_message 被调用
        mock_psm.assert_called_once()
        # Assert: 状态回到 IDLE（证明 release 被调用）
        assert global_task_state.current_state == TaskState.IDLE

    @pytest.mark.asyncio
    async def test_process_session_message_release_on_exception(
        self, reset_global_task_state
    ):
        """异常路径：process_session_message 抛异常时 release 仍被调用（状态回到 IDLE）"""
        from lifeprism.server.services import schedule_service
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        with (
            patch(
                "lifeprism.server.services.schedule_service.process_session_message",
                new=AsyncMock(side_effect=RuntimeError("psm failed")),
            ),
        ):
            # 异常被 _process_session_message 内部 try/except 捕获，不传播
            await schedule_service._process_session_message()

        # Assert: 状态回到 IDLE（异常路径下 finally 仍执行 release）
        assert global_task_state.current_state == TaskState.IDLE


# ==================== Seam 3: _run_sync_loop 互斥逻辑 ====================


class TestRunSyncLoopMutex:
    """Seam 3: SyncClient._run_sync_loop 互斥逻辑

    验证 ADR 决策 4：云端 sync_once 遇 LOCAL_TASK 放弃本次 + 调 ping 端点
    """

    @pytest.mark.asyncio
    async def test_run_sync_loop_calls_ping_when_local_task_active(
        self, reset_global_task_state
    ):
        """LOCAL_TASK 占用时：try_acquire 失败，调 send_ping，不执行 sync_once"""
        from lifeprism.sync.sync_client import SyncClient
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        # 预先占用 LOCAL_TASK（模拟本地任务正在执行）
        assert global_task_state.try_acquire(TaskState.LOCAL_TASK, 0) is True

        # 创建 SyncClient 实例（mock 依赖）
        sync_client = SyncClient.__new__(SyncClient)
        sync_client._sync_lock = __import__("threading").Lock()
        sync_client._is_syncing = False
        sync_client._sync_task = None
        sync_client._template_hashes = None
        sync_client.db = MagicMock()
        sync_client.sync_repository = MagicMock()

        # 使用极短的 sleep 让循环快速执行一次
        with (
            patch(
                "lifeprism.config.settings_manager.get_setting", return_value="http://test:8000"
            ),
            patch.object(sync_client, "sync_once") as mock_sync_once,
            patch.object(sync_client, "send_ping") as mock_send_ping,
            patch.object(sync_client, "finish_sync"),
        ):
            # 启动循环任务
            task = asyncio.create_task(sync_client._run_sync_loop(0.01))
            # 等待一小段时间让循环执行一次
            await asyncio.sleep(0.3)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Assert: sync_once 未被调用（被互斥跳过）
        mock_sync_once.assert_not_called()
        # Assert: send_ping 被调用（至少一次，可能多次因循环）
        mock_send_ping.assert_called()

    @pytest.mark.asyncio
    async def test_run_sync_loop_releases_on_sync_exception(
        self, reset_global_task_state
    ):
        """sync_once 抛异常时 release() 在内层 finally 被调用"""
        from lifeprism.sync.sync_client import SyncClient
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        sync_client = SyncClient.__new__(SyncClient)
        sync_client._sync_lock = __import__("threading").Lock()
        sync_client._is_syncing = False
        sync_client._sync_task = None
        sync_client._template_hashes = None
        sync_client.db = MagicMock()
        sync_client.sync_repository = MagicMock()

        with (
            patch(
                "lifeprism.config.settings_manager.get_setting", return_value="http://test:8000"
            ),
            patch.object(
                sync_client, "sync_once", side_effect=RuntimeError("sync failed")
            ),
            patch.object(sync_client, "send_ping"),
            patch.object(sync_client, "finish_sync"),
        ):
            # 启动循环任务
            task = asyncio.create_task(sync_client._run_sync_loop(0.01))
            await asyncio.sleep(0.3)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Assert: 异常后状态已释放（IDLE）—— 证明内层 finally 调用 release
        assert global_task_state.current_state == TaskState.IDLE


# ==================== Seam 4: _start_sync_on_startup 互斥逻辑 ====================


class TestStartSyncOnStartupMutex:
    """Seam 4: main._start_sync_on_startup 互斥逻辑

    验证 ADR 决策 4：启动同步遇 LOCAL_TASK 放弃 + 调 send_ping
    """

    @pytest.mark.asyncio
    async def test_start_sync_calls_ping_when_local_task_active(
        self, reset_global_task_state
    ):
        """LOCAL_TASK 占用时：启动同步调 send_ping，不执行 sync_once"""
        from lifeprism.server.main import _start_sync_on_startup
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        # 预先占用 LOCAL_TASK
        assert global_task_state.try_acquire(TaskState.LOCAL_TASK, 0) is True

        mock_sync_client = MagicMock()
        mock_sync_client.try_start_sync = MagicMock(return_value=True)
        mock_sync_client.finish_sync = MagicMock()
        mock_sync_client.sync_once = MagicMock()
        mock_sync_client.send_ping = MagicMock()
        mock_sync_client.start_scheduled_sync = MagicMock(return_value=MagicMock())
        mock_sync_client._start_ssh_tunnel = AsyncMock(return_value=None)

        mock_app = MagicMock()
        mock_app.state.sync_client = mock_sync_client

        with patch("lifeprism.server.main.settings") as mock_settings:
            mock_settings.run_mode = "full"
            await _start_sync_on_startup(mock_app)

        # Assert: sync_once 未被调用（被互斥跳过）
        mock_sync_client.sync_once.assert_not_called()
        # Assert: send_ping 被调用
        mock_sync_client.send_ping.assert_called_once()
        # Assert: finish_sync 被调用（finally 守卫）
        mock_sync_client.finish_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_sync_executes_sync_when_idle(
        self, reset_global_task_state
    ):
        """IDLE 状态：启动同步正常执行 sync_once + release"""
        from lifeprism.server.main import _start_sync_on_startup
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        mock_sync_client = MagicMock()
        mock_sync_client.try_start_sync = MagicMock(return_value=True)
        mock_sync_client.finish_sync = MagicMock()
        mock_sync_client.sync_once = MagicMock()
        mock_sync_client.send_ping = MagicMock()
        mock_sync_client.start_scheduled_sync = MagicMock(return_value=MagicMock())
        mock_sync_client._start_ssh_tunnel = AsyncMock(return_value=None)

        mock_app = MagicMock()
        mock_app.state.sync_client = mock_sync_client

        with patch("lifeprism.server.main.settings") as mock_settings:
            mock_settings.run_mode = "full"
            await _start_sync_on_startup(mock_app)

        # Assert: sync_once 被调用
        mock_sync_client.sync_once.assert_called_once()
        # Assert: send_ping 未被调用
        mock_sync_client.send_ping.assert_not_called()
        # Assert: 状态已释放回 IDLE
        assert global_task_state.current_state == TaskState.IDLE


# ==================== Seam 5: _run_sync_background 互斥逻辑 ====================


class TestRunSyncBackgroundMutex:
    """Seam 5: sync_status_api._run_sync_background 互斥逻辑

    验证 ADR 决策 4：手动触发同步遇 LOCAL_TASK 放弃 + 调 send_ping
    """

    def test_run_sync_background_calls_ping_when_local_task_active(
        self, reset_global_task_state
    ):
        """LOCAL_TASK 占用时：手动同步调 send_ping，不执行 sync_once"""
        from lifeprism.server.api.sync_status_api import _run_sync_background
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        # 预先占用 LOCAL_TASK
        assert global_task_state.try_acquire(TaskState.LOCAL_TASK, 0) is True

        mock_sync_client = MagicMock()
        mock_sync_client.sync_once = MagicMock()
        mock_sync_client.send_ping = MagicMock()
        mock_sync_client.finish_sync = MagicMock()

        # 调用 _run_sync_background（同步函数，直接调用）
        _run_sync_background(mock_sync_client)

        # Assert: sync_once 未被调用（被互斥跳过）
        mock_sync_client.sync_once.assert_not_called()
        # Assert: send_ping 被调用
        mock_sync_client.send_ping.assert_called_once()
        # Assert: finish_sync 被调用（finally 守卫）
        mock_sync_client.finish_sync.assert_called_once()

    def test_run_sync_background_executes_sync_when_idle(
        self, reset_global_task_state
    ):
        """IDLE 状态：手动同步正常执行 sync_once + release"""
        from lifeprism.server.api.sync_status_api import _run_sync_background
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        mock_sync_client = MagicMock()
        mock_sync_client.sync_once = MagicMock()
        mock_sync_client.send_ping = MagicMock()
        mock_sync_client.finish_sync = MagicMock()

        _run_sync_background(mock_sync_client)

        # Assert: sync_once 被调用
        mock_sync_client.sync_once.assert_called_once()
        # Assert: send_ping 未被调用
        mock_sync_client.send_ping.assert_not_called()
        # Assert: 状态已释放回 IDLE
        assert global_task_state.current_state == TaskState.IDLE

    def test_run_sync_background_releases_on_sync_exception(
        self, reset_global_task_state
    ):
        """异常路径：sync_once 抛异常时 release 在 finally 被调用（状态回到 IDLE）"""
        from lifeprism.server.api.sync_status_api import _run_sync_background
        from lifeprism.server.services.global_task_state import (
            TaskState,
            global_task_state,
        )

        mock_sync_client = MagicMock()
        mock_sync_client.sync_once = MagicMock(side_effect=RuntimeError("sync failed"))
        mock_sync_client.send_ping = MagicMock()
        mock_sync_client.finish_sync = MagicMock()

        # 异常被 _run_sync_background 外层 except 捕获，不传播
        _run_sync_background(mock_sync_client)

        # Assert: 状态已释放回 IDLE（内层 finally 调用 release）
        assert global_task_state.current_state == TaskState.IDLE
        # Assert: finish_sync 被调用（外层 finally 守卫）
        mock_sync_client.finish_sync.assert_called_once()
