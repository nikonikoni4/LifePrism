# Monitor Screenshot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 `lifeprism` monitor 进程内落地截图能力，按 PRD 实现 `scheduled` / `active` / `enter` 三类截图、`engaged_segment_id`、本地文件存储与过期清理。

**Architecture:** 保留当前独立 monitor 进程，不新增第二个守护进程。`WindowMonitor` 继续负责窗口与 AFK 状态；新增 `InputActivityTracker`、`ScreenshotScheduler`、`ScreenshotStore`、`ScreenshotCleanupWorker`，通过同进程多线程协作，并统一走 `settings_manager` 管理路径与配置。

**Tech Stack:** Python 3.8+, `threading`, `queue`, `dataclasses`, `pathlib`, SQLite (`DatabaseManager` / `LWBaseDataProvider`), `pytest`, `mss`（截图）, `pynput`（键鼠监听）, PyInstaller。

---

## Implementation Notes

- 实施顺序固定：`@test-driven-development` -> 代码实现 -> 局部验证 -> 提交。
- 完成前必须执行 `@verification-before-completion`，不要凭主观判断声称“已完成”。
- 所有新测试放到 `test/`；不要再往仓库里引入散落的 ad-hoc 脚本测试。
- 不删除旧测试文件；优先把当前失效的 `test/monitor/test_config.py`、`test/monitor/test_storage.py` 改造成有效回归测试。
- 本期不扩展前端页面，也不新增公开 API 契约；截图相关配置先落到 `settings_manager` 与内部运行时。

### Task 1: 配置、表结构与数据目录骨架

**Files:**
- Modify: `lifeprism/config/settings_manager.py`
- Modify: `lifeprism/config/database.py`
- Modify: `lifeprism/server/services/setting_service.py`
- Modify: `test/config/test_database.py`
- Create: `test/config/test_monitor_screenshot_settings.py`

**Step 1: Write the failing test**

```python
from lifeprism.config.database import TABLE_CONFIGS
from lifeprism.config.settings_manager import SettingsManager
from lifeprism.server.services.setting_service import _DATA_SUBDIRS


def test_screen_captures_table_config_exists():
    config = TABLE_CONFIGS["screen_captures"]
    assert config["table_name"] == "screen_captures"
    assert "captured_at" in config["columns"]
    assert "engaged_segment_id" in config["columns"]
    assert any(index["name"] == "idx_screen_captures_captured_at" for index in config["indexes"])


def test_monitor_screenshot_defaults_and_data_dir():
    defaults = SettingsManager.DEFAULTS
    assert defaults["scheduled_screenshot_interval_seconds"] == 60
    assert defaults["active_screenshot_frequency_level"] == 2
    assert defaults["keyboard_keepalive_seconds"] == 12
    assert defaults["mouse_keepalive_seconds"] == 6
    assert defaults["enter_screenshot_delay_ms"] == 700
    assert defaults["screenshot_retention_days"] == 3
    assert defaults["cleanup_check_interval_seconds"] == 86400
    assert "screenshots" in _DATA_SUBDIRS
```

**Step 2: Run test to verify it fails**

Run: `pytest test/config/test_database.py test/config/test_monitor_screenshot_settings.py -q`

Expected: FAIL with `KeyError: 'screen_captures'` and missing screenshot default keys.

**Step 3: Write minimal implementation**

