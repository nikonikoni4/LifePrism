"""记忆请求必须明确指定聊天实际读取的用户文件，避免同名副本歧义。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from lifeprism.llm.function import agent_schedule_job as jobs

pytestmark = pytest.mark.regression


def test_memory_request_names_canonical_profile_and_recent_state(tmp_path, monkeypatch):
    """既有daily_data/user.md不能让模型猜测目标，两个写入路径须显式给出。"""
    monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
    monkeypatch.setattr(jobs.prompt_loader, "load_prompt", Mock(return_value="update memory"))
    monkeypatch.setattr(jobs, "read_md", Mock(return_value="previous state"))
    monkeypatch.setattr(
        jobs, "extract_date_logs_from_file", Mock(return_value={"2026-10-07": "facts"})
    )
    monkeypatch.setattr(jobs, "query_user_activity_summary", Mock(return_value="overview"))
    send = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(jobs, "bus", SimpleNamespace(send=send))
    monkeypatch.setattr(jobs.llm_call_logger, "log_call", Mock())

    asyncio.run(jobs.update_memory("2026-10-07"))

    message = send.call_args.args[0]
    content = "\n".join(block["text"] for block in message.content)
    assert str((tmp_path / "user/user.md").resolve()) in content
    assert str((tmp_path / "user/daily_data/recent_state.md").resolve()) in content
