import shutil
import uuid
from pathlib import Path

import pytest

from lifeprism.monitor.screenshot.cleanup_worker import ScreenshotCleanupWorker


class FakeProvider:
    def __init__(self, rows):
        self.rows = list(rows)
        self.deleted_ids = []

    def list_expired_captures(self, cutoff_iso: str):
        return list(self.rows)

    def delete_capture(self, capture_id: str) -> bool:
        self.deleted_ids.append(capture_id)
        self.rows = [row for row in self.rows if row["id"] != capture_id]
        return True


def _make_temp_dir() -> Path:
    temp_dir = Path.cwd() / f"test_tmp_cleanup_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.mark.core
def test_cleanup_deletes_file_then_metadata():
    temp_dir = _make_temp_dir()
    try:
        file_path = temp_dir / "screenshots" / "2026-03-28" / "old.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"png")

        provider = FakeProvider(
            [
                {
                    "id": "cap-1",
                    "file_path": "screenshots/2026-03-28/old.png",
                    "captured_at": "2026-03-28T10:00:00",
                }
            ]
        )
        worker = ScreenshotCleanupWorker(
            provider=provider,
            data_root=temp_dir,
            retention_days=3,
        )

        result = worker.run_once(now_iso="2026-04-02T12:00:00")

        assert result.deleted_files == 1
        assert result.deleted_rows == 1
        assert result.failed_files == 0
        assert provider.deleted_ids == ["cap-1"]
        assert not file_path.exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.core
def test_cleanup_keeps_metadata_when_file_delete_fails():
    temp_dir = _make_temp_dir()
    try:
        file_path = temp_dir / "screenshots" / "2026-03-28" / "locked.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"png")

        provider = FakeProvider(
            [
                {
                    "id": "cap-2",
                    "file_path": "screenshots/2026-03-28/locked.png",
                    "captured_at": "2026-03-28T10:00:00",
                }
            ]
        )
        worker = ScreenshotCleanupWorker(
            provider=provider,
            data_root=temp_dir,
            retention_days=3,
            delete_file_func=lambda path: (_ for _ in ()).throw(OSError("locked")),
        )

        result = worker.run_once(now_iso="2026-04-02T12:00:00")

        assert result.deleted_files == 0
        assert result.deleted_rows == 0
        assert result.failed_files == 1
        assert provider.deleted_ids == []
        assert file_path.exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
