from __future__ import annotations

from typing import Any


def build_authored_context(
    custom_blocks: list[dict[str, Any]],
    diaries: list[dict[str, Any]],
    mood_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建用户主动输入的高语义内容上下文。

    聚合用户在 timeline 中手动添加的 custom blocks、日记、心情记录等主观数据，
    形成结构化的 authored 上下文，用于 AI 总结时理解用户的主观视角。

    Args:
        custom_blocks: timeline 中的自定义时间块列表，每项包含 id, start_time, end_time, text
        diaries: 日记列表，每项包含 date, content_excerpt, ai_summary 等字段
        mood_entries: 心情记录列表，每项包含 id, mood_type_id, score, content, created_at

    Returns:
        dict: 包含以下键的字典：
            - custom_blocks: 自定义时间块列表（block_id, start, end, text）
            - diary: 日记上下文（exists, title, content_excerpt）
            - diary_ai_summary: 日记 AI 摘要上下文（exists, summary）
            - mood: 心情上下文（exists, entries）
    """

    # 处理 custom_blocks
    custom_block_items = [
        {
            "block_id": str(block["id"]),  # 确保转换为字符串
            "start": block["start_time"],
            "end": block["end_time"],
            "text": block.get("content", ""),  # 字段名是 content 而不是 text
        }
        for block in custom_blocks
    ]

    # 处理 diary
    diary_context = {
        "exists": False,
        "title": None,
        "content_excerpt": None,
    }

    if diaries:
        # 取最新的一条日记
        latest_diary = diaries[0]
        diary_context = {
            "exists": True,
            "title": latest_diary.get("date"),
            "content_excerpt": latest_diary.get("content_excerpt", ""),
        }

    # 处理 diary_ai_summary
    diary_ai_summary_context = {
        "exists": False,
        "summary": None,
    }

    if diaries:
        latest_diary = diaries[0]
        ai_summary = latest_diary.get("ai_summary")
        if ai_summary:
            diary_ai_summary_context = {
                "exists": True,
                "summary": ai_summary,
            }

    # 处理 mood
    mood_context = {
        "exists": False,
        "entries": [],
    }

    if mood_entries:
        mood_context = {
            "exists": True,
            "entries": [
                {
                    "entry_id": entry["id"],
                    "mood_type_id": entry["mood_type_id"],
                    "score": entry.get("score", 0),
                    "content": entry.get("content"),
                    "created_at": entry["created_at"],
                }
                for entry in mood_entries
            ],
        }

    return {
        "custom_blocks": custom_block_items,
        "diary": diary_context,
        "diary_ai_summary": diary_ai_summary_context,
        "mood": mood_context,
    }
