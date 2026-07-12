"""ScheduleService UTC 时区迁移测试

验证定时任务服务在 UTC 时区迁移后的行为正确性。

测试 seam:
- Seam 1: _SYSTEM_CRON_JOB_TIME 常量 - Cron 表达式对应 UTC 02:00（本地 10:00）
- Seam 2: start() - AsyncIOScheduler 初始化时显式设置 UTC 时区
- Seam 3: add_cron_job() - CronTrigger 显式设置 UTC 时区
- Seam 4: add_interval_job() - IntervalTrigger 显式设置 UTC 时区
- Seam 5: _should_execute_cron_today() - "今天"判断基于 UTC 日期
- Seam 6: _execute_cron_with_state() - 状态记录使用 UTC 日期
- Seam 7: _dreaming() 模块函数 - "昨天"计算基于 UTC
- Seam 8: _add_system_jobs() - "过触发时间"判断基于 UTC 时间

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- .scratch/utc-timezone-migration/05-schedule-service-migration.md
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: _SYSTEM_CRON_JOB_TIME 常量 ====================


def test_system_cron_job_time_is_utc_02():
    """_SYSTEM_CRON_JOB_TIME 应为 "0 2 * * *"（UTC 02:00 = 北京时间 10:00）

    迁移前: "0 10 * * *"（本地时区 10:00）
    迁移后: "0 2 * * *"（UTC 02:00 = 本地 UTC+8 10:00）
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    assert ScheduleService._SYSTEM_CRON_JOB_TIME == "0 2 * * *"


# ==================== Seam 2: start() 设置 UTC 时区 ====================


def test_start_initializes_scheduler_with_utc_timezone():
    """start() 初始化 AsyncIOScheduler 时应显式传入 UTC 时区

    APScheduler 默认使用系统本地时区，迁移后必须显式设置为 UTC，
    否则服务器时区变化会导致 Cron 触发时间错位。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()
    mock_scheduler.start = MagicMock()

    with patch(
        "lifeprism.server.services.schedule_service.AsyncIOScheduler"
    ) as mock_scheduler_cls:
        mock_scheduler_cls.return_value = mock_scheduler
        # 模拟 run_mode 为 full 以跳过守卫
        with patch(
            "lifeprism.server.services.schedule_service.settings"
        ) as mock_settings:
            mock_settings.run_mode = "full"
            service.start()

    # 验证 AsyncIOScheduler 被调用时传入了 timezone 参数
    assert mock_scheduler_cls.called, "应创建 AsyncIOScheduler 实例"
    call_kwargs = mock_scheduler_cls.call_args.kwargs
    assert "timezone" in call_kwargs, "AsyncIOScheduler 必须显式设置 timezone"
    # timezone 可以是字符串 'UTC' 或 pytz.UTC 对象
    tz_value = call_kwargs["timezone"]
    tz_str = str(tz_value)
    assert tz_str == "UTC", f"timezone 应为 UTC，实际为 {tz_str}"


# ==================== Seam 3: add_cron_job() 设置 UTC 时区 ====================


def test_add_cron_job_uses_utc_timezone_for_trigger():
    """add_cron_job() 创建 CronTrigger 时应显式传入 UTC 时区

    CronTrigger.from_crontab 默认使用本地时区，迁移后必须显式设置为 UTC。
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

    with patch(
        "lifeprism.server.services.schedule_service.CronTrigger"
    ) as mock_cron_trigger_cls:
        mock_trigger = MagicMock()
        mock_cron_trigger_cls.from_crontab.return_value = mock_trigger

        service.add_cron_job(dummy_func, "0 2 * * *", job_id="test_job")

        # 验证 from_crontab 被调用时传入了 timezone 参数
        assert mock_cron_trigger_cls.from_crontab.called
        call_args = mock_cron_trigger_cls.from_crontab.call_args
        call_kwargs = call_args.kwargs
        assert "timezone" in call_kwargs, "CronTrigger.from_crontab 必须设置 timezone"
        tz_value = call_kwargs["timezone"]
        assert str(tz_value) == "UTC", f"timezone 应为 UTC，实际为 {tz_value}"


# ==================== Seam 4: add_interval_job() 设置 UTC 时区 ====================


