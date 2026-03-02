from datetime import date, timedelta

import pytest

from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
from lifeprism.server.providers.habit_provider import habit_provider
from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest,
    FrequencyObject,
    SettlementActionRequest,
)
from lifeprism.server.services.habit_service import habit_service


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with habit_provider.db.get_connection() as conn:
        conn.execute("DELETE FROM habit_chain_nodes")
        conn.execute("DELETE FROM habit_chains")
        conn.execute("DELETE FROM habit_checkins")
        conn.execute("DELETE FROM habit_challenges")
        conn.execute("DELETE FROM habits")
    habit_service._refresh_cache()


def test_resume_after_failed_settlement_creates_new_challenge():
    created = habit_service.create_habit(CreateHabitRequest(
        name="issue1-resume", frequency=FrequencyObject(type="daily"),
    ))
    challenge = habit_challenge_provider.get_current_challenge(created.id)
    with habit_provider.db.get_connection() as conn:
        conn.execute(
            """
            UPDATE habit_challenges
            SET completed_count = ?, required_completions = ?, end_date = ?
            WHERE id = ?
            """,
            (
                0,
                12,
                (date.today() - timedelta(days=1)).isoformat(),
                challenge["id"],
            ),
        )

    settlement_resp = habit_service.check_settlements()
    assert len(settlement_resp.settlements) == 1
    assert settlement_resp.settlements[0].result == "failed"
    assert habit_challenge_provider.get_current_challenge(created.id) is not None

    resumed = habit_service.resume_habit(
        created.id,
        SettlementActionRequest(source="settlement", challengeId=challenge["id"]),
    )
    assert resumed.status == "active"
    assert resumed.currentChallenge is not None
    assert resumed.currentChallenge.status == "in_progress"
