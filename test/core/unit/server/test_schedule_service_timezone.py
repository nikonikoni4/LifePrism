"""ScheduleService 本地时区行为测试

验证定时任务服务在 Issue #29 后使用本地时区的行为正确性。

测试 seam:
- Seam 1: _SYSTEM_CRON_JOB_TIME 常量 - Cron 表达式对应本地 10:00
- Seam 2: start() - AsyncIOScheduler 初始化时显式设置本地时区
- Seam 3: add_cron_job() - CronTrigger 显式设置本地时区
- Seam 4: add_interval_job() - IntervalTrigger 显式设置本地时区
- Seam 5: _should_execute_cron_today() - "今天"判断基于本地日期
- Seam 6: _execute_cron_with_state() - 状态记录使用本地日期
- Seam 7: _dreaming() 模块函数 - "昨天"计算基于本地时区
- Seam 8: _add_system_jobs() - "过触发时间"判断基于本地时间

参考:
- docs/coding-rules/time-handling-rules.md
- .scratch/utc-timezone-migration/issues/29-scheduled-task-local-timezone-fix.md
"""

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core

TEST_TIMEZONE = "Asia/Shanghai"


# ==================== Seam 1: _SYSTEM_CRON_JOB_TIME 常量 ====================


def test_system_cron_job_time_is_local_10():
    """_SYSTEM_CRON_JOB_TIME 应为 "0 10 * * *"（本地 10:00）

    Issue #29 后: Cron 表达式基于本地时区，"0 10 * * *" 表示本地 10:00 触发。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    assert ScheduleService._SYSTEM_CRON_JOB_TIME == "0 10 * * *"


# ==================== Seam 2: start() 设置本地时区 ====================


def test_start_initializes_scheduler_with_local_timezone():
    """start() 初始化 AsyncIOScheduler 时应使用本地时区

    APScheduler 默认使用系统本地时区，Issue #29 后显式设置为用户配置的本地时区，
    确保 Cron 表达式按本地时间触发。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()
    mock_scheduler.start = MagicMock()

    with patch("lifeprism.server.services.schedule_service.AsyncIOScheduler") as mock_scheduler_cls:
        mock_scheduler_cls.return_value = mock_scheduler
        with patch("lifeprism.server.services.schedule_service.settings") as mock_settings:
            mock_settings.run_mode = "full"
            with patch(
                "lifeprism.server.services.schedule_service.get_user_timezone",
                return_value=TEST_TIMEZONE,
            ):
                service.start()

    assert mock_scheduler_cls.called, "应创建 AsyncIOScheduler 实例"
    call_kwargs = mock_scheduler_cls.call_args.kwargs
    assert "timezone" in call_kwargs, "AsyncIOScheduler 必须显式设置 timezone"
    tz_value = call_kwargs["timezone"]
    tz_str = str(tz_value)
    assert tz_str == TEST_TIMEZONE, f"timezone 应为 {TEST_TIMEZONE}，实际为 {tz_str}"


# ==================== Seam 3: add_cron_job() 设置本地时区 ====================


def test_add_cron_job_uses_local_timezone_for_trigger():
    """add_cron_job() 创建 CronTrigger 时应显式传入本地时区

    CronTrigger.from_crontab 默认使用系统本地时区，Issue #29 后显式设置为
    用户配置的本地时区，确保 Cron 表达式按本地时间触发。
    """

    async def dummy_func():
        pass

    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "test_job"
    mock_scheduler.add_job.return_value = mock_job
    service._scheduler = mock_scheduler

    with patch("lifeprism.server.services.schedule_service.CronTrigger") as mock_cron_trigger_cls:
        mock_trigger = MagicMock()
        mock_cron_trigger_cls.from_crontab.return_value = mock_trigger
        with patch(
            "lifeprism.server.services.schedule_service.get_user_timezone",
            return_value=TEST_TIMEZONE,
        ):
            service.add_cron_job(dummy_func, "0 10 * * *", job_id="test_job")

        assert mock_cron_trigger_cls.from_crontab.called
        call_kwargs = mock_cron_trigger_cls.from_crontab.call_args.kwargs
        assert "timezone" in call_kwargs, "CronTrigger.from_crontab 必须设置 timezone"
        tz_value = call_kwargs["timezone"]
        assert str(tz_value) == TEST_TIMEZONE, f"timezone 应为 {TEST_TIMEZONE}，实际为 {tz_value}"


