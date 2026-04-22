import pytest
from lifeprism.monitor.screenshot.models import CaptureReason, WindowContext
from lifeprism.monitor.screenshot.policy import get_frequency_policy
from lifeprism.monitor.screenshot.scheduler import ScreenshotScheduler


@pytest.mark.core
def test_afk_blocks_all_requests():
    scheduler = ScreenshotScheduler(
        policy=get_frequency_policy(2),
        scheduled_interval_seconds=60,
        enter_delay_ms=700,
    )
    requests = scheduler.evaluate(
        now_epoch=100.0,
        now_iso="2026-04-02T10:00:00",
        window=WindowContext(app="Code.exe", title="main.py", is_afk=True),
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )

    assert requests == []


@pytest.mark.core
def test_scheduled_capture_has_no_segment():
    scheduler = ScreenshotScheduler(
        policy=get_frequency_policy(2),
        scheduled_interval_seconds=60,
        enter_delay_ms=700,
    )
    first = scheduler.evaluate(
        now_epoch=0.0,
        now_iso="2026-04-02T10:00:00",
        window=WindowContext(app="Code.exe", title="main.py", is_afk=False),
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )
    requests = scheduler.evaluate(
        now_epoch=60.0,
        now_iso="2026-04-02T10:01:00",
        window=WindowContext(app="Code.exe", title="main.py", is_afk=False),
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )

    assert first == []
    assert len(requests) == 1
    assert requests[0].reason is CaptureReason.SCHEDULED
    assert requests[0].engaged_segment_id is None
    assert requests[0].frequency_level is None


@pytest.mark.core
def test_scheduler_waits_one_interval_from_first_absolute_tick():
    scheduler = ScreenshotScheduler(
        policy=get_frequency_policy(2),
        scheduled_interval_seconds=60,
        enter_delay_ms=700,
    )
    window = WindowContext(app="Code.exe", title="main.py", is_afk=False)

    first = scheduler.evaluate(
        now_epoch=1_700_000_000.0,
        now_iso="2026-04-02T10:00:00",
        window=window,
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )
    second = scheduler.evaluate(
        now_epoch=1_700_000_060.0,
        now_iso="2026-04-02T10:01:00",
        window=window,
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )

    assert first == []
    assert len(second) == 1
    assert second[0].reason is CaptureReason.SCHEDULED


@pytest.mark.core
def test_active_capture_triggers_first_and_repeat_in_same_segment():
    scheduler = ScreenshotScheduler(
        policy=get_frequency_policy(2),
        scheduled_interval_seconds=999,
        enter_delay_ms=700,
    )
    window = WindowContext(app="Code.exe", title="main.py", is_afk=False)

    assert scheduler.evaluate(0.0, "2026-04-02T10:00:00", window, True, "seg-1", []) == []

    # L2: first_active_after_seconds=45
    first = scheduler.evaluate(45.0, "2026-04-02T10:00:45", window, True, "seg-1", [])
    assert len(first) == 1
    assert first[0].reason is CaptureReason.ACTIVE
    assert first[0].engaged_segment_id == "seg-1"
    assert first[0].frequency_level == 2

    # L2: repeat_active_every_seconds=180
    repeat = scheduler.evaluate(225.0, "2026-04-02T10:03:45", window, True, "seg-1", [])
    assert len(repeat) == 1
    assert repeat[0].reason is CaptureReason.ACTIVE
    assert repeat[0].engaged_segment_id == "seg-1"


@pytest.mark.core
def test_enter_capture_obeys_cooldown():
    scheduler = ScreenshotScheduler(
        policy=get_frequency_policy(2),
        scheduled_interval_seconds=999,
        enter_delay_ms=700,
    )
    window = WindowContext(app="Code.exe", title="main.py", is_afk=False)

    scheduler.evaluate(0.0, "2026-04-02T10:00:00", window, True, "seg-1", [])

    # Enter事件在10.0s，延迟700ms后还未到
    first = scheduler.evaluate(10.0, "2026-04-02T10:00:10", window, True, "seg-1", [10.0])
    assert first == []

    # 10.7s时Enter延迟到达，触发第一张Enter截图
    first_due = scheduler.evaluate(10.7, "2026-04-02T10:00:10.700000", window, True, "seg-1", [10.0])
    assert len(first_due) == 1
    assert first_due[0].reason is CaptureReason.ENTER
    assert first_due[0].engaged_segment_id == "seg-1"
    assert first_due[0].frequency_level == 2

    # 在冷却期内（90s内）尝试触发Enter截图，应该被阻止
    cooldown_blocked = scheduler.evaluate(
        20.0,
        "2026-04-02T10:00:20",
        window,
        True,
        "seg-1",
        [19.0],
    )
    assert cooldown_blocked == []

    # L2: enter_cooldown_seconds=90，从10.7s开始，90s后是100.7s
    # 使用101.5s避免与45s的第一张active截图时间点冲突
    after_cooldown = scheduler.evaluate(
        101.5,
        "2026-04-02T10:01:41.500000",
        window,
        True,
        "seg-1",
        [100.5],
    )
    # 此时会同时触发active截图（45s后第一张）和enter截图
    # 只验证enter截图存在即可
    enter_captures = [r for r in after_cooldown if r.reason is CaptureReason.ENTER]
    assert len(enter_captures) == 1
