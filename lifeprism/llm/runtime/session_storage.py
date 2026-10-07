"""业务 Session 的目录归属，不参与工具选择或 token 分类。"""

from pathlib import Path
from typing import Literal

from lifeprism.llm.bus import InboundMessage, MessageType
from lifeprism.llm.bus.events import validate_workflow_id


def resolve_session_category(message: InboundMessage) -> Literal["workflow", "chat", "task"]:
    """返回目录规则和会话头共用的业务类别。"""
    if message.workflow_id is not None:
        return "workflow"
    return "chat" if message.type == MessageType.CHAT else "task"


def resolve_session_folder(root: Path, message: InboundMessage) -> Path:
    """解析工作流或聊天目录，并拒绝符号链接逃出存储根目录。

    Args:
        root: 所有业务会话的存储根目录。
        message: 携带 workflow_id 和消息类型的入站消息。

    Returns:
        指定归属下存放 JSONL 文件的绝对目录。
    """
    validate_workflow_id(message.workflow_id)
    category = resolve_session_category(message)
    if category == "workflow":
        relative = Path("workflows") / str(message.workflow_id)
    elif category == "chat":
        # 聊天不按渠道细分目录；channel 只在收发与事件层使用。
        relative = Path("chat")
    else:
        # 未显式指定工作流的旧调用仍可执行，但不按消息/统计类型猜测归属。
        relative = Path("tasks")
    resolved_root = root.resolve()
    expected = resolved_root / relative
    folder = expected.resolve()
    if not folder.is_relative_to(resolved_root):
        raise ValueError("Session 存储归属目录不能逃出存储根目录")
    if folder != expected:
        raise ValueError("Session 存储归属目录不能通过符号链接指向其他目录")
    return folder
