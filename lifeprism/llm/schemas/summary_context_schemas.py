from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SummaryType = Literal["daily", "weekly", "monthly"]
DayWindowMode = Literal["4_to_4"]
CoverageLevel = Literal["none", "low", "medium", "high"]
ConfidenceLevel = Literal["low", "medium", "high"]
SegmentType = Literal["active", "long_computer_usage"]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SummaryRange(StrictBaseModel):
    start: str
    end: str
    timezone: str
    day_window_mode: DayWindowMode


class LimitationItem(StrictBaseModel):
    code: str
    message: str


class CoverageContext(StrictBaseModel):
    has_activity_data: bool
    has_todo_data: bool
    has_goal_data: bool
    has_habit_data: bool
    has_custom_blocks: bool
    has_diary: bool
    has_diary_ai_summary: bool
    has_mood: bool
    has_screenshot_data: bool = False
    activity_coverage_level: CoverageLevel
    execution_coverage_level: CoverageLevel
    authored_coverage_level: CoverageLevel
    overall_coverage_level: CoverageLevel
    limitations: list[LimitationItem] = Field(default_factory=list)


class CategoryBreakdownItem(StrictBaseModel):
    category_id: str
    category_name: str
    minutes: int
    ratio: float


class ActivitySegment(StrictBaseModel):
    start: str
    end: str
    duration_minutes: int
    segment_type: SegmentType
    density_threshold: float
    bridge_bucket_count: int = 0
    top_categories: list[CategoryBreakdownItem] = Field(default_factory=list)


class WorkEntertainmentMix(StrictBaseModel):
    should_analyze: bool
    reason: str


class ActivityContext(StrictBaseModel):
    total_active_minutes: int
    category_breakdown: list[CategoryBreakdownItem] = Field(default_factory=list)
    active_segments: list[ActivitySegment] = Field(default_factory=list)
    long_computer_usage_segments: list[ActivitySegment] = Field(default_factory=list)
    work_entertainment_mix: WorkEntertainmentMix


class TodoExecutionItem(StrictBaseModel):
    todo_id: str
    title: str


class HabitExecutionItem(StrictBaseModel):
    habit_id: str
    name: str


class TodoExecutionContext(StrictBaseModel):
    total: int
    completed: int
    incomplete: int
    overdue: int
    completion_rate: float
    completed_items: list[TodoExecutionItem] = Field(default_factory=list)
    overdue_items: list[TodoExecutionItem] = Field(default_factory=list)


class HabitExecutionContext(StrictBaseModel):
    tracked: int
    completed_checkins: int
    missed_checkins: int
    completion_rate: float
    completed_items: list[HabitExecutionItem] = Field(default_factory=list)
    missed_items: list[HabitExecutionItem] = Field(default_factory=list)


class ExecutionContext(StrictBaseModel):
    todos: TodoExecutionContext
    habits: HabitExecutionContext


class CustomBlockItem(StrictBaseModel):
    block_id: str
    start: str
    end: str
    text: str


class DiaryContext(StrictBaseModel):
    exists: bool
    title: str | None = None
    content_excerpt: str | None = None


class DiaryAISummaryContext(StrictBaseModel):
    exists: bool
    summary: str | None = None


class MoodEntryItem(StrictBaseModel):
    entry_id: str
    mood_type_id: str
    score: int
    content: str | None = None
    created_at: str


class MoodContext(StrictBaseModel):
    exists: bool
    entries: list[MoodEntryItem] = Field(default_factory=list)


class AuthoredContext(StrictBaseModel):
    custom_blocks: list[CustomBlockItem] = Field(default_factory=list)
    diary: DiaryContext
    diary_ai_summary: DiaryAISummaryContext
    mood: MoodContext


class UncertaintyContext(StrictBaseModel):
    confidence_level: ConfidenceLevel
    visible_messages: list[str] = Field(default_factory=list)
    inference_warnings: list[str] = Field(default_factory=list)


class SummaryContext(StrictBaseModel):
    summary_type: SummaryType
    range: SummaryRange
    coverage: CoverageContext
    activity: ActivityContext
    execution: ExecutionContext
    authored: AuthoredContext
    uncertainty: UncertaintyContext
