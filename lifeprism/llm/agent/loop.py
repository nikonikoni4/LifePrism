# Agent调用循环实现
from typing import Any
from lifeprism.llm.providers import LLMResponse, create_llm_client,ToolCallRequest
from lifeprism.llm.session import Session,session_manager
import asyncio
from lifeprism.llm.bus import (
    InboundMessage,
    OutboundMessage,
    bus,
    MessageType, 
    MessageQueue,
    ChannelType,
)
from lifeprism.llm.agent.context import Context
from lifeprism.utils import get_logger,DEBUG
from lifeprism.utils.lazy_singleton import LazySingleton
from lifeprism.llm.agent.tools import (
    ToolRegistry,
    LifeprismDataQueryTool
)

MAX_TOOL_CALL = 20
logger = get_logger(__name__)
logger.setLevel(DEBUG)
class AgentLoop:
    def __init__(self, bus: MessageQueue):
        self._bus = bus
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_id -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._running = True
        self._tool_registry = ToolRegistry()
    async def _run_agent_loop(self,messages:list[dict[str,Any]],tools:list[dict[str, Any]])->LLMResponse:
        llm = create_llm_client()
        response:LLMResponse = await llm.chat(
            messages=messages,
            tools = tools
        )
        # TODO  工具调用实现
        tool_call_count = 1
        while response.tool_calls and tool_call_count <=MAX_TOOL_CALL:
            tool_results =[]
            for tool_call in response.tool_calls:
                logger.debug(f"工具调用 ： {tool_call.name} ，调用参数{tool_call.arguments}")
                result = await self._tool_registry.execute(tool_call.name,tool_call.arguments)
                logger.debug(f"工具结果 ： {tool_call.name} - {result}")
                messages.append({'role':'tool','tool_call_id':tool_call.id,'content':result})
            response:LLMResponse = await llm.chat(
                messages=messages,
                tools = tools
            )
            
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
                self._tool_registry.register(LifeprismDataQueryTool())
                tools: list[dict[str, Any]] = self._tool_registry.get_definitions()
            elif msg.type == MessageType.CLASSIFY:
                tools = []

            # 3. 构建完整消息（含历史）
            session: Session = session_manager.get_or_create_session(msg.session_id)
            session.add_message("user", content=msg.content)
            messages = Context.build_prompt(system_prompt, session.get_history_message())

            # 4. 调用 LLM
            result = await self._run_agent_loop(messages, tools)

            # 5. 保存 assistant 回复并发布结果
            session.add_message("assistant", content=result.content)
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

