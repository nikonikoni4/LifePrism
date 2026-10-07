"""guard：工具调用执行前的裁决组件。

护栏订阅 myagent 的 ``tool/call`` 事件（waterfall 链），在工具真正执行前对
本批调用逐条做权限/路径检测，返回反对意见表由调用方裁决。当前只有路径白名单
一个护栏：``ToolUseGuard``。

payload 类型（``ToolCallInfo`` / ``ToolCallPayload``）定义在 myagent
（``myagent.infra.events.payload``）。事件广播的就是那两个类的实例，类型必须
同源，故本包直接沿用，不在 lifeprism 内重复定义。
"""

from lifeprism.llm.guard.tool_use_guard import ToolUseGuard

__all__ = [
    "ToolUseGuard",
]
