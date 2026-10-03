"""runtime_tools：迁移自 ``lifeprism.llm.agent.tools`` 的生产业务工具。

本包只承载生产业务工具（文件系统、系统数据查询、习惯、自定义记录、web），
工具直接继承 myagent 的 ``Tool``（见 ``base.py``）。``build_tools(message_type)``
按消息类型构造工具列表，替代旧 ``loop.py`` 中逐条 ``tool_registry.register(...)``
的写法。web 工具仅导出、不在任何消息类型下注册，保持既有未注册行为。
"""

from lifeprism.llm.bus.events import MessageType
from lifeprism.llm.runtime_tools.base import (
    ERROR,
    SUCCESS,
    Tool,
    ToolErrorType,
    ToolResult,
)
from lifeprism.llm.runtime_tools.custom_records_tool import (
    CreateCustomRecordEntryTool,
    CreateCustomRecordTypeTool,
    ListCustomRecordTypesTool,
    QueryCustomRecordEntriesTool,
)
from lifeprism.llm.runtime_tools.filesystem import (
    EditFileTool,
    FileTreeTool,
    ReadFileTool,
    SearchFileTool,
    SearchStringTool,
    WriteFileTool,
)
from lifeprism.llm.runtime_tools.habit_tool import (
    BackfillCheckinTool,
    CancelCheckinHabitTool,
    CheckinHabitTool,
    QueryUserHabitsTool,
)
from lifeprism.llm.runtime_tools.lifeprismsystem import (
    UpdateUserBehaviorNoteTool,
    UserActivitySummaryTool,
    UserComputerLogTool,
    UserMoodCreateTool,
    UserMoodQuryTool,
)
from lifeprism.llm.runtime_tools.web import WebFetchTool, WebSearchTool

__all__ = [
    "ERROR",
    "SUCCESS",
    "Tool",
    "ToolErrorType",
    "ToolResult",
    "build_tools",
    # filesystem
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "FileTreeTool",
    "SearchFileTool",
    "SearchStringTool",
    # lifeprismsystem
    "UserActivitySummaryTool",
    "UserComputerLogTool",
    "UpdateUserBehaviorNoteTool",
    "UserMoodQuryTool",
    "UserMoodCreateTool",
    # habit
    "QueryUserHabitsTool",
    "CheckinHabitTool",
    "CancelCheckinHabitTool",
    "BackfillCheckinTool",
    # custom records
    "ListCustomRecordTypesTool",
    "CreateCustomRecordTypeTool",
    "CreateCustomRecordEntryTool",
    "QueryCustomRecordEntriesTool",
    # web（仅导出，不注册）
    "WebSearchTool",
    "WebFetchTool",
]


def _filesystem_tools() -> list[Tool]:
    """文件系统工具（6 个）：读取/写入/编辑文件、文件树、按名搜索、按内容搜索。"""
    return [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        FileTreeTool(),
        SearchFileTool(),
        SearchStringTool(),
    ]


def _lifeprismsystem_tools() -> list[Tool]:
    """LifePrism 系统数据工具（5 个）：行为活动/电脑日志/行为备注/心情查询/心情创建。"""
    return [
        UserActivitySummaryTool(),
        UserComputerLogTool(),
        UpdateUserBehaviorNoteTool(),
        UserMoodQuryTool(),
        UserMoodCreateTool(),
    ]


def _habit_tools() -> list[Tool]:
    """习惯工具（4 个）：查询/今日打卡/取消打卡/补签。"""
    return [
        QueryUserHabitsTool(),
        CheckinHabitTool(),
        CancelCheckinHabitTool(),
        BackfillCheckinTool(),
    ]


def _custom_records_tools() -> list[Tool]:
    """自定义记录工具（4 个）：列类型/建类型/录入/查询。"""
    return [
        ListCustomRecordTypesTool(),
        CreateCustomRecordTypeTool(),
        CreateCustomRecordEntryTool(),
        QueryCustomRecordEntriesTool(),
    ]


def build_tools(message_type: str) -> list[Tool]:
    """按消息类型构造工具实例列表。

    Args:
        message_type: 消息类型，取值见 ``lifeprism.llm.bus.events.MessageType``。

    Returns:
        - ``CHAT``：文件系统 6 + lifeprismsystem 5 + habit 4 + custom_records 4
        - ``DREAM_TASK``：UserActivitySummaryTool、UserComputerLogTool + 文件系统 6
        - 其他消息类型：空列表

    说明：web 工具（web_search / web_fetch）不在任何消息类型下注册；
    会话查询、bootstrap 等工具不属于本包，不在此注册。
    """
    if message_type == MessageType.CHAT:
        return (
            _filesystem_tools()
            + _lifeprismsystem_tools()
            + _habit_tools()
            + _custom_records_tools()
        )
    if message_type == MessageType.DREAM_TASK:
        return [UserActivitySummaryTool(), UserComputerLogTool()] + _filesystem_tools()
    return []