def test_add_interval_job_uses_utc_timezone_for_trigger():
    """add_interval_job() 创建 IntervalTrigger 时应显式传入 UTC 时区

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

        service.add_interval_job(dummy_func, seconds=30, job_id="test_job")

        assert mock_interval_trigger_cls.called
        call_kwargs = mock_interval_trigger_cls.call_args.kwargs
        assert "timezone" in call_kwargs, "IntervalTrigger 必须设置 timezone"
        tz_value = call_kwargs["timezone"]
        assert str(tz_value) == "UTC", f"timezone 应为 UTC，实际为 {tz_value}"


# ==================== Seam 5: _should_execute_cron_today() 使用 UTC 日期 ====================


def test_should_execute_cron_today_uses_utc_date():
    """_should_execute_cron_today() 的"今天"判断应基于 UTC 日期

    场景：UTC 时间 2026-07-12 22:00（本地 UTC+8 为 2026-07-13 06:00）
    - UTC 日期：2026-07-12
    - 本地日期：2026-07-13
    - 如果任务在 UTC 22:00 执行并记录 UTC 日期，再次触发时应正确识别为"今天已执行"。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    # 使用临时状态文件
    temp_path = Path("test_temp") / ".schedule_state_utc_test.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path

    try:
        # 模拟 UTC 时间 2026-07-12 22:00（本地 2026-07-13 06:00）
        mock_utc_time = datetime(2026, 7, 12, 22, 0, 0, tzinfo=timezone.utc)

        with patch(
            "lifeprism.server.services.schedule_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = mock_utc_time

            # 第一次判断：没有执行记录，应返回 True
            assert service._should_execute_cron_today("test_job") is True

            # 模拟任务执行后保存状态（应保存 UTC 日期 "2026-07-12"）
            service._save_cron_state("test_job", mock_utc_time.strftime("%Y-%m-%d"))

            # 第二次判断：同一天（UTC 日期），应返回 False
            assert service._should_execute_cron_today("test_job") is False

        # 验证状态文件中保存的是 UTC 日期 "2026-07-12"，而非本地日期 "2026-07-13"
        import json

        with open(temp_path, encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("test_job") == "2026-07-12", (
            f"状态应保存 UTC 日期 '2026-07-12'，实际为 '{state.get('test_job')}'"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()


def test_should_execute_cron_today_utc_date_rollover():
    """UTC 日期翻转后应重新执行任务

    场景：任务在 UTC 2026-07-12 02:00 执行（记录 UTC 日期 2026-07-12），
    下一次 UTC 2026-07-13 02:00 触发时，应识别为"新的一天"并允许执行。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_utc_rollover.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path

    try:
        # 第一天 UTC 02:00
        day1 = datetime(2026, 7, 12, 2, 0, 0, tzinfo=timezone.utc)
        # 第二天 UTC 02:00
        day2 = datetime(2026, 7, 13, 2, 0, 0, tzinfo=timezone.utc)

        with patch(
            "lifeprism.server.services.schedule_service.datetime"
        ) as mock_datetime:
            # 第一天：执行并记录状态
            mock_datetime.now.return_value = day1
            assert service._should_execute_cron_today("job") is True
            service._save_cron_state("job", day1.strftime("%Y-%m-%d"))
            assert service._should_execute_cron_today("job") is False

            # 第二天：应允许执行（UTC 日期已翻转）
            mock_datetime.now.return_value = day2
            assert service._should_execute_cron_today("job") is True
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()


# ==================== Seam 6: _execute_cron_with_state() 使用 UTC 日期 ====================


@pytest.mark.asyncio
async def test_execute_cron_with_state_records_utc_date():
    """_execute_cron_with_state() 执行后应保存 UTC 日期

    场景：UTC 时间 2026-07-12 20:00（本地 2026-07-13 04:00）
    - 应记录 UTC 日期 "2026-07-12"，而非本地日期 "2026-07-13"
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_utc_exec.json"
    temp_path.parent.mkdir(exist_ok=True)
    service._state_file_path = temp_path

    # UTC 2026-07-12 20:00 = 本地 2026-07-13 04:00
    mock_utc_time = datetime(2026, 7, 12, 20, 0, 0, tzinfo=timezone.utc)

    execution_count = 0

    async def test_func():
        nonlocal execution_count
        execution_count += 1

    try:
        with patch(
            "lifeprism.server.services.schedule_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = mock_utc_time
            await service._execute_cron_with_state(test_func, "test_job")

        assert execution_count == 1, "任务应被执行一次"

        # 验证保存的是 UTC 日期
        import json

        with open(temp_path, encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("test_job") == "2026-07-12", (
            f"应保存 UTC 日期 '2026-07-12'，实际为 '{state.get('test_job')}'"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()


# ==================== Seam 7: _dreaming() 模块函数使用 UTC 计算昨天 ====================


@pytest.mark.asyncio
async def test_dreaming_uses_utc_yesterday():
    """_dreaming() 计算"昨天"应基于 UTC 日期

    场景：UTC 时间 2026-07-12 02:00（本地 2026-07-12 10:00）
    - UTC 昨天：2026-07-11
    - 本地昨天：2026-07-11（两者一致，因任务在 UTC 02:00 触发）

    场景：UTC 时间 2026-07-12 20:00（本地 2026-07-13 04:00）
    - UTC 昨天：2026-07-11
    - 本地昨天：2026-07-12
    - 迁移后应使用 UTC 昨天（与数据库中 UTC 时间戳一致）
    """
    from lifeprism.server.services import schedule_service

    # 捕获传给 dreaming() 的 date 参数
    captured_date = []

    async def mock_dreaming(date):
        captured_date.append(date)

    async def mock_generate_diary_ai_summary(date):
        pass

    # 模拟 SyncService.incremental_sync
    mock_sync_service = MagicMock()
    mock_sync_service.incremental_sync = AsyncMock(
        return_value={"message": "ok"}
    )

    # UTC 2026-07-12 20:00（本地 2026-07-13 04:00）
    mock_utc_time = datetime(2026, 7, 12, 20, 0, 0, tzinfo=timezone.utc)

    with patch(
        "lifeprism.server.services.schedule_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = mock_utc_time

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

    # 验证传给 dreaming() 的 date 是 UTC 昨天 "2026-07-11"
    assert len(captured_date) == 1, "dreaming() 应被调用一次"
    assert captured_date[0] == "2026-07-11", (
        f"应传 UTC 昨天 '2026-07-11'，实际为 '{captured_date[0]}'"
    )


# ==================== Seam 8: _add_system_jobs() 使用 UTC 时间 ====================


def test_add_system_jobs_uses_utc_time_for_compensation_check():
    """_add_system_jobs() 判断"是否过触发时间"应基于 UTC 时间

    场景：UTC 时间 2026-07-12 03:00（本地 2026-07-12 11:00）
    - Cron 表达式 "0 2 * * *"（UTC 02:00）
    - UTC 03:00 > UTC 02:00，已过触发时间，应触发补偿执行
    - 如果错误使用本地时间 11:00 > 02:00，也会触发，但语义错误

    场景：UTC 时间 2026-07-12 01:00（本地 2026-07-12 09:00）
    - Cron 表达式 "0 2 * * *"（UTC 02:00）
    - UTC 01:00 < UTC 02:00，未过触发时间，不应触发补偿
    - 如果错误使用本地时间 09:00 > 02:00，会错误触发补偿
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()

    # 测试场景 1：UTC 03:00，已过 UTC 02:00，应触发补偿
    utc_after = datetime(2026, 7, 12, 3, 0, 0, tzinfo=timezone.utc)

    with patch(
        "lifeprism.server.services.schedule_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = utc_after

        with patch.object(service, "_should_execute_cron_today", return_value=True):
            with patch.object(service, "add_interval_job"):
                with patch.object(service, "add_cron_job"):
                    with patch(
                        "lifeprism.server.services.schedule_service.asyncio"
                    ) as mock_asyncio:
                        mock_loop = MagicMock()
                        mock_asyncio.get_event_loop.return_value = mock_loop

                        service._scheduler = mock_scheduler
                        # 手动构造 system_jobs（使用 UTC cron 表达式）
                        service._system_jobs = [
                            {
                                "func": AsyncMock(),
                                "trigger": "cron",
                                "kwargs": {"cron_expr": "0 2 * * *"},
                                "job_id": "update_memory",
                            }
                        ]
                        service._add_system_jobs()

                        # 验证触发了补偿执行
                        assert mock_loop.create_task.called, (
                            "UTC 03:00 已过 UTC 02:00，应触发补偿执行"
                        )


def test_add_system_jobs_no_compensation_before_utc_trigger_time():
    """UTC 01:00 未过 UTC 02:00，不应触发补偿执行"""
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    mock_scheduler = MagicMock()

    # UTC 01:00 < UTC 02:00，未过触发时间
    utc_before = datetime(2026, 7, 12, 1, 0, 0, tzinfo=timezone.utc)

    with patch(
        "lifeprism.server.services.schedule_service.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = utc_before

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
                                "kwargs": {"cron_expr": "0 2 * * *"},
                                "job_id": "update_memory",
                            }
                        ]
                        service._add_system_jobs()

                        # 验证未触发补偿执行
                        assert not mock_loop.create_task.called, (
                            "UTC 01:00 未过 UTC 02:00，不应触发补偿执行"
                        )


# ==================== Seam 9: TEST_MODE 下 cron 表达式基于 UTC ====================


def test_test_mode_cron_expr_uses_utc_time():
    """TEST_MODE 下生成的 cron 表达式应基于 UTC 时间

    迁移后 CronTrigger 使用 UTC 时区，TEST_MODE 下生成的 cron_expr
    也必须基于 UTC 时间，否则测试模式下任务不会在预期时间触发。
    """
    import lifeprism.server.services.schedule_service as ss_module

    original_test_mode = ss_module.TEST_MODE

    try:
        ss_module.TEST_MODE = True

        # 模拟 UTC 时间 2026-07-12 05:30（本地 13:30）
        mock_utc_time = datetime(2026, 7, 12, 5, 30, 0, tzinfo=timezone.utc)

        # 用 mock_settings 替换 schedule_service 模块中的 settings 引用，
        # 避免触及真实 SettingsManager 的只读 property
        mock_settings = MagicMock()
        mock_settings.auto_summary_session = False
        mock_settings.auto_update_memory = True
        mock_settings.auto_diary_summary = False

        with patch.object(ss_module, "settings", mock_settings):
            with patch(
                "lifeprism.server.services.schedule_service.datetime"
            ) as mock_datetime:
                # 保留 datetime 构造函数（用于 datetime(...) 调用），
                # 同时让 now() 返回 mock UTC 时间
                mock_datetime.now.return_value = mock_utc_time
                mock_datetime.side_effect = lambda *a, **k: datetime(*a, **k)

                service = ss_module.ScheduleService()

        # 找到 cron 类型的系统任务
        cron_jobs = [j for j in service._system_jobs if j["trigger"] == "cron"]
        assert len(cron_jobs) == 1, "应注册一个 cron 任务"

        cron_expr = cron_jobs[0]["kwargs"]["cron_expr"]
        parts = cron_expr.split()
        # 应基于 UTC 05:30 + 1 分钟 = UTC 05:31
        assert parts[0] == "31", f"cron 分钟应为 31（UTC），实际为 {parts[0]}"
        assert parts[1] == "5", f"cron 小时应为 5（UTC），实际为 {parts[1]}"
    finally:
        ss_module.TEST_MODE = original_test_mode


# ==================== Seam 10: add_cron_job 状态记录使用 UTC ====================


@pytest.mark.asyncio
async def test_add_cron_job_wrapped_func_records_utc_date():
    """add_cron_job() 包装函数执行后应保存 UTC 日期

    add_cron_job 内部会包装传入的 func，执行后调用 _save_cron_state。
    验证保存的日期是 UTC 日期。
    """
    from lifeprism.server.services.schedule_service import ScheduleService

    service = ScheduleService()
    temp_path = Path("test_temp") / ".schedule_state_utc_cron.json"
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
        service.add_cron_job(test_func, "0 2 * * *", job_id="cron_state_job")

        # 获取包装后的函数（add_job 的第一个位置参数）
        wrapped = service._scheduler.add_job.call_args.args[0]

        # UTC 2026-07-12 23:00（本地 2026-07-13 07:00）
        mock_utc_time = datetime(2026, 7, 12, 23, 0, 0, tzinfo=timezone.utc)

        with patch(
            "lifeprism.server.services.schedule_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = mock_utc_time
            await wrapped()

        assert call_count == 1, "原函数应被调用一次"

        # 验证保存的是 UTC 日期
        import json

        with open(temp_path, encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("cron_state_job") == "2026-07-12", (
            f"应保存 UTC 日期 '2026-07-12'，实际为 '{state.get('cron_state_job')}'"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if temp_path.parent.exists() and not list(temp_path.parent.iterdir()):
            temp_path.parent.rmdir()