```python
# lifeprism/config/settings_manager.py
DEFAULTS = {
    # existing keys...
    "keyboard_keepalive_seconds": 12,
    "mouse_keepalive_seconds": 6,
    "scheduled_screenshot_interval_seconds": 60,
    "active_screenshot_frequency_level": 2,
    "enter_screenshot_delay_ms": 700,
    "screenshot_retention_days": 3,
    "cleanup_check_interval_seconds": 86400,
}

# lifeprism/config/database.py
SCREEN_CAPTURES_CONFIG = {
    "table_name": "screen_captures",
    "columns": {
        "id": {"type": "TEXT", "constraints": ["PRIMARY KEY", "NOT NULL"]},
        "captured_at": {"type": "TEXT", "constraints": ["NOT NULL"]},
        "capture_reason": {"type": "TEXT", "constraints": ["NOT NULL"]},
        "file_path": {"type": "TEXT", "constraints": ["NOT NULL", "UNIQUE"]},
        "window_app": {"type": "TEXT", "constraints": []},
        "window_title": {"type": "TEXT", "constraints": []},
        "frequency_level": {"type": "INTEGER", "constraints": []},
        "engaged_segment_id": {"type": "TEXT", "constraints": []},
        "is_afk": {"type": "INTEGER", "constraints": ["NOT NULL"]},
    },
    "indexes": [
        {"name": "idx_screen_captures_captured_at", "columns": ["captured_at"]},
        {"name": "idx_screen_captures_segment_id", "columns": ["engaged_segment_id"]},
        {"name": "idx_screen_captures_reason_time", "columns": ["capture_reason", "captured_at"]},
    ],
    "timestamps": True,
    "update_at": False,
}

TABLE_CONFIGS["screen_captures"] = SCREEN_CAPTURES_CONFIG

# lifeprism/server/services/setting_service.py
_DATA_SUBDIRS = ["dataset", "plan", "debug_logs", "workflow", "external_files", "docs", "diary", "screenshots"]
```

**Step 4: Run test to verify it passes**

Run: `pytest test/config/test_database.py test/config/test_monitor_screenshot_settings.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add lifeprism/config/settings_manager.py lifeprism/config/database.py lifeprism/server/services/setting_service.py test/config/test_database.py test/config/test_monitor_screenshot_settings.py
git commit -m "feat: add monitor screenshot config foundation"
```

### Task 2: 纯领域模型与频率策略

**Files:**
- Create: `lifeprism/monitor/screenshot/__init__.py`
- Create: `lifeprism/monitor/screenshot/models.py`
- Create: `lifeprism/monitor/screenshot/policy.py`
- Create: `test/monitor/test_screenshot_policy.py`

**Step 1: Write the failing test**

```python
from lifeprism.monitor.screenshot.models import CaptureReason
from lifeprism.monitor.screenshot.policy import get_frequency_policy


def test_get_frequency_policy_for_medium_level():
    policy = get_frequency_policy(2)
    assert policy.first_active_after_seconds == 30
    assert policy.repeat_active_every_seconds == 60
    assert policy.enter_cooldown_seconds == 6


def test_invalid_frequency_level_raises():
    try:
        get_frequency_policy(99)
    except ValueError as exc:
        assert "active_screenshot_frequency_level" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_capture_reason_enum_values():
    assert CaptureReason.SCHEDULED.value == "scheduled"
    assert CaptureReason.ACTIVE.value == "active"
    assert CaptureReason.ENTER.value == "enter"
```

**Step 2: Run test to verify it fails**

Run: `pytest test/monitor/test_screenshot_policy.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'lifeprism.monitor.screenshot'`

**Step 3: Write minimal implementation**

```python
# lifeprism/monitor/screenshot/models.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CaptureReason(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENTER = "enter"


@dataclass(frozen=True)
class FrequencyPolicy:
    level: int
    first_active_after_seconds: int
    repeat_active_every_seconds: int
    enter_cooldown_seconds: int


@dataclass(frozen=True)
class WindowContext:
    app: Optional[str]
    title: Optional[str]
    is_afk: bool


@dataclass(frozen=True)
class CaptureRequest:
    reason: CaptureReason
    captured_at: str
    window_app: Optional[str]
    window_title: Optional[str]
    frequency_level: Optional[int]
    engaged_segment_id: Optional[str]

# lifeprism/monitor/screenshot/policy.py
_POLICIES = {
    1: FrequencyPolicy(level=1, first_active_after_seconds=45, repeat_active_every_seconds=90, enter_cooldown_seconds=8),
    2: FrequencyPolicy(level=2, first_active_after_seconds=30, repeat_active_every_seconds=60, enter_cooldown_seconds=6),
    3: FrequencyPolicy(level=3, first_active_after_seconds=20, repeat_active_every_seconds=40, enter_cooldown_seconds=4),
}


def get_frequency_policy(level: int) -> FrequencyPolicy:
    try:
        return _POLICIES[level]
    except KeyError as exc:
        raise ValueError(f"invalid active_screenshot_frequency_level: {level}") from exc
```

