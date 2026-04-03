import shutil
import uuid
from pathlib import Path

from lifeprism.monitor.screenshot.cleanup_worker import ScreenshotCleanupWorker
from lifeprism.monitor.screenshot.input_tracker import InputActivityTracker
from lifeprism.monitor.screenshot.policy import get_frequency_policy
from lifeprism.monitor.screenshot.scheduler import ScreenshotScheduler
from lifeprism.monitor.screenshot.models import WindowContext
from lifeprism.monitor.windows_monitor.runtime import MonitorRuntime


def _make_temp_dir() -> Path:
    temp_dir = Path.cwd() / f"test_tmp_runtime_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_runtime_emits_scheduled_active_and_enter():
    temp_dir = _make_temp_dir()
    try:
        runtime = MonitorRuntime.for_test(
            data_root=temp_dir,
            time_points=[0.0, 10.0, 20.0, 30.0, 31.0, 60.0],
            window_snapshots=[
                {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
                {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
                {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
                {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
                {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
                {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
            ],
            input_script=[
                (0.0, "keyboard", "a"),
                (10.0, "keyboard", "b"),
                (20.0, "keyboard", "c"),
                (30.0, "keyboard", "enter"),
            ],
        )

        runtime.run_for_ticks()

        with runtime.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT capture_reason, engaged_segment_id, frequency_level
                FROM screen_captures
                ORDER BY captured_at ASC
                """
            )
            rows = cursor.fetchall()

        reasons = [row["capture_reason"] for row in rows]
        assert reasons.count("active") == 1
        assert reasons.count("enter") == 1
        assert reasons.count("scheduled") == 1

        active_row = next(row for row in rows if row["capture_reason"] == "active")
        enter_row = next(row for row in rows if row["capture_reason"] == "enter")
        scheduled_row = next(row for row in rows if row["capture_reason"] == "scheduled")

        assert active_row["engaged_segment_id"] == enter_row["engaged_segment_id"]
        assert active_row["engaged_segment_id"] is not None
        assert active_row["frequency_level"] == 2
        assert enter_row["frequency_level"] == 2
        assert scheduled_row["engaged_segment_id"] is None
        assert scheduled_row["frequency_level"] is None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class _FailingStore:
    def __init__(self):
        self.calls = 0

    def capture(self, request):
        self.calls += 1
        raise RuntimeError("capture failed")


class _NoopProvider:
    def list_expired_captures(self, cutoff_iso: str):
        return []


def test_runtime_logs_and_continues_when_capture_fails():
    now = {"value": 0.0}
    tracker = InputActivityTracker(
        keyboard_keepalive_seconds=12,
        mouse_keepalive_seconds=6,
        time_source=lambda: now["value"],
        segment_id_factory=lambda: "seg-test",
    )
    tracker.record_keyboard_event("a")
    failing_store = _FailingStore()
    runtime = MonitorRuntime(
        window_context_source=lambda: WindowContext(
            app="Code.exe",
            title="scheduler.py",
            is_afk=False,
        ),
        input_tracker=tracker,
        scheduler=ScreenshotScheduler(
            policy=get_frequency_policy(2),
            scheduled_interval_seconds=60,
            enter_delay_ms=700,
        ),
        screenshot_store=failing_store,
        screenshot_provider=_NoopProvider(),
        cleanup_worker=ScreenshotCleanupWorker(
            provider=_NoopProvider(),
            data_root=Path.cwd(),
            retention_days=3,
        ),
        input_listener=None,
        db_manager=None,
        time_source=lambda: now["value"],
        iso_time_source=lambda: "2026-04-02T10:01:00",
        scheduler_sleep_seconds=0.0,
        cleanup_interval_seconds=86400,
        sleep_func=lambda seconds: None,
    )

    runtime._run_scheduler_tick()
    now["value"] = 60.0
    runtime._run_scheduler_tick()

    assert failing_store.calls == 1
