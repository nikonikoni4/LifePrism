"""每日索引调度必须先等记忆更新，云端不构建。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.core


@pytest.mark.asyncio
async def test_rag_schedule_waits_for_memory_then_runs_independently(monkeypatch, tmp_path):
    import lifeprism.server.services.schedule_service as module

    config = SimpleNamespace(
        run_mode="full",
        lifeprism_data_path=str(tmp_path),
        auto_summary_session=False,
        auto_update_memory=True,
        auto_diary_summary=False,
        get=lambda key, default=None: True if key == "rag.enabled" else default,
    )
    monkeypatch.setattr(module, "settings", config)
    service = module.ScheduleService()
    job = SimpleNamespace(run=AsyncMock())
    service._rag_job = job
    service._rag_data_root = tmp_path.resolve()
    monkeypatch.setattr(service, "_load_cron_state", lambda: {})
    monkeypatch.setattr(module, "get_local_today", lambda: __import__("datetime").date(2026, 10, 8))
    await service.run_rag_daily()
    job.run.assert_not_awaited()
    # 完成记忆任务的入口可以立即运行，无需等待下一个轮询。
    monkeypatch.setattr(module.global_task_state, "try_acquire", lambda *args: True)
    monkeypatch.setattr(module.global_task_state, "release", lambda: None)
    await service.run_rag_daily(after_memory=True)
    job.run.assert_awaited_once_with("2026-10-08", ["user", "diary"])


def test_rag_jobs_registered_even_when_memory_disabled(monkeypatch, tmp_path):
    import lifeprism.server.services.schedule_service as module

    config = SimpleNamespace(
        run_mode="full",
        lifeprism_data_path=str(tmp_path),
        auto_summary_session=False,
        auto_update_memory=False,
        auto_diary_summary=False,
    )
    monkeypatch.setattr(module, "settings", config)
    service = module.ScheduleService()
    assert {"rag_daily", "rag_retry"} <= {job["job_id"] for job in service._system_jobs}


@pytest.mark.asyncio
async def test_rag_schedule_recreates_job_after_data_directory_moves(monkeypatch, tmp_path):
    import lifeprism.rag.service as rag
    import lifeprism.server.services.schedule_service as module
    import lifeprism.sync.rag_sync as sync

    config = SimpleNamespace(
        run_mode="full",
        lifeprism_data_path=str(tmp_path / "old"),
        auto_summary_session=False,
        auto_update_memory=False,
        auto_diary_summary=False,
        get=lambda key, default=None: True if key == "rag.enabled" else default,
    )
    monkeypatch.setattr(module, "settings", config)
    service = module.ScheduleService()
    old_job = SimpleNamespace(run=AsyncMock())
    new_job = SimpleNamespace(run=AsyncMock())
    service._rag_job = old_job
    service._rag_data_root = (tmp_path / "old").resolve()
    service._rag_sync_client = object()
    config.lifeprism_data_path = str(tmp_path / "new")
    monkeypatch.setattr(rag, "get_rag_service", lambda: object())
    monkeypatch.setattr(sync, "DailyRagJob", lambda *args: new_job)
    monkeypatch.setattr(module.global_task_state, "try_acquire", lambda *args: True)
    monkeypatch.setattr(module.global_task_state, "release", lambda: None)
    await service.run_rag_daily(after_memory=True)
    old_job.run.assert_not_awaited()
    new_job.run.assert_awaited_once()
    assert service._state_file_path.parent == (tmp_path / "new").resolve()


@pytest.mark.asyncio
async def test_rag_schedule_compensates_memory_enabled_after_startup(monkeypatch, tmp_path):
    import lifeprism.server.services.schedule_service as module

    config = SimpleNamespace(
        run_mode="full",
        lifeprism_data_path=str(tmp_path),
        auto_summary_session=False,
        auto_update_memory=False,
        auto_diary_summary=False,
        get=lambda key, default=None: True if key == "rag.enabled" else default,
    )
    monkeypatch.setattr(module, "settings", config)
    service = module.ScheduleService()
    config.auto_update_memory = True
    # 固定到下午，避免测试依赖当前时钟。
    from datetime import datetime

    monkeypatch.setattr(
        module, "datetime", SimpleNamespace(now=lambda tz: datetime(2026, 10, 8, 12))
    )
    memory = AsyncMock()
    monkeypatch.setattr(module, "_dreaming", memory)
    await service.run_rag_daily()
    memory.assert_awaited_once_with(service)
