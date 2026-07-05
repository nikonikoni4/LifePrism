"""会话查询工具"""
from typing import Any
from pathlib import Path
import json
import re
from datetime import datetime

from lifeprism.llm.agent.tools.base import Tool, ERROR
from lifeprism.llm.session.manager import SessionManager, ChatHistoryManager
from lifeprism.config import settings
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class QuerySessionListTool(Tool):
    """查询会话列表及每个会话的最新总结和最后用户消息"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        """函数调用中使用的工具名"""
        return "query_session_list"

    @property
    def description(self) -> str:
        """工具功能说明"""
        return """查询会话列表，返回每个会话的最新总结和最后用户消息。
        适用场景：用户想查看所有会话或筛选特定日期的会话，以便选择要切换的目标会话。
        返回的 last_summary 是 AI 对该会话的最新总结（可能为空，表示会话刚创建还没有生成总结）。
        返回的 last_user_message 是该会话中最后一条用户消息。
        """

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "date_filter": {
                    "type": ["string", "null"],
                    "description": "可选，日期筛选，格式 YYYY-MM-DD，只返回该日期更新的会话"
                }
            },
            "required": []
        }

    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具

        参数:
            **kwargs: 工具特有参数
                - date_filter: 日期筛选（可选，格式 YYYY-MM-DD）

        返回:
            dict[str, dict[str, str]]: 格式为 {"session_id": {"last_summary": str, "last_user_message": str}}
        """
        try:
            date_filter = kwargs.get('date_filter')

            # 验证日期格式
            if date_filter and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_filter):
                return f"{ERROR}日期格式错误，应为 YYYY-MM-DD"

            # 1. 遍历所有 session 文件
            session_path = settings.session_path
            if not session_path.exists():
                logger.warning("Session 路径不存在: %s", session_path)
                return {}

            session_data = {}  # {session_id: {"updated_at": str, "last_user_message": str}}

            for file in session_path.glob('*.jsonl'):
                session_id = file.stem
                try:
                    with open(file, encoding='utf-8') as f:
                        metadata = None
                        last_user_msg = None

                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            data = json.loads(line)

                            # 读取 metadata
                            if data.get("_type") == "metadata":
                                metadata = data
                            # 记录所有 user 消息，保留最后一条
                            elif data.get('role') == 'user':
                                content = data.get('content', '')
                                # 处理多模态消息（content 为 list）
                                if isinstance(content, list):
                                    # 提取文本内容
                                    text_parts = []
                                    for block in content:
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            text_parts.append(block.get('text', ''))
                                        elif isinstance(block, str):
                                            text_parts.append(block)
                                    last_user_msg = ' '.join(text_parts)
                                else:
                                    last_user_msg = content

                        # 检查是否有 metadata
                        if not metadata:
                            logger.warning("Session %s 缺少 metadata，跳过", session_id)
                            continue

                        updated_at = metadata.get('updated_at', '')

                        # 应用日期过滤
                        if date_filter:
                            # updated_at 格式为 ISO 8601 (YYYY-MM-DDTHH:MM:SS)
                            if not updated_at.startswith(date_filter):
                                continue

                        session_data[session_id] = {
                            "updated_at": updated_at,
                            "last_user_message": last_user_msg or ""
                        }

                except Exception as e:
                    logger.warning("读取 session %s 失败: %s，跳过该文件", session_id, e)
                    continue

            # 2. 加载 chat_history.json
            try:
                history_manager = ChatHistoryManager()
                histories = history_manager.histories
            except Exception as e:
                logger.error("加载 chat_history.json 失败: %s", e)
                histories = []

            # 3. 按 session_id 分组，取每个 session 的最新总结
            session_summaries = {}  # {session_id: last_summary}
            for history in histories:
                # 兼容性：跳过没有 session_id 的记录
                if 'session_id' not in history:
                    continue

                session_id = history.get('session_id')
                timestamp = history.get('timestamp', '')
                content = history.get('content', '')

                # 如果该 session_id 还没有记录，或者当前记录的时间戳更新
                if session_id not in session_summaries:
                    session_summaries[session_id] = {
                        'timestamp': timestamp,
                        'content': content
                    }
                else:
                    # 比较时间戳，保留最新的
                    if timestamp > session_summaries[session_id]['timestamp']:
                        session_summaries[session_id] = {
                            'timestamp': timestamp,
                            'content': content
                        }

            # 4. 聚合结果
            result = {}
            for session_id, data in session_data.items():
                last_summary = ""
                if session_id in session_summaries:
                    last_summary = session_summaries[session_id]['content']

                result[session_id] = {
                    "last_summary": last_summary,
                    "last_user_message": data["last_user_message"]
                }

            logger.info("查询会话列表: date_filter=%s, 结果数=%s", date_filter, len(result))
            return result

        except Exception as e:
            logger.error("查询会话列表失败: %s", e)
            return f"{ERROR}查询会话列表失败: {e}"


class QuerySessionHistoryTool(Tool):
    """查询指定会话的历史对话记录"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        """函数调用中使用的工具名"""
        return "query_session_history"

    @property
    def description(self) -> str:
        """工具功能说明"""
        return """查询指定会话的最近 N 轮对话记录。
        适用场景：用户想查看某个会话的历史对话内容，以便确认是否是目标会话或回忆上下文。
        返回最近的用户和助手消息，按时间倒序排列。
        """

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "会话 ID，要查询的目标会话"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回的消息轮数，默认 10，最小 1，最大 50",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50
                }
            },
            "required": ["session_id"]
        }

    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具

        参数:
            **kwargs: 工具特有参数
                - session_id: 会话 ID
                - limit: 返回的消息轮数（默认 10）

        返回:
            list[dict[str, str]]: 历史消息列表，每项包含 role, content, timestamp
        """
        try:
            session_id = kwargs.get('session_id', '')
            limit = kwargs.get('limit', 10)

            if not session_id:
                return f"{ERROR}session_id 参数不能为空"

            # 获取 session 文件路径
            session_path = SessionManager.get_session_path_by_id(session_id)

            # 检查文件是否存在
            if not session_path.exists():
                logger.warning("会话 %s 不存在", session_id)
                return f"{ERROR}会话 {session_id} 不存在"

            # 读取 session 文件
            messages = []
            try:
                with open(session_path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        # 跳过 metadata 行
                        if data.get("_type") == "metadata":
                            continue
                        # 只保留 user 和 assistant 消息
                        if data.get('role') in ['user', 'assistant']:
                            messages.append({
                                'role': data.get('role', ''),
                                'content': data.get('content', ''),
                                'timestamp': data.get('timestamp', '')
                            })
            except Exception as e:
                logger.error("读取 session %s 失败: %s", session_id, e)
                return f"{ERROR}读取会话失败: {e}"

            # 按 timestamp 倒序，取最近 limit 条（最大 50）
            messages.reverse()
            result = messages[:min(limit, 50)]

            logger.info("查询会话历史: session_id=%s, limit=%s, 结果数=%s", session_id, limit, len(result))
            return result

        except Exception as e:
            logger.error("查询会话历史失败: %s", e)
            return f"{ERROR}查询会话历史失败: {e}"
