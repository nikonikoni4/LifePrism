"""
V2 ChatBot 改为使用graph 增加功能解说和相关功能解答
"""
from lifeprism.llm.schemas.chatbot_schemas import ChatBotSchemas
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.memory import InMemorySaver
from typing import Optional, Union, AsyncGenerator, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
from lifeprism.llm.custom_prompt.common_prompt import intent_router_template,norm_chat_template
from lifeprism.llm.custom_prompt.chatbot_prompt.feature_introduce import intro_template,intro_router_template
from lifeprism.llm.utils import create_llm
import json
import traceback
from datetime import datetime
from lifeprism.utils import get_logger
import logging
from langchain_core.messages import HumanMessage, AIMessage,AIMessageChunk,ToolMessage
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy
from lifeprism.llm.tools.database_tools import get_daily_stats,get_multi_days_stats
from lifeprism.config.settings_manager import settings
logger = get_logger(__name__,logging.DEBUG)

class LLMParseError(Exception):
    """
    LLM 输出解析错误 - 可重试
    
    当 LLM 返回的内容无法正确解析（如 JSON 格式错误、缺少必要字段等）时抛出此错误。
    此错误类型被标记为可重试，重试机制会捕获此错误并重新调用 LLM。
    
    Attributes:
        message: 错误描述信息
        original_error: 原始异常（可选）
        raw_content: LLM 返回的原始内容（可选，用于调试）
    """
    def __init__(self, message: str, original_error: Exception = None, raw_content: str = None):
        super().__init__(message)
        self.message = message
        self.original_error = original_error
        self.raw_content = raw_content

    def __str__(self):
        base_msg = f"LLMParseError: {self.message}"
        if self.raw_content:
            # 截断过长的原始内容
            content_preview = self.raw_content[:100] + "..." if len(self.raw_content) > 100 else self.raw_content
            base_msg += f"\n原始内容: {content_preview}"
        return base_msg


def get_history_messages(messages: list[HumanMessage| AIMessage]):
    history_messages = ""
    for i,msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            history_messages += f"{i}. User: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_messages += f"{i}. Assistant: {msg.content}\n"
    return history_messages

