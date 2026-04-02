from pydantic import ValidationError
import pytest

from lifeprism.llm.schemas.summary_context_schemas import (
    SummaryContext,
    SummaryRange,
    CoverageContext,
    ActivityContext,
    ExecutionContext,
    AuthoredContext,
    UncertaintyContext,
    ActivitySegment,
    CategoryBreakdownItem,
)


def _make_context() -> SummaryContext:
    return SummaryContext(
        summary_type="daily",
        range=SummaryRange(
            start="2026-04-02T04:00:00+08:00",
            end="2026-04-03T04:00:00+08:00",
            timezone="Asia/Hong_Kong",
            day_window_mode="4_to_4",
        ),
        coverage=CoverageContext(
            has_activity_data=True,
            has_todo_data=True,
            has_goal_data=False,
            has_habit_data=True,
            has_custom_blocks=False,
            has_diary=True,
            has_diary_ai_summary=True,
            has_mood=False,
            has_screenshot_data=False,
            activity_coverage_level="high",
            execution_coverage_level="medium",
            authored_coverage_level="low",
            overall_coverage_level="medium",
            limitations=[],
        ),
        activity=ActivityContext(
            total_active_seconds=3600,
            category_breakdown=[
                CategoryBreakdownItem(
                    category_id="cat-work",
                    category_name="工作",
                    seconds=2400,
                    ratio=0.67,
                )
            ],
            active_segments=[
                ActivitySegment(
                    start="2026-04-02T09:00:00+08:00",
                    end="2026-04-02T10:00:00+08:00",
                    duration_seconds=3600,
                    segment_type="active",
                    density_threshold=0.2,
                    bridge_bucket_count=1,
                    top_categories=[],
                )
            ],
            long_computer_usage_segments=[],
            work_entertainment_mix={
                "should_analyze": False,
                "reason": "missing_required_main_categories",
            },
        ),
        execution=ExecutionContext(
            todos={
                "total": 2,
                "completed": 1,
                "incomplete": 1,
                "overdue": 0,
                "completion_rate": 0.5,
                "completed_items": [],
                "overdue_items": [],
            },
            habits={
                "tracked": 1,
                "completed_checkins": 1,
                "missed_checkins": 0,
                "completion_rate": 1.0,
                "completed_items": [],
                "missed_items": [],
            },
        ),
        authored=AuthoredContext(
            custom_blocks=[],
            diary={"exists": True, "title": "2026-04-02", "content_excerpt": "hello"},
            diary_ai_summary={"exists": True, "summary": "done"},
            mood={"exists": False, "entries": []},
        ),
        uncertainty=UncertaintyContext(
            confidence_level="medium",
            visible_messages=["缺少 custom block"],
            inference_warnings=["节奏结论基于密度分段"],
        ),
    )


def test_summary_context_matches_prd_shape():
    payload = _make_context().model_dump(mode="json")
    assert payload["summary_type"] == "daily"
    assert payload["range"]["day_window_mode"] == "4_to_4"
    assert payload["activity"]["active_segments"][0]["segment_type"] == "active"
    assert payload["coverage"]["overall_coverage_level"] == "medium"


def test_summary_type_rejects_invalid_value():
    with pytest.raises(ValidationError):
        SummaryContext(**{**_make_context().model_dump(), "summary_type": "yearly"})


def test_day_window_mode_rejects_invalid_value():
    payload = _make_context().model_dump()
    payload["range"]["day_window_mode"] = "0_to_24"
    with pytest.raises(ValidationError):
        SummaryContext(**payload)


def test_coverage_level_rejects_invalid_value():
    payload = _make_context().model_dump()
    payload["coverage"]["overall_coverage_level"] = "very_high"
    with pytest.raises(ValidationError):
        SummaryContext(**payload)


def test_segment_type_rejects_invalid_value():
    payload = _make_context().model_dump()
    payload["activity"]["active_segments"][0]["segment_type"] = "focus"
    with pytest.raises(ValidationError):
        SummaryContext(**payload)


def test_extra_fields_are_forbidden_on_submodel():
    payload = _make_context().model_dump()
    payload["coverage"]["unexpected"] = True
    with pytest.raises(ValidationError):
        SummaryContext(**payload)