# ==================== Seam 4: add_interval_job() 设置本地时区 ====================


def test_add_interval_job_uses_local_timezone_for_trigger():
    """add_interval_job() 创建 IntervalTrigger 时应显式传入本地时区

    IntervalTrigger 虽然是间隔执行（不受时区影响），但显式设置时区
    可避免 start_date 等隐含时区依赖。
    """

    def dummy_func():
        pass

    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "test_job"
    mock_scheduler.add_job.return_value = mock_job
    service._scheduler = mock_scheduler

    with patch(
        "lifeprism.server.services.schedule_service.IntervalTrigger"
    ) as mock_interval_trigger_cls:
        mock_trigger = MagicMock()
        mock_interval_trigger_cls.return_value = mock_trigger
        with patch(
            "lifeprism.server.services.schedule_service.get_user_timezone",
            return_value=TEST_TIMEZONE,
        ):
            service.add_interval_job(dummy_func, seconds=30, job_id="test_job")

        assert mock_interval_trigger_cls.called
        call_kwargs = mock_interval_trigger_cls.call_args.kwargs
        assert "timezone" in call_kwargs, "IntervalTrigger 必须设置 timezone"
        tz_value = call_kwargs["timezone"]
        assert str(tz_value) == TEST_TIMEZONE, f"timezone 应为 {TEST_TIMEZONE}，实际为 {tz_value}"


# ==================== Seam 5: _should_execute_cron_today() 使用本地日期 ====================


def test_should_execute_cron_today_uses_local_date():
    """_should_execute_cron_today() 的"今天"判断应基于本地日期

    场景：本地日期 2026-07-13（无论 UTC 日期是 12 还是 13）
    - 任务执行后记录本地日期 "2026-07-13"
    - 同一天再次判断时应识别为"今天已执行"
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_local_test.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path

    try:
        mock_local_today = date(2026, 7, 13)

        with patch(
            "lifeprism.server.services.schedule_service.get_local_today",
            return_value=mock_local_today,
        ):
            # 第一次判断：没有执行记录，应返回 True
            assert service._should_execute_cron_today("test_job") is True

            # 模拟任务执行后保存状态（应保存本地日期 "2026-07-13"）
            service._save_cron_state("test_job", mock_local_today.isoformat())

            # 第二次判断：同一天（本地日期），应返回 False
            assert service._should_execute_cron_today("test_job") is False

        # 验证状态文件中保存的是本地日期 "2026-07-13"
        import json

        with open(temp_path, encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("test_job") == "2026-07-13", (
            f"状态应保存本地日期 '2026-07-13'，实际为 '{state.get('test_job')}'"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()


def test_should_execute_cron_today_local_date_rollover():
    """本地日期翻转后应重新执行任务

    场景：任务在本地 2026-07-12 执行（记录本地日期 2026-07-12），
    下一次本地 2026-07-13 触发时，应识别为"新的一天"并允许执行。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_local_rollover.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path

    try:
        day1 = date(2026, 7, 12)
        day2 = date(2026, 7, 13)

        with patch(
            "lifeprism.server.services.schedule_service.get_local_today",
            return_value=day1,
        ):
            # 第一天：执行并记录状态
            assert service._should_execute_cron_today("job") is True
            service._save_cron_state("job", day1.isoformat())
            assert service._should_execute_cron_today("job") is False

        with patch(
            "lifeprism.server.services.schedule_service.get_local_today",
            return_value=day2,
        ):
            # 第二天：应允许执行（本地日期已翻转）
            assert service._should_execute_cron_today("job") is True
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()


# ==================== Seam 6: _execute_cron_with_state() 使用本地日期 ====================


