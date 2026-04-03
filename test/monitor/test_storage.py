import shutil
import uuid
from pathlib import Path

from lifeprism.monitor.provider.screenshot_data_provider import ScreenshotDataProvider
from lifeprism.monitor.screenshot.models import CaptureReason, CaptureRequest
from lifeprism.monitor.screenshot.store import ScreenshotStore
from lifeprism.storage.database_manager import DatabaseManager
from lifeprism.storage.lw_table_manager import LWTableManager


class FakeCaptureBackend:
    def capture_to_file(self, target_path: Path) -> None:
        target_path.write_bytes(b"fake-png")


def _make_temp_dir() -> Path:
    temp_dir = Path.cwd() / f"test_tmp_legacy_store_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_screenshot_store_generates_relative_png_path():
    temp_dir = _make_temp_dir()
    try:
        db_manager = DatabaseManager(DB_PATH=str(temp_dir / "legacy_store.db"))
        LWTableManager(db_manager=db_manager).init_database()
        store = ScreenshotStore(
            provider=ScreenshotDataProvider(db_manager=db_manager),
            capture_backend=FakeCaptureBackend(),
            data_root=temp_dir,
            id_factory=lambda: "cap-legacy",
        )

        payload = store.capture(
            CaptureRequest(
                reason=CaptureReason.SCHEDULED,
                captured_at="2026-04-02T11:00:00",
                window_app="test_app.exe",
                window_title="Test Window Title",
                frequency_level=None,
                engaged_segment_id=None,
            )
        )

        assert payload["file_path"] == (
            "screenshots/2026-04-02/"
            "2026-04-02T11-00-00_scheduled_cap-legacy.png"
        )
        assert (temp_dir / payload["file_path"]).exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
