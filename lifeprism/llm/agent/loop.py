# Agent调用循环实现
from typing import Any
from lifeprism.llm.providers import LLMResponse, create_llm_client
from lifeprism.llm.session import Session,session_manager
import asyncio
from lifeprism.llm.bus import InboundMessage,OutboundMessage,bus,MessageType
from lifeprism.llm.agent.context import Context

class AgentLoop:
    def __init__(self):
        self._processing_lock = asyncio.Lock()
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_id -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._running = True

    async def _run_agent_loop(self,messages:list[dict[str,Any]],tools:list[dict[str, Any]])->str:
        llm = create_llm_client()
        result:LLMResponse = await llm.chat(
            messages=messages,
            tools = tools
        )
        # TODO 工具调用实现
        
        
        return result.content
    
    async def _process_msg(self,msg:InboundMessage):
        """
        依据不同的消息类型，创建system prompt + tool description
        """
        # 1. 构建system prompt
        system_prompt = Context.build_system_prompt(msg.type)

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
        session.add_message("assistant", content=result)
        await bus.publish_outbound(OutboundMessage(id=msg.id, response=result))
            
    

    async def loop(self):

        while self._running:
            # 1. 从bus中获取消息
            msg:InboundMessage = await bus.consume_inbound()

            # 2. 创建任务，后台处理
            task = asyncio.create_task(self._process_msg(msg))

            # 3. 注册任务激活
            self._active_tasks.setdefault(msg.id,[]).append(task)

            # 4. 添加任务注销函数
            task.add_done_callback(lambda t,k = msg.id: self._active_tasks.get(k,[]).remove(t) if t in self._active_tasks.get(k,[]) else None  )