@pytest.mark.asyncio
async def test_execute_cron_with_state_records_local_date():
    """_execute_cron_with_state() 执行后应保存本地日期

    场景：本地日期 2026-07-13
    - 应记录本地日期 "2026-07-13"
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_local_exec.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path

    mock_local_today = date(2026, 7, 13)

    execution_count = 0

    async def test_func():
        nonlocal execution_count
        execution_count += 1

    try:
        with patch(
            "lifeprism.server.services.schedule_service.get_local_today",
            return_value=mock_local_today,
        ):
            await service._execute_cron_with_state(test_func, "test_job")

        assert execution_count == 1, "任务应被执行一次"

        # 验证保存的是本地日期
        import json

        with open(temp_path, encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("test_job") == "2026-07-13", (
            f"应保存本地日期 '2026-07-13'，实际为 '{state.get('test_job')}'"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()


# ==================== Seam 7: _dreaming() 模块函数使用本地时区计算昨天 ====================


@pytest.mark.asyncio
async def test_dreaming_uses_local_yesterday():
    """_dreaming() 计算"昨天"应基于本地日期

    场景：本地日期 2026-07-13
    - 本地昨天：2026-07-12
    - 应传本地昨天 "2026-07-12" 给 dreaming()
    """
    from lifeprism.server.services import schedule_service

    captured_date = []

    async def mock_dreaming(date):
        captured_date.append(date)

    async def mock_generate_diary_ai_summary(date):
        pass

    mock_sync_service = MagicMock()
    mock_sync_service.incremental_sync = AsyncMock(return_value={"message": "ok"})

    mock_local_today = date(2026, 7, 13)

    with patch(
        "lifeprism.server.services.schedule_service.get_local_today",
        return_value=mock_local_today,
    ):
        with patch(
            "lifeprism.server.services.schedule_service.dreaming",
            mock_dreaming,
        ):
            with patch(
                "lifeprism.server.services.schedule_service.generate_diary_ai_summary",
                mock_generate_diary_ai_summary,
            ):
                with patch(
                    "lifeprism.server.services.schedule_service.SyncService",
                    return_value=mock_sync_service,
                ):
                    with patch(
                        "lifeprism.server.services.schedule_service.settings"
                    ) as mock_settings:
                        mock_settings.auto_diary_summary = True
                        mock_settings.auto_update_memory = True
                        await schedule_service._dreaming()

    assert len(captured_date) == 1, "dreaming() 应被调用一次"
    assert captured_date[0] == "2026-07-12", (
        f"应传本地昨天 '2026-07-12'，实际为 '{captured_date[0]}'"
    )


# ==================== Seam 8: _add_system_jobs() 使用本地时间 ====================


def test_add_system_jobs_uses_local_time_for_compensation_check():
    """_add_system_jobs() 判断"是否过触发时间"应基于本地时间

    场景：本地时间 2026-07-12 11:00
    - Cron 表达式 "0 10 * * *"（本地 10:00）
    - 本地 11:00 > 本地 10:00，已过触发时间，应触发补偿执行
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()

    # 本地 11:00，已过本地 10:00，应触发补偿
    local_after = datetime(2026, 7, 12, 11, 0, 0)

    with patch("lifeprism.server.services.schedule_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = local_after
        mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

        with patch.object(service, "_should_execute_cron_today", return_value=True):
            with patch.object(service, "add_interval_job"):
                with patch.object(service, "add_cron_job"):
                    with patch(
                        "lifeprism.server.services.schedule_service.asyncio"
                    ) as mock_asyncio:
                        mock_loop = MagicMock()
                        mock_asyncio.get_event_loop.return_value = mock_loop

                        service._scheduler = mock_scheduler
                        service._system_jobs = [
                            {
                                "func": AsyncMock(),
                                "trigger": "cron",
                                "kwargs": {"cron_expr": "0 10 * * *"},
                                "job_id": "update_memory",
                            }
                        ]
                        service._add_system_jobs()

                        assert mock_loop.create_task.called, (
                            "本地 11:00 已过本地 10:00，应触发补偿执行"
                        )


def test_add_system_jobs_no_compensation_before_local_trigger_time():
    """本地 09:00 未过本地 10:00，不应触发补偿执行"""
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()

    # 本地 09:00 < 本地 10:00，未过触发时间
    local_before = datetime(2026, 7, 12, 9, 0, 0)

    with patch("lifeprism.server.services.schedule_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = local_before
        mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

        with patch.object(service, "_should_execute_cron_today", return_value=True):
            with patch.object(service, "add_interval_job"):
                with patch.object(service, "add_cron_job"):
                    with patch(
                        "lifeprism.server.services.schedule_service.asyncio"
                    ) as mock_asyncio:
                        mock_loop = MagicMock()
                        mock_asyncio.get_event_loop.return_value = mock_loop

                        service._scheduler = mock_scheduler
                        service._system_jobs = [
                            {
                                "func": AsyncMock(),
                                "trigger": "cron",
                                "kwargs": {"cron_expr": "0 10 * * *"},
                                "job_id": "update_memory",
                            }
                        ]
                        service._add_system_jobs()

                        assert not mock_loop.create_task.called, (
                            "本地 09:00 未过本地 10:00，不应触发补偿执行"
                        )


# ==================== Seam 9: TEST_MODE 下 cron 表达式基于 UTC ====================


def test_test_mode_cron_expr_uses_utc_time():
    """TEST_MODE 下生成的 cron 表达式应基于 UTC 时间

    Issue #29 未修改 TEST_MODE 相关逻辑，TEST_MODE 下仍使用 UTC 时间生成 cron 表达式。
    """
    import lifeprism.server.services.schedule_service as ss_module

    original_test_mode = ss_module.TEST_MODE

    try:
        ss_module.TEST_MODE = True

        mock_utc_time = datetime(2026, 7, 12, 5, 30, 0, tzinfo=timezone.utc)

        mock_settings = MagicMock()
        mock_settings.auto_summary_session = False
        mock_settings.auto_update_memory = True
        mock_settings.auto_diary_summary = False

        with patch.object(ss_module, "settings", mock_settings):
            with patch("lifeprism.server.services.schedule_service.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_utc_time
                mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

                service = ss_module.ScheduleService()

        cron_jobs = [j for j in service._system_jobs if j["trigger"] == "cron"]
        assert len(cron_jobs) == 1, "应注册一个 cron 任务"

        cron_expr = cron_jobs[0]["kwargs"]["cron_expr"]
        parts = cron_expr.split()
        # TEST_MODE 仍基于 UTC 05:30 + 1 分钟 = UTC 05:31
        assert parts[0] == "31", f"cron 分钟应为 31（UTC），实际为 {parts[0]}"
        assert parts[1] == "5", f"cron 小时应为 5（UTC），实际为 {parts[1]}"
    finally:
        ss_module.TEST_MODE = original_test_mode


# ==================== Seam 10: add_cron_job 状态记录使用本地日期 ====================


@pytest.mark.asyncio
async def test_add_cron_job_wrapped_func_records_local_date():
    """add_cron_job() 包装函数执行后应保存本地日期

    add_cron_job 内部会包装传入的 func，执行后调用 _save_cron_state。
    验证保存的日期是本地日期。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_local_cron.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path
    service._scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "cron_state_job"
    service._scheduler.add_job.return_value = mock_job

    call_count = 0

    async def test_func():
        nonlocal call_count
        call_count += 1

    try:
        service.add_cron_job(test_func, "0 10 * * *", job_id="cron_state_job")

        wrapped = service._scheduler.add_job.call_args.args[0]

        mock_local_today = date(2026, 7, 13)

        with patch(
            "lifeprism.server.services.schedule_service.get_local_today",
            return_value=mock_local_today,
        ):
            await wrapped()

        assert call_count == 1, "原函数应被调用一次"

        import json

        with open(temp_path, encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("cron_state_job") == "2026-07-13", (
            f"应保存本地日期 '2026-07-13'，实际为 '{state.get('cron_state_job')}'"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()
