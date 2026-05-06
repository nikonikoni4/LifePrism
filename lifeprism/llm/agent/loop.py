# Agent调用循环实现
from typing import Any
from lifeprism.llm.providers import LLMResponse, create_llm_client,ToolCallRequest
from lifeprism.llm.session import Session,session_manager
import asyncio
import json
from lifeprism.llm.bus import (
    InboundMessage,
    OutboundMessage,
    bus,
    MessageType, 
    MessageQueue,
    ChannelType,
)
from lifeprism.llm.agent.context import Context
from lifeprism.server.services import setting_service
from lifeprism.utils import get_logger,DEBUG
from lifeprism.utils.lazy_singleton import LazySingleton
from lifeprism.llm.agent.tools import (
    ToolRegistry,
    UserActivitySummaryTool,
    UserComputerLogTool,
    UpdateUserBehaviorNoteTool,
    UserMoodQuryTool,
    UserMoodCreateTool,
    DeleteBootstrapTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ERROR
)
from collections import defaultdict
from lifeprism.config import settings
MAX_TOOL_CALL = 20
MAX_TOOL_ERROR_COUNT = 5


logger = get_logger(__name__)
logger.setLevel(DEBUG)
class AgentLoop:
    def __init__(self, bus: MessageQueue):
        self._bus = bus
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_id -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._running = True
        self._tool_registry = ToolRegistry()
    async def _run_agent_loop(self, session: Session, system_prompt: str, tools: list[dict[str, Any]]) -> LLMResponse:
        llm = create_llm_client()
        messages = Context.build_prompt(system_prompt, session.get_history_message())
        response: LLMResponse = await llm.chat(
            messages=messages,
            tools=tools
        )
        session.add_message(
            'assistant',
            content=response.content or '',
            tool_calls=[
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.name,
                        'arguments': json.dumps(tc.arguments, ensure_ascii=False)
                    }
                } for tc in response.tool_calls
            ]
        )


        # 工具调用实现
        tool_call_count = 1
        # 工具调用错误统计
        tool_error = defaultdict(int)
        while response.tool_calls and tool_call_count <=MAX_TOOL_CALL:
            # 将模型回复（包含tool_calls）添加到messages中
            for tool_call in response.tool_calls:
                logger.debug(f"工具调用 ： {tool_call.name} ，调用参数{tool_call.arguments}")
                result = await self._tool_registry.execute(tool_call.name,tool_call.arguments)
                logger.debug(f"工具结果 ： {tool_call.name} - {result}")
                logger.debug(f"工具结果是否为字符串: {isinstance(result,str)}")
                logger.debug(f"工具结果是否以错误开头: {result.startswith(ERROR)}")
                # 只有在出错时才累加错误计数并检查阈值
                if isinstance(result,str) and result.startswith(ERROR):
                    tool_error[tool_call.name] += 1
                    logger.debug(f"工具 {tool_call.name} 错误计数: {tool_error[tool_call.name]}/{MAX_TOOL_ERROR_COUNT}")
                    if tool_error[tool_call.name] > MAX_TOOL_ERROR_COUNT:
                        logger.warning(f"工具 {tool_call.name} 超过最大错误次数，添加警告信息")
                        result += f"，已连续调用{tool_error[tool_call.name]}次，超过最大错误次数{MAX_TOOL_ERROR_COUNT}，请立即放弃该工具调用，尝试切换其他工具。若无可替代工具，向用户说明情况"
                session.add_message('tool', result, tool_call_id=tool_call.id)
            messages = Context.build_prompt(system_prompt, session.get_history_message())
            logger.debug(f"第{tool_call_count+1}次 llm调用开始， message 长度 {len(messages)}")
            logger.debug(messages)
            response: LLMResponse = await llm.chat(
                messages=messages,
                tools=tools
            )
            session.add_message(
                'assistant',
                content=response.content or '',
                tool_calls=[
                    {
                        'id': tc.id,
                        'type': 'function',
                        'function': {
                            'name': tc.name,
                            'arguments': json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    } for tc in response.tool_calls
                ]
            )
            logger.debug(f"模型返回 ： {response}")
            logger.debug(f"模型工具调用 ： {response.tool_calls}")
            logger.debug("="*50)
            tool_call_count += 1

        # 如果因为达到MAX_TOOL_CALL而退出，且response仍有tool_calls，需要强制生成文本回复
        if response.tool_calls and tool_call_count > MAX_TOOL_CALL:
            logger.warning(f"达到最大工具调用次数 {MAX_TOOL_CALL}，强制生成文本回复")
            session.add_message(
                'system',
                content=f'已达到最大工具调用次数 {MAX_TOOL_CALL}，请直接向用户说明当前情况，让用户判断是否继续工作。'
            )
            messages = Context.build_prompt(system_prompt, session.get_history_message())
            response = await llm.chat(messages=messages)
            session.add_message(
                'assistant',
                content=response.content or '',
                tool_calls=[
                    {
                        'id': tc.id,
                        'type': 'function',
                        'function': {
                            'name': tc.name,
                            'arguments': json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    } for tc in response.tool_calls
                ]
            )
            logger.debug(f"强制文本回复: {response}")

        return response
    
    def _process_cmd(self,msg:InboundMessage)->None | OutboundMessage:
        """
        处理命令消息
        args :
            msg : InboundMessage
        return
            None | OutboundMessage
        """
        # 1. 当前只有微信有命令行工具 /new
        if msg.channel == ChannelType.WECHAT:
            if msg.content.startswith("/new"):
                # 新建会话
                new_session = session_manager.get_or_create_session()
                # 立即保存 session 到文件，避免重启后丢失
                session_manager.save_session(new_session)
                # 传出新的session_id , channel 下一次使用时必须使用上一次消息传出的session_id
                response_text = f"[SUCCESS] 新建会话 {new_session.id} ---\n 可以开始新的聊天了！"
                return OutboundMessage(
                    id=msg.id,
                    response=LLMResponse(content=response_text),
                    session_id=new_session.id
                )
            elif msg.content.startswith("/continue"):
                # 继续会话
                # 1.去除/continue 和空格，获取session_id
                session_id = msg.content.replace("/continue","").strip()

                # 2. 先检查是否提供了参数
                if not session_id:
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content="[ERROR] 请提供会话ID，例如：/continue <session_id>")
                    )

                # 3. 检查session_id是否存在
                if session_id not in session_manager.show_session_list():
                    logger.info(f"session_id ： {session_id}")
                    logger.info(f"session_list ： {session_manager.show_session_list()}")
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content=f"[ERROR] 会话 {session_id} 不存在")
                    )
                else:
                    # 存在则返回session_id
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content=f"[SUCCESS] 继续会话 {session_id}"),
                        session_id=session_id
                    )
            elif msg.content.startswith("/session-list"):
                # 判断是否有日期
                date = msg.content.replace("/session-list","").strip()

                # 列出所有会话
                sessions = session_manager.show_session_content_list(date)
                if not sessions and date:
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content=f"[SUCCESS] 暂无{date}的会话记录,请检查日期是否为YYYY-MM-DD")
                    )
                elif not sessions:
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content="[SUCCESS] 暂无会话记录")
                    )
                response_text = "[SUCCESS] 会话列表:\n" + "\n".join(
                    f"• {s['session_id']}: {s['session_current_msg']}" for s in sessions
                )
                return OutboundMessage(
                    id=msg.id,
                    response=LLMResponse(content=response_text)
                )
        else :
            return None



    async def _process_msg(self,msg:InboundMessage):
        """
        依据不同的消息类型，创建system prompt + tool description
        """
        try:
            # ======================= cmd message process ============================
            # 1. 判断该消息是否为命令消息,如果是则直接处理，不进行后续的通用处理过程
            out_msg = self._process_cmd(msg)
            if out_msg:
                await self._bus.publish_outbound(out_msg)
                return

            # ======================= common message process =========================
            # 1. 构建system prompt
            system_prompt = Context.build_system_prompt(msg)

            # 2. 构建tool description
            tools = []
            if msg.type == MessageType.CHAT:
                self._tool_registry.register(UserActivitySummaryTool())
                self._tool_registry.register(UserComputerLogTool())
                self._tool_registry.register(UpdateUserBehaviorNoteTool())
                self._tool_registry.register(UserMoodQuryTool())
                self._tool_registry.register(UserMoodCreateTool())
                self._tool_registry.register(ReadFileTool())
                self._tool_registry.register(WriteFileTool())
                self._tool_registry.register(EditFileTool())
                if (settings.lifeprism_data_path / 'agent/chat/bootstrap.md').exists():
                    self._tool_registry.register(DeleteBootstrapTool())
                tools: list[dict[str, Any]] = self._tool_registry.get_definitions()
            elif msg.type == MessageType.CLASSIFY:
                tools = []

            # 3. 构建完整消息（含历史）
            session: Session = session_manager.get_or_create_session(msg.session_id)
            session.add_message("user", content=Context._build_user_message(msg))
            if msg.type == MessageType.CHAT: 
                session_manager.save_session(session)

            # 4. 调用 LLM
            result = await self._run_agent_loop(session, system_prompt, tools)

            # 5. 保存 assistant 回复并发布结果
            await self._bus.publish_outbound(OutboundMessage(id=msg.id, response=result,session_id=session.id))

            # 6. 保存session
            if msg.type == MessageType.CHAT: # 只有聊天数据才保存
                session_manager.save_session(session)
        except Exception as e:
            logger.error(f"[AgentLoop] 处理消息 id={msg.id} 时出错: {e}", exc_info=True)
            await self._bus.publish_outbound(
                OutboundMessage(
                    id=msg.id,
                    response=LLMResponse(content=f"[ERROR] {e}")
                )
            )
            
    

    async def loop(self):

        while self._running:
            # 1. 从bus中获取消息
            msg:InboundMessage = await self._bus.consume_inbound()

            # 2. 创建任务，后台处理
            task = asyncio.create_task(self._process_msg(msg))

            # 3. 注册任务激活
            self._active_tasks.setdefault(msg.id,[]).append(task)

            # 4. 添加任务注销函数
            task.add_done_callback(lambda t,k = msg.id: self._active_tasks.get(k,[]).remove(t) if t in self._active_tasks.get(k,[]) else None  )

    def stop(self):
        self._running = False

agent_loop = LazySingleton(AgentLoop, bus=bus)

