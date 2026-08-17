"""
Context.build_prefix_messages 单元测试（custom prompt 注入）

测试分支（ADR docs/adr/2026-08-18-custom-prompt-user-role-injection.md 实现契约）:
1. 非 CHAT 类型：不注入 custom prompt（仅 1 条 system 消息）
2. CHAT 类型 + 文件不存在：不注入
3. CHAT 类型 + 文件内容 strip 后为空：不注入（空定义对齐 sync/file_filter.is_empty_content）
4. CHAT 类型 + 有内容：注入 user role 消息，system-reminder 包裹，含来源说明与原文
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from lifeprism.llm.agent.context import Context
from lifeprism.llm.bus import InboundMessage, MessageType

pytestmark = pytest.mark.core

# 统一的 settings mock：lifeprism_data_path 指向假路径（_read_file 已 mock，不实际读盘）
_FAKE_DATA_PATH = Path("D:/fake/lifeprism_data")


@pytest.fixture
def mock_settings():
    """mock context 模块内的 settings，隔离真实路径解析"""
    with patch("lifeprism.llm.agent.context.settings") as mock_s:
        mock_s.lifeprism_data_path = _FAKE_DATA_PATH
        yield mock_s


@pytest.fixture
def mock_system_prompt():
    """mock build_system_prompt，隔离 identity/bootstrap/skill 加载"""
    with patch.object(Context, "build_system_prompt", return_value="SYS_PROMPT"):
        yield


def _chat_msg() -> InboundMessage:
    return InboundMessage(type=MessageType.CHAT, content="测试")


def _classify_msg() -> InboundMessage:
    return InboundMessage(
        type=MessageType.CLASSIFY, content="分类", extra={"system_prompt": "分类提示"}
    )


class TestBuildPrefixMessages:
    """build_prefix_messages 四分支测试"""

    def test_non_chat_type_no_custom_prompt(self, mock_settings, mock_system_prompt):
        """非 CHAT 类型：即使文件有内容也不注入 custom prompt"""
        with patch.object(Context, "_read_file", return_value="规则内容"):
            prefix = Context.build_prefix_messages(_classify_msg())

        assert len(prefix) == 1
        assert prefix[0] == {"role": "system", "content": "SYS_PROMPT"}

    def test_chat_type_file_missing(self, mock_settings, mock_system_prompt):
        """CHAT 类型 + 文件不存在（_read_file 返回 None）：不注入"""
        with patch.object(Context, "_read_file", return_value=None):
            prefix = Context.build_prefix_messages(_chat_msg())

        assert len(prefix) == 1
        assert prefix[0] == {"role": "system", "content": "SYS_PROMPT"}

    def test_chat_type_empty_content(self, mock_settings, mock_system_prompt):
        """CHAT 类型 + 内容 strip 后为空（纯空白）：不注入"""
        with patch.object(Context, "_read_file", return_value="  \n\t\n"):
            prefix = Context.build_prefix_messages(_chat_msg())

        assert len(prefix) == 1
        assert prefix[0] == {"role": "system", "content": "SYS_PROMPT"}

    def test_chat_type_with_content(self, mock_settings, mock_system_prompt):
        """CHAT 类型 + 有内容：注入 user role 消息，system-reminder 包裹"""
        with patch.object(Context, "_read_file", return_value="用户规则：回复保持简洁"):
            prefix = Context.build_prefix_messages(_chat_msg())

        assert len(prefix) == 2
        assert prefix[0] == {"role": "system", "content": "SYS_PROMPT"}

        injected = prefix[1]
        assert injected["role"] == "user"
        content = injected["content"]
        # system-reminder 包裹
        assert content.startswith("<system-reminder>\n")
        assert content.endswith("</system-reminder>")
        # 含来源说明、管理方式与文件原文
        assert "# custom prompt" in content
        assert "custom_prompt.md" in content
        assert "用户规则：回复保持简洁" in content

    def test_custom_prompt_read_path(self, mock_settings, mock_system_prompt):
        """CHAT 类型：custom prompt 从 agent/chat/custom_prompt.md 读取"""
        with patch.object(Context, "_read_file", return_value="规则") as mock_read:
            Context.build_prefix_messages(_chat_msg())

        read_paths = [call.args[0] for call in mock_read.call_args_list]
        expected = str(_FAKE_DATA_PATH / "agent/chat/custom_prompt.md")
        assert expected in read_paths

    def test_returns_new_list_each_call(self, mock_settings, mock_system_prompt):
        """每次调用返回独立列表，调用方拼接历史不会污染缓存结构"""
        with patch.object(Context, "_read_file", return_value="规则"):
            prefix_1 = Context.build_prefix_messages(_chat_msg())
            prefix_2 = Context.build_prefix_messages(_chat_msg())

        assert prefix_1 is not prefix_2
        assert prefix_1[0] is not prefix_2[0] or prefix_1 == prefix_2
