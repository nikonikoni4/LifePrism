import pytest
from lifeprism.monitor.screenshot.input_tracker import InputActivityTracker


@pytest.mark.core
def test_keyboard_activity_enters_engaged_and_creates_segment():
    tracker = InputActivityTracker(
        keyboard_keepalive_seconds=12,
        mouse_keepalive_seconds=6,
        time_source=lambda: 100.0,
        segment_id_factory=lambda: "seg-1",
    )

    tracker.record_keyboard_event("a")
    snapshot = tracker.snapshot()

    assert snapshot.engaged is True
    assert snapshot.engaged_segment_id == "seg-1"


@pytest.mark.core
def test_segment_expires_after_both_keepalives_end():
    now = {"value": 100.0}
    tracker = InputActivityTracker(
        keyboard_keepalive_seconds=12,
        mouse_keepalive_seconds=6,
        time_source=lambda: now["value"],
        segment_id_factory=lambda: "seg-2",
    )

    tracker.record_keyboard_event("ctrl")
    now["value"] = 113.1
    snapshot = tracker.snapshot()

    assert snapshot.engaged is False
    assert snapshot.engaged_segment_id is None


@pytest.mark.core
def test_enter_event_is_buffered_for_scheduler():
    tracker = InputActivityTracker(
        keyboard_keepalive_seconds=12,
        mouse_keepalive_seconds=6,
        time_source=lambda: 100.0,
        segment_id_factory=lambda: "seg-3",
    )

    tracker.record_keyboard_event("enter")

    assert tracker.consume_enter_events() == [100.0]
    assert tracker.consume_enter_events() == []
