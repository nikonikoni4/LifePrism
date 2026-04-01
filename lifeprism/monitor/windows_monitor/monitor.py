import time
import re
from datetime import datetime
from typing import Optional, List
from lifeprism.utils.logger import get_logger
from .windows_api import get_active_window_handle, get_window_title, get_app_name
from .storage import Storage

logger = get_logger(__name__)

class WindowMonitor:
    def __init__(self, config: dict, storage: Storage):
        self.config = config
        self.storage = storage
        self.poll_time = config.get("poll_time", 1.0)
        self.exclude_titles = config.get("exclude_titles", [])

        self.current_app: Optional[str] = None
        self.current_title: Optional[str] = None
        self.start_time: Optional[datetime] = None

        self._running = False
        self._compile_exclude_patterns()

    def _compile_exclude_patterns(self):
        self._exclude_patterns = [re.compile(p) for p in self.exclude_titles]

    def _should_exclude(self, title: str) -> bool:
        for pattern in self._exclude_patterns:
            if pattern.search(title):
                return True
        return False

    def _flush(self):
        """将当前在内存中的事件保存到存储中"""
        if self.current_app is not None and self.start_time is not None:
            now = datetime.now()
            duration = (now - self.start_time).total_seconds()
            if duration > 0:
                self.storage.save_event(
                    timestamp=self.start_time.isoformat(),
                    duration=duration,
                    app=self.current_app,
                    title=self.current_title
                )
            self.start_time = now

    def run(self):
        self._running = True
        logger.info(f"WindowMonitor started (poll_time: {self.poll_time}s)")

        try:
            while self._running:
                hwnd = get_active_window_handle()
                if hwnd:
                    app = get_app_name(hwnd)
                    title = get_window_title(hwnd)

                    if self._should_exclude(title):
                        self._flush()
                        self.current_app = None
                        self.current_title = None
                        self.start_time = None
                    elif app != self.current_app or title != self.current_title:
                        # 窗口改变，保存旧事件
                        self._flush()
                        # 开始新事件
                        self.current_app = app
                        self.current_title = title
                        self.start_time = datetime.now()
                else:
                    # 无活跃窗口（如锁屏或无焦点）
                    self._flush()
                    self.current_app = None
                    self.current_title = None
                    self.start_time = None

                time.sleep(self.poll_time)
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        finally:
            self.stop()

    def stop(self):
        if self._running:
            logger.info("Stopping WindowMonitor...")
            self._flush()
            self._running = False
