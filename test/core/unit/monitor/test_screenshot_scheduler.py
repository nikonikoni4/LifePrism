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

    first = scheduler.evaluate(30.0, "2026-04-02T10:00:30", window, True, "seg-1", [])
    assert len(first) == 1
    assert first[0].reason is CaptureReason.ACTIVE
    assert first[0].engaged_segment_id == "seg-1"
    assert first[0].frequency_level == 2

    repeat = scheduler.evaluate(90.0, "2026-04-02T10:01:30", window, True, "seg-1", [])
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

    first = scheduler.evaluate(10.0, "2026-04-02T10:00:10", window, True, "seg-1", [10.0])
    assert first == []

    first_due = scheduler.evaluate(10.7, "2026-04-02T10:00:10.700000", window, True, "seg-1", [10.0])
    assert len(first_due) == 1
    assert first_due[0].reason is CaptureReason.ENTER
    assert first_due[0].engaged_segment_id == "seg-1"
    assert first_due[0].frequency_level == 2

    cooldown_blocked = scheduler.evaluate(
        12.7,
        "2026-04-02T10:00:12.700000",
        window,
        True,
        "seg-1",
        [12.0],
    )
    assert cooldown_blocked == []

    after_cooldown = scheduler.evaluate(
        17.0,
        "2026-04-02T10:00:17",
        window,
        True,
        "seg-1",
        [16.0],
    )
    assert len(after_cooldown) == 1
    assert after_cooldown[0].reason is CaptureReason.ENTER
