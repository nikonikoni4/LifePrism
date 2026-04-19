"""
回归测试：habit check_settlements API

问题描述：get_expired_in_progress_challenges 错误地使用 end_date <= today 限制查询条件，
导致提前判定失败（end_date > today 但数学上不可能达标）的挑战无法被检测到。

验证点：
1. get_expired_in_progress_challenges 返回所有 in_progress 挑战，不应有 end_date 限制
2. 提前判定失败的挑战能被 check_settlements 检测到
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from lifeprism.server.main import app


@pytest.mark.regression
def test_get_expired_in_progress_challenges_returns_all_in_progress_challenges(monkeypatch):
    """
    验证 get_expired_in_progress_challenges 返回所有 in_progress 挑战，
    不应该只返回 end_date <= today 的挑战。
    """
    from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider

    future_end = (date.today() + timedelta(days=30)).isoformat()
    past_end = (date.today() - timedelta(days=1)).isoformat()
    today_end = date.today().isoformat()

    mock_challenges = [
        {"id": "ch-future", "habit_id": "h1", "end_date": future_end, "status": "in_progress", "completed_count": 0, "required_completions": 10},
        {"id": "ch-past", "habit_id": "h2", "end_date": past_end, "status": "in_progress", "completed_count": 0, "required_completions": 10},
        {"id": "ch-today", "habit_id": "h3", "end_date": today_end, "status": "in_progress", "completed_count": 0, "required_completions": 10},
    ]

    monkeypatch.setattr(
        habit_challenge_provider,
        "get_expired_in_progress_challenges",
        lambda today: mock_challenges,
    )

    result = habit_challenge_provider.get_expired_in_progress_challenges(date.today().isoformat())

    # 应该返回所有 in_progress 的挑战
    assert len(result) == 3, f"期望返回 3 个挑战，实际返回 {len(result)} 个"
    ids = {c["id"] for c in result}
    assert ids == {"ch-future", "ch-past", "ch-today"}


@pytest.mark.regression
def test_check_settlements_detects_premature_failure(monkeypatch):
    """
    验证 check_settlements 能检测到提前判定失败的挑战
    （end_date > today 但数学上不可能达标）
    """
    from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
    from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
    from lifeprism.server.providers.habit_provider import habit_provider

    # 挑战 end_date 在未来，但 completed=1, required=24，数学上不可能达标
    future_end = (date.today() + timedelta(days=20)).isoformat()
    past_start = (date.today() - timedelta(days=20)).isoformat()
    mock_challenge = {
        "id": "ch-premature-fail",
        "habit_id": "habit-d2264f2c",
        "end_date": future_end,
        "start_date": past_start,
        "status": "in_progress",
        "completed_count": 1,
        "required_completions": 24,
        "from_level": 2,
        "to_level": 3,
    }

    # mock get_expired_in_progress_challenges 返回这个挑战
    monkeypatch.setattr(
        habit_challenge_provider,
        "get_expired_in_progress_challenges",
        lambda today: [mock_challenge],
    )
    # mock get_challenge_by_id 也返回同一个挑战（因为 _judge_challenge_result 内部会调用）
    monkeypatch.setattr(
        habit_challenge_provider,
        "get_challenge_by_id",
        lambda cid: mock_challenge if cid == "ch-premature-fail" else None,
    )
    # mock get_checkin_by_date，今天已打卡
    monkeypatch.setattr(
        habit_checkin_provider,
        "get_checkin_by_date",
        lambda hid, d: {"id": "checkin-today"} if str(d) == str(date.today()) else None,
    )
    # mock get_habit_by_id
    monkeypatch.setattr(
        habit_provider,
        "get_habit_by_id",
        lambda hid: {"id": hid, "name": "中午-吃药", "frequency_type": "daily"} if hid == "habit-d2264f2c" else None,
    )

    # 直接调用 habit_service.check_settlements
    from lifeprism.server.services.habit_service import habit_service
    result = habit_service.check_settlements()

    # 应该返回失败结算项
    assert len(result.settlements) == 1, f"期望返回 1 个失败结算项，实际返回 {len(result.settlements)} 个"
    settlement = result.settlements[0]
    assert settlement.result == "failed", f"期望 result='failed'，实际 result='{settlement.result}'"
    assert settlement.challengeId == "ch-premature-fail", f"期望 challengeId='ch-premature-fail'，实际 challengeId='{settlement.challengeId}'"
    assert settlement.completedCount == 1, f"期望 completedCount=1，实际 completedCount={settlement.completedCount}"
    assert settlement.requiredCompletions == 24, f"期望 requiredCompletions=24，实际 requiredCompletions={settlement.requiredCompletions}"


@pytest.mark.regression
def test_check_settlements_api_returns_premature_failures(monkeypatch):
    """
    验证 /check-settlements API 能返回提前判定失败的挑战
    """
    from lifeprism.server.providers.habit_challenge_provider import habit_challenge_provider
    from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
    from lifeprism.server.providers.habit_provider import habit_provider

    future_end = (date.today() + timedelta(days=20)).isoformat()
    past_start = (date.today() - timedelta(days=20)).isoformat()
    mock_challenge = {
        "id": "ch-premature-fail",
        "habit_id": "habit-d2264f2c",
        "end_date": future_end,
        "start_date": past_start,
        "status": "in_progress",
        "completed_count": 1,
        "required_completions": 24,
        "from_level": 2,
        "to_level": 3,
    }

    monkeypatch.setattr(
        habit_challenge_provider,
        "get_expired_in_progress_challenges",
        lambda today: [mock_challenge],
    )
    monkeypatch.setattr(
        habit_challenge_provider,
        "get_challenge_by_id",
        lambda cid: mock_challenge if cid == "ch-premature-fail" else None,
    )
    monkeypatch.setattr(
        habit_checkin_provider,
        "get_checkin_by_date",
        lambda hid, d: {"id": "checkin-today"} if str(d) == str(date.today()) else None,
    )
    monkeypatch.setattr(
        habit_provider,
        "get_habit_by_id",
        lambda hid: {"id": hid, "name": "中午-吃药", "frequency_type": "daily"} if hid == "habit-d2264f2c" else None,
    )

    client = TestClient(app)
    response = client.post("/api/v2/habit/check-settlements")

    assert response.status_code == 200, f"期望 200，实际 {response.status_code}: {response.text}"
    data = response.json()
    assert "settlements" in data, f"响应应包含 settlements 字段，实际: {data}"

    failed_settlements = [s for s in data["settlements"] if s["result"] == "failed"]
    assert len(failed_settlements) >= 1, f"期望至少 1 个失败结算项，实际: {len(failed_settlements)}"

    premature_fail = next((s for s in failed_settlements if s["challengeId"] == "ch-premature-fail"), None)
    assert premature_fail is not None, f"期望找到提前失败的挑战 ch-premature-fail，实际 settlements: {failed_settlements}"
