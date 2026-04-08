from typing import Dict, List

from lifeprism.monitor.screenshot.models import CaptureReason, CaptureRequest, FrequencyPolicy, WindowContext


class ScreenshotScheduler:
    """根据窗口状态、engaged 状态和频率策略生成截图请求。"""

    def __init__(
        self,
        policy: FrequencyPolicy,
        scheduled_interval_seconds: int,
        enter_delay_ms: int,
    ) -> None:
        self.policy = policy
        self.scheduled_interval_seconds = scheduled_interval_seconds
        self.enter_delay_ms = enter_delay_ms
        self._next_scheduled_at: float | None = None
        self._segment_started_at: Dict[str, float] = {}
        self._segment_first_active_done: set[str] = set()
        self._next_active_at: Dict[str, float] = {}
        self._enter_cooldown_until = 0.0

    def evaluate(
        self,
        now_epoch: float,
        now_iso: str,
        window: WindowContext,
        engaged: bool,
        engaged_segment_id: str | None,
        enter_events: List[float],
    ) -> List[CaptureRequest]:
        """根据当前状态评估并生成截图请求。

        Args:
            now_epoch: 当前时间戳（秒，浮点数）
            now_iso: 当前时间的 ISO 格式字符串
            window: 当前窗口上下文（应用名、标题、是否 AFK）
            engaged: 用户是否处于活跃状态（键盘/鼠标有输入）
            engaged_segment_id: 当前活跃段的唯一标识符，None 表示未活跃
            enter_events: 待处理的 Enter 键事件时间戳列表

        Returns:
            截图请求列表，可能包含以下类型：
            - SCHEDULED: 固定周期截图
            - ACTIVE: 用户活跃时的截图（首次或重复）
            - ENTER: 按下 Enter 键后的延迟截图
        """
        if window.is_afk:
            return []

        requests: List[CaptureRequest] = []

        if self._next_scheduled_at is None:
            self._next_scheduled_at = now_epoch + self.scheduled_interval_seconds
        elif now_epoch >= self._next_scheduled_at:
            requests.append(
                CaptureRequest(
                    reason=CaptureReason.SCHEDULED,
                    captured_at=now_iso,
                    window_app=window.app,
                    window_title=window.title,
                    frequency_level=None,
                    engaged_segment_id=None,
                )
            )
            self._next_scheduled_at = now_epoch + self.scheduled_interval_seconds

        if not engaged or not engaged_segment_id:
            return requests

        segment_started_at = self._segment_started_at.setdefault(engaged_segment_id, now_epoch)
        if (
            engaged_segment_id not in self._segment_first_active_done
            and now_epoch - segment_started_at >= self.policy.first_active_after_seconds
        ):
            requests.append(
                CaptureRequest(
                    reason=CaptureReason.ACTIVE,
                    captured_at=now_iso,
                    window_app=window.app,
                    window_title=window.title,
                    frequency_level=self.policy.level,
                    engaged_segment_id=engaged_segment_id,
                )
            )
            self._segment_first_active_done.add(engaged_segment_id)
            self._next_active_at[engaged_segment_id] = (
                now_epoch + self.policy.repeat_active_every_seconds
            )
        elif now_epoch >= self._next_active_at.get(engaged_segment_id, float("inf")):
            requests.append(
                CaptureRequest(
                    reason=CaptureReason.ACTIVE,
                    captured_at=now_iso,
                    window_app=window.app,
                    window_title=window.title,
                    frequency_level=self.policy.level,
                    engaged_segment_id=engaged_segment_id,
                )
            )
            self._next_active_at[engaged_segment_id] = (
                now_epoch + self.policy.repeat_active_every_seconds
            )

        due_enter_events = [
            event_time
            for event_time in enter_events
            if event_time + (self.enter_delay_ms / 1000.0) <= now_epoch
        ]
        if due_enter_events and now_epoch >= self._enter_cooldown_until:
            requests.append(
                CaptureRequest(
                    reason=CaptureReason.ENTER,
                    captured_at=now_iso,
                    window_app=window.app,
                    window_title=window.title,
                    frequency_level=self.policy.level,
                    engaged_segment_id=engaged_segment_id,
                )
            )
            self._enter_cooldown_until = now_epoch + self.policy.enter_cooldown_seconds

        return requests
