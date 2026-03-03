"""习惯系统 Request / Response Pydantic 模型"""
import re
from typing import List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def to_camel(value: str) -> str:
    """snake_case 转 camelCase。"""
    parts = value.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def to_snake(value: str) -> str:
    """camelCase 转 snake_case。"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


class APIModel(BaseModel):
    """统一输出 camelCase，内部字段使用 snake_case。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def __getattr__(self, item: str):
        snake_item = to_snake(item)
        if snake_item != item and snake_item in self.__class__.model_fields:
            return super().__getattribute__(snake_item)
        return super().__getattr__(item)


# ============================================================================
# 公共子模型
# ============================================================================


class FrequencyObject(APIModel):
    type: Literal["daily", "weekdays", "weekend", "custom"] = Field(..., description="频率类型")
    specific_days: Optional[List[int]] = Field(
        default=None,
        description="每周哪几天执行（1=周一...7=周日），custom 类型时必填",
    )

    @field_validator("specific_days")
    @classmethod
    def validate_specific_days(cls, values: Optional[List[int]]) -> Optional[List[int]]:
        if values is None:
            return values
        if any(day < 1 or day > 7 for day in values):
            raise ValueError("specificDays 必须在 1-7 范围内")
        return sorted(set(values))


class ChallengeObject(APIModel):
    id: str
    habit_id: str
    from_level: int
    to_level: int
    challenge_weeks: int
    required_completions: int
    completed_count: int
    start_date: str
    end_date: str
    streak_base: int
    status: str
    finished_at: Optional[str] = None


class AnchorInfoObject(APIModel):
    chain_name: str
    node_name: str
    trigger_time: Optional[str] = None


class SettlementItem(APIModel):
    challenge_id: str
    habit_id: str
    habit_name: str
    result: Literal["succeeded", "failed"]
    from_level: int
    to_level: int
    completed_count: int
    required_completions: int
    can_save_by_backfill: bool = False


# ============================================================================
# Habit CRUD
# ============================================================================