**Step 4: Run test to verify it passes**

Run: `pytest test/monitor/test_screenshot_policy.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add lifeprism/monitor/screenshot/__init__.py lifeprism/monitor/screenshot/models.py lifeprism/monitor/screenshot/policy.py test/monitor/test_screenshot_policy.py
git commit -m "feat: add screenshot domain models and policy"
```

### Task 3: 元数据 Provider 与落盘 Store

**Files:**
- Create: `lifeprism/monitor/provider/screenshot_data_provider.py`
- Modify: `lifeprism/monitor/provider/__init__.py`
- Create: `lifeprism/monitor/screenshot/store.py`
- Create: `test/storage/test_screenshot_provider.py`
- Create: `test/monitor/test_screenshot_store.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from lifeprism.monitor.provider.screenshot_data_provider import ScreenshotDataProvider
from lifeprism.monitor.screenshot.models import CaptureReason, CaptureRequest
from lifeprism.monitor.screenshot.store import ScreenshotStore


class FakeCaptureBackend:
    def capture_to_file(self, target_path: Path) -> None:
        target_path.write_bytes(b"fake-png")


def test_store_writes_relative_path_and_metadata(tmp_path, db_manager):
    provider = ScreenshotDataProvider(db_manager=db_manager)
    store = ScreenshotStore(
        provider=provider,
        capture_backend=FakeCaptureBackend(),
        data_root=tmp_path,
        id_factory=lambda: "cap-0001",
    )

    request = CaptureRequest(
        reason=CaptureReason.SCHEDULED,
        captured_at="2026-04-02T10:30:00",
        window_app="Code.exe",
        window_title="monitor.py",
        frequency_level=None,
        engaged_segment_id=None,
    )

    record = store.capture(request)
    assert record["id"] == "cap-0001"
    assert record["file_path"] == "screenshots/2026-04-02/2026-04-02T10-30-00_scheduled_cap-0001.png"


def test_store_rolls_back_file_when_metadata_insert_fails(tmp_path, failing_provider):
    store = ScreenshotStore(
        provider=failing_provider,
        capture_backend=FakeCaptureBackend(),
        data_root=tmp_path,
        id_factory=lambda: "cap-0002",
    )
    # capture() should raise and leave no png file behind
```

**Step 2: Run test to verify it fails**

Run: `pytest test/storage/test_screenshot_provider.py test/monitor/test_screenshot_store.py -q`

Expected: FAIL with missing provider/store modules.

**Step 3: Write minimal implementation**

```python
# lifeprism/monitor/provider/screenshot_data_provider.py
class ScreenshotDataProvider(LWBaseDataProvider):
    def create_capture(self, data: dict) -> bool:
        return self.db.insert("screen_captures", data) > 0

    def list_expired_captures(self, cutoff_iso: str) -> list[dict]:
        sql = """
        SELECT id, file_path, captured_at
        FROM screen_captures
        WHERE captured_at < ?
        ORDER BY captured_at ASC
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (cutoff_iso,))
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def delete_capture(self, capture_id: str) -> bool:
        return self.db.delete("screen_captures", {"id": capture_id}) > 0

# lifeprism/monitor/screenshot/store.py
class ScreenshotStore:
    def capture(self, request: CaptureRequest) -> dict:
        capture_id = self.id_factory()
        target_dir = self.data_root / "screenshots" / request.captured_at[:10]
        target_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{request.captured_at.replace(':', '-')}_{request.reason.value}_{capture_id}.png"
        file_path = target_dir / file_name
        relative_path = file_path.relative_to(self.data_root).as_posix()

        self.capture_backend.capture_to_file(file_path)
        payload = {
            "id": capture_id,
            "captured_at": request.captured_at,
            "capture_reason": request.reason.value,
            "file_path": relative_path,
            "window_app": request.window_app,
            "window_title": request.window_title,
            "frequency_level": request.frequency_level,
            "engaged_segment_id": request.engaged_segment_id,
            "is_afk": 0,
        }
        try:
            self.provider.create_capture(payload)
        except Exception:
            if file_path.exists():
                file_path.unlink()
            raise
        return payload
```

