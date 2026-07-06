from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class CleanupResult:
    deleted_files: int = 0
    deleted_rows: int = 0
    failed_files: int = 0


class ScreenshotCleanupWorker:
    """负责清理过期截图文件与元数据。"""

    def __init__(
        self,
        provider,
        data_root: Path,
        retention_days: int,
        delete_file_func: Callable[[Path], None] | None = None,
    ) -> None:
        self.provider = provider
        self.data_root = Path(data_root)
        self.retention_days = retention_days
        self.delete_file_func = delete_file_func or self._delete_file

    def run_once(self, now_iso: str) -> CleanupResult:
        """执行一次清理任务，删除过期的截图文件和元数据。

        Args:
            now_iso: 当前时间的 ISO 格式字符串

        Returns:
            CleanupResult: 清理结果统计（已删除文件数、已删除记录数、失败数）
        """
        cutoff = (datetime.fromisoformat(now_iso) - timedelta(days=self.retention_days)).isoformat()
        expired = self.provider.list_expired_captures(cutoff)

        deleted_files = 0
        deleted_rows = 0
        failed_files = 0

        for item in expired:
            target = self.data_root / item["file_path"]
            try:
                if target.exists():
                    self.delete_file_func(target)
                    deleted_files += 1
                self.provider.delete_capture(item["id"])
                deleted_rows += 1
            except FileNotFoundError:
                self.provider.delete_capture(item["id"])
                deleted_rows += 1
            except OSError:
                failed_files += 1

        return CleanupResult(
            deleted_files=deleted_files,
            deleted_rows=deleted_rows,
            failed_files=failed_files,
        )

    @staticmethod
    def _delete_file(target: Path) -> None:
        target.unlink()
