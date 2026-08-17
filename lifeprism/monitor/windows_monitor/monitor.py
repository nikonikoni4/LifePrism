import re
import threading
import time
from datetime import datetime, timezone

from lifeprism.config.settings_manager import settings
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
from lifeprism.monitor.screenshot.models import WindowContext
from lifeprism.monitor.windows_monitor.windows_api import (
    get_active_window_handle,
    get_app_name,
    get_last_input_time,
    get_tick_count,
    get_window_title,
    is_any_video_playing,
)
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)


class WindowMonitor:
    def __init__(self, provider: MonitorDataProvider):
        self.provider = provider
        self.poll_time = settings.get("poll_time", 1.0)
        self.exclude_titles = settings.get("exclude_titles", [])
        self.afk_timeout = settings.get("afk_timeout", 180.0)
        # 媒体播放时的 AFK 上限（秒）。非媒体场景由 afk_timeout 生效，此项实际只对
        # is_any_video_playing()=True 的场景起作用，避免全屏看视频/玩游戏离开后时长无限积累。
        self.afk_timeout_media = settings.get("afk_timeout_media", 3600.0)

        self.current_app: str | None = None
        self.current_title: str | None = None
        self.start_time: datetime | None = None
        self.is_afk = False
        self._state_lock = threading.Lock()

        self._running = False
        self._compile_exclude_patterns()

    def _compile_exclude_patterns(self):
        self._exclude_patterns = [re.compile(p) for p in self.exclude_titles]

    def _should_exclude(self, title: str) -> bool:
        return any(pattern.search(title) for pattern in self._exclude_patterns)

    def _compute_afk_state(self, idle_time: float, video_playing: bool) -> bool:
        """根据空闲时间和媒体播放状态判定是否 AFK。

        - 媒体播放时使用 afk_timeout_media（更长，避免看视频被误判）
        - 非媒体时使用 afk_timeout（基础短超时）

        Args:
            idle_time: 距离最后一次键鼠输入的秒数
            video_playing: is_any_video_playing() 的返回值

        Returns:
            True 表示判定为 AFK
        """
        if video_playing:
            return idle_time > self.afk_timeout_media
        return idle_time > self.afk_timeout

    def _flush(self):
        """将当前在内存中的事件保存到存储中"""
        if self.current_app is not None and self.start_time is not None:
            now = datetime.now(timezone.utc)
            duration = (now - self.start_time).total_seconds()
            if duration > 0:
                self.provider.save_event(
                    timestamp=self.start_time.isoformat(),
                    duration=duration,
                    app=self.current_app,
                    title=self.current_title,
                )
            self.start_time = now

    def snapshot_window_context(self) -> WindowContext:
        with self._state_lock:
            return WindowContext(
                app=self.current_app,
                title=self.current_title,
                is_afk=self.is_afk,
            )

    def run(self):
        self._running = True
        logger.info(
            "WindowMonitor started (poll_time: %ss, afk_timeout: %ss)",
            self.poll_time,
            self.afk_timeout,
        )

        try:
            while self._running:
                # 1. 检测 AFK 状态
                last_input = get_last_input_time()
                now_tick = get_tick_count()
                idle_time = now_tick - last_input

                # 媒体播放时使用更长的 afk_timeout_media，非媒体使用 afk_timeout
                currently_afk = self._compute_afk_state(idle_time, is_any_video_playing())

                if currently_afk:
                    if not self.is_afk:
                        # 刚进入 AFK 状态，保存当前窗口并清空状态（不追踪 AFK 时间段）
                        logger.debug("User is AFK (idle for %.1fs)", idle_time)
                        self._flush()
                        with self._state_lock:
                            self.is_afk = True
                            self.current_app = None
                            self.current_title = None
                            self.start_time = None
                else:
                    if self.is_afk:
                        # 从 AFK 状态恢复
                        logger.debug("User is back from AFK")
                        self._flush()
                        with self._state_lock:
                            self.is_afk = False
                            self.current_app = None

                # 2. 如果非 AFK，处理窗口逻辑
                if not self.is_afk:
                    hwnd = get_active_window_handle()
                    if hwnd:
                        app = get_app_name(hwnd)
                        title = get_window_title(hwnd)

                        if self._should_exclude(title):
                            self._flush()
                            with self._state_lock:
                                self.current_app = None
                                self.current_title = None
                                self.start_time = None
                        elif app != self.current_app or title != self.current_title:
                            self._flush()
                            with self._state_lock:
                                self.current_app = app
                                self.current_title = title
                                self.start_time = datetime.now(timezone.utc)
                    else:
                        self._flush()
                        with self._state_lock:
                            self.current_app = None
                            self.current_title = None
                            self.start_time = None

                time.sleep(self.poll_time)
        except Exception as e:
            # LEGITIMATE: API 边界兜底 — 监控主循环异常退出
            logger.error("Monitor loop error: %s", e)
        finally:
            self.stop()

    def stop(self):
        if self._running:
            logger.info("Stopping WindowMonitor...")
            self._flush()
            self._running = False