**Step 4: Run test to verify it passes**

Run: `pytest test/storage/test_screenshot_provider.py test/monitor/test_screenshot_store.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add lifeprism/monitor/provider/screenshot_data_provider.py lifeprism/monitor/provider/__init__.py lifeprism/monitor/screenshot/store.py test/storage/test_screenshot_provider.py test/monitor/test_screenshot_store.py
git commit -m "feat: add screenshot metadata provider and store"
```

### Task 4: InputActivityTracker 状态机

**Files:**
- Create: `lifeprism/monitor/screenshot/input_tracker.py`
- Create: `test/monitor/test_input_activity_tracker.py`

**Step 1: Write the failing test**

```python
from lifeprism.monitor.screenshot.input_tracker import InputActivityTracker


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


def test_enter_event_is_buffered_for_scheduler():
    tracker = InputActivityTracker(
        keyboard_keepalive_seconds=12,
        mouse_keepalive_seconds=6,
        time_source=lambda: 100.0,
        segment_id_factory=lambda: "seg-3",
    )
    tracker.record_keyboard_event("enter")
    assert tracker.consume_enter_events() == [100.0]
```

**Step 2: Run test to verify it fails**

Run: `pytest test/monitor/test_input_activity_tracker.py -q`

Expected: FAIL with missing tracker module.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InputSnapshot:
    engaged: bool
    engaged_segment_id: Optional[str]
    last_keyboard_at: Optional[float]
    last_mouse_at: Optional[float]


class InputActivityTracker:
    def __init__(self, keyboard_keepalive_seconds, mouse_keepalive_seconds, time_source, segment_id_factory):
        self.keyboard_keepalive_seconds = keyboard_keepalive_seconds
        self.mouse_keepalive_seconds = mouse_keepalive_seconds
        self.time_source = time_source
        self.segment_id_factory = segment_id_factory
        self._last_keyboard_at = None
        self._last_mouse_at = None
        self._engaged_segment_id = None
        self._pending_enter_events = []

    def record_keyboard_event(self, key_name: str) -> None:
        now = self.time_source()
        self._last_keyboard_at = now
        if self._engaged_segment_id is None:
            self._engaged_segment_id = self.segment_id_factory()
        if key_name.lower() == "enter":
            self._pending_enter_events.append(now)

    def record_mouse_event(self) -> None:
        now = self.time_source()
        self._last_mouse_at = now
        if self._engaged_segment_id is None:
            self._engaged_segment_id = self.segment_id_factory()

    def snapshot(self) -> InputSnapshot:
        now = self.time_source()
        keyboard_alive = self._last_keyboard_at is not None and now - self._last_keyboard_at <= self.keyboard_keepalive_seconds
        mouse_alive = self._last_mouse_at is not None and now - self._last_mouse_at <= self.mouse_keepalive_seconds
        engaged = keyboard_alive or mouse_alive
        if not engaged:
            self._engaged_segment_id = None
        return InputSnapshot(engaged=engaged, engaged_segment_id=self._engaged_segment_id, last_keyboard_at=self._last_keyboard_at, last_mouse_at=self._last_mouse_at)

    def consume_enter_events(self) -> list[float]:
        items = list(self._pending_enter_events)
        self._pending_enter_events.clear()
        return items