class CreateHabitRequest(APIModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    frequency: FrequencyObject
    initial_level: int = Field(default=0, ge=0, le=4)
    value_id: Optional[str] = None
    commitment_id: Optional[str] = None


class UpdateHabitRequest(APIModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    frequency: Optional[FrequencyObject] = None
    level: Optional[int] = Field(default=None, ge=0, le=4)
    value_id: Optional[str] = None
    commitment_id: Optional[str] = None


class HabitListItem(APIModel):
    id: str
    name: str
    description: Optional[str] = None
    frequency: FrequencyObject
    current_level: int
    status: str
    current_challenge: Optional[ChallengeObject] = None
    value_id: Optional[str] = None
    commitment_id: Optional[str] = None
    created_at: str
    paused_at: Optional[str] = None
    streak: int = 0
    today_completed: bool = False
    anchor_info: Optional[AnchorInfoObject] = None


class HabitDetailResponse(HabitListItem):
    pass


class HabitListResponse(APIModel):
    habits: List[HabitListItem] = Field(default_factory=list)


# ============================================================================
# CheckIn
# ============================================================================


class CheckInObject(APIModel):
    id: str
    habit_id: str
    challenge_id: str
    date: str
    completed: bool = True
    completed_at: Optional[str] = None
    created_at: str


class CheckInResponse(APIModel):
    checkin: CheckInObject
    habit: HabitListItem
    settlement: Optional[SettlementItem] = None


class CancelCheckInResponse(APIModel):
    habit: HabitListItem
    settlement: Optional[SettlementItem] = None


class BackfillCheckInRequest(APIModel):
    challenge_id: str = Field(..., min_length=1, description="目标挑战 ID")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="补签日期 YYYY-MM-DD")


class BackfillDateAvailabilityItem(APIModel):
    date: str = Field(..., description="日期 YYYY-MM-DD")
    selectable: bool = Field(..., description="是否可补录")
    reason: Optional[Literal["already_checked_in", "before_challenge_start", "after_challenge_end"]] = Field(
        default=None, description="不可补录原因"
    )


class BackfillAvailabilityRequest(APIModel):
    habit_id: str = Field(..., min_length=1, description="习惯 ID")
    challenge_id: str = Field(..., min_length=1, description="挑战 ID")


class BackfillAvailabilityResponse(APIModel):
    habit_id: str
    challenge_id: str
    days: List[BackfillDateAvailabilityItem] = Field(default_factory=list)


# ============================================================================
# Stats
# ============================================================================


class TodayOverviewItem(APIModel):
    habit_id: str
    name: str
    is_scheduled_today: bool
    today_checked_in: bool


class TodayOverviewResponse(APIModel):
    items: List[TodayOverviewItem] = Field(default_factory=list)
    scheduled_count: int = 0
    completed_count: int = 0


class WeeklyRateItem(APIModel):
    week_start_date: str
    week_end_date: str
    rate: float
    habit_count: int


class WeeklyStatsResponse(APIModel):
    weeks: List[WeeklyRateItem] = Field(default_factory=list)


class HeatmapDayItem(APIModel):
    date: str
    total_habits: int
    completed_habits: int
    completion_rate: Optional[float] = None
    is_rest_day: bool


class HeatmapResponse(APIModel):
    days: List[HeatmapDayItem] = Field(default_factory=list)


# ============================================================================
# Chain / Node
# ============================================================================


class ChainNodeObject(APIModel):
    id: int
    sort_order: int
    name: str
    habit_id: Optional[str] = None
    habit_name: Optional[str] = None
    trigger_time: Optional[str] = None


class ChainListItem(APIModel):
    id: int
    name: str
    description: Optional[str] = None
    show_in_timeline: bool = False
    nodes: List[ChainNodeObject] = Field(default_factory=list)


class ChainDetailResponse(ChainListItem):
    pass


class ChainListResponse(APIModel):
    chains: List[ChainListItem] = Field(default_factory=list)


class CreateChainRequest(APIModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class UpdateChainNodeTimeItem(APIModel):
    node_id: int
    trigger_time: str


class UpdateChainRequest(APIModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    show_in_timeline: Optional[bool] = None
    trigger_times: Optional[List[UpdateChainNodeTimeItem]] = None


class CreateNodeRequest(APIModel):
    name: str = Field(..., min_length=1, max_length=100)
    habit_id: Optional[str] = None
    trigger_time: Optional[str] = None
    insert_after_node_id: Optional[int] = None  # None = 追加到末尾


class UpdateNodeRequest(APIModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    habit_id: Optional[str] = None
    trigger_time: Optional[str] = None


class ReorderItem(APIModel):
    node_id: int
    sort_order: int


class ReorderNodesRequest(APIModel):
    items: List[ReorderItem] = Field(validation_alias=AliasChoices("items", "nodes"))


# ============================================================================
# Timeline
# ============================================================================


class TimelineNodeItem(APIModel):
    id: int
    name: str
    habit_id: Optional[str] = None
    habit_name: Optional[str] = None
    trigger_time: Optional[str] = None
    sort_order: int
    today_checked_in: bool = False


class TimelineChainItem(APIModel):
    id: int
    name: str
    nodes: List[TimelineNodeItem] = Field(default_factory=list)


class TimelineResponse(APIModel):
    chains: List[TimelineChainItem] = Field(default_factory=list)


# ============================================================================
# Settlement
# ============================================================================


class CheckSettlementsResponse(APIModel):
    settlements: List[SettlementItem] = Field(default_factory=list)


class SettlementActionRequest(APIModel):
    source: Literal["settlement"]
    challenge_id: str


# ============================================================================
# Challenge History
# ============================================================================


class ChallengeHistoryResponse(APIModel):
    challenges: List[ChallengeObject] = Field(default_factory=list)
