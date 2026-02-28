"""习惯系统 Request / Response Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal


# ============================================================================
# 公共子模型
# ============================================================================

class FrequencyObject(BaseModel):
    type: Literal["daily", "weekdays", "weekend", "custom"] = Field(..., description="频率类型")
    specificDays: Optional[List[int]] = Field(default=None, description="每周哪几天执行（0=周一...6=周日），custom 类型时必填")


class ChallengeObject(BaseModel):
    id: str
    habitId: str
    fromLevel: int
    toLevel: int
    challengeWeeks: int
    requiredCompletions: int
    completedCount: int
    startDate: str
    endDate: str
    streakBase: int
    status: str
    finishedAt: Optional[str] = None


class AnchorInfoObject(BaseModel):
    chainName: str
    nodeName: str
    triggerTime: Optional[str] = None


class SettlementItem(BaseModel):
    habitId: str
    habitName: str
    result: Literal["succeeded", "failed"]
    fromLevel: int
    toLevel: int
    completedCount: int
    requiredCompletions: int
    canSaveByBackfill: bool = False


# ============================================================================
# Habit CRUD
# ============================================================================

class CreateHabitRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    frequency: FrequencyObject
    initialLevel: int = Field(default=0, ge=0, le=4)
    valueId: Optional[str] = None
    commitmentId: Optional[str] = None


class UpdateHabitRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    frequency: Optional[FrequencyObject] = None
    level: Optional[int] = Field(default=None, ge=0, le=4)
    valueId: Optional[str] = None
    commitmentId: Optional[str] = None


class HabitListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    frequency: FrequencyObject
    currentLevel: int
    status: str
    currentChallenge: Optional[ChallengeObject] = None
    valueId: Optional[str] = None
    commitmentId: Optional[str] = None
    createdAt: str
    pausedAt: Optional[str] = None
    streak: int = 0
    anchorInfo: Optional[AnchorInfoObject] = None


class HabitDetailResponse(HabitListItem):
    pass


class HabitListResponse(BaseModel):
    habits: List[HabitListItem] = Field(default_factory=list)


# ============================================================================
# CheckIn
# ============================================================================

class CheckInObject(BaseModel):
    id: str
    habitId: str
    challengeId: str
    date: str
    completed: bool = True
    completedAt: Optional[str] = None
    createdAt: str


class CheckInResponse(BaseModel):
    checkin: CheckInObject
    habit: HabitListItem
    settlement: Optional[SettlementItem] = None


class CancelCheckInResponse(BaseModel):
    habit: HabitListItem
    settlement: Optional[SettlementItem] = None


class BackfillCheckInRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="补签日期 YYYY-MM-DD")


# ============================================================================
# Stats
# ============================================================================

class TodayOverviewItem(BaseModel):
    habitId: str
    name: str
    isScheduledToday: bool
    todayCheckedIn: bool


class TodayOverviewResponse(BaseModel):
    items: List[TodayOverviewItem] = Field(default_factory=list)
    scheduledCount: int = 0
    completedCount: int = 0


class WeeklyStatsResponse(BaseModel):
    completionRate: float  # 0.0~1.0，所有习惯本周完成率的算术平均值


class HeatmapDayItem(BaseModel):
    date: str
    count: int  # 当天所有习惯的打卡总数


class HeatmapResponse(BaseModel):
    days: List[HeatmapDayItem] = Field(default_factory=list)


# ============================================================================
# Chain / Node
# ============================================================================

class ChainNodeObject(BaseModel):
    id: int
    sortOrder: int
    name: str
    habitId: Optional[str] = None
    habitName: Optional[str] = None
    triggerTime: Optional[str] = None


class ChainListItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    showInTimeline: bool = False
    nodes: List[ChainNodeObject] = Field(default_factory=list)


class ChainDetailResponse(ChainListItem):
    pass


class ChainListResponse(BaseModel):
    chains: List[ChainListItem] = Field(default_factory=list)


class CreateChainRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class UpdateChainRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    showInTimeline: Optional[bool] = None


class CreateNodeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    habitId: Optional[str] = None
    triggerTime: Optional[str] = None
    insertAfterNodeId: Optional[int] = None  # None = 追加到末尾


class UpdateNodeRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    habitId: Optional[str] = None
    triggerTime: Optional[str] = None


class ReorderItem(BaseModel):
    nodeId: int
    sortOrder: int


class ReorderNodesRequest(BaseModel):
    items: List[ReorderItem]


# ============================================================================
# Timeline
# ============================================================================

class TimelineNodeItem(BaseModel):
    id: int
    name: str
    habitId: Optional[str] = None
    habitName: Optional[str] = None
    triggerTime: Optional[str] = None
    sortOrder: int
    todayCheckedIn: bool = False


class TimelineChainItem(BaseModel):
    id: int
    name: str
    nodes: List[TimelineNodeItem] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    chains: List[TimelineChainItem] = Field(default_factory=list)


# ============================================================================
# Settlement
# ============================================================================

class CheckSettlementsResponse(BaseModel):
    settlements: List[SettlementItem] = Field(default_factory=list)


# ============================================================================
# Challenge History
# ============================================================================

class ChallengeHistoryResponse(BaseModel):
    challenges: List[ChallengeObject] = Field(default_factory=list)
