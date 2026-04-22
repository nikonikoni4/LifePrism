from datetime import date, timedelta
from pathlib import Path
from typing import Any

from lifeprism.config.settings_manager import settings
from lifeprism.llm.providers.dataset_providers.old_llm_lw_data_provider import old_llm_lw_data_provider
from lifeprism.server.providers.diary_provider import diary_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.providers.mood_provider import mood_provider
from lifeprism.server.providers.timeline_provider import timeline_provider
from lifeprism.server.providers.todo_provider import todo_provider


def _date_range(start_date: str, end_date: str):
    current = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


class SummaryReadProvider:
    def get_activity_logs_by_range(self, start_time: str, end_time: str) -> list[dict[str, Any]]:
        return old_llm_lw_data_provider.query_behavior_logs(
            start_time=start_time,
            end_time=end_time,
            limit=None,
            order_by="start_time ASC",
        )

    def get_todos_by_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for one_date in _date_range(start_date, end_date):
            rows.extend(todo_provider.get_todos_by_date(one_date, include_cross_day=False))
        return rows

    def get_habits(self) -> list[dict[str, Any]]:
        return habit_provider.get_habits(status="active")

    def get_current_challenge_by_habit(self, habit_id: str) -> dict[str, Any] | None:
        return habit_challenge_provider.get_current_challenge(habit_id)

    def get_habit_checkins_by_range(
        self,
        start_date: str,
        end_date: str,
        habit_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return habit_checkin_provider.get_checkins_in_date_range(start_date, end_date, habit_ids)

    def get_custom_blocks_by_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for one_date in _date_range(start_date, end_date):
            rows.extend(timeline_provider.get_custom_blocks_by_date(one_date))
        return rows

    def get_diaries_by_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        rows = diary_provider.get_diaries_by_date_range(start_date, end_date)
        return [{**row, "content_excerpt": self._read_diary_excerpt(row["date"])} for row in rows]

    def get_mood_entries_by_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return mood_provider.get_mood_entries(start_date=start_date, end_date=end_date)

    def _read_diary_excerpt(self, diary_date: str, max_chars: int = 200) -> str:
        year, month, _ = diary_date.split("-")
        diary_path = Path(settings.lifeprism_data_path) / "diary" / year / month / f"{diary_date}.md"
        if not diary_path.exists():
            return ""
        content = diary_path.read_text(encoding="utf-8").strip()
        content = " ".join(line.strip() for line in content.splitlines() if line.strip())
        return content[:max_chars]


summary_read_provider = SummaryReadProvider()
