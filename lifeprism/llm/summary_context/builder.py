from __future__ import annotations

from typing import Any

from lifeprism.llm.schemas.summary_context_schemas import (
    ActivityContext,
    ActivitySegment,
    AuthoredContext,
    CategoryBreakdownItem,
    CoverageContext,
    CustomBlockItem,
    DiaryAISummaryContext,
    DiaryContext,
    ExecutionContext,
    HabitExecutionContext,
    HabitExecutionItem,
    LimitationItem,
    MoodContext,
    MoodEntryItem,
    SummaryContext,
    SummaryRange,
    TodoExecutionContext,
    TodoExecutionItem,
    UncertaintyContext,
    WorkEntertainmentMix,
)


def build_summary_context(raw_context: dict[str, Any]) -> SummaryContext:
    """将 service 层返回的原始字典映射为 SummaryContext schema。

    这是数据转换的主入口，将松散的字典结构转换为严格的 Pydantic 模型，
    确保类型安全和字段完整性。

    Args:
        raw_context: service 层返回的原始上下文字典

    Returns:
        SummaryContext: 结构化的总结上下文对象
    """

    return SummaryContext(
        summary_type=raw_context["summary_type"],
        range=_build_summary_range(raw_context["range"]),
        coverage=_build_coverage_context(raw_context["coverage"]),
        activity=_build_activity_context(raw_context["activity"]),
        execution=_build_execution_context(raw_context["execution"]),
        authored=_build_authored_context(raw_context["authored"]),
        uncertainty=_build_uncertainty_context(raw_context["uncertainty"]),
    )


def _build_summary_range(raw: dict[str, Any]) -> SummaryRange:
    """构建时间范围对象"""
    return SummaryRange(
        start=raw["start"],
        end=raw["end"],
        timezone=raw["timezone"],
        day_window_mode=raw["day_window_mode"],
    )


def _build_coverage_context(raw: dict[str, Any]) -> CoverageContext:
    """构建数据覆盖度上下文对象"""
    return CoverageContext(
        has_activity_data=raw["has_activity_data"],
        has_todo_data=raw["has_todo_data"],
        has_goal_data=raw["has_goal_data"],
        has_habit_data=raw["has_habit_data"],
        has_custom_blocks=raw["has_custom_blocks"],
        has_diary=raw["has_diary"],
        has_diary_ai_summary=raw["has_diary_ai_summary"],
        has_mood=raw["has_mood"],
        has_screenshot_data=raw["has_screenshot_data"],
        activity_coverage_level=raw["activity_coverage_level"],
        execution_coverage_level=raw["execution_coverage_level"],
        authored_coverage_level=raw["authored_coverage_level"],
        overall_coverage_level=raw["overall_coverage_level"],
        limitations=[
            LimitationItem(code=item["code"], message=item["message"])
            for item in raw["limitations"]
        ],
    )


def _build_activity_context(raw: dict[str, Any]) -> ActivityContext:
    """构建活动上下文对象，将秒转换为分钟"""
    return ActivityContext(
        total_active_minutes=raw["total_active_seconds"] // 60,
        category_breakdown=[
            CategoryBreakdownItem(
                category_id=item["category_id"],
                category_name=item["category_name"],
                minutes=item["seconds"] // 60,
                ratio=item["ratio"],
            )
            for item in raw["category_breakdown"]
        ],
        active_segments=[
            ActivitySegment(
                start=seg["start"],
                end=seg["end"],
                duration_minutes=seg["duration_seconds"] // 60,
                segment_type=seg["segment_type"],
                density_threshold=seg["density_threshold"],
                bridge_bucket_count=seg["bridge_bucket_count"],
                top_categories=[
                    CategoryBreakdownItem(
                        category_id=cat["category_id"],
                        category_name=cat["category_name"],
                        minutes=cat["seconds"] // 60,
                        ratio=cat["ratio"],
                    )
                    for cat in seg["top_categories"]
                ],
            )
            for seg in raw["active_segments"]
        ],
        long_computer_usage_segments=[
            ActivitySegment(
                start=seg["start"],
                end=seg["end"],
                duration_minutes=seg["duration_seconds"] // 60,
                segment_type=seg["segment_type"],
                density_threshold=seg["density_threshold"],
                bridge_bucket_count=seg["bridge_bucket_count"],
                top_categories=[
                    CategoryBreakdownItem(
                        category_id=cat["category_id"],
                        category_name=cat["category_name"],
                        minutes=cat["seconds"] // 60,
                        ratio=cat["ratio"],
                    )
                    for cat in seg["top_categories"]
                ],
            )
            for seg in raw["long_computer_usage_segments"]
        ],
        work_entertainment_mix=WorkEntertainmentMix(
            should_analyze=raw["work_entertainment_mix"]["should_analyze"],
            reason=raw["work_entertainment_mix"]["reason"],
        ),
    )