```

**Step 4: Run test to verify it passes**

Run: `pytest test/monitor/test_input_activity_tracker.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add lifeprism/monitor/screenshot/input_tracker.py test/monitor/test_input_activity_tracker.py
git commit -m "feat: add monitor input activity tracker"
```

### Task 5: ScreenshotScheduler 规则引擎

**Files:**
- Create: `lifeprism/monitor/screenshot/scheduler.py`
- Create: `test/monitor/test_screenshot_scheduler.py`

**Step 1: Write the failing test**

```python
from lifeprism.monitor.screenshot.models import CaptureReason, WindowContext
from lifeprism.monitor.screenshot.policy import get_frequency_policy
from lifeprism.monitor.screenshot.scheduler import ScreenshotScheduler


def test_afk_blocks_all_requests():
    scheduler = ScreenshotScheduler(policy=get_frequency_policy(2), scheduled_interval_seconds=60, enter_delay_ms=700)
    requests = scheduler.evaluate(
        now_epoch=100.0,
        now_iso="2026-04-02T10:00:00",
        window=WindowContext(app="Code.exe", title="main.py", is_afk=True),
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )
    assert requests == []


def test_scheduled_capture_has_no_segment():
    scheduler = ScreenshotScheduler(policy=get_frequency_policy(2), scheduled_interval_seconds=60, enter_delay_ms=700)
    requests = scheduler.evaluate(
        now_epoch=160.0,
        now_iso="2026-04-02T10:01:00",
        window=WindowContext(app="Code.exe", title="main.py", is_afk=False),
        engaged=False,
        engaged_segment_id=None,
        enter_events=[],
    )
    assert requests[0].reason == CaptureReason.SCHEDULED
    assert requests[0].engaged_segment_id is None


def test_active_and_enter_follow_segment_and_cooldown():
    scheduler = ScreenshotScheduler(policy=get_frequency_policy(2), scheduled_interval_seconds=60, enter_delay_ms=700)
    # first active at 30s, enter delayed 700ms, cooldown 6s
```

**Step 2: Run test to verify it fails**

Run: `pytest test/monitor/test_screenshot_scheduler.py -q`

Expected: FAIL with missing scheduler module.

**Step 3: Write minimal implementation**

```python
class ScreenshotScheduler:
    def __init__(self, policy, scheduled_interval_seconds, enter_delay_ms):
        self.policy = policy
        self.scheduled_interval_seconds = scheduled_interval_seconds
        self.enter_delay_ms = enter_delay_ms
        self._next_scheduled_at = scheduled_interval_seconds
        self._segment_started_at = {}
        self._segment_first_active_done = set()
        self._next_active_at = {}
        self._enter_cooldown_until = 0.0

    def evaluate(self, now_epoch, now_iso, window, engaged, engaged_segment_id, enter_events):
        if window.is_afk:
            return []

        requests = []

        if now_epoch >= self._next_scheduled_at:
            requests.append(CaptureRequest(
                reason=CaptureReason.SCHEDULED,
                captured_at=now_iso,
                window_app=window.app,
                window_title=window.title,
                frequency_level=None,
                engaged_segment_id=None,
            ))
            self._next_scheduled_at = now_epoch + self.scheduled_interval_seconds

        if engaged and engaged_segment_id:
            started_at = self._segment_started_at.setdefault(engaged_segment_id, now_epoch)
            if engaged_segment_id not in self._segment_first_active_done and now_epoch - started_at >= self.policy.first_active_after_seconds:
                requests.append(CaptureRequest(
                    reason=CaptureReason.ACTIVE,
                    captured_at=now_iso,
                    window_app=window.app,
                    window_title=window.title,
                    frequency_level=self.policy.level,
                    engaged_segment_id=engaged_segment_id,
                ))
                self._segment_first_active_done.add(engaged_segment_id)
                self._next_active_at[engaged_segment_id] = now_epoch + self.policy.repeat_active_every_seconds
            elif now_epoch >= self._next_active_at.get(engaged_segment_id, float("inf")):
                requests.append(...)
                self._next_active_at[engaged_segment_id] = now_epoch + self.policy.repeat_active_every_seconds

            if enter_events and now_epoch >= self._enter_cooldown_until:
                requests.append(CaptureRequest(
                    reason=CaptureReason.ENTER,
                    captured_at=now_iso,
                    window_app=window.app,
                    window_title=window.title,
                    frequency_level=self.policy.level,
                    engaged_segment_id=engaged_segment_id,
                ))
                self._enter_cooldown_until = now_epoch + self.policy.enter_cooldown_seconds

        return requests
