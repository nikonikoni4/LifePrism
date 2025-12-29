from lifewatch.llm.llm_classify.schemas.chatbot_schemas import ChatBotSchemas
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.memory import InMemorySaver
from typing import Optional, Union, AsyncGenerator, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
from lifewatch.llm.custom_prompt.common_prompt import intent_router_template,norm_chat_template
from lifewatch.llm.custom_prompt.chatbot_prompt.feature_introduce import intro_template,intro_router_template
from lifewatch.llm.llm_classify.utils import create_ChatTongyiModel
from langchain.tools import ToolRuntime
from typing import TypedDict
import json
from lifewatch.utils import get_logger
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy
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
        self.tokens_usage = {}
        self.checkpointer = checkpointer or InMemorySaver()
        self.main_chat_bot = self.get_new_agent(enable_search=False,
                            enable_thinking=False,
                            enable_streaming=False,temperature=0.5)
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
            - 其他意图 → norm_chat → END
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
        
        # 定义条件路由函数
        def route_by_intent(state: ChatBotSchemas) -> str:
            """根据意图路由到不同节点"""
            intent = state.intent[-1] if state.intent else ""
            if intent == "lifeprism软件使用和讲解":
                return "feat_intro_router"
            else:
                return "norm_chat"
        
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
        
        # norm_chat → END
        self.graph.add_edge("norm_chat", END)
        
        # 编译 graph，传入 checkpointer
        return self.graph.compile(checkpointer=self.checkpointer)


    def init_tokens_usage(self,thread_id:str):
        """
        初始化新会话的token使用情况
        """
        logger.debug(f"初始化token使用情况: {thread_id}")
        if thread_id not in self.tokens_usage:
            self.tokens_usage[thread_id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "search_count": 0
            }

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
        return create_ChatTongyiModel(enable_search=enable_search,
                            enable_thinking=enable_thinking,
                            enable_streaming=enable_streaming,temperature=temperature)
    def update_usage(self,result):
        token_usage = result.response_metadata.get("token_usage", {})
        self.tokens_usage[self.thread_id]["input_tokens"] += token_usage.get("input_tokens", 0)
        self.tokens_usage[self.thread_id]["output_tokens"] += token_usage.get("output_tokens", 0)
        self.tokens_usage[self.thread_id]["total_tokens"] += token_usage.get("total_tokens", 0)
        # self.tokens_usage[self.thread_id]["call_count"] += 1 # 这里有问题，暂时不改

        

    @classmethod
    @asynccontextmanager
    async def create_with_persistence(
        cls,
        db_path: Union[str, Path] = r"lifewatch\llm\llm_classify\chat\chat_history.db"
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
    
    async def intent_router(self,main_state:ChatBotSchemas)->ChatBotSchemas:
        """
        意图识别
        """
        promot = intent_router_template.format(
            question=main_state.messages[-1].content,
        )
        chat_model = self.get_new_agent(enable_search=False,
                            enable_thinking=False,
                            enable_streaming=False,temperature=0.5)
        result = await chat_model.ainvoke(promot) 
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
        from lifewatch.llm.llm_classify.utils.user_guide_parser import load_user_guide
        from lifewatch.llm.llm_classify.schemas.user_guide_schemas import SummaryOption
        chat_model = self.get_new_agent(enable_search=False,
                            enable_thinking=False,
                            enable_streaming=False,temperature=0.5)
        guide = load_user_guide()
        all_ids = guide.get_all_ids()
        # 第一次路由
        option = SummaryOption(id = True,title = False,abstract = True)
        outline = guide.transform_to_table(guide.get_children_summary(options=option))
        result = await chat_model.ainvoke(intro_router_template.format(
            question=main_state.messages[-1].content,
            outline=outline,
        ))
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
        result = await chat_model.ainvoke(intro_router_template.format(outline=outline, question=main_state.messages[-1].content))
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
        history_messages = get_history_messages(main_state.messages)
        prompt = intro_template.format(
            question=main_state.messages[-1].content,
            guide_content=main_state.guide_content[-1],
            history_messages=history_messages
        )
        result = await self.main_chat_bot.ainvoke(prompt)
        self.update_usage(result)
        return {
            "messages" : [result]
        }
    
    async def norm_chat(self,main_state:ChatBotSchemas)->ChatBotSchemas:
        history_messages = get_history_messages(main_state.messages)
        prompt = norm_chat_template.format(
            question=main_state.messages[-1].content,
            history_messages=history_messages
        )
        result = await self.main_chat_bot.ainvoke(prompt)
        self.update_usage(result)
        return {
            "messages" : [result]
        }
    
    async def chat(self, user_input: str, thread_id: str = None) -> str:
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
            {"messages": [HumanMessage(content=user_input)]},
            config  = self.config
        )
        
        # 返回最后一条 AI 消息的内容
        return result["messages"][-1].content

async def main():
    app = ChatBot()
    app.set_thread_id("test_graph2")
    while True:
        user_input = input("User: ")
        if user_input == "exit":
            break
        result = await app.chat(user_input)
        print("AI: ", result)
from asyncio import run
if __name__ == "__main__":
    run(main())