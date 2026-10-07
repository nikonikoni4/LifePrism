"""会话提取任务的配置注册契约。"""

from types import SimpleNamespace

import pytest

import lifeprism.server.services.schedule_service as schedule

pytestmark = pytest.mark.core


@pytest.mark.parametrize(
    "enabled,test_mode,expected",
    [(False, False, None), (True, False, {"hours": 4}), (True, True, {"minutes": 1})],
)
def test_session_extraction_interval(tmp_path, monkeypatch, enabled, test_mode, expected):
    monkeypatch.setattr(
        schedule,
        "settings",
        SimpleNamespace(
            lifeprism_data_path=tmp_path,
            auto_summary_session=enabled,
            auto_update_memory=False,
            auto_diary_summary=False,
            run_mode="agent_only",
        ),
    )
    monkeypatch.setattr(schedule, "TEST_MODE", test_mode)
    service = schedule.ScheduleService()
    jobs = [job for job in service._system_jobs if job["job_id"] == "process_session_message"]
    if expected is None:
        assert not jobs
    else:
        assert jobs == [
            {
                "func": schedule._process_session_message,
                "trigger": "interval",
                "kwargs": expected,
                "job_id": "process_session_message",
            }
        ]
