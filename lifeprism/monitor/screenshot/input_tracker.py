import threading
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class InputSnapshot:
    engaged: bool
    engaged_segment_id: str | None
    last_keyboard_at: float | None
    last_mouse_at: float | None


class InputActivityTracker:
    """维护输入 keepalive、engaged 状态与 enter 事件缓冲。"""

    def __init__(
        self,
        keyboard_keepalive_seconds: int,
        mouse_keepalive_seconds: int,
        time_source: Callable[[], float],
        segment_id_factory: Callable[[], str],
    ) -> None:
        self.keyboard_keepalive_seconds = keyboard_keepalive_seconds
        self.mouse_keepalive_seconds = mouse_keepalive_seconds
        self.time_source = time_source
        self.segment_id_factory = segment_id_factory
        self._last_keyboard_at: float | None = None
        self._last_mouse_at: float | None = None
        self._engaged_segment_id: str | None = None
        self._pending_enter_events: list[float] = []
        self._lock = threading.Lock()

    def record_keyboard_event(self, key_name: str) -> None:
        """记录键盘事件，更新活跃状态并缓冲 Enter 键事件。

        Args:
            key_name: 按键名称，如 "a", "Enter", "Shift" 等
        """
        now = self.time_source()
        with self._lock:
            self._last_keyboard_at = now
            if self._engaged_segment_id is None:
                self._engaged_segment_id = self.segment_id_factory()
            if key_name.lower() == "enter":
                self._pending_enter_events.append(now)

    def record_mouse_event(self) -> None:
        """记录鼠标事件，更新活跃状态。"""
        now = self.time_source()
        with self._lock:
            self._last_mouse_at = now
            if self._engaged_segment_id is None:
                self._engaged_segment_id = self.segment_id_factory()

    def snapshot(self) -> InputSnapshot:
        """生成当前输入状态的快照。

        Returns:
            InputSnapshot: 包含活跃状态、活跃段 ID 和最后输入时间的快照
        """
        now = self.time_source()
        with self._lock:
            keyboard_alive = (
                self._last_keyboard_at is not None
                and now - self._last_keyboard_at <= self.keyboard_keepalive_seconds
            )
            mouse_alive = (
                self._last_mouse_at is not None
                and now - self._last_mouse_at <= self.mouse_keepalive_seconds
            )
            engaged = keyboard_alive or mouse_alive
            if not engaged:
                self._engaged_segment_id = None
            return InputSnapshot(
                engaged=engaged,
                engaged_segment_id=self._engaged_segment_id,
                last_keyboard_at=self._last_keyboard_at,
                last_mouse_at=self._last_mouse_at,
            )

    def consume_enter_events(self) -> list[float]:
        """消费并清空缓冲的 Enter 键事件。

        Returns:
            Enter 键事件时间戳列表（秒，浮点数）
        """
        with self._lock:
            events = list(self._pending_enter_events)
            self._pending_enter_events.clear()
            return events
