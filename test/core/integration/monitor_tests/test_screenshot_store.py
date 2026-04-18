import shutil
import uuid
from pathlib import Path

import pytest

from lifeprism.monitor.provider.screenshot_data_provider import ScreenshotDataProvider
from lifeprism.monitor.screenshot.models import CaptureReason, CaptureRequest
from lifeprism.monitor.screenshot.store import ScreenshotStore
from lifeprism.storage.database_manager import DatabaseManager
from lifeprism.storage.lw_table_manager import LWTableManager


class FakeCaptureBackend:
    def capture_to_file(self, target_path: Path) -> None:
        target_path.write_bytes(b"fake-png")


class FailingProvider:
    def create_capture(self, data: dict) -> bool:
        raise RuntimeError("db write failed")


def _build_db_manager(tmp_path: Path) -> DatabaseManager:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "screenshot_store_test.db"
    db_manager = DatabaseManager(DB_PATH=str(db_path))
    LWTableManager(db_manager=db_manager).init_database()
    return db_manager


def _make_temp_dir() -> Path:
    temp_dir = Path.cwd() / f"test_tmp_store_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.mark.core
def test_screenshot_store_writes_relative_path_and_metadata():
    temp_dir = _make_temp_dir()
    try:
        db_manager = _build_db_manager(temp_dir)
        provider = ScreenshotDataProvider(db_manager=db_manager)
        store = ScreenshotStore(
            provider=provider,
            capture_backend=FakeCaptureBackend(),
            data_root=temp_dir,
            id_factory=lambda: "cap-0001",
        )

        request = CaptureRequest(
            reason=CaptureReason.SCHEDULED,
            captured_at="2026-04-02T10:30:00",
            window_app="Code.exe",
            window_title="monitor.py",
            frequency_level=None,
            engaged_segment_id=None,
            is_afk=False,
        )

        record = store.capture(request)

        assert record["id"] == "cap-0001"
        assert record["file_path"] == "screenshots/2026-04-02/2026-04-02T10-30-00_scheduled_cap-0001.png"
        assert (temp_dir / record["file_path"]).exists()

        rows = provider.list_expired_captures("2026-04-03T00:00:00")
        assert len(rows) == 1
        assert rows[0]["id"] == "cap-0001"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.core
def test_screenshot_store_rolls_back_file_when_metadata_insert_fails():
    temp_dir = _make_temp_dir()
    try:
        store = ScreenshotStore(
            provider=FailingProvider(),
            capture_backend=FakeCaptureBackend(),
            data_root=temp_dir,
            id_factory=lambda: "cap-0002",
        )
        request = CaptureRequest(
            reason=CaptureReason.SCHEDULED,
            captured_at="2026-04-02T10:31:00",
            window_app="Code.exe",
            window_title="monitor.py",
            frequency_level=None,
            engaged_segment_id=None,
            is_afk=False,
        )

        with pytest.raises(RuntimeError, match="db write failed"):
            store.capture(request)

        expected_path = temp_dir / "screenshots" / "2026-04-02" / "2026-04-02T10-31-00_scheduled_cap-0002.png"
        assert not expected_path.exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