class ChatBot:
    def __init__(self,checkpointer: Optional[Union[InMemorySaver, AsyncSqliteSaver]] = None):
        self.current_total_tokens = 0
        # tokens_usage: 每轮对话的使用量（每轮对话前清空）
        self.tokens_usage: Dict[str, Dict[str, int]] = {}
        # session_tokens_usage: 会话累计使用量（持续累加）
        self.session_tokens_usage: Dict[str, Dict[str, int]] = {}
        self.checkpointer = checkpointer or InMemorySaver()
        # 用于流式输出
        self.llm_streaming = self.get_new_agent(enable_search=False,
                            enable_thinking=False,
                            enable_streaming=True,temperature=0.5)
        self.config: Optional[dict] = None
        self.thread_id = None
        # self._is_persistent = isinstance(self.checkpointer, AsyncSqliteSaver)
        # 这里的feature_list必须与lifewatch\llm\custom_prompt\common_prompt.py
        # 中的intent_router_template中的feature_list保持一致
        self.feature_list = ["lifeprism软件使用和讲解","一般模式"] # 
        self.graph = StateGraph(ChatBotSchemas)
        self.chatbot = self._build_graph()
    def _build_graph(self):
        """
        构建对话流程图
        
        流程：
        START → intent_router → (根据意图分支)
            - "lifeprism软件使用和讲解" → feat_intro_router → feature_introduce → END
            - 其他意图 → norm_chat → (是否有工具调用?)
                - 有 → tool_node → tool_result_handler → END
                - 无 → END
        """
        from langgraph.graph import START, END
        
        # 添加节点
        self.graph.add_node("intent_router",
                            self.intent_router,
                            retry_policy=RetryPolicy(retry_on=[LLMParseError],max_attempts=2))
        self.graph.add_node("feat_intro_router",
                            self.feat_intro_router,
                            retry_policy=RetryPolicy(retry_on=[LLMParseError],max_attempts=2))
        self.graph.add_node("feature_introduce",
                            self.feature_introduce,
                            retry_policy=RetryPolicy(retry_on=[LLMParseError],max_attempts=2))
        self.graph.add_node("norm_chat",
                            self.norm_chat,
                            retry_policy=RetryPolicy(retry_on=[LLMParseError], max_attempts=2))
        self.graph.add_node("tool_node", self.tool_node)
        self.graph.add_node("tool_result_handler", self.tool_result_handler)
        
        # 定义条件路由函数
        def route_by_intent(main_state: ChatBotSchemas) -> str:
            """根据意图路由到不同节点"""
            intent = main_state["intent"][-1] if main_state["intent"] else ""
            if intent == "lifeprism软件使用和讲解":
                return "feat_intro_router"
            else:
                return "norm_chat"
        
        def route_after_norm_chat(main_state: ChatBotSchemas) -> str:
            """判断 norm_chat 后是否需要调用工具"""
            last_message = main_state["messages"][-1] if main_state["messages"] else None
            if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tool_node"
            return END
        
        # 添加边
        # START → intent_router
        self.graph.add_edge(START, "intent_router")
        
        # intent_router → 条件分支
        self.graph.add_conditional_edges(
            "intent_router",
            route_by_intent,
            {
                "feat_intro_router": "feat_intro_router",
                "norm_chat": "norm_chat"
            }
        )
        
        # feat_intro_router → feature_introduce
        self.graph.add_edge("feat_intro_router", "feature_introduce")
        
        # feature_introduce → END
        self.graph.add_edge("feature_introduce", END)
        
        # norm_chat → 条件分支（判断是否有工具调用）
        self.graph.add_conditional_edges(
            "norm_chat",
            route_after_norm_chat,
            {
                "tool_node": "tool_node",
                END: END
            }
        )
        
        # tool_node → tool_result_handler
        self.graph.add_edge("tool_node", "tool_result_handler")
        
        # tool_result_handler → END
        self.graph.add_edge("tool_result_handler", END)
        
        # 编译 graph，传入 checkpointer
        return self.graph.compile(checkpointer=self.checkpointer)


    def init_tokens_usage(self, thread_id: str):
        """
        初始化会话的 token 使用情况（仅在不存在时初始化）
        
        - tokens_usage: 每轮对话的使用量
        - session_tokens_usage: 会话累计使用量
        """
        logger.debug(f"初始化token使用情况: {thread_id}")
        
        # 仅在不存在时初始化
        if thread_id not in self.tokens_usage:
            self.tokens_usage[thread_id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "search_count": 0
            }
        
        if thread_id not in self.session_tokens_usage:
            self.session_tokens_usage[thread_id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "search_count": 0
            }
    
    def reset_turn_usage(self):
        """
        清空本轮对话的 tokens_usage（每次用户发送消息时调用）
        """
        if self.thread_id and self.thread_id in self.tokens_usage:
            self.tokens_usage[self.thread_id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "search_count": 0
            }
            logger.debug(f"清空本轮对话使用量: {self.thread_id}")

    def set_thread_id(self, thread_id: str):
        """
        设置当前会话的 thread_id。
        
        Args:
            thread_id: 会话ID，用于区分不同的对话
        """
        logger.debug(f"设置thread_id: {thread_id}")
        self.config = {"configurable": {"thread_id": thread_id}}
        self.thread_id = thread_id
        self.init_tokens_usage(thread_id)
    def get_new_agent(self,enable_search:bool,enable_thinking:bool,enable_streaming:bool,temperature:float):
        """
        用于获取新的agent
        """
        logger.debug(f"获取新的agent: enable_search={enable_search}, enable_thinking={enable_thinking}, enable_streaming={enable_streaming}, temperature={temperature}")
        return create_llm(enable_search=enable_search,
                            enable_thinking=enable_thinking,
                            enable_streaming=enable_streaming,temperature=temperature)
    def update_usage(self, result):
        """
        更新 token 使用量
        
        同时更新:
        - tokens_usage: 本轮对话使用量
        - session_tokens_usage: 会话累计使用量
        """
        logger.debug(f"[update_usage] result type: {type(result)}")
        logger.debug(f"[update_usage] result: {result}")
        
        # 检查 result 是否有 response_metadata 属性
        if not hasattr(result, 'response_metadata'):
            logger.error(f"[update_usage] result 没有 response_metadata 属性! result type: {type(result)}")
            logger.error(f"[update_usage] result 内容: {result}")
            return
        
        logger.debug(f"[update_usage] response_metadata: {result.response_metadata}")
        
        token_usage = result.response_metadata.get("token_usage", {})
        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        total_tokens = token_usage.get("total_tokens", 0)
        
        # 更新本轮对话使用量
        self.tokens_usage[self.thread_id]["input_tokens"] += input_tokens
        self.tokens_usage[self.thread_id]["output_tokens"] += output_tokens
        self.tokens_usage[self.thread_id]["total_tokens"] += total_tokens
        
        # 更新会话累计使用量
        self.session_tokens_usage[self.thread_id]["input_tokens"] += input_tokens
        self.session_tokens_usage[self.thread_id]["output_tokens"] += output_tokens
        self.session_tokens_usage[self.thread_id]["total_tokens"] += total_tokens

        

    @classmethod
    @asynccontextmanager
    async def create_with_persistence(
        cls,
        db_path: Union[str, Path] = settings.chat_db_path
    ) -> AsyncGenerator["ChatBot", None]:
        """
        异步上下文管理器工厂方法：创建使用 AsyncSqliteSaver 持久化的 ChatBot 实例。
        
        使用方式:
            async with ChatBot.create_with_persistence() as chatbot:
                async for content in chatbot.chat("你好"):
                    print(content)
        
        Args:
            db_path: SQLite 数据库文件路径
            
        Yields:
            使用 AsyncSqliteSaver 的 ChatBot 实例
        """
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            yield cls(checkpointer)
    

        
    # ===============================================================
    # nodes 
    # ===============================================================
    async def intent_router(self,main_state:ChatBotSchemas)->ChatBotSchemas:
        """
        意图识别
        """
        promot = intent_router_template.format(
            question=main_state["current_human_message"],
        )
        llm = self.get_new_agent(enable_search=False,
                            enable_thinking=False,
                            enable_streaming=False,temperature=0.5)
        logger.debug(f"[intent_router] 调用 LLM...")
        try:
            result = await llm.ainvoke(promot)
            logger.debug(f"[intent_router] LLM 返回 result type: {type(result)}")
        except Exception as e:
            logger.error(f"[intent_router] LLM 调用失败: {e}")
            logger.error(f"[intent_router] 堆栈跟踪:\n{traceback.format_exc()}")
            raise
        self.update_usage(result)
        
        # 去掉 LLM 返回内容中的引号（LLM 有时会返回带引号的字符串）
        intent_content = result.content.strip().strip('"').strip("'")
        
        # 检查result是否在feature_list中
        if intent_content not in self.feature_list:
            raise LLMParseError(
                message=f"无效的功能分类: '{intent_content}' 不在预期列表中",
                raw_content=result.content  # 保存原始输出，便于调试
            )
        logger.debug(f"意图识别结果: {intent_content}")
        return {
            "intent" : [intent_content]
        } 
    
    async def feat_intro_router(self,main_state:ChatBotSchemas)->ChatBotSchemas:
        """
        功能介绍路由
        """
        from lifeprism.llm.utils.user_guide_parser import load_user_guide
        from lifeprism.llm.schemas.user_guide_schemas import SummaryOption
        llm = self.get_new_agent(enable_search=False,
                            enable_thinking=False,
                            enable_streaming=False,temperature=0.5)
        guide = load_user_guide()
        all_ids = guide.get_all_ids()
        # 第一次路由
        option = SummaryOption(id = True,title = False,abstract = True)
        outline = guide.transform_to_table(guide.get_children_summary(options=option))
        logger.debug(f"[feat_intro_router] 第一次路由调用 LLM...")
        try:
            result = await llm.ainvoke(intro_router_template.format(
                question=main_state["current_human_message"],
                outline=outline,
            ))
            logger.debug(f"[feat_intro_router] LLM 返回 result type: {type(result)}")
        except Exception as e:
            logger.error(f"[feat_intro_router] 第一次路由 LLM 调用失败: {e}")
            logger.error(f"[feat_intro_router] 堆栈跟踪:\n{traceback.format_exc()}")
            raise
        self.update_usage(result)
        # 判断id_list是否包含在id中
        id_list = json.loads(result.content)
        logger.debug(f"路由结果: {id_list}")
        
        # 获取新的outline
        outline = []
        for id in id_list:
            if id in all_ids:
                outline += guide.get_children_summary(id, options=option)
        if outline == []:
            logger.error(f"无效的id列表: '{id_list}' 不在预期列表中")
            raise LLMParseError(
                message=f"无效的id列表: '{id_list}' 不在预期列表中",
                raw_content=id_list  # 保存原始输出，便于调试
            )
        
        # 第二次调用：细筛
        logger.debug("\n=== 第2步：细筛路由 ===")
        outline = guide.transform_to_table(outline)
        logger.debug(f"细筛范围:\n{outline}")
        logger.debug(f"[feat_intro_router] 第二次路由调用 LLM...")
        try:
            result = await llm.ainvoke(intro_router_template.format(outline=outline, question=main_state["current_human_message"]))
            logger.debug(f"[feat_intro_router] 第二次路由 LLM 返回 result type: {type(result)}")
        except Exception as e:
            logger.error(f"[feat_intro_router] 第二次路由 LLM 调用失败: {e}")
            logger.error(f"[feat_intro_router] 堆栈跟踪:\n{traceback.format_exc()}")
            raise
        self.update_usage(result)
        id_list = json.loads(result.content)
        logger.debug(f"路由结果: {id_list}")

        # 获取content
        logger.debug("\n=== 第3步：获取内容 ===")
        content = ""
        for id in id_list:
            if id in all_ids:
                content += guide.get_section_as_markdown(id,start_level=3,max_heading_depth=3)
                content += "\n"
        if content == "":
            logger.error(f"无效的id列表: '{id_list}' 不在预期列表中")
            raise LLMParseError(
                message=f"无效的id列表: '{id_list}' 不在预期列表中",
                raw_content=id_list  # 保存原始输出，便于调试
            )
        logger.debug(f"获取的内容:\n{content}")

        
        self.update_usage(result)
        logger.debug(f"功能介绍结果:\n{result.content}")
        # 打印 usage 统计
        logger.debug("\n=== Token Usage 统计 ===")
        # logger.debug(f"调用次数: {self.tokens_usage[self.thread_id]['call_count']}")
        logger.debug(f"输入 Tokens: {self.tokens_usage[self.thread_id]['input_tokens']}")
        logger.debug(f"输出 Tokens: {self.tokens_usage[self.thread_id]['output_tokens']}")
        logger.debug(f"总 Tokens: {self.tokens_usage[self.thread_id]['total_tokens']}")


        return {
            "guide_content" : [content]
        } 
    
    async def feature_introduce(self,main_state:ChatBotSchemas)->ChatBotSchemas:
        """
        功能介绍
        """
        # 设置历史消息
        history_messages = get_history_messages(main_state["messages"])
        prompt = intro_template.format(
            question=main_state["current_human_message"],
            guide_content=main_state["guide_content"][-1],
            history_messages=history_messages
        )
        logger.debug(f"[feature_introduce] 调用 LLM...")
        try:
            result = await self.llm_streaming.ainvoke(prompt)
            logger.debug(f"[feature_introduce] LLM 返回 result type: {type(result)}")
        except Exception as e:
            logger.error(f"[feature_introduce] LLM 调用失败: {e}")
            logger.error(f"[feature_introduce] 堆栈跟踪:\n{traceback.format_exc()}")
            raise
        self.update_usage(result)
        return {
            "messages" : [result]
        }
    
    # 可用工具集合（用于验证 LLM 返回的工具调用）
    VALID_TOOLS = {"get_daily_stats","get_multi_days_stats"}
    
    async def norm_chat(self, main_state: ChatBotSchemas) -> ChatBotSchemas:
        # 当前的时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_messages = get_history_messages(main_state["messages"])
        prompt = norm_chat_template.format(
            question=main_state["current_human_message"],
            history_messages=history_messages,
            custom_prompt=f"当前时间: {current_time}"
        )
        llm_with_tool = self.llm_streaming.bind_tools([get_daily_stats,get_multi_days_stats])
        logger.debug(f"[norm_chat] 调用 LLM (with tools)...")
        try:
            result = await llm_with_tool.ainvoke(prompt)
            logger.debug(f"[norm_chat] LLM 返回 result: {result}")
            logger.debug(f"[norm_chat] LLM 返回 result type: {type(result)}")
        except Exception as e:
            logger.error(f"[norm_chat] LLM 调用失败: {e}")
            logger.error(f"[norm_chat] 堆栈跟踪:\n{traceback.format_exc()}")
            raise
        self.update_usage(result)
        
        # 验证工具调用是否有效
        if hasattr(result, 'tool_calls') and result.tool_calls:
            for tool_call in result.tool_calls:
                tool_name = tool_call.get("name", "")
                if tool_name not in self.VALID_TOOLS:
                    logger.warning(f"LLM 请求了未知工具: {tool_name}")
                    raise LLMParseError(
                        message=f"LLM 请求了未知工具: {tool_name}，可用工具: {self.VALID_TOOLS}",
                        raw_content=str(result.tool_calls)
                    )
        
        return {
            "messages": [result]
        }
    
    async def tool_node(self, main_state: ChatBotSchemas) -> ChatBotSchemas:
        """
        处理工具调用的节点，执行工具并返回结果
        """ 
        # 1. 获取最后一条 AI 消息中的工具调用请求
        last_message = main_state["messages"][-1]
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            logger.warning("tool_node 被调用但没有 tool_calls")
            return {}
        
        # 2. 工具映射表
        tool_map = {
            "get_daily_stats": get_daily_stats,
            "get_multi_days_stats": get_multi_days_stats
        }
        
        # 3. 执行所有工具调用
        tool_messages = []
        tool_results = []
        
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]
            
            logger.debug(f"执行工具调用: {tool_name}, 参数: {tool_args}")
            
            if tool_name in tool_map:
                try:
                    # 执行工具（使用 invoke 方法）
                    tool_result = tool_map[tool_name].invoke(tool_args)
                    # 根据返回类型处理结果
                    if isinstance(tool_result, str):
                        result_str = tool_result
                    else:
                        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"工具执行失败: {e}")
                    result_str = f"工具执行失败: {str(e)}"
            else:
                logger.error(f"未知工具: {tool_name}")
                result_str = f"未知工具: {tool_name}"
            
            # 创建 ToolMessage
            tool_messages.append(ToolMessage(
                content=result_str,
                tool_call_id=tool_call_id
            ))
            tool_results.append(result_str)
        
        logger.debug(f"工具执行完成，结果数量: {len(tool_results)}")
        
        # 4. 返回结果
        return {
            "messages": tool_messages,
            "tools_result": tool_results
        }
    
    async def tool_result_handler(self, main_state: ChatBotSchemas) -> ChatBotSchemas:
        """
        结合工具调用结果信息，生成最终回答（不绑定工具，节省 tokens）
        """
        from lifeprism.llm.custom_prompt.common_prompt import tool_result_template
        
        # 1. 获取历史对话（get_history_messages 只处理 HumanMessage 和 AIMessage，自动忽略 ToolMessage）
        history_messages = get_history_messages(main_state["messages"])
        
        # 2. 获取工具返回结果
        tool_result = "\n".join(main_state["tools_result"]) if main_state["tools_result"] else ""
        
        # 3. 构建 prompt
        prompt = tool_result_template.format(
            history_messages=history_messages,
            question=main_state["current_human_message"],
            tool_result=tool_result
        )
        
        logger.debug(f"tool_result_handler prompt 构建完成")
        
        # 4. 调用 LLM（不绑定工具）
        logger.debug(f"[tool_result_handler] 调用 LLM...")
        try:
            result = await self.llm_streaming.ainvoke(prompt)
            logger.debug(f"[tool_result_handler] LLM 返回 result type: {type(result)}")
        except Exception as e:
            logger.error(f"[tool_result_handler] LLM 调用失败: {e}")
            logger.error(f"[tool_result_handler] 堆栈跟踪:\n{traceback.format_exc()}")
            raise
        self.update_usage(result)
        
        return {
            "messages": [result]
        }

        

    
    # ===============================================================
    # chat 接口 not stream；stream ; stream_with_status
    # ===============================================================
    async def chat_not_stream(self, user_input: str, thread_id: str = None) -> str:
        """
        发送消息并获取回复（主入口）
        
        Args:
            user_input: 用户输入的消息
            thread_id: 会话ID，用于区分不同对话。如果不传则使用 self.thread_id
            
        Returns:
            AI 的回复内容
        """
        from langchain_core.messages import HumanMessage
        
        # 使用传入的 thread_id 或者已设置的 thread_id
        if thread_id is None and self.thread_id is None:
            raise ValueError("请先调用 set_thread_id() 或传入 thread_id 参数")
        
        # 只有传入 thread_id 时才更新
        if thread_id is not None:
            self.set_thread_id(thread_id)
        # 调用编译后的 graph
        result = await self.chatbot.ainvoke(
            {
                "messages": [HumanMessage(content=user_input)],
                "current_human_message": user_input,
                "intent": [],
                "guide_content": [],
                "tools_result": []
            },
            config=self.config
        )
        
        # 返回最后一条 AI 消息的内容
        return result["messages"][-1].content
    
    async def chat_stream(self, user_input: str, thread_id: str = None):
        """
        发送消息并获取流式回复
        
        Args:
            user_input: 用户输入的消息
            thread_id: 会话ID
            
        Yields:
            AI 回复的内容片段
        """
        from langchain_core.messages import HumanMessage, AIMessageChunk
        
        # 使用传入的 thread_id 或者已设置的 thread_id
        if thread_id is None and self.thread_id is None:
            raise ValueError("请先调用 set_thread_id() 或传入 thread_id 参数")
        
        if thread_id is not None:
            self.set_thread_id(thread_id)
        
        # 清空本轮对话使用量
        self.reset_turn_usage()
        
        # 使用 astream 进行流式输出
        # stream_mode="messages" 会流式输出所有消息事件
        async for event in self.chatbot.astream(
            {
                "messages": [HumanMessage(content=user_input)],
                "current_human_message": user_input,
                "intent": [],
                "guide_content": [],
                "tools_result": []
            },
            config=self.config,
            stream_mode="messages"
        ):
            # event 是一个 tuple: (message, metadata)
            if len(event) >= 1:
                message = event[0]
                # 只输出 AI 消息的内容
                if isinstance(message, AIMessageChunk) and message.content:
                    yield message.content
    
    async def chat_stream_with_status(self, user_input: str, thread_id: str = None):
        """
        发送消息并获取流式回复（带状态信息）
        
        前端可以根据 type 区分：
        - type="status": 当前执行的步骤（节点开始时触发）
        - type="content": AI 回复的内容片段
        
        Args:
            user_input: 用户输入的消息
            thread_id: 会话ID
            
        Yields:
            dict: {"type": "status"|"content", "message": str, "node": str}
        """
        
        if thread_id is None and self.thread_id is None:
            raise ValueError("请先调用 set_thread_id() 或传入 thread_id 参数")
        
        if thread_id is not None:
            self.set_thread_id(thread_id)
        
        # 清空本轮对话使用量
        self.reset_turn_usage()
        
        # 节点名称到中文描述的映射
        node_names = {
            "intent_router": "正在识别意图...",
            "feat_intro_router": "正在检索相关文档...",
            "feature_introduce": "正在生成回答...",
            "norm_chat": "正在生成回答...",
            "tool_node": "正在查询数据...",
            "tool_result_handler": "正在整合数据生成回答...",
        }
        
        last_node = None  # 记录上一个节点，避免重复发送状态
        
        logger.debug(f"[chat_stream_with_status] 开始 astream_events, thread_id={self.thread_id}")
        
        try:
            # 使用 astream_events 获取更详细的事件（包括节点开始）
            async for event in self.chatbot.astream_events(
                {
                    "messages": [HumanMessage(content=user_input)],
                    "current_human_message": user_input,
                    "intent": [],
                    "guide_content": [],
                    "tools_result": []
                },
                config=self.config,
                version="v2"  # 使用 v2 版本的事件格式
            ):
                event_type = event.get("event", "")
                # logger.debug(f"[chat_stream_with_status] 收到事件: type={event_type}, name={event.get('name', 'N/A')}")
                
                # 节点开始事件
                if event_type == "on_chain_start":
                    node_name = event.get("name", "")
                    if node_name in node_names and node_name != last_node:
                        last_node = node_name
                        logger.debug(f"[chat_stream_with_status] 节点开始: {node_name}")
                        yield {
                            "type": "status",
                            "node": node_name,
                            "message": node_names[node_name]
                        }
                
                # 消息流式输出事件
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {
                            "type": "content",
                            "node": last_node,
                            "message": chunk.content
                        }
                        
        except LLMParseError as e:
            logger.error(f"[chat_stream_with_status] LLM 解析重试失败: {e}")
            logger.error(f"[chat_stream_with_status] 堆栈跟踪:\n{traceback.format_exc()}")
            yield {
                "type": "error",
                "node": last_node or "unknown",
                "message": "抱歉，我暂时无法处理这个请求，请换一种方式提问。"
            }
        except AttributeError as e:
            # 专门捕获 AttributeError，可能是 'dict' object has no attribute 'status_code' 的来源
            logger.error(f"[chat_stream_with_status] AttributeError: {e}")
            logger.error(f"[chat_stream_with_status] 完整堆栈跟踪:\n{traceback.format_exc()}")
            yield {
                "type": "error",
                "node": last_node or "unknown",
                "message": f"属性错误: {str(e)}"
            }
        except Exception as e:
            logger.error(f"[chat_stream_with_status] 未知错误: {e}")
            logger.error(f"[chat_stream_with_status] 错误类型: {type(e).__name__}")
            logger.error(f"[chat_stream_with_status] 完整堆栈跟踪:\n{traceback.format_exc()}")
            yield {
                "type": "error",
                "node": last_node or "unknown",
                "message": f"发生错误: {str(e)}"
            }

async def main():
    # 使用持久化保存器（保存到数据库）
    async with ChatBot.create_with_persistence() as app:
        app.set_thread_id("test_stream_status")
        while True:
            user_input = input("User: ")
            if user_input == "exit":
                break
            
            print()  # 换行
            async for event in app.chat_stream_with_status(user_input):
                if event["type"] == "status":
                    # 显示当前步骤
                    print(f"🔄 {event['message']}")
                elif event["type"] == "content":
                    # 显示 AI 回复内容
                    print(event["message"], end="", flush=True)
            print()  # 换行

from asyncio import run
if __name__ == "__main__":
    run(main())