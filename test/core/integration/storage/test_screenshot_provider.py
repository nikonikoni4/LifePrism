import shutil
import uuid
from pathlib import Path

import pytest
from lifeprism.monitor.provider.screenshot_data_provider import ScreenshotDataProvider
from lifeprism.storage.database_manager import DatabaseManager
from lifeprism.storage.lw_table_manager import LWTableManager


def _build_db_manager(tmp_path: Path) -> DatabaseManager:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "screen_captures_test.db"
    db_manager = DatabaseManager(DB_PATH=str(db_path))
    LWTableManager(db_manager=db_manager).init_database()
    return db_manager


def _make_temp_dir() -> Path:
    temp_dir = Path.cwd() / f"test_tmp_provider_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.mark.core
def test_screenshot_provider_create_list_and_delete():
    temp_dir = _make_temp_dir()
    try:
        db_manager = _build_db_manager(temp_dir)
        provider = ScreenshotDataProvider(db_manager=db_manager)

        created = provider.create_capture(
            {
                "id": "cap-1",
                "captured_at": "2026-04-02T10:30:00",
                "capture_reason": "scheduled",
                "file_path": "screenshots/2026-04-02/shot-1.png",
                "window_app": "Code.exe",
                "window_title": "monitor.py",
                "frequency_level": None,
                "engaged_segment_id": None,
                "is_afk": 0,
            }
        )

        assert created is True

        expired = provider.list_expired_captures("2026-04-03T00:00:00")
        assert len(expired) == 1
        assert expired[0]["id"] == "cap-1"
        assert expired[0]["file_path"] == "screenshots/2026-04-02/shot-1.png"

        deleted = provider.delete_capture("cap-1")
        assert deleted is True
        assert provider.list_expired_captures("2026-04-03T00:00:00") == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
