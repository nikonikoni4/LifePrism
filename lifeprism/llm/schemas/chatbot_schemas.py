import operator
from typing import Annotated

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class ChatBotSchemas(TypedDict):
    """
    LangGraph 状态 Schema

    使用 TypedDict 而不是 Pydantic BaseModel，因为：
    1. LangGraph 官方推荐使用 TypedDict 定义状态
    2. Pydantic 验证器与 LangChain 消息类型（如 ToolMessage）存在兼容性问题
    3. TypedDict 更轻量，不会触发不必要的类型验证
    """

    # 对话消息列表 - 使用 operator.add 进行累加
    messages: Annotated[list[BaseMessage], operator.add]

    # 用户意图列表
    intent: Annotated[list[str], operator.add]

    # 用户意图对应的引导内容
    guide_content: Annotated[list[str], operator.add]

    # 当前用户问题（本轮对话）
    current_human_message: str | None

    # 工具调用结果
    tools_result: Annotated[list[str], operator.add]
