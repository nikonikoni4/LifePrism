from dataclasses import dataclass
from enum import Enum
from typing import Optional


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
    app: Optional[str]
    title: Optional[str]
    is_afk: bool


@dataclass(frozen=True)
class CaptureRequest:
    reason: CaptureReason
    captured_at: str
    window_app: Optional[str]
    window_title: Optional[str]
    frequency_level: Optional[int]
    engaged_segment_id: Optional[str]
    is_afk: bool
