import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from lifeprism.config.settings_manager import settings
from lifeprism.monitor.provider.screenshot_data_provider import ScreenshotDataProvider
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
from lifeprism.monitor.screenshot.backends import MSSCaptureBackend, PynputInputListener
from lifeprism.monitor.screenshot.cleanup_worker import ScreenshotCleanupWorker
from lifeprism.monitor.screenshot.input_tracker import InputActivityTracker
from lifeprism.monitor.screenshot.models import WindowContext
from lifeprism.monitor.screenshot.policy import get_frequency_policy
from lifeprism.monitor.screenshot.scheduler import ScreenshotScheduler
from lifeprism.monitor.screenshot.store import ScreenshotStore
from lifeprism.monitor.windows_monitor.monitor import WindowMonitor
from lifeprism.repository.database_manager import DatabaseManager
from lifeprism.repository.lw_table_manager import LWTableManager
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)


class _NoopInputListener:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


class MonitorRuntime:
    """组合 WindowMonitor、输入跟踪、调度器、截图存储与清理逻辑。"""

    def __init__(
        self,
        *,
        window_context_source: Callable[[], WindowContext],
        input_tracker: InputActivityTracker,
        scheduler: ScreenshotScheduler,
        screenshot_store: ScreenshotStore,
        screenshot_provider: ScreenshotDataProvider,
        cleanup_worker: ScreenshotCleanupWorker,
        input_listener,
        db_manager: DatabaseManager,
        monitor: Optional[WindowMonitor] = None,
        time_source: Callable[[], float] | None = None,
        iso_time_source: Callable[[], str] | None = None,
        scheduler_sleep_seconds: float = 1.0,
        cleanup_interval_seconds: int = 86400,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.window_context_source = window_context_source
        self.input_tracker = input_tracker
        self.scheduler = scheduler
        self.screenshot_store = screenshot_store
        self.screenshot_provider = screenshot_provider
        self.cleanup_worker = cleanup_worker
        self.input_listener = input_listener
        self.db_manager = db_manager
        self.monitor = monitor
        self.time_source = time_source or time.time
        self.iso_time_source = iso_time_source or (lambda: datetime.now().replace(microsecond=0).isoformat())
        self.scheduler_sleep_seconds = scheduler_sleep_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.sleep_func = sleep_func
        self._running = False
        self._pending_enter_events: List[float] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None

    @classmethod
    def for_test(
        cls,
        *,
        data_root: Path,
        time_points: List[float],
        window_snapshots: List[Dict[str, object]],
        input_script: List[tuple[float, str, str]],
    ) -> "MonitorRuntime":
        data_root = Path(data_root)
        data_root.mkdir(parents=True, exist_ok=True)
        db_manager = DatabaseManager(DB_PATH=str(data_root / "runtime_test.db"))
        LWTableManager(db_manager=db_manager).init_database()
        screenshot_provider = ScreenshotDataProvider(db_manager=db_manager)
        input_tracker = InputActivityTracker(
            keyboard_keepalive_seconds=12,
            mouse_keepalive_seconds=6,
            time_source=lambda: cls._test_state["now"],
            segment_id_factory=lambda: f"seg-{uuid.uuid4().hex[:8]}",
        )
        scheduler = ScreenshotScheduler(
            policy=get_frequency_policy(2),
            scheduled_interval_seconds=180,
            enter_delay_ms=700,
        )
        screenshot_store = ScreenshotStore(
            provider=screenshot_provider,
            capture_backend=_TestCaptureBackend(),
            data_root=data_root,
            id_factory=lambda: f"cap-{uuid.uuid4().hex[:8]}",
        )
        cleanup_worker = ScreenshotCleanupWorker(
            provider=screenshot_provider,
            data_root=data_root,
            retention_days=settings.get("screenshot_retention_days", 7),
        )

        runtime = cls(
            window_context_source=lambda: cls._test_state["window"],
            input_tracker=input_tracker,
            scheduler=scheduler,
            screenshot_store=screenshot_store,
            screenshot_provider=screenshot_provider,
            cleanup_worker=cleanup_worker,
            input_listener=_NoopInputListener(),
            db_manager=db_manager,
            time_source=lambda: cls._test_state["now"],
            iso_time_source=lambda: cls._epoch_to_iso(cls._test_state["now"]),
            scheduler_sleep_seconds=0.0,
            cleanup_interval_seconds=86400,
            sleep_func=lambda seconds: None,
        )
        runtime._test_time_points = list(time_points)
        runtime._test_window_snapshots = list(window_snapshots)
        runtime._test_input_script = list(input_script)
        runtime._test_input_index = 0
        cls._test_state = {
            "now": 0.0,
            "window": WindowContext(app=None, title=None, is_afk=False),
        }
        return runtime

    def run_for_ticks(self) -> None:
        for index, now_epoch in enumerate(self._test_time_points):
            self._set_test_tick(index, now_epoch)
            self._run_scheduler_tick()

    def start(self) -> None:
        self._running = True
        self.input_listener.start()

        if self.monitor is not None:
            self._monitor_thread = threading.Thread(
                target=self.monitor.run,
                name="LifePrism-WindowMonitor",
                daemon=True,
            )
            self._monitor_thread.start()

        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="LifePrism-ScreenshotCleanup",
            daemon=True,
        )
        self._cleanup_thread.start()

        try:
            while self._running:
                self._run_scheduler_tick()
                self.sleep_func(self.scheduler_sleep_seconds)
        finally:
            self.stop()

    def stop(self) -> None:
        self._running = False
        self.input_listener.stop()
        if self.monitor is not None:
            self.monitor.stop()

    def _cleanup_loop(self) -> None:
        while self._running:
            try:
                self.cleanup_worker.run_once(self.iso_time_source())
            except Exception as exc:
                logger.error("截图清理任务执行失败: %s", exc)
            self.sleep_func(self.cleanup_interval_seconds)

    def _run_scheduler_tick(self) -> None:
        now_epoch = self.time_source()
        self._pending_enter_events.extend(self.input_tracker.consume_enter_events())
        due_enter_events: List[float] = []
        remaining_enter_events: List[float] = []
        enter_delay_seconds = self.scheduler.enter_delay_ms / 1000.0
        for event_time in self._pending_enter_events:
            if event_time + enter_delay_seconds <= now_epoch:
                due_enter_events.append(event_time)
            else:
                remaining_enter_events.append(event_time)
        self._pending_enter_events = remaining_enter_events

        if not settings.get("screenshot_monitor", False):
            return

        window_context = self.window_context_source()
        input_snapshot = self.input_tracker.snapshot()
        requests = self.scheduler.evaluate(
            now_epoch=now_epoch,
            now_iso=self.iso_time_source(),
            window=window_context,
            engaged=input_snapshot.engaged,
            engaged_segment_id=input_snapshot.engaged_segment_id,
            enter_events=due_enter_events,
        )
        for request in requests:
            try:
                self.screenshot_store.capture(request)
            except Exception as exc:
                logger.error("截图请求执行失败: %s", exc)

    def _set_test_tick(self, index: int, now_epoch: float) -> None:
        self._test_state["now"] = now_epoch
        snapshot = self._test_window_snapshots[min(index, len(self._test_window_snapshots) - 1)]
        self._test_state["window"] = WindowContext(
            app=snapshot.get("app"),
            title=snapshot.get("title"),
            is_afk=bool(snapshot.get("is_afk", False)),
        )
        while self._test_input_index < len(self._test_input_script):
            event_time, event_type, payload = self._test_input_script[self._test_input_index]
            if event_time != now_epoch:
                break
            if event_type == "keyboard":
                self.input_tracker.record_keyboard_event(payload)
            elif event_type == "mouse":
                self.input_tracker.record_mouse_event()
            self._test_input_index += 1

    @staticmethod
    def _epoch_to_iso(now_epoch: float) -> str:
        base = datetime(2026, 4, 2, 10, 0, 0)
        return (base + timedelta(seconds=now_epoch)).isoformat()