```

**Step 4: Run test to verify it passes**

Run: `pytest test/monitor/test_screenshot_scheduler.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add lifeprism/monitor/screenshot/scheduler.py test/monitor/test_screenshot_scheduler.py
git commit -m "feat: add screenshot scheduler rules"
```

### Task 6: ScreenshotCleanupWorker 清理链路

**Files:**
- Create: `lifeprism/monitor/screenshot/cleanup_worker.py`
- Create: `test/monitor/test_screenshot_cleanup_worker.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from lifeprism.monitor.screenshot.cleanup_worker import ScreenshotCleanupWorker


def test_cleanup_deletes_file_then_metadata(tmp_path, provider_with_expired_rows):
    png = tmp_path / "screenshots" / "2026-03-28" / "old.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    png.write_bytes(b"png")

    worker = ScreenshotCleanupWorker(
        provider=provider_with_expired_rows,
        data_root=tmp_path,
        retention_days=3,
    )

    result = worker.run_once(now_iso="2026-04-02T12:00:00")
    assert result.deleted_files == 1
    assert result.deleted_rows == 1


def test_cleanup_keeps_metadata_when_file_delete_fails(tmp_path, provider_with_locked_file):
    worker = ScreenshotCleanupWorker(...)
    result = worker.run_once(now_iso="2026-04-02T12:00:00")
    assert result.deleted_rows == 0
    assert result.failed_files == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest test/monitor/test_screenshot_cleanup_worker.py -q`

Expected: FAIL with missing cleanup worker module.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class CleanupResult:
    deleted_files: int = 0
    deleted_rows: int = 0
    failed_files: int = 0


class ScreenshotCleanupWorker:
    def __init__(self, provider, data_root: Path, retention_days: int):
        self.provider = provider
        self.data_root = data_root
        self.retention_days = retention_days

    def run_once(self, now_iso: str) -> CleanupResult:
        now = datetime.fromisoformat(now_iso)
        cutoff = (now - timedelta(days=self.retention_days)).isoformat()
        expired = self.provider.list_expired_captures(cutoff)
        deleted_files = 0
        deleted_rows = 0
        failed_files = 0

        for item in expired:
            target = self.data_root / item["file_path"]
            try:
                if target.exists():
                    target.unlink()
                    deleted_files += 1
                self.provider.delete_capture(item["id"])
                deleted_rows += 1
            except FileNotFoundError:
                self.provider.delete_capture(item["id"])
                deleted_rows += 1
            except OSError:
                failed_files += 1

        return CleanupResult(deleted_files=deleted_files, deleted_rows=deleted_rows, failed_files=failed_files)
```

**Step 4: Run test to verify it passes**

Run: `pytest test/monitor/test_screenshot_cleanup_worker.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add lifeprism/monitor/screenshot/cleanup_worker.py test/monitor/test_screenshot_cleanup_worker.py
git commit -m "feat: add screenshot cleanup worker"
```

### Task 7: 运行时集成、键鼠监听与打包依赖

**Files:**
- Modify: `pyproject.toml`
- Modify: `lifeprism.spec`
- Create: `lifeprism/monitor/screenshot/backends.py`
- Create: `lifeprism/monitor/windows_monitor/runtime.py`
- Modify: `lifeprism/monitor/windows_monitor/monitor.py`
- Modify: `lifeprism/monitor/windows_monitor/main.py`
- Create: `test/integration/test_monitor_screenshot_flow.py`

