from collections.abc import Callable
from pathlib import Path
from typing import Any

from lifeprism.monitor.screenshot.models import CaptureRequest


class ScreenshotStore:
    """负责截图文件落盘及元数据写入。"""

    def __init__(
        self,
        provider,
        capture_backend,
        data_root: Path,
        id_factory: Callable[[], str],
    ) -> None:
        self.provider = provider
        self.capture_backend = capture_backend
        self.data_root = Path(data_root)
        self.id_factory = id_factory

    def capture(self, request: CaptureRequest) -> dict[str, Any]:
        capture_id = self.id_factory()
        date_dir = request.captured_at[:10]
        target_dir = self.data_root / "screenshots" / date_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        normalized_timestamp = request.captured_at.replace(":", "-")
        file_name = f"{normalized_timestamp}_{request.reason.value}_{capture_id}.png"
        file_path = target_dir / file_name
        relative_path = file_path.relative_to(self.data_root).as_posix()

        self.capture_backend.capture_to_file(file_path)

        # 对 app 和 title 进行标准化处理，与 data_clean.py 保持一致
        window_app = request.window_app
        if window_app:
            window_app = window_app.lower().strip().split(".exe")[0]

        window_title = request.window_title
        if window_title:
            window_title = window_title.split("和另外")[0].strip().lower()

        # 保持 captured_at 的 ISO 8601 格式（UTC 时区）
        payload = {
            "id": capture_id,
            "captured_at": request.captured_at,
            "capture_reason": request.reason.value,
            "file_path": relative_path,
            "window_app": window_app,
            "window_title": window_title,
            "frequency_level": request.frequency_level,
            "engaged_segment_id": request.engaged_segment_id,
            "is_afk": 1 if request.is_afk else 0,
        }

        try:
            created = self.provider.create_capture(payload)
            if not created:
                raise RuntimeError("screenshot metadata insert returned false")
        except Exception:
            if file_path.exists():
                file_path.unlink()
            raise

        return payload