class _TestCaptureBackend:
    def capture_to_file(self, target_path: Path) -> None:
        target_path.write_bytes(b"fake-png")


def build_monitor_runtime() -> MonitorRuntime:
    window_provider = MonitorDataProvider()
    monitor = WindowMonitor(window_provider)
    screenshot_provider = ScreenshotDataProvider()
    input_tracker = InputActivityTracker(
        keyboard_keepalive_seconds=settings.get("keyboard_keepalive_seconds", 12),
        mouse_keepalive_seconds=settings.get("mouse_keepalive_seconds", 6),
        time_source=time.time,
        segment_id_factory=lambda: f"seg-{uuid.uuid4().hex[:8]}",
    )
    scheduler = ScreenshotScheduler(
        policy=get_frequency_policy(settings.get("active_screenshot_frequency_level", 2)),
        scheduled_interval_seconds=settings.get("scheduled_screenshot_interval_seconds", 180),
        enter_delay_ms=settings.get("enter_screenshot_delay_ms", 700),
    )
    screenshot_store = ScreenshotStore(
        provider=screenshot_provider,
        capture_backend=MSSCaptureBackend(),
        data_root=settings.lifeprism_data_path,
        id_factory=lambda: f"cap-{uuid.uuid4().hex[:8]}",
    )
    cleanup_worker = ScreenshotCleanupWorker(
        provider=screenshot_provider,
        data_root=settings.lifeprism_data_path,
        retention_days=settings.get("screenshot_retention_days", 3),
    )

    return MonitorRuntime(
        window_context_source=monitor.snapshot_window_context,
        input_tracker=input_tracker,
        scheduler=scheduler,
        screenshot_store=screenshot_store,
        screenshot_provider=screenshot_provider,
        cleanup_worker=cleanup_worker,
        input_listener=PynputInputListener(input_tracker),
        db_manager=screenshot_provider.db,
        monitor=monitor,
        scheduler_sleep_seconds=settings.get("poll_time", 1.0),
        cleanup_interval_seconds=settings.get("cleanup_check_interval_seconds", 86400),
    )
