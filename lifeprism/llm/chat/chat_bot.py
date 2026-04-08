"""
ChatBot 模块 - 使用 Channel 进行消息收发
"""
from lifeprism.llm.channel import channel_manager
from lifeprism.llm.bus import MessageType

class ChatBot:
    """
    聊天机器人类，作为 Channel 的高层封装。
    会话持久化和上下文构建由 AgentLoop 自动处理。
    """

    def __init__(self):
        self._channel = channel_manager

    async def chat(self, content: str, session_id: str | None = None, **extra) -> str:
        """
        发送聊天请求并同步等待响应内容。

        Args:
            content: 用户输入内容
            session_id: 会话 ID，若为 None 则 AgentLoop 会自动创建
            **extra: 额外参数（如 skill_list 等）

        Returns:
            str: AI 返回的文本内容
        """
        # channel.send 内部已经实现了 ID 匹配、限速和 Future 等待逻辑
        response_content = await self._channel.send(
            content=content,
            session_id=session_id,
            type=MessageType.CHAT,
            extra=extra
        )
        return response_content

    async def close(self):
        """关闭通道资源"""
        await self._channel.close()
