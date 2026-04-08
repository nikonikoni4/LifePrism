# Agent调用循环实现
from typing import Any
from lifeprism.llm.providers import LLMResponse, create_llm_client
from lifeprism.llm.session import Session,session_manager
import asyncio
from lifeprism.llm.bus import InboundMessage,OutboundMessage,bus,MessageType, MessageQueue
from lifeprism.llm.agent.context import Context
from lifeprism.utils import get_logger
from lifeprism.utils.lazy_singleton import LazySingleton
logger = get_logger(__name__)

class AgentLoop:
    def __init__(self, bus: MessageQueue):
        self._bus = bus
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_id -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._running = True

    async def _run_agent_loop(self,messages:list[dict[str,Any]],tools:list[dict[str, Any]])->LLMResponse:
        llm = create_llm_client()
        result:LLMResponse = await llm.chat(
            messages=messages,
            tools = tools
        )
        # TODO  工具调用实现
        
        
        return result
    
    async def _process_msg(self,msg:InboundMessage):
        """
        依据不同的消息类型，创建system prompt + tool description
        """
        try:
            # 1. 构建system prompt
            system_prompt = Context.build_system_prompt(msg)

            # 2. 构建tool description
            if msg.type == MessageType.CHAT:
                tools: list[dict[str, Any]] = []
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
            await self._bus.publish_outbound(OutboundMessage(id=msg.id, response=result))

            # 6. 保存session
            if msg.type != MessageType.CLASSIFY: # 分类数据不保存
                session_manager.save_session(session)
        except Exception as e:
            logger.error(f"[AgentLoop] 处理消息 id={msg.id} 时出错: {e}", exc_info=True)
            await self._bus.publish_outbound(OutboundMessage(id=msg.id, response=f"[ERROR] {e}"))
            
    

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

