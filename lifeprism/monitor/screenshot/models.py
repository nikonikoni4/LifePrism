from dataclasses import dataclass
from enum import Enum


class CaptureReason(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENTER = "enter"


@dataclass(frozen=True)
class FrequencyPolicy:
    level: int
    first_active_after_seconds: int
    repeat_active_every_seconds: int
    enter_cooldown_seconds: int


@dataclass(frozen=True)
class WindowContext:
    app: str | None
    title: str | None
    is_afk: bool


@dataclass(frozen=True)
class CaptureRequest:
    reason: CaptureReason
    captured_at: str
    window_app: str | None
    window_title: str | None
    frequency_level: int | None
    engaged_segment_id: str | None
    is_afk: bool
