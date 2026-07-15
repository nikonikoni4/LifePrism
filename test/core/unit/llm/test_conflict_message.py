"""
CONFLICT_RESOLVE 消息类型定义测试（Issue 34）

测试 seam:
- Seam 1: MessageType.CONFLICT_RESOLVE 常量定义
- Seam 2: MESSAGE_TYPE 列表同步包含 CONFLICT_RESOLVE
- Seam 3: InboundMessage 构建 CONFLICT_RESOLVE（Markdown 格式 + extra.system_prompt）

TDD: 严格 red-green 循环
"""

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: MessageType.CONFLICT_RESOLVE 常量 ====================


class TestConflictResolveMessageType:
    """Seam 1: MessageType.CONFLICT_RESOLVE 常量定义"""

    def test_conflict_resolve_constant_exists(self):
        """MessageType 应包含 CONFLICT_RESOLVE 类属性"""
        from lifeprism.llm.bus.events import MessageType

        assert hasattr(MessageType, "CONFLICT_RESOLVE")

    def test_conflict_resolve_constant_value(self):
        """CONFLICT_RESOLVE 的值应为 'conflict_resolve'"""
        from lifeprism.llm.bus.events import MessageType

        assert MessageType.CONFLICT_RESOLVE == "conflict_resolve"

    def test_message_type_is_plain_class_not_enum(self):
        """MessageType 必须是 plain class（不是 Enum）"""
        from lifeprism.llm.bus.events import MessageType
        from enum import Enum

        # MessageType 不应继承 Enum
        assert not issubclass(MessageType, Enum)


# ==================== Seam 2: MESSAGE_TYPE 列表同步 ====================


class TestMessageTypeListSync:
    """Seam 2: MESSAGE_TYPE 列表必须同步包含 CONFLICT_RESOLVE

    InboundMessage.__post_init__ 校验依赖此列表，
    若不加入会导致构建时抛 ValueError。
    """

    def test_message_type_list_contains_conflict_resolve(self):
        """MESSAGE_TYPE 列表应包含 MessageType.CONFLICT_RESOLVE"""
        from lifeprism.llm.bus.events import MESSAGE_TYPE, MessageType

        assert MessageType.CONFLICT_RESOLVE in MESSAGE_TYPE

    def test_message_type_list_preserves_existing_types(self):
        """MESSAGE_TYPE 列表更新后不应丢失已有类型"""
        from lifeprism.llm.bus.events import MESSAGE_TYPE, MessageType

        assert MessageType.CHAT in MESSAGE_TYPE
        assert MessageType.CLASSIFY in MESSAGE_TYPE
        assert MessageType.GENERAL_TASK in MESSAGE_TYPE
        assert MessageType.DREAM_TASK in MESSAGE_TYPE


# ==================== Seam 3: InboundMessage 构建 CONFLICT_RESOLVE ====================


class TestInboundMessageConflictResolve:
    """Seam 3: InboundMessage 构建 CONFLICT_RESOLVE 消息（Markdown 格式）

    验证 SyncClient 检测到 CONFLICT 时构建的 InboundMessage：
    - type = MessageType.CONFLICT_RESOLVE
    - content 使用 Markdown 格式（## 文件冲突 / ### 本地版本 / ### 云端版本 / ### 合并指令）
    - extra 包含 conflict_file_path 和 system_prompt
    """

    def test_inbound_message_conflict_resolve_constructs_without_error(self):
        """CONFLICT_RESOLVE 类型的 InboundMessage 应能正常构建（不抛 ValueError）"""
        from lifeprism.llm.bus.events import InboundMessage, MessageType

        msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={"conflict_file_path": "diary/test.md", "system_prompt": "你是文档合并助手。"},
        )
        assert msg.type == MessageType.CONFLICT_RESOLVE

    def test_inbound_message_content_uses_markdown_format(self):
        """content 应使用 Markdown 格式包含本地版本、云端版本和合并指令"""
        from lifeprism.llm.bus.events import InboundMessage, MessageType

        file_path = "diary/2026-07-14.md"
        local_content = "# 本地日记\n今天心情不错"
        remote_content = "# 云端日记\n今天天气晴朗"
        merge_instruction = "请合并以上两份文档，保留双方的有效信息，生成一份完整的合并文档。"

        msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content=(
                f"## 文件冲突需要解决\n\n"
                f"文件路径: {file_path}\n\n"
                f"### 本地版本\n\n{local_content}\n\n"
                f"### 云端版本\n\n{remote_content}\n\n"
                f"### 合并指令\n\n{merge_instruction}"
            ),
            extra={
                "conflict_file_path": file_path,
                "system_prompt": "你是文档合并助手。",
            },
        )

        # 验证 content 已归一化为 MessageContent（list of blocks）
        text = "".join(
            block.get("text", "")
            for block in msg.content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        assert "## 文件冲突需要解决" in text
        assert "### 本地版本" in text
        assert "### 云端版本" in text
        assert "### 合并指令" in text
        assert file_path in text
        assert local_content in text
        assert remote_content in text

    def test_inbound_message_extra_contains_system_prompt_and_file_path(self):
        """extra 应包含 conflict_file_path 和 system_prompt"""
        from lifeprism.llm.bus.events import InboundMessage, MessageType

        msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={
                "conflict_file_path": "user/user.md",
                "system_prompt": (
                    "你是文档合并助手。请合并两份 Markdown 文档，"
                    "保留双方的有效信息，移除重复内容，保持文档结构清晰。"
                    "直接输出合并后的文档内容，不要解释。"
                ),
            },
        )

        assert msg.extra is not None
        assert msg.extra["conflict_file_path"] == "user/user.md"
        assert "你是文档合并助手" in msg.extra["system_prompt"]