def _build_execution_context(raw: dict[str, Any]) -> ExecutionContext:
    """构建执行上下文对象"""
    return ExecutionContext(
        todos=TodoExecutionContext(
            total=raw["todos"]["total"],
            completed=raw["todos"]["completed"],
            incomplete=raw["todos"]["incomplete"],
            overdue=raw["todos"]["overdue"],
            completion_rate=raw["todos"]["completion_rate"],
            completed_items=[
                TodoExecutionItem(todo_id=item["todo_id"], title=item["title"])
                for item in raw["todos"]["completed_items"]
            ],
            overdue_items=[
                TodoExecutionItem(todo_id=item["todo_id"], title=item["title"])
                for item in raw["todos"]["overdue_items"]
            ],
        ),
        habits=HabitExecutionContext(
            tracked=raw["habits"]["tracked"],
            completed_checkins=raw["habits"]["completed_checkins"],
            missed_checkins=raw["habits"]["missed_checkins"],
            completion_rate=raw["habits"]["completion_rate"],
            completed_items=[
                HabitExecutionItem(habit_id=item["habit_id"], name=item["name"])
                for item in raw["habits"]["completed_items"]
            ],
            missed_items=[
                HabitExecutionItem(habit_id=item["habit_id"], name=item["name"])
                for item in raw["habits"]["missed_items"]
            ],
        ),
    )


def _build_authored_context(raw: dict[str, Any]) -> AuthoredContext:
    """构建主观输入上下文对象"""
    return AuthoredContext(
        custom_blocks=[
            CustomBlockItem(
                block_id=block["block_id"],
                start=block["start"],
                end=block["end"],
                text=block["text"],
            )
            for block in raw["custom_blocks"]
        ],
        diary=DiaryContext(
            exists=raw["diary"]["exists"],
            title=raw["diary"]["title"],
            content_excerpt=raw["diary"]["content_excerpt"],
        ),
        diary_ai_summary=DiaryAISummaryContext(
            exists=raw["diary_ai_summary"]["exists"],
            summary=raw["diary_ai_summary"]["summary"],
        ),
        mood=MoodContext(
            exists=raw["mood"]["exists"],
            entries=[
                MoodEntryItem(
                    entry_id=entry["entry_id"],
                    mood_type_id=entry["mood_type_id"],
                    score=entry["score"],
                    content=entry["content"],
                    created_at=entry["created_at"],
                )
                for entry in raw["mood"]["entries"]
            ],
        ),
    )


def _build_uncertainty_context(raw: dict[str, Any]) -> UncertaintyContext:
    """构建不确定性上下文对象"""
    return UncertaintyContext(
        confidence_level=raw["confidence_level"],
        visible_messages=raw["visible_messages"],
        inference_warnings=raw["inference_warnings"],
    )


if __name__ == "__main__":
    from lifeprism.llm.summary_context.service import get_daily_summary_context
    import json

    result = build_summary_context(get_daily_summary_context("2026-04-02"))
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))