**Step 1: Write the failing test**

```python
from lifeprism.monitor.windows_monitor.runtime import MonitorRuntime


def test_runtime_emits_scheduled_active_and_enter(tmp_path, db_manager):
    runtime = MonitorRuntime.for_test(
        db_manager=db_manager,
        data_root=tmp_path,
        time_points=[0.0, 30.0, 60.0, 61.0],
        window_snapshots=[
            {"app": "Code.exe", "title": "scheduler.py", "is_afk": False},
        ],
        input_script=[
            ("keyboard", "a"),
            ("keyboard", "enter"),
        ],
    )

    runtime.run_for_ticks(4)

    captures = runtime.screenshot_provider.list_all()
    reasons = [item["capture_reason"] for item in captures]
    assert "scheduled" in reasons
    assert "active" in reasons
    assert "enter" in reasons
```

**Step 2: Run test to verify it fails**

Run: `pytest test/integration/test_monitor_screenshot_flow.py -q`

Expected: FAIL with missing runtime module.

**Step 3: Write minimal implementation**

```python
# pyproject.toml
dependencies = [
    # existing deps...
    "mss>=9.0.1",
    "pynput>=1.7.7",
]

# lifeprism/monitor/screenshot/backends.py
from mss import mss
from pynput import keyboard, mouse


class MSSCaptureBackend:
    def capture_to_file(self, target_path):
        import mss.tools

        with mss() as sct:
            shot = sct.grab(sct.monitors[0])
            mss.tools.to_png(shot.rgb, shot.size, output=str(target_path))


class PynputInputListener:
    def __init__(self, tracker):
        self.tracker = tracker
        self._keyboard = keyboard.Listener(on_press=self._on_key_press)
        self._mouse = mouse.Listener(on_move=self._on_mouse_move, on_click=self._on_mouse_click)

    def _on_key_press(self, key):
        try:
            name = key.char or str(key).replace("Key.", "")
        except AttributeError:
            name = str(key).replace("Key.", "")
        self.tracker.record_keyboard_event(name)

    def _on_mouse_move(self, x, y):
        self.tracker.record_mouse_event()

    def _on_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.tracker.record_mouse_event()

# lifeprism/monitor/windows_monitor/runtime.py
class MonitorRuntime:
    def start(self):
        self.input_listener.start()
        self.cleanup_thread.start()
        self.monitor.run()

# lifeprism/monitor/windows_monitor/monitor.py
# 只保留窗口/AFK 更新与当前窗口上下文缓存；截图调度转交 runtime 线程

# lifeprism/monitor/windows_monitor/main.py
def main():
    runtime = build_monitor_runtime()
    runtime.start()

# lifeprism.spec
hiddenimports += ["mss", "mss.tools", "pynput", "pynput.keyboard", "pynput.mouse"]
```

**Step 4: Run test to verify it passes**

Run: `pytest test/integration/test_monitor_screenshot_flow.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml lifeprism.spec lifeprism/monitor/screenshot/backends.py lifeprism/monitor/windows_monitor/runtime.py lifeprism/monitor/windows_monitor/monitor.py lifeprism/monitor/windows_monitor/main.py test/integration/test_monitor_screenshot_flow.py
git commit -m "feat: integrate monitor screenshot runtime"
```

### Task 8: 修复遗留测试并执行完整验证

**Files:**
- Modify: `test/monitor/test_config.py`
- Modify: `test/monitor/test_storage.py`
- Modify: `test/integration/test_monitor_flow.py`

**Step 1: Write the failing test**

