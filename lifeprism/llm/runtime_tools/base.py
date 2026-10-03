"""runtime_tools 工具基座：直接复用 myagent 的 Tool 契约。

本目录承接从 ``lifeprism.llm.agent.tools`` 迁移过来的生产业务工具。工具直接
继承 myagent 的 ``Tool``（不再自定义基类），因此 ``execute`` 的返回值契约由
myagent 定义：

- 返回 ``str`` 视为成功，由 ``ToolRegister`` 包装为 ``ToolResult(content=...)``
- 需要标记失败时返回 ``ToolResult.error(content, ToolErrorType.XXX)``，
  ``ToolRegister`` 依据 ``error_type`` 做失败分类与熔断计数

业务实现沿用旧工具目录的前缀约定（``ERROR`` / ``SUCCESS``），由
``normalize_tool_result`` 装饰器在 ``execute`` 返回值边界完成转换：
``"Error: "`` 前缀的字符串成为 ``ToolResult.error``，从而在不改动业务实现
的前提下满足新契约。
"""

import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any

from myagent.agent.core.tool.tool import Tool, ToolErrorType, ToolResult

# 错误和成功标识（沿用旧工具目录约定）
ERROR = "Error: "
SUCCESS = "Success: "

__all__ = [
    "ERROR",
    "SUCCESS",
    "Tool",
    "ToolErrorType",
    "ToolResult",
    "normalize_result",
    "normalize_tool_result",
]


def normalize_result(text: str) -> ToolResult | str:
    """把 ``execute`` 返回的字符串归一化为 myagent Tool 契约形态。

    Args:
        text: ``execute`` 的原始字符串返回值。

    Returns:
        以 ``ERROR`` 前缀开头的失败文本转换为
        ``ToolResult.error(text, ToolErrorType.TOOL_EXECUTION)``；
        其他文本原样返回（``str`` 即成功）。
    """
    if text.startswith(ERROR):
        return ToolResult.error(text, ToolErrorType.TOOL_EXECUTION)
    return text


def normalize_tool_result(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[ToolResult | str]]:
    """装饰工具 ``execute``，在返回值边界归一化结果。

    - ``str``：交给 :func:`normalize_result`（``ERROR`` 前缀 → ``ToolResult.error``，
      其余原样返回）
    - ``dict`` / ``list``：按既有类型约定序列化为 JSON 字符串
    - 其他类型：原样透传

    使用 ``functools.wraps`` 保留被装饰函数的签名与元信息。
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> ToolResult | str:
        """调用被装饰的 ``execute``，并按返回类型归一化后再交回框架。"""
        result = await func(*args, **kwargs)
        if isinstance(result, str):
            return normalize_result(result)
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return result

    return wrapper
