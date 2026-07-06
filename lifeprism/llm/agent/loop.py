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
    FileTreeTool,
    SearchFileTool,
    SearchStringTool,
    QuerySessionListTool,
    QuerySessionHistoryTool,
    ERROR
)
from collections import defaultdict
from lifeprism.config import settings
from lifeprism.llm.utils.helpers import estimate_prompt_tokens
MAX_TOOL_CALL = 20
MAX_TOOL_ERROR_COUNT = 5

# def auto_compact(self):
# """计算session是否超过最大token限制，超过则进行自动压缩"""
# # 1.判断token是否超过限制
# if not self._exceed_token_threshold_compact():
# return 
# # 2. 进行模型压缩，获取压缩信息


# # 3. 构建新的user信息


# # 4.记录compact位置
logger  = get_logger(__name__)
logger.setLevel(DEBUG)
class AgentLoop:
    def __init__(self, bus: MessageQueue):
        self._bus = bus
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_id -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._running = True
        self._tool_registry = ToolRegistry()
    async def _run_agent_loop(self, session: Session, system_prompt: str, tools: list[dict[str, Any]]) -> tuple[LLMResponse, list[dict[str, Any]]]:
        """执行 Agent 循环

        Args:
            session: 会话对象
            system_prompt: 系统提示词
            tools: 工具定义列表

        Returns:
            tuple: (LLMResponse, tool_call_chain)
                - LLMResponse: 最终的 LLM 响应
                - tool_call_chain: 完整的工具调用链，每轮包含 reasoning 和 tool_calls
                  每个 tool_call 包含: id, name, arguments, result, is_error(bool)
        """
        llm = create_llm_client()
        messages = Context.build_prompt(system_prompt, session.get_history_message())
        logger.info("LLM 调用开始, session=%s", session.id)
        # logger.debug("构建的 messages 数量=%s", len(messages))
        # for idx, msg in enumerate(messages):
        #     logger.debug(
        #         "Message[%s]: role=%s, content_type=%s, content_length=%s, has_tool_calls=%s",
        #         idx, msg.get('role'), type(msg.get('content')).__name__,
        #         len(str(msg.get('content', ''))) if msg.get('content') else 0,
        #         'tool_calls' in msg
        #     )
        #     if isinstance(msg.get('content'), list):
        #         for block_idx, block in enumerate(msg['content']):
        #             if isinstance(block, dict):
        #                 logger.debug(
        #                     "  Block[%s]: type=%s, has_text=%s, text_length=%s",
        #                     block_idx, block.get('type'),
        #                     'text' in block,
        #                     len(block.get('text', '')) if 'text' in block else 0
        #                 )
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
            ],
            reasoning_content=response.reasoning_content
        )

        # 工具调用链记录
        tool_call_chain: list[dict[str, Any]] = []

        # 工具调用实现
        tool_call_count = 1
        # 工具调用错误统计
        tool_error = defaultdict(int)
        while response.tool_calls and tool_call_count <=MAX_TOOL_CALL:
            # 记录当前轮次的工具调用
            round_tool_calls = []

            # 将模型回复（包含tool_calls）添加到messages中
            for tool_call in response.tool_calls:
                logger.debug("工具调用 ： %s ，调用参数%s", tool_call.name, tool_call.arguments)
                result = await self._tool_registry.execute(tool_call.name,tool_call.arguments)
                logger.debug("工具结果 ： %s - %s", tool_call.name, result)

                # 先判断工具调用是否出错
                is_error = isinstance(result, str) and result.startswith(ERROR)
                logger.debug("工具结果是否为字符串: %s", isinstance(result, str))
                logger.debug("工具结果是否以错误开头: %s", is_error)

                # 记录工具调用到当前轮次（含错误标记）
                round_tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "result": result,
                    "is_error": is_error
                })

                # 只有在出错时才累加错误计数并检查阈值
                if is_error:
                    tool_error[tool_call.name] += 1
                    logger.debug("工具 %s 错误计数: %s/%s", tool_call.name, tool_error[tool_call.name], MAX_TOOL_ERROR_COUNT)
                    if tool_error[tool_call.name] > MAX_TOOL_ERROR_COUNT:
                        logger.warning("工具 %s 超过最大错误次数，添加警告信息", tool_call.name)
                        result += f"，已连续调用{tool_error[tool_call.name]}次，超过最大错误次数{MAX_TOOL_ERROR_COUNT}，请立即放弃该工具调用，尝试切换其他工具。若无可替代工具，向用户说明情况"

                # 将工具结果转换为字符串（如果是 dict/list，转为 JSON）
                if isinstance(result, (dict, list)):
                    result_content = json.dumps(result, ensure_ascii=False)
                else:
                    result_content = str(result)

                session.add_message('tool', result_content, tool_call_id=tool_call.id)

            # 将当前轮次的工具调用添加到链中（含推理内容）
            tool_call_chain.append({
                "round": tool_call_count,
                "reasoning": response.reasoning_content,
                "tool_calls": round_tool_calls
            })
            messages = Context.build_prompt(system_prompt, session.get_history_message())
            logger.debug("第%s次 llm调用开始， message 长度 %s", tool_call_count+1, len(messages))
            logger.debug(messages)
            # # 添加详细的消息结构日志
            # for idx, msg in enumerate(messages):
            #     logger.debug(
            #         "Message[%s]: role=%s, content_type=%s, content=%s",
            #         idx, msg.get('role'), type(msg.get('content')).__name__,
            #         str(msg.get('content'))[:200] if msg.get('content') else 'None'
            #     )
            #     if isinstance(msg.get('content'), list):
            #         for block_idx, block in enumerate(msg['content']):
            #             if isinstance(block, dict):
            #                 logger.debug(
            #                     "  Block[%s]: type=%s, text=%s",
            #                     block_idx, block.get('type'),
            #                     str(block.get('text', ''))[:100] if 'text' in block else 'N/A'
            #                 )
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
                ],
                reasoning_content=response.reasoning_content
            )
            logger.debug("模型返回 ： %s", response)
            logger.debug("模型工具调用 ： %s", response.tool_calls)
            logger.debug("="*50)
            tool_call_count += 1

        # 如果因为达到MAX_TOOL_CALL而退出，且response仍有tool_calls，需要强制生成文本回复
        if response.tool_calls and tool_call_count > MAX_TOOL_CALL:
            logger.warning("达到最大工具调用次数 %s，强制生成文本回复", MAX_TOOL_CALL)
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
                ],
                reasoning_content=response.reasoning_content
            )
            logger.debug("强制文本回复: %s", response)

        # 记录最后一轮的 reasoning（即使没有工具调用也记录，避免丢失最终的思考过程）
        if response.reasoning_content:
            tool_call_chain.append({
                "round": tool_call_count,
                "reasoning": response.reasoning_content,
                "tool_calls": []
            })

        return response, tool_call_chain
    
    def _process_cmd(self,msg:InboundMessage)->None | OutboundMessage:
        """
        处理命令消息
        args :
            msg : InboundMessage
        return
            None | OutboundMessage
        """
        message_text = self._message_text(msg)
        # 1. 当前只有微信有命令行工具 /new
        if msg.channel == ChannelType.WECHAT:
            if message_text.startswith("/new"):
                # 获取当前 session_id（用于恢复提示）
                old_session_id = msg.session_id
                logger.info("创建新会话，上一个会话 ID: %s", old_session_id)

                # 新建会话
                new_session = session_manager.get_or_create_session()
                # 立即保存 session 到文件，避免重启后丢失
                session_manager.save_session(new_session)
                logger.info("保存新会话: session_id=%s", new_session.id)

                # 构造响应文本
                response_text = f"[SUCCESS] 新建会话 {new_session.id} --- 可以开始新的聊天了！"

                # 如果有上一个会话，提示如何恢复
                if old_session_id is not None:
                    response_text += f"\n\n可以通过使用以下指令恢复上一个会话：\n/continue {old_session_id}"

                return OutboundMessage(
                    id=msg.id,
                    response=LLMResponse(content=response_text),
                    session_id=new_session.id
                )
            elif message_text.startswith("/continue"):
                # 继续会话
                # 1.去除/continue 和空格，获取session_id
                session_id = message_text.replace("/continue","").strip()

                # 2. 先检查是否提供了参数
                if not session_id:
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content="[ERROR] 请提供会话ID，例如：/continue <session_id>")
                    )

                # 3. 检查session_id是否存在
                if session_id not in session_manager.show_session_list():
                    logger.debug("session_id ： %s", session_id)
                    logger.debug("session_list ： %s", session_manager.show_session_list())
                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content=f"[ERROR] 会话 {session_id} 不存在")
                    )
                else:
                    # 4. 加载 session 并提取最后两轮对话
                    session = session_manager.get_or_create_session(session_id)
                    logger.info("继续会话 %s，提取最后两轮对话", session_id)

                    # 提取最后的 user 和 assistant 消息
                    last_user_msg = None
                    last_assistant_msg = None

                    # 倒序查找最后一条 user 消息和 assistant 消息
                    for message in reversed(session.messages):
                        if message.get('role') == 'user' and last_user_msg is None:
                            content = message.get('content', '')
                            # 处理多模态消息（content 是 list）
                            if isinstance(content, list):
                                last_user_msg = ''.join(
                                    block.get('text', '')
                                    for block in content
                                    if isinstance(block, dict) and block.get('type') == 'text'
                                )
                            else:
                                last_user_msg = content

                        if message.get('role') == 'assistant' and last_assistant_msg is None:
                            content = message.get('content', '')
                            # 处理多模态消息（content 是 list）
                            if isinstance(content, list):
                                last_assistant_msg = ''.join(
                                    block.get('text', '')
                                    for block in content
                                    if isinstance(block, dict) and block.get('type') == 'text'
                                )
                            else:
                                last_assistant_msg = content

                        # 如果两条消息都找到了，提前退出
                        if last_user_msg is not None and last_assistant_msg is not None:
                            break

                    # 构造响应文本
                    response_text = f"[SUCCESS] 继续会话 {session_id}"

                    if last_user_msg or last_assistant_msg:
                        response_text += "\n\n最后两轮对话："
                        if last_user_msg:
                            response_text += f"\nuser:\n{last_user_msg}"
                        if last_assistant_msg:
                            response_text += f"\n\nA:\n{last_assistant_msg}"

                    return OutboundMessage(
                        id=msg.id,
                        response=LLMResponse(content=response_text),
                        session_id=session_id
                    )
            elif message_text.startswith("/session-list"):
                # 判断是否有日期
                date = message_text.replace("/session-list","").strip()

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

    @staticmethod
    def _message_text(msg: InboundMessage) -> str:
        """Extract plain text from normalized message content blocks."""
        return "".join(
            block.get("text", "")
            for block in msg.content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )



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
                self._tool_registry.register(FileTreeTool())
                self._tool_registry.register(SearchFileTool())
                self._tool_registry.register(SearchStringTool())
                self._tool_registry.register(QuerySessionListTool())
                self._tool_registry.register(QuerySessionHistoryTool())
                if (settings.lifeprism_data_path / 'agent/chat/bootstrap.md').exists():
                    self._tool_registry.register(DeleteBootstrapTool())
                tools: list[dict[str, Any]] = self._tool_registry.get_definitions()
            elif msg.type == MessageType.DREAM_TASK:
                self._tool_registry.register(UserActivitySummaryTool())
                self._tool_registry.register(UserComputerLogTool())
                self._tool_registry.register(ReadFileTool())
                self._tool_registry.register(WriteFileTool())
                self._tool_registry.register(EditFileTool())
                self._tool_registry.register(FileTreeTool())
                self._tool_registry.register(SearchFileTool())
                self._tool_registry.register(SearchStringTool())
                tools: list[dict[str, Any]] = self._tool_registry.get_definitions()
            elif msg.type == MessageType.CLASSIFY:
                tools = []

            # 3. 构建完整消息（含历史）
            session: Session = session_manager.get_or_create_session(msg.session_id)
            # 判断token是否超标,自动压缩
            session = await self.auto_compact(session,tools)
            session.add_message("user", content=Context._build_user_message(msg))
            if msg.type == MessageType.CHAT: 
                session_manager.save_session(session)
                logger.info("保存会话: session_id=%s", session.id)

            # 4. 调用 LLM
            result, tool_call_chain = await self._run_agent_loop(session, system_prompt, tools)

            # 5. 保存 assistant 回复并发布结果
            await self._bus.publish_outbound(
                OutboundMessage(
                    id=msg.id,
                    response=result,
                    session_id=session.id,
                    extra={"tool_call_chain": tool_call_chain} if tool_call_chain else None
                )
            )

            # 6. 保存session
            if msg.type == MessageType.CHAT: # 只有聊天数据才保存
                session_manager.save_session(session)
                logger.info("保存会话: session_id=%s", session.id)
        except ValueError as e:
            logger.error("处理消息失败: msg_id=%s, error=%s", msg.id, e)
            raise 
        except Exception as e:
            logger.error("[AgentLoop] 处理消息 id=%s 时出错: %s", msg.id, e, exc_info=True)
            await self._bus.publish_outbound(
                OutboundMessage(
                    id=msg.id,
                    response=LLMResponse(content=f"[ERROR] {e}")
                )
            )
        finally:
            # 7. 清空工具注册表，避免工具累积和不同消息类型的工具混用
            self._tool_registry.clear()
            
    

    async def loop(self):

        while self._running:
            # 1. 从bus中获取消息
            msg:InboundMessage = await self._bus.consume_inbound()

            # 2. 创建任务，后台处理
            task = asyncio.create_task(self._process_msg(msg))

            # 3. 注册任务激活
            self._active_tasks.setdefault(msg.id,[]).append(task)

            # 4. 添加任务注销函数，并确保异常不被静默处理
            def _handle_task_done(t: "Task", k: str):
                if t in self._active_tasks.get(k, []):
                    self._active_tasks.get(k, []).remove(t)
                exc = t.exception()
                if exc is not None:
                    logger.error("[AgentLoop] Task exception was never retrieved: %s", exc, exc_info=exc)

            task.add_done_callback(lambda t, k=msg.id: _handle_task_done(t, k))

    def stop(self):
        self._running = False

    async def auto_compact(self,session:Session,tools)->Session:
        """计算session是否超过最大token限制，超过则进行自动压缩"""
        messages = session.get_history_message()
        # 1.判断token是否超过限制
        if not estimate_prompt_tokens(messages,tools) > settings.token_limit:
            # 这里暂定token_limit是常数，但是实际上应该是依据模型的上下文窗口*0.6或者其他系数来限制
            return session
        # 2. 进行模型压缩，获取压缩信息
        compact_system_prompt = """
        ## task 
        你需要压缩用户的聊天记录
        ## 提取内容
        1. user msg : 完整保存用户的最后5条信息
        2. event : 提取出聊天记录中的客观事实
            1. 对于工具类查询问题简单说明查询了那些内容，基本结果是什么。不需要详细说明，并提示必要时使用工具重新查询
            2. 如果使用工具记录了心情或事件，需要把相关id写出来，便于后续查询和避免反复写入
            3. 对于非工具类的事件，需要确认事情发生的时间(避免时间逻辑上出错)，发生的经过，用户的反应
            4. 对于情绪类事件，（如果有点话）需要记录诱发原因，用户的反应，用户的心情
        ## 提取说明
        对于event中的非工具累时间和情绪累事件提取组成部分（比如，用户描述事情发生的时间，诱发原因等）是如果有才记录，如果没有则不记录
        """
        llm = create_llm_client()
        compact_content = json.dumps(messages, ensure_ascii=False)
        messages = [
            {"role":"system","content":compact_system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## 需要压缩的内容 \n {compact_content}",
                    }
                ],
            }
        ]
        try : 
            logger.info("auto_compact LLM 调用开始, session=%s", session.id)
            response:LLMResponse= await llm.chat(messages)
        except Exception as e:
            logger.error("auto compact llm 处理出错, %s", e)
            return session
        # 3.记录compact位置
        session.last_compacted_loc = len(session.messages)
        # 4. 构建新的user信息
        session.add_message("system","conversation compacted")
        session.add_message("user",f"# 消息压缩总结 \n\n{response.content}",**{'is_compact_summary':True})
        # 5. 保存session
        session_manager.save_session(session)
        logger.info("保存会话: session_id=%s", session.id)
        return session
        
agent_loop = LazySingleton(AgentLoop, bus=bus)

