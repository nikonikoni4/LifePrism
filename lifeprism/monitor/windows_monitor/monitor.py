import time
import re
from datetime import datetime
from typing import Optional, List
from lifeprism.utils.logger import get_logger
from lifeprism.monitor.windows_monitor.windows_api import (
    get_active_window_handle,
    get_window_title,
    get_app_name,
    get_last_input_time,
    get_tick_count,
    is_any_video_playing
)
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
from lifeprism.config.settings_manager import settings

logger = get_logger(__name__)

class WindowMonitor:
    def __init__(self, provider: MonitorDataProvider):
        self.provider = provider
        self.poll_time = settings.get("poll_time", 1.0)
        self.exclude_titles = settings.get("exclude_titles", [])
        self.afk_timeout = settings.get("afk_timeout", 180.0)

        self.current_app: Optional[str] = None
        self.current_title: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.is_afk = False

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
                self.provider.save_event(
                    timestamp=self.start_time.isoformat(),
                    duration=duration,
                    app=self.current_app,
                    title=self.current_title
                )
            self.start_time = now

    def run(self):
        self._running = True
        logger.info(f"WindowMonitor started (poll_time: {self.poll_time}s, afk_timeout: {self.afk_timeout}s)")

        try:
            while self._running:
                # 1. 检测 AFK 状态
                last_input = get_last_input_time()
                now_tick = get_tick_count()
                idle_time = now_tick - last_input

                # 如果超过阈值且没有视频播放请求，判定为 AFK
                currently_afk = idle_time > self.afk_timeout and not is_any_video_playing()

                if currently_afk:
                    if not self.is_afk:
                        # 刚进入 AFK 状态，保存当前窗口并清空状态（不追踪 AFK 时间段）
                        logger.info(f"User is AFK (idle for {idle_time:.1f}s)")
                        self._flush()
                        self.is_afk = True
                        # self.current_app = "AFK"
                        # self.current_title = "Away From Keyboard"
                        # self.start_time = datetime.now()
                        self.current_app = None
                        self.current_title = None
                        self.start_time = None
                else:
                    if self.is_afk:
                        # 从 AFK 状态恢复
                        logger.info("User is back from AFK")
                        self._flush()
                        self.is_afk = False
                        # 强制触发重新获取窗口
                        self.current_app = None

                # 2. 如果非 AFK，处理窗口逻辑
                if not self.is_afk:
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
                            self._flush()
                            self.current_app = app
                            self.current_title = title
                            self.start_time = datetime.now()
                    else:
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