```python
from lifeprism.config.settings_manager import SettingsManager


def test_monitor_screenshot_settings_defaults():
    defaults = SettingsManager.DEFAULTS
    assert defaults["scheduled_screenshot_interval_seconds"] == 60
    assert defaults["active_screenshot_frequency_level"] == 2


def test_store_file_name_uses_reason_and_id(tmp_path, db_manager):
    # 将旧的 test_storage.py 改造成对 ScreenshotStore 的有效回归测试
    ...


def test_window_monitor_still_persists_window_events(db_manager):
    # 保留旧 monitor 主链路，确保截图改造没有破坏 window_events
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest test/monitor/test_config.py test/monitor/test_storage.py test/integration/test_monitor_flow.py -q`

Expected: FAIL because旧文件仍引用不存在的 `lifeprism.monitor.windows_monitor.config` / `storage`。

**Step 3: Write minimal implementation**

```python
# test/monitor/test_config.py
def test_monitor_screenshot_settings_defaults():
    defaults = SettingsManager.DEFAULTS
    assert defaults["enter_screenshot_delay_ms"] == 700

# test/monitor/test_storage.py
def test_screenshot_store_generates_relative_png_path(...):
    ...

# test/integration/test_monitor_flow.py
def test_save_window_event_flow():
    # 保持原有断言，同时确认新增 screen_captures 表不会影响 window_events 写入
    ...
```

**Step 4: Run full verification**

Run: `pytest test/config/test_database.py test/config/test_monitor_screenshot_settings.py test/storage/test_window_provider.py test/storage/test_screenshot_provider.py test/monitor/test_config.py test/monitor/test_storage.py test/monitor/test_screenshot_policy.py test/monitor/test_input_activity_tracker.py test/monitor/test_screenshot_scheduler.py test/monitor/test_screenshot_store.py test/monitor/test_screenshot_cleanup_worker.py test/integration/test_monitor_flow.py test/integration/test_monitor_screenshot_flow.py -q`

Expected: PASS

Run: `cmd /c build.bat backend`

Expected: build success with backend artifact under `pyinstaller-dist/lifeprism-backend/`

Manual smoke check:

1. 启动后端。
2. 保持非 AFK，输入键盘 30 秒以上，并按一次 `Enter`。
3. 确认 `localData/screenshots/YYYY-MM-DD/` 出现 PNG 文件。
4. 确认 `screen_captures` 表内存在 `scheduled`、`active`、`enter` 记录。
5. 将一条旧记录时间改到 3 天前，触发清理，确认文件与元数据按规则删除。

**Step 5: Commit**

```bash
git add test/monitor/test_config.py test/monitor/test_storage.py test/integration/test_monitor_flow.py
git add test/config/test_database.py test/config/test_monitor_screenshot_settings.py test/storage/test_window_provider.py test/storage/test_screenshot_provider.py
git add test/monitor/test_screenshot_policy.py test/monitor/test_input_activity_tracker.py test/monitor/test_screenshot_scheduler.py test/monitor/test_screenshot_store.py test/monitor/test_screenshot_cleanup_worker.py test/integration/test_monitor_screenshot_flow.py
git commit -m "test: verify monitor screenshot end to end"
```

## Risks

- `mss` / `pynput` 在 PyInstaller 下可能需要额外 hidden import；不要跳过 `build.bat backend`。
- 键鼠监听与主监控循环存在并发访问，窗口上下文和 tracker snapshot 必须加锁或保证原子读取。
- `enter` 延迟与冷却逻辑很容易在“同一 tick 多事件”场景下重复触发，测试必须覆盖。
- 路径必须始终基于 `settings.lifeprism_data_path`；不要在截图模块里手写 `localData`。
- 本期不扩展 settings API / frontend，因此截图参数变更先依赖配置文件或内部构造参数；若要开放给 UI，另开任务。

## Suggested Review Checklist

- `scheduled` 记录是否永远 `engaged_segment_id = NULL`
- `active` / `enter` 是否总是同时带 `frequency_level` 与 `engaged_segment_id`
- AFK 状态下是否彻底阻止三类截图
- 元数据写入失败时是否正确回滚已生成的截图文件
- 迁移数据路径时 `screenshots/` 是否跟随复制
- 旧 `window_events` 链路是否保持不变